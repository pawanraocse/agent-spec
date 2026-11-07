#!/usr/bin/env python3
"""Tests for `agent-spec-tokens.py audit` additions: lean coexistence (T-013) and the
exit-code contract the optional CI step (T-012) relies on.

Run: python3 tests/test_audit.py
"""
import json
import os
import subprocess
import sys
import tempfile

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKENS = os.path.join(REPO_DIR, "bin", "agent-spec-tokens.py")


def harness_project(t):
    os.makedirs(os.path.join(t, ".agent-spec"))
    hooks = os.path.join(t, ".cursor", "hooks")
    os.makedirs(hooks)
    for name in ("agent-spec-session-start.py", "agent-spec-pre-tool-use.py"):
        open(os.path.join(hooks, name), "w").write("# stub\n")
    json.dump({"version": 1, "hooks": {
        "sessionStart": [{"command": "python3 .cursor/hooks/agent-spec-session-start.py"}],
        "preToolUse": [{"command": "python3 .cursor/hooks/agent-spec-pre-tool-use.py"}]}},
        open(os.path.join(t, ".cursor", "hooks.json"), "w"))
    rules = os.path.join(t, ".cursor", "rules")
    os.makedirs(rules)
    open(os.path.join(rules, "agent-spec.mdc"), "w").write("---\nalwaysApply: true\n---\nrules\n")
    return rules


def audit(t):
    return subprocess.run([sys.executable, TOKENS, "audit", "--scan", t], capture_output=True, text=True)


def test_clean_harness_exits_zero():
    with tempfile.TemporaryDirectory() as t:
        harness_project(t)
        res = audit(t)
        assert res.returncode == 0 and "no findings" in res.stdout, res.stdout


def test_lean_always_apply_next_to_agent_spec_is_flagged():
    with tempfile.TemporaryDirectory() as t:
        rules = harness_project(t)
        open(os.path.join(rules, "algosec-lean.mdc"), "w").write("---\nalwaysApply: true\n---\nterse\n")
        res = audit(t)
        assert res.returncode != 0, "findings must fail the audit so CI can gate on it"
        assert "algosec-lean is Always Apply" in res.stdout, res.stdout
        assert "alwaysApply: false" in res.stdout, "must say how to fix"


def test_lean_on_demand_is_not_flagged_as_stacking():
    with tempfile.TemporaryDirectory() as t:
        rules = harness_project(t)
        open(os.path.join(rules, "algosec-lean.mdc"), "w").write("---\nalwaysApply: false\n---\nterse\n")
        res = audit(t)
        assert "algosec-lean is Always Apply" not in res.stdout, res.stdout


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("  ok", fn.__name__)
    print("%d audit tests passed" % len(tests))
