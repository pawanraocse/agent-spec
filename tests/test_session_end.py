#!/usr/bin/env python3
"""Tests for hooks/cursor-session-end.py and the hooks.json merge that registers it
(T-051): receipt + daily row on sessionEnd/stop, fail-open, idempotent merge.

Run: python3 tests/test_session_end.py
"""
import json
import os
import subprocess
import sys
import tempfile

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


def fire(home, proj, payload, stdin=None):
    env = dict(os.environ, HOME=home)
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
        mine = [h for h in hooks[event] if "agent-spec" in h["command"]]
        assert len(mine) == 1, (event, hooks[event])
        assert isinstance(mine[0]["timeout"], int) and mine[0]["timeout"] >= 5
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
