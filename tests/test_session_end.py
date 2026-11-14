#!/usr/bin/env python3
"""Tests for hooks/cursor-session-end.py and the hooks.json merge that registers it
(T-051): receipt + daily row on sessionEnd/stop, fail-open, idempotent merge.

Run: python3 tests/test_session_end.py
"""
import json
import os
import subprocess
import sys
import sqlite3
import tempfile
import time

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO_DIR, "hooks", "cursor-session-end.py")
MERGE = os.path.join(REPO_DIR, "hooks", "merge-hooks-json.py")
UNMERGE = os.path.join(REPO_DIR, "hooks", "unmerge-hooks-json.py")
SID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def project():
    """A project with .agent-spec/bin holding the receipt + tokens + gate scripts, and a
    transcript at a Cursor-style path under a fake HOME."""
    home = tempfile.mkdtemp()
    proj = os.path.realpath(tempfile.mkdtemp())
    bindir = os.path.join(proj, ".agent-spec", "bin")
    os.makedirs(bindir)
    for name in ("agent-spec-receipt.py", "agent-spec-tokens.py", "agent-spec-gate.py"):
        with open(os.path.join(REPO_DIR, "bin", name)) as src, open(os.path.join(bindir, name), "w") as dst:
            dst.write(src.read())
    slug = proj.lstrip(os.sep).replace(os.sep, "-").replace(".", "-")
    tdir = os.path.join(home, ".cursor", "projects", slug, "agent-transcripts", SID)
    os.makedirs(tdir)
    tpath = os.path.join(tdir, SID + ".jsonl")
    with open(tpath, "w") as fh:
        fh.write(json.dumps({"role": "user", "message": {"content": [{"type": "text", "text": "hi"}]}}) + "\n")
        fh.write(json.dumps({"role": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Shell", "input": {"command": "ls"}}]}}) + "\n")
    return home, proj, tpath


def fake_store(home, chats=None):
    """A Cursor user dir under the fake HOME with a globalStorage store holding `chats`
    ({composer_id: composerData dict}); the hook never sees this machine's real store."""
    user = os.path.join(home, "cursor-user")
    os.makedirs(os.path.join(user, "globalStorage"), exist_ok=True)
    db = sqlite3.connect(os.path.join(user, "globalStorage", "state.vscdb"))
    db.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value BLOB)")
    for cid, data in (chats or {}).items():
        db.execute("INSERT OR REPLACE INTO cursorDiskKV VALUES (?, ?)", ("composerData:" + cid, json.dumps(data)))
    db.commit()
    db.close()
    return user


def hook_env(home):
    return dict(os.environ, HOME=home, AGENT_SPEC_CURSOR_USER_DIR=fake_store(home))


def fire(home, proj, payload, stdin=None):
    env = hook_env(home)
    res = subprocess.run([sys.executable, HOOK], cwd=proj, env=env, capture_output=True, text=True,
                         input=stdin if stdin is not None else json.dumps(payload))
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout) == {}, "hook must print {} (no followup_message)"
    return res


def receipt_path(proj):
    return os.path.join(proj, ".agent-spec", "metrics", "receipts", SID + ".json")


def test_session_end_writes_receipt_and_daily_row():
    home, proj, tpath = project()
    fire(home, proj, {"hook_event_name": "sessionEnd", "session_id": SID, "transcript_path": tpath})
    r = json.load(open(receipt_path(proj)))
    assert r["session_id"] == SID and r["tool_calls_total"] == 1, r
    rows = open(os.path.join(proj, ".agent-spec", "metrics", "daily.jsonl")).read().splitlines()
    assert len(rows) == 1 and json.loads(rows[0])["session_id"] == SID


def test_stop_is_debounced_and_never_duplicates_rows():
    home, proj, tpath = project()
    payload = {"hook_event_name": "stop", "conversation_id": SID, "transcript_path": tpath, "status": "completed"}
    fire(home, proj, payload)
    first = open(receipt_path(proj)).read()
    fire(home, proj, payload)   # inside the 30 s window: skipped
    assert open(receipt_path(proj)).read() == first
    old = os.path.getmtime(receipt_path(proj)) - 120
    os.utime(receipt_path(proj), (old, old))
    fire(home, proj, payload)   # outside the window: rewritten, still one daily row
    rows = open(os.path.join(proj, ".agent-spec", "metrics", "daily.jsonl")).read().splitlines()
    assert len(rows) == 1


def test_stop_hands_the_hook_probe_its_collect_turn_once():
    home, proj, tpath = project()
    marker = os.path.join(proj, ".agent-spec", ".hook-probe-pending")
    with open(marker, "w") as fh:
        fh.write("2026-11-13T00:00:00Z")
    payload = {"hook_event_name": "stop", "conversation_id": SID, "transcript_path": tpath, "status": "completed"}
    res = subprocess.run([sys.executable, HOOK], cwd=proj, env=hook_env(home),
                         capture_output=True, text=True, input=json.dumps(payload))
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout) == {"followup_message": "/agent-spec-hook-probe collect"}, res.stdout
    assert not os.path.exists(marker), "marker must be consumed so the followup never loops"
    fire(home, proj, payload)   # next stop: plain receipt path again, no followup


