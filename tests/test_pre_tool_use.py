#!/usr/bin/env python3
"""Tests for hooks/cursor-pre-tool-use.py: default nudge, ranged reads, optional hard cap
(T-011) and the payload debug log.

Run: python3 tests/test_pre_tool_use.py
"""
import json
import os
import subprocess
import sys
import tempfile

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO_DIR, "hooks", "cursor-pre-tool-use.py")


def project(big_bytes=30000):
    t = tempfile.mkdtemp()
    os.makedirs(os.path.join(t, ".agent-spec"))
    with open(os.path.join(t, "big.txt"), "w") as fh:
        fh.write("x" * big_bytes)
    with open(os.path.join(t, "small.txt"), "w") as fh:
        fh.write("x" * 100)
    return t


def call(proj, payload, **env):
    e = dict(os.environ, TMPDIR=os.path.join(proj, "tmp"))
    os.makedirs(e["TMPDIR"], exist_ok=True)
    for k in ("AGENT_SPEC_READ_HARD_CAP_KB", "AGENT_SPEC_HOOK_DEBUG"):
        e.pop(k, None)
    e.update(env)
    res = subprocess.run([sys.executable, HOOK], cwd=proj, input=json.dumps(payload),
                         capture_output=True, text=True, env=e)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def read(proj, name, **extra):
    args = {"path": os.path.join(proj, name)}
    args.update(extra)
    return {"tool_name": "Read", "tool_input": args, "session_id": "s1"}


def test_default_nudges_once_then_allows():
    p = project()
    assert call(p, read(p, "big.txt"))["permission"] == "deny"
    assert call(p, read(p, "big.txt"))["permission"] == "allow", "retry must go through"


def test_ranged_read_allowed():
    p = project()
    assert call(p, read(p, "big.txt", offset=10, limit=50))["permission"] == "allow"


def test_small_read_allowed():
    p = project()
    assert call(p, read(p, "small.txt"))["permission"] == "allow"


def test_hard_cap_denies_every_time():
    p = project()
    for _ in range(3):
        out = call(p, read(p, "big.txt"), AGENT_SPEC_READ_HARD_CAP_KB="10")
        assert out["permission"] == "deny", out
    assert "AGENT_SPEC_READ_HARD_CAP_KB" in out["agent_message"], "message must say how to lift it"


def test_hard_cap_still_allows_ranged_and_small():
    p = project()
    assert call(p, read(p, "big.txt", limit=40), AGENT_SPEC_READ_HARD_CAP_KB="10")["permission"] == "allow"
    assert call(p, read(p, "small.txt"), AGENT_SPEC_READ_HARD_CAP_KB="10")["permission"] == "allow"


def test_hard_cap_off_by_default_and_ignores_garbage():
    p = project()
    assert call(p, read(p, "big.txt"), AGENT_SPEC_READ_HARD_CAP_KB="abc")["permission"] == "deny"  # nudge
    assert call(p, read(p, "big.txt"), AGENT_SPEC_READ_HARD_CAP_KB="abc")["permission"] == "allow"  # retry


def test_alternate_payload_shapes_count_as_ranged():
    p = project()
    payload = {"toolName": "Read", "arguments": {"file_path": os.path.join(p, "big.txt"), "start_line": 5},
               "sessionId": "s2"}
    assert call(p, payload)["permission"] == "allow"
    stringy = {"tool_name": "Read", "session_id": "s3",
               "tool_input": json.dumps({"path": os.path.join(p, "big.txt"), "offset": 3, "limit": 9})}
    assert call(p, stringy)["permission"] == "allow"


def test_debug_log_records_shape_not_contents():
    p = project()
    call(p, read(p, "big.txt", offset=1, limit=2), AGENT_SPEC_HOOK_DEBUG="1")
    log = os.path.join(p, "tmp", "algosec-agent-spec-hook-debug.jsonl")
    assert os.path.exists(log), "debug log not written"
    row = json.loads(open(log).read().splitlines()[-1])
    assert row["tool"] == "Read" and "offset" in row["arg_keys"] and "limit" in row["arg_keys"], row
    assert "big.txt" not in json.dumps(row), "debug log must not record paths or file contents"


def test_range_detection_is_tolerant():
    p = project()
    big = os.path.join(p, "big.txt")
    shapes = [
        {"path": big, "Offset": 5},                    # key case
        {"path": big, "offset": 0, "limit": 40},       # offset 0 with a limit
        {"path": big, "range": {"start_line": 3}},     # nested range
        {"path": big, "view_range": [1, 20]},          # list-valued range
    ]
    for i, args in enumerate(shapes):
        payload = {"tool_name": "Read", "tool_input": args, "session_id": "r%d" % i}
        assert call(p, payload)["permission"] == "allow", args


