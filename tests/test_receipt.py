#!/usr/bin/env python3
"""Tests for bin/agent-spec-receipt.py (T-050): one JSON per session, counts only.

Run: python3 tests/test_receipt.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECEIPT = os.path.join(REPO_DIR, "bin", "agent-spec-receipt.py")
SID = "11111111-2222-3333-4444-555555555555"

DIGEST = ("<agent-spec-digest>\nstack: test\nremembered:\n- fact one\n- fact two\n- fact three\n"
          "Do NOT open PROJECT-INDEX.md again.\n</agent-spec-digest>")


def make_env():
    """A fake HOME holding one Cursor transcript for a throwaway project."""
    home = tempfile.mkdtemp()
    proj = os.path.realpath(tempfile.mkdtemp())
    os.makedirs(os.path.join(proj, ".agent-spec"))
    with open(os.path.join(proj, "big.txt"), "w") as fh:
        fh.write("x" * 30000)
    with open(os.path.join(proj, "small.txt"), "w") as fh:
        fh.write("x" * 50)
    slug = proj.lstrip(os.sep).replace(os.sep, "-").replace(".", "-")
    tdir = os.path.join(home, ".cursor", "projects", slug, "agent-transcripts", SID)
    os.makedirs(tdir)
    tool = lambda name, **inp: {"role": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": inp}]}}
    rows = [
        {"role": "user", "message": {"content": [{"type": "text", "text": DIGEST}]}},
        tool("Read", path=os.path.join(proj, "big.txt")),                       # whole-file, flagged
        tool("Read", path=os.path.join(proj, "big.txt"), offset=1, limit=20),   # ranged
        tool("Read", path=os.path.join(proj, "small.txt")),                     # small
        tool("Shell", command="./.agent-spec/bin/graphify-cli.py query --file a.py"),
        tool("Shell", command="sed -n 1,5p bin/graphify-cli.py"),               # not a query
        {"role": "assistant", "message": {"content": [{"type": "text", "text": "done"}]}},
    ]
    with open(os.path.join(tdir, SID + ".jsonl"), "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return home, proj, os.path.join(tdir, SID + ".jsonl")


def run(home, proj, *args):
    env = dict(os.environ, HOME=home)
    return subprocess.run([sys.executable, RECEIPT, "--project", proj] + list(args),
                          capture_output=True, text=True, env=env, cwd=proj)


def test_receipt_counts():
    home, proj, _ = make_env()
    res = run(home, proj, "--stdout")
    assert res.returncode == 0, res.stderr
    r = json.loads(res.stdout)
    assert r["schema"] == 1 and r["session_id"] == SID, r
    assert r["graph_queries"] == 1, "only a real graphify-cli subcommand counts"
    assert r["whole_file_reads"]["count"] == 1, r["whole_file_reads"]
    assert r["whole_file_reads"]["files"][0] == {"path": "big.txt", "bytes": 30000}
    assert r["facts_injected"] == 3, r["facts_injected"]
    assert r["tool_calls"]["Read"] == 3 and r["tool_calls_total"] == 5
    assert set(r["tokens"]) == {"input", "output", "cache_read", "cache_write", "estimated"}
    assert "gate" in r["gates"]
    assert "x" * 100 not in json.dumps(r), "receipt must hold counts, never file contents"


def test_write_and_daily_upsert_is_idempotent():
    home, proj, _ = make_env()
    for _ in range(2):
        assert run(home, proj, "--daily").returncode == 0
    path = os.path.join(proj, ".agent-spec", "metrics", "receipts", SID + ".json")
    assert json.load(open(path))["session_id"] == SID
    rows = open(os.path.join(proj, ".agent-spec", "metrics", "daily.jsonl")).read().splitlines()
    assert len(rows) == 1, "second run must replace the session's row, not append"
    row = json.loads(rows[0])
    assert row["session_id"] == SID and row["whole_file_reads"] == 1 and row["graph_queries"] == 1


def test_experience_line_is_upserted_per_session():
    """L-001: --experience appends ONE line per session (the stop hook refires every turn)."""
    home, proj, tpath = make_env()
    with open(tpath, "a") as fh:
        for text in ("<user_query>\nadd the export command\n</user_query>",
                     "no, that is wrong - use csv", "thanks, now run the tests"):
            fh.write(json.dumps({"role": "user", "message": {"content": [{"type": "text", "text": text}]}}) + "\n")
    for _ in range(2):
        assert run(home, proj, "--experience").returncode == 0
    lines = open(os.path.join(proj, ".agent-spec", "experience.jsonl")).read().splitlines()
    assert len(lines) == 1, "second run must replace the session's line"
    e = json.loads(lines[0])
    assert e["exp_id"] == "session:" + SID and e["kind"] == "session", e
    assert e["task"] == "add the export command", e["task"]
    assert e["corrections"] == 1, "one later user turn opened with 'no'"
    assert e["facts_injected"] == 3 and e["tokens"]["input"] >= 0 and "gates" in e
    assert "x" * 100 not in json.dumps(e), "experience holds counts and a short task, never file contents"


def test_experience_task_is_redacted_and_capped():
    home, proj, tpath = make_env()
    secret = "api_key=sk-abcdef0123456789abcdef0123456789"
    with open(tpath, "a") as fh:
        fh.write(json.dumps({"role": "user", "message": {"content": [
            {"type": "text", "text": "<user_query>%s %s</user_query>" % (secret, "y" * 400)}]}}) + "\n")
    assert run(home, proj, "--experience").returncode == 0
    e = json.loads(open(os.path.join(proj, ".agent-spec", "experience.jsonl")).read().splitlines()[0])
    assert "sk-abcdef" not in e["task"] and len(e["task"]) <= 200, e["task"]


def test_explicit_transcript_and_session_selector():
    home, proj, tpath = make_env()
    assert run(home, proj, "--stdout", "--session", SID).returncode == 0
    assert run(home, proj, "--stdout", "--session", "nope").returncode == 1
    elsewhere = tempfile.mkdtemp()
    assert run(home, proj, "--stdout", "--transcript", tpath).returncode == 0


def test_no_transcript_fails_cleanly():
    home = tempfile.mkdtemp()
    proj = tempfile.mkdtemp()
    res = run(home, proj, "--stdout")
    assert res.returncode == 1 and "no Cursor transcript" in res.stderr


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("  ok", fn.__name__)
    print("%d receipt tests passed" % len(tests))