def run_hook(home, proj, payload):
    res = subprocess.run([sys.executable, HOOK], cwd=proj, env=hook_env(home),
                         capture_output=True, text=True, input=json.dumps(payload))
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def test_context_nudge_is_measured_and_fires_once():
    """Cursor's own contextTokensUsed past the reset break-even -> one /agent-spec-compact
    follow-up quoting the numbers; a later stop in the same chat stays quiet."""
    home, proj, tpath = project()
    fake_store(home, {SID: {"contextTokensUsed": 120000, "contextTokenLimit": 200000},
                      "fresh": {"contextTokensUsed": 18000, "subagentComposerIds": ["sub"]},
                      "sub": {"contextTokensUsed": 4000}})   # a subagent is not a fresh chat
    payload = {"hook_event_name": "stop", "conversation_id": SID, "transcript_path": tpath, "status": "completed"}
    out = run_hook(home, proj, payload)
    msg = out.get("followup_message") or ""
    assert "/agent-spec-compact" in msg and "120,000" in msg and "18,000" in msg, out
    assert run_hook(home, proj, payload) == {}, "one nudge per chat"


def test_no_context_nudge_while_carrying_is_cheaper():
    home, proj, tpath = project()
    fake_store(home, {SID: {"contextTokensUsed": 30000}, "fresh": {"contextTokensUsed": 18000}})
    payload = {"hook_event_name": "stop", "conversation_id": SID, "transcript_path": tpath, "status": "completed"}
    assert run_hook(home, proj, payload) == {}
    off = dict(payload)
    fake_store(home, {SID: {"contextTokensUsed": 150000}})
    env = dict(hook_env(home), AGENT_SPEC_CONTEXT_NUDGE="0")
    res = subprocess.run([sys.executable, HOOK], cwd=proj, env=env, capture_output=True, text=True,
                         input=json.dumps(off))
    assert json.loads(res.stdout) == {}, "AGENT_SPEC_CONTEXT_NUDGE=0 turns it off"


def test_context_check_is_throttled_and_rejects_unsafe_ids():
    """Review fixes: one store read per chat per interval (the store is copied on WSL), and a
    conversation_id that is not a plain id never becomes part of a file name."""
    home, proj, tpath = project()
    fake_store(home, {SID: {"contextTokensUsed": 30000}, "fresh": {"contextTokensUsed": 18000}})
    payload = {"hook_event_name": "stop", "conversation_id": SID, "transcript_path": tpath, "status": "completed"}
    assert run_hook(home, proj, payload) == {}
    checked = os.path.join(proj, ".agent-spec", "metrics", "context-checked", SID)
    assert os.path.isfile(checked)
    fake_store(home, {SID: {"contextTokensUsed": 150000}, "fresh": {"contextTokensUsed": 18000}})
    assert run_hook(home, proj, payload) == {}, "checked moments ago: no second store read"
    os.utime(checked, (0, 0))
    assert "/agent-spec-compact" in (run_hook(home, proj, payload).get("followup_message") or "")

    bad = dict(payload, conversation_id="../../escape")
    fake_store(home, {"../../escape": {"contextTokensUsed": 150000}, "fresh": {"contextTokensUsed": 18000}})
    assert "/agent-spec-compact" not in (run_hook(home, proj, bad).get("followup_message") or "")
    assert not os.path.exists(os.path.join(proj, "escape"))
    assert not [f for f in os.listdir(os.path.join(proj, ".agent-spec")) if "escape" in f]