def test_targeted_edit_reported_as_write_is_allowed():
    p = project()
    big = os.path.join(p, "big.txt")
    edit = {"tool_name": "Write", "session_id": "w1",
            "tool_input": {"path": big, "old_string": "x", "new_string": "y"}}
    assert call(p, edit)["permission"] == "allow", "StrReplace-shaped payload must not be nudged"
    full = {"tool_name": "Write", "session_id": "w2", "tool_input": {"path": big, "contents": "new"}}
    assert call(p, full)["permission"] == "deny", "full rewrite of a big file is still nudged"


def test_debug_marker_file_enables_log_with_decision():
    p = project()
    open(os.path.join(p, ".agent-spec", ".hook-debug"), "w").close()
    call(p, read(p, "big.txt", offset=0, limit=7))
    log = os.path.join(p, "tmp", "algosec-agent-spec-hook-debug.jsonl")
    row = json.loads(open(log).read().splitlines()[-1])
    assert row["ranged"] is True and row["decision"] == "allow", row
    assert row["arg_shape"]["offset"] == 0 and row["arg_shape"]["path"] == "str", row


def test_fail_open_on_garbage():
    p = project()
    res = subprocess.run([sys.executable, HOOK], cwd=p, input="not json", capture_output=True, text=True)
    assert json.loads(res.stdout)["permission"] == "allow"


# ---- S-002: secrets & sensitive-path quarantine -------------------------------------------

def call_raw(proj, raw):
    """Feed raw bytes/str to the hook (for malformed payloads); returns (parsed stdout, rc)."""
    data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
    res = subprocess.run([sys.executable, HOOK], cwd=proj, input=data, capture_output=True)
    return json.loads(res.stdout.decode("utf-8")), res.returncode


def tool(name, **args):
    return {"tool_name": name, "tool_input": args, "session_id": "q1"}


def quarantine_log(proj):
    path = os.path.join(proj, ".agent-spec", "metrics", "quarantine.jsonl")
    if not os.path.exists(path):
        return []
    return [json.loads(line) for line in open(path).read().splitlines() if line.strip()]


# (payload, expected rule-id) -- one row per pattern in the S-002 spec
QUARANTINE_CASES = [
    (tool("Read", path="/w/.env"), "env-file"),
    (tool("Read", file_path="/w/.env.local"), "env-file"),
    (tool("Read", target_file="/w/.env.production"), "env-file"),
    (tool("Read", path="/w/certs/server.pem"), "pem-file"),
    (tool("Read", path="/w/certs/server.key"), "key-file"),
    (tool("Read", path="/h/.ssh/id_rsa"), "ssh-private-key"),
    (tool("Read", path="/w/id_rsa.pub"), "ssh-private-key"),
    (tool("Read", path="/w/id_ed25519"), "ssh-private-key"),
    (tool("Read", path="/w/id_ed25519.pub"), "ssh-private-key"),
    (tool("Read", path="/w/credentials"), "credentials-file"),
    (tool("Read", path="/w/credentials.json"), "credentials-file"),
    (tool("Read", path="/w/secrets.yaml"), "secrets-file"),
    (tool("Read", path="/w/secrets.json"), "secrets-file"),
    (tool("Read", path="/w/secrets.toml"), "secrets-file"),
    (tool("Read", path="~/.aws/config"), "aws-dir"),
    (tool("Read", path="/Users/x/.ssh/known_hosts"), "ssh-dir"),
    (tool("Read", path="~/.gnupg/pubring.kbx"), "gnupg-dir"),
    # other tools / path argument names
    (tool("Write", path="/w/.env", contents="A=1"), "env-file"),
    (tool("Write", file_path="/w/.env", old_string="a", new_string="b"), "env-file"),
    (tool("StrReplace", path="/w/secrets.yaml", old_string="a", new_string="b"), "secrets-file"),
    (tool("Edit", file_path="/w/server.pem", old_string="a", new_string="b"), "pem-file"),
    (tool("Delete", path="/w/.env"), "env-file"),
    (tool("Grep", pattern="TOKEN", path="/w/.env"), "env-file"),
    (tool("Grep", pattern="Host", path="~/.ssh"), "ssh-dir"),
    (tool("Glob", glob_pattern="**/*.pem"), "pem-file"),
    (tool("Glob", glob_pattern="*.key", target_directory="/w"), "key-file"),
    (tool("Glob", glob_pattern="*", target_directory="~/.aws"), "aws-dir"),
    # Shell command text
    (tool("Shell", command="cat .env"), "env-file"),
    (tool("Shell", command="cat .env.local | head -3"), "env-file"),
    (tool("Shell", command="source ./.env && ./run.sh"), "env-file"),
    (tool("Shell", command="cp ~/.ssh/id_rsa /tmp/x"), "ssh-private-key"),
    (tool("Shell", command="ls -la ~/.aws"), "aws-dir"),
    (tool("Shell", command="tar czf /tmp/k.tgz $HOME/.gnupg"), "gnupg-dir"),
    (tool("Shell", command="openssl x509 -in \"certs/server.pem\" -noout"), "pem-file"),
    (tool("Shell", command="scp --key=deploy.key host:/x"), "key-file"),
    (tool("Shell", command="cat credentials.json"), "credentials-file"),
    (tool("Shell", command="cat config/secrets.toml"), "secrets-file"),
    (tool("Bash", command="cat ~/.ssh/id_ed25519"), "ssh-private-key"),
]