def test_snapshot_nudge_fires_on_a_long_chat_and_not_before():
    """Regression: the marker was written on the first stop, and `tokens` (a dict) was
    compared to an int, so the AF-004 nudge never fired."""
    home, proj, tpath = project()
    payload = {"hook_event_name": "sessionEnd", "conversation_id": SID, "transcript_path": tpath}
    assert run_hook(home, proj, payload) == {}, "short chat: no nudge, marker not spent"
    with open(tpath, "a") as fh:
        for _ in range(6):
            fh.write(json.dumps({"role": "user", "message": {"content": [{"type": "text", "text": "next"}]}}) + "\n")
            fh.write(json.dumps({"role": "assistant", "message": {"content": [{"type": "text", "text": "ok"}]}}) + "\n")
    out = run_hook(home, proj, payload)
    # HA-001: the follow-up is the command itself, so the skill runs rather than being asked for.
    assert out.get("followup_message") == "/agent-spec-snapshot", out
    assert run_hook(home, proj, payload) == {}, "one snapshot nudge per chat"


def _stub(proj, name, body):
    """A stand-in .agent-spec/bin script that records it ran by writing `<name>.ran`."""
    path = os.path.join(proj, ".agent-spec", "bin", name)
    with open(path, "w") as fh:
        fh.write("import os, sys\nopen(os.path.join(%r, %r), 'w').write(' '.join(sys.argv[1:]))\n%s\n"
                 % (proj, name + ".ran", body))
    return os.path.join(proj, name + ".ran")


def _wait_for(path, seconds=5.0):
    end = time.time() + seconds
    while time.time() < end:
        if os.path.exists(path):
            return True
        time.sleep(0.05)
    return False


def test_stop_refreshes_the_graph_only_when_an_edit_marked_it_dirty():
    """HA-002: the event spine marks the graph dirty; the next stop rebuilds it in the
    background and spends the marker. No marker, no build."""
    home, proj, tpath = project()
    ran = _stub(proj, "graphify-build.py", "")
    payload = {"hook_event_name": "stop", "conversation_id": SID, "transcript_path": tpath}
    run_hook(home, proj, payload)
    assert not _wait_for(ran, 0.5), "clean graph: no build"
    marker = os.path.join(proj, ".agent-spec", ".graph-dirty")
    open(marker, "w").close()
    run_hook(home, proj, payload)
    assert _wait_for(ran), "dirty graph: build started"
    assert open(ran).read() == "--quiet"
    assert not os.path.exists(marker), "marker spent"


def test_session_end_rotates_the_snapshot_and_stop_does_not():
    """HA-003: rotation is deterministic, so it runs in the hook instead of relying on the
    snapshot skill's last step."""
    home, proj, tpath = project()
    ran = _stub(proj, "agent-spec-memory.py", "")
    run_hook(home, proj, {"hook_event_name": "stop", "conversation_id": SID, "transcript_path": tpath})
    assert not os.path.exists(ran), "stop must not rotate"
    run_hook(home, proj, {"hook_event_name": "sessionEnd", "conversation_id": SID, "transcript_path": tpath})
    assert open(ran).read() == "rotate"


def _automation_rows(proj):
    path = os.path.join(proj, ".agent-spec", "metrics", "automation.jsonl")
    return [json.loads(l) for l in open(path)] if os.path.exists(path) else []