def test_quarantine_denies_every_pattern_every_time():
    p = project()
    for payload, rule in QUARANTINE_CASES:
        for attempt in range(2):  # a hard deny has no retry-as-is bypass
            out = call(p, payload)
            assert out["permission"] == "deny", (payload, attempt, out)
            assert rule in out["agent_message"], (payload, rule, out)
            assert out["user_message"] and "quarantine" in out["user_message"].lower(), out


def test_quarantine_allows_lookalikes():
    p = project()
    allowed = [
        tool("Read", path="/w/.env.example"),
        tool("Read", path="/w/.env.sample"),
        tool("Read", path="/w/.env.template"),
        tool("Read", path="/w/README.md"),
        tool("Read", path="/w/environment.py"),
        tool("Read", path="/w/keyboard.py"),
        tool("Read", path="/w/secrets_manager.py"),
        tool("Read", path="/w/credentials_helper.py"),
        tool("Read", path="/w/monkey.pem.md"),
        tool("Read", path="/w/docs/ssh-notes.md"),
        tool("Glob", glob_pattern="**/*.py", target_directory="/w"),
        tool("Grep", pattern=r"\.env|id_rsa|secrets\.", path="/w/README.md"),
        tool("Write", path="/w/notes.md", contents="never commit .env or ~/.ssh/id_rsa"),
        tool("Shell", command="cat README.md"),
        tool("Shell", command="python3 environment.py && python3 keyboard.py"),
        tool("Shell", command="cp .env.example .env.sample"),
        tool("Shell", command="env | sort"),
        tool("Task", prompt="read the docs"),
    ]
    for payload in allowed:
        out = call(p, payload)
        assert out["permission"] == "allow", (payload, out)
    assert quarantine_log(p) == [], "allowed calls must not be logged"


def test_quarantine_log_line_is_redacted_and_complete():
    p = project()
    call(p, {"tool_name": "Write", "session_id": "sess-9",
             "tool_input": {"path": "/very/private/dir/.env.production", "contents": "API_KEY=hunter2"}})
    call(p, {"toolName": "Shell", "sessionId": "sess-10",
             "arguments": {"command": "cat /home/u/.ssh/id_rsa"}})
    call(p, tool("Read", path="/w/secrets.yaml"))
    rows = quarantine_log(p)
    assert len(rows) == 3, rows
    first = rows[0]
    assert set(first) >= {"ts", "tool", "pattern", "path", "session_id"}, first
    assert first["tool"] == "Write" and first["pattern"] == "env-file", first
    assert first["session_id"] == "sess-9", first
    assert first["path"] == ".env.production", "basename only"
    assert first["ts"].endswith("Z") and "T" in first["ts"], first
    assert rows[1]["tool"] == "Shell" and rows[1]["pattern"] == "ssh-private-key", rows[1]
    assert rows[1]["session_id"] == "sess-10" and rows[1]["path"] == "id_rsa", rows[1]
    blob = open(os.path.join(p, ".agent-spec", "metrics", "quarantine.jsonl")).read()
    assert "hunter2" not in blob and "very/private" not in blob and "/home/u" not in blob, blob


def test_quarantine_log_failure_never_breaks_the_deny():
    p = project()
    open(os.path.join(p, ".agent-spec", "metrics"), "w").write("a file, not a directory")
    out = call(p, tool("Read", path="/w/.env"))
    assert out["permission"] == "deny", out


def test_quarantine_denies_without_agent_spec_dir_and_logs_nothing():
    t = tempfile.mkdtemp()  # unregistered folder: no .agent-spec
    out = call(t, tool("Read", path="/w/.env"))
    assert out["permission"] == "deny", out
    assert not os.path.exists(os.path.join(t, ".agent-spec")), "must not create .agent-spec"