def test_automations_log_a_row_and_obey_the_dashboard_switch():
    """HA-006: every run leaves a row for the Automations panel; a name in
    .agent-spec/automation.json "disabled" stops it, and a disabled graph keeps its marker."""
    home, proj, tpath = project()
    _stub(proj, "agent-spec-memory.py", "print('nothing to rotate')")
    _stub(proj, "graphify-build.py", "")
    marker = os.path.join(proj, ".agent-spec", ".graph-dirty")
    open(marker, "w").close()
    run_hook(home, proj, {"hook_event_name": "sessionEnd", "conversation_id": SID, "transcript_path": tpath})
    rows = {r["name"]: r for r in _automation_rows(proj)}
    assert rows["graph-refresh"]["status"] == "started" and rows["graph-refresh"]["session"] == SID, rows
    assert rows["snapshot-rotate"]["status"] == "ok" and rows["snapshot-rotate"]["reason"] == "nothing to rotate"
    assert isinstance(rows["snapshot-rotate"]["duration_ms"], int)

    with open(os.path.join(proj, ".agent-spec", "automation.json"), "w") as fh:
        json.dump({"disabled": ["graph-refresh", "snapshot-rotate", "snapshot-followup"]}, fh)
    open(marker, "w").close()
    with open(tpath, "a") as fh:
        for _ in range(6):
            fh.write(json.dumps({"role": "user", "message": {"content": [{"type": "text", "text": "n"}]}}) + "\n")
    before = len(_automation_rows(proj))
    out = run_hook(home, proj, {"hook_event_name": "sessionEnd", "conversation_id": SID, "transcript_path": tpath})
    assert out == {}, "snapshot follow-up switched off"
    assert len(_automation_rows(proj)) == before, "nothing ran, nothing logged"
    assert os.path.exists(marker), "disabled refresh leaves the marker for later"


def test_failing_rotate_and_build_stay_fail_open():
    home, proj, tpath = project()
    _stub(proj, "agent-spec-memory.py", "raise SystemExit(3)")
    _stub(proj, "graphify-build.py", "raise SystemExit(3)")
    open(os.path.join(proj, ".agent-spec", ".graph-dirty"), "w").close()
    fire(home, proj, {"hook_event_name": "sessionEnd", "session_id": SID, "transcript_path": tpath})


def test_fail_open_cases():
    home, proj, tpath = project()
    fire(home, proj, None, stdin="not json")                 # garbage payload, no transcript
    outside = tempfile.mkdtemp()                              # not an agent-spec project
    fire(home, outside, {"hook_event_name": "sessionEnd", "session_id": SID, "transcript_path": tpath})
    assert not os.path.exists(os.path.join(outside, ".agent-spec")), "must not create files outside a project"
    fire(home, proj, {"hook_event_name": "sessionEnd", "session_id": "no-such", "transcript_path": "/nope"})


def test_merge_registers_events_with_timeouts_idempotently():
    d = tempfile.mkdtemp()
    path = os.path.join(d, "hooks.json")
    json.dump({"version": 1, "hooks": {"stop": [{"command": "./foreign.sh"}]}}, open(path, "w"))
    for _ in range(2):
        assert subprocess.run([sys.executable, MERGE, path]).returncode == 0
    hooks = json.load(open(path))["hooks"]
    for event in ("sessionStart", "preToolUse", "sessionEnd", "stop"):
        mine = [h for h in hooks[event] if "agent-spec" in h["command"] and "cursor-event" not in h["command"]]
        assert len(mine) == 1, (event, hooks[event])
        assert isinstance(mine[0]["timeout"], int) and mine[0]["timeout"] >= 5
    # DV-001: the event spine is registered once per traced event, `stop` included.
    for event in ("beforeSubmitPrompt", "postToolUse", "subagentStop", "afterAgentResponse", "stop"):
        spine = [h for h in hooks[event] if "agent-spec-cursor-event" in h["command"]]
        assert len(spine) == 1, (event, hooks[event])
    assert hooks["sessionStart"][0]["timeout"] >= 10, "digest worst case is ~5 s"
    assert any(h["command"] == "./foreign.sh" for h in hooks["stop"]), "foreign handler must survive"
    subprocess.run([sys.executable, UNMERGE, path], check=True)
    after = json.load(open(path))["hooks"]
    assert all("agent-spec" not in h["command"] for hs in after.values() for h in hs)
    assert any(h["command"] == "./foreign.sh" for h in after["stop"])


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("  ok", fn.__name__)
    print("%d session-end tests passed" % len(tests))