def test_quarantine_matches_malformed_payloads_but_still_fails_open_otherwise():
    p = project()
    # truncated JSON that still names a secret path -> raw-text fallback denies
    out, rc = call_raw(p, '{"tool_name": "Read", "tool_input": {"path": "/w/.env"')
    assert rc == 0 and out["permission"] == "deny", out
    # tool_input is a string that is not JSON, but contains a secret path
    out, rc = call_raw(p, json.dumps({"tool_name": "Shell", "tool_input": "cat ~/.ssh/id_rsa {oops"}))
    assert rc == 0 and out["permission"] == "deny", out
    # valid JSON, not an object
    out, rc = call_raw(p, json.dumps(["cat", ".env"]))
    assert rc == 0 and out["permission"] == "deny", out
    # tool_input is a list (unexpected shape)
    out, rc = call_raw(p, json.dumps({"tool_name": "Read", "tool_input": ["/w/server.pem"]}))
    assert rc == 0 and out["permission"] == "deny", out
    # invalid UTF-8 around a secret path
    out, rc = call_raw(p, b'{"tool_name":"Read","tool_input":{"path":"\xff\xfe/w/id_rsa"')
    assert rc == 0 and out["permission"] == "deny", out
    # malformed but NOT secret -> fail open
    for raw in ('not json', '{"tool_name": "Read", "tool_input": {"path": "/w/README.md"',
                '', '[1, 2', b'\xff\xfe\x00garbage',
                json.dumps({"tool_name": "Shell", "tool_input": "cat README.md {oops"})):
        out, rc = call_raw(p, raw)
        assert rc == 0 and out["permission"] == "allow", (raw, out)
    assert [r["pattern"] for r in quarantine_log(p)] == ["env-file", "ssh-private-key", "env-file",
                                                         "pem-file", "ssh-private-key"]


def test_quarantine_runs_before_hard_cap_and_nudges():
    p = project()
    big_env = os.path.join(p, ".env")
    open(big_env, "w").write("x" * 30000)
    # a big rangeless read of .env is a quarantine deny, repeated, not a one-shot nudge
    for _ in range(2):
        out = call(p, {"tool_name": "Read", "tool_input": {"path": big_env}, "session_id": "z"},
                   AGENT_SPEC_READ_HARD_CAP_KB="10")
        assert out["permission"] == "deny" and "env-file" in out["agent_message"], out
    # a ranged read of a secret is still denied
    assert call(p, read(p, ".env", offset=1, limit=5))["permission"] == "deny"


# ---- S-004: context threshold proactive nudge (>80k tokens) -------------------------------

def test_token_threshold_nudge_fires_above_80k_and_retries_allow():
    p = project()
    payload = {"tool_name": "Read", "tool_input": {"path": os.path.join(p, "small.txt")},
               "session_id": "tok_s1", "session_tokens": 85000}
    out1 = call(p, payload)
    assert out1["permission"] == "deny", out1
    assert "/agent-spec-compact" in out1["agent_message"], out1
    assert "85000" in out1["agent_message"], out1

    # Check that nudge was logged to quarantine.jsonl (CP-050)
    qlog = os.path.join(p, ".agent-spec", "metrics", "quarantine.jsonl")
    assert os.path.isfile(qlog), "quarantine.jsonl must exist after context threshold nudge"
    with open(qlog, encoding="utf-8") as fh:
        lines = [json.loads(line) for line in fh if line.strip()]
    assert any(l.get("pattern") == "S-004-threshold" and "session_tokens=85000" in l.get("path", "") for l in lines)

    # Retry with same session must allow through
    out2 = call(p, payload)
    assert out2["permission"] == "allow", out2


def test_token_threshold_under_80k_allowed():
    p = project()
    payload = {"tool_name": "Read", "tool_input": {"path": os.path.join(p, "small.txt")},
               "session_id": "tok_s2", "session_tokens": 50000}
    out = call(p, payload)
    assert out["permission"] == "allow", out


def test_token_threshold_custom_env_and_dict_tokens():
    p = project()
    payload = {"tool_name": "Read", "tool_input": {"path": os.path.join(p, "small.txt")},
               "session_id": "tok_s3", "tokens": {"input": 450, "output": 100}}
    # With threshold 500, total 550 triggers nudge
    out1 = call(p, payload, AGENT_SPEC_TOKEN_THRESHOLD="500")
    assert out1["permission"] == "deny", out1
    assert "/agent-spec-compact" in out1["agent_message"], out1
    out2 = call(p, payload, AGENT_SPEC_TOKEN_THRESHOLD="500")
    assert out2["permission"] == "allow", out2


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("  ok", fn.__name__)
    print("%d preToolUse tests passed" % len(tests))
