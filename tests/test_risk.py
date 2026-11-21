#!/usr/bin/env python3
"""Tests for the risk classifier (P4-011), the preToolUse tier gate (P4-012) and one-use
approvals (H-030).

Run: python3 tests/test_risk.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RISK = os.path.join(REPO, "bin", "agent-spec-risk.py")
HOOK = os.path.join(REPO, "hooks", "cursor-pre-tool-use.py")

_spec = importlib.util.spec_from_file_location("agent_spec_risk", RISK)
risk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(risk)


def make_project():
    t = tempfile.mkdtemp()
    spec = os.path.join(t, ".agent-spec")
    os.makedirs(os.path.join(spec, "graph"))
    os.makedirs(os.path.join(spec, "metrics"))
    os.makedirs(os.path.join(spec, "bin"))
    shutil.copy(RISK, os.path.join(spec, "bin", "agent-spec-risk.py"))
    edges = [{"source": "f%d.py" % i, "target": "hub.py", "type": "imports"} for i in range(25)]
    edges += [{"source": "f%d.py" % i, "target": "mid.py", "type": "imports"} for i in range(12)]
    nodes = [{"id": "hub.py", "layer": "util"}, {"id": "mid.py", "layer": "util"}, {"id": "domain.py", "layer": "domain"}]
    with open(os.path.join(spec, "graph", "knowledge-graph.json"), "w") as fh:
        json.dump({"nodes": nodes, "edges": edges}, fh)
    return t


class ClassifyTest(unittest.TestCase):
    def setUp(self):
        self.p = make_project()

    def tearDown(self):
        shutil.rmtree(self.p)

    def tier(self, tool, **args):
        return risk.classify(self.p, tool, args)["tier"]

    def test_tiers(self):
        self.assertEqual(self.tier("Read", file_path="hub.py"), 0)
        self.assertEqual(self.tier("Shell", command="python3 -m pytest -q"), 0)
        self.assertEqual(self.tier("Shell", command="ls -la"), 1)
        self.assertEqual(self.tier("Write", file_path="leaf.py"), 1)
        self.assertEqual(self.tier("StrReplace", file_path="mid.py"), 2)
        self.assertEqual(self.tier("Edit", file_path="domain.py"), 2)
        self.assertEqual(self.tier("Write", file_path=os.path.join(self.p, "hub.py")), 3)
        self.assertEqual(self.tier("Write", file_path="db/migrations/0003_add.sql"), 3)
        self.assertEqual(self.tier("Shell", command="git push --force origin main"), 3)
        self.assertEqual(self.tier("Shell", command="rm -rf build/"), 3)

    def test_thresholds_from_risk_json(self):
        with open(os.path.join(self.p, ".agent-spec", "risk.json"), "w") as fh:
            json.dump({"tier3_fan_in": 50, "core_globs": ["leaf.py"]}, fh)
        self.assertEqual(self.tier("Write", file_path="hub.py"), 2)
        self.assertEqual(self.tier("Write", file_path="leaf.py"), 3)

    def test_cross_repo_caller_is_tier_3(self):
        with open(os.path.join(self.p, ".agent-spec", "graph", "mesh-graph.json"), "w") as fh:
            json.dump({"edges": [{"source": "ui:src/api.ts", "target": "api:leaf.py", "type": "http"}]}, fh)
        self.assertEqual(self.tier("Write", file_path="leaf.py"), 3)

    def test_approval_is_one_use_and_expires(self):
        r = risk.classify(self.p, "Write", {"file_path": "hub.py"})
        key = risk.record_blocked(self.p, r, "s1")
        self.assertEqual([e["key"] for e in risk.pending(self.p)], [key])
        self.assertFalse(risk.consume_approval(self.p, r))
        risk.decide(self.p, key, approve=True)
        self.assertEqual(risk.pending(self.p), [])
        self.assertTrue(risk.consume_approval(self.p, r))
        self.assertFalse(risk.consume_approval(self.p, r), "an approval is used once")
        key = risk.record_blocked(self.p, r, "s1")
        with open(os.path.join(self.p, ".agent-spec", "risk.json"), "w") as fh:
            json.dump({"approval_ttl_s": -1}, fh)
        risk.decide(self.p, key, approve=True)
        self.assertFalse(risk.consume_approval(self.p, r), "an expired approval does not apply")
        with open(os.path.join(self.p, ".agent-spec", "metrics", "risk.jsonl")) as fh:
            events = [json.loads(l)["event"] for l in fh]
        self.assertEqual(events, ["blocked", "approved", "used", "blocked", "approved"])

    def test_deny_and_unknown_key(self):
        r = risk.classify(self.p, "Write", {"file_path": "hub.py"})
        key = risk.record_blocked(self.p, r)
        risk.decide(self.p, key, approve=False)
        self.assertFalse(risk.consume_approval(self.p, r))
        with self.assertRaises(KeyError):
            risk.decide(self.p, "nope", approve=True)


class SelfApprovalTest(unittest.TestCase):
    """2026-11-18 security review: the gated agent must not approve its own action, change the
    gate's config, approvals or code, or reach a tier-3 file through the shell."""

    def setUp(self):
        self.p = make_project()

    def tearDown(self):
        shutil.rmtree(self.p)

    def test_gate_state_is_protected(self):
        for path in (".agent-spec/risk.json", ".agent-spec/risk/approvals.json",
                     ".agent-spec/bin/agent-spec-risk.py", ".cursor/hooks/agent-spec-pre-tool-use.py"):
            r = risk.classify(self.p, "Write", {"file_path": path})
            self.assertTrue(r.get("protected") and r["tier"] == 3, (path, r))

    def test_shell_self_approval_and_state_writes_are_protected(self):
        for cmd in ("./.agent-spec/bin/agent-spec-risk.py approve abc123",
                    "python3 .agent-spec/bin/agent-spec-risk.py deny abc123",
                    "echo '{\"enforce\":\"off\"}' > .agent-spec/risk.json",
                    "sed -i s/block/off/ .agent-spec/risk.json",
                    "cp /tmp/x .agent-spec/bin/agent-spec-risk.py"):
            r = risk.classify(self.p, "Shell", {"command": cmd})
            self.assertTrue(r.get("protected"), (cmd, r))
        self.assertFalse(risk.classify(self.p, "Shell", {"command": "cat .agent-spec/risk.json"}).get("protected"))
        for cmd in ("ls .agent-spec/bin/graphify-cli.py 2>/dev/null", "python3 .agent-spec/bin/agent-spec-memory.py handoff",
                    "./.agent-spec/bin/graphify-cli.py search redact 2>&1 | head -40",
                    "bash .agent-spec/bin/x.sh >/dev/null 2>&1"):
            self.assertFalse(risk.classify(self.p, "Shell", {"command": cmd}).get("protected"), cmd)
        for cmd in ("python3 -c \"open('.agent-spec/risk.json','w')\"",
                    "python3 .agent-spec/bin/agent-spec-digest.py > .agent-spec/bin/agent-spec-risk.py",
                    "ls .agent-spec/bin 2>/dev/null; echo x >> .agent-spec/risk.json"):
            self.assertTrue(risk.classify(self.p, "Shell", {"command": cmd}).get("protected"), cmd)

    def test_shell_write_to_tier3_file_is_tier3(self):
        for cmd in ("sed -i 's/a/b/' hub.py", "cat > db/migrations/0004.sql <<EOF", "echo x >> hub.py",
                    "mv new.py hub.py"):
            self.assertEqual(risk.classify(self.p, "Shell", {"command": cmd})["tier"], 3, cmd)
        self.assertEqual(risk.classify(self.p, "Shell", {"command": "echo hi > notes.txt"})["tier"], 1)

    def test_cli_approve_refuses_without_a_terminal(self):
        res = subprocess.run([sys.executable, RISK, "--project", self.p, "approve", "abc"],
                             capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(res.returncode, 2)
        self.assertIn("interactive terminal", res.stderr)


class HookGateTest(unittest.TestCase):
    def setUp(self):
        self.p = make_project()

    def tearDown(self):
        shutil.rmtree(self.p)

    def hook(self, tool, args):
        payload = {"tool_name": tool, "tool_input": args, "conversation_id": "c1"}
        env = dict(os.environ, TMPDIR=self.p)
        res = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), cwd=self.p,
                             capture_output=True, text=True, env=env, timeout=20)
        return json.loads(res.stdout or "{}")

    def test_tier3_blocks_until_approved_once(self):
        out = self.hook("Write", {"file_path": "hub.py", "content": "x"})
        self.assertEqual(out["permission"], "deny")
        self.assertIn("Risk tier 3", out.get("agent_message", "") + json.dumps(out))
        key = risk.pending(self.p)[0]["key"]
        risk.decide(self.p, key, approve=True)
        self.assertEqual(self.hook("Write", {"file_path": "hub.py", "content": "x"})["permission"], "allow")
        self.assertEqual(self.hook("Write", {"file_path": "hub.py", "content": "x"})["permission"], "deny")

    def test_protected_path_is_denied_and_never_approvable(self):
        out = self.hook("Write", {"file_path": ".agent-spec/risk.json", "content": '{"enforce": "off"}'})
        self.assertEqual(out["permission"], "deny")
        self.assertNotIn("agent-spec-risk.py approve", json.dumps(out))
        self.assertEqual(risk.pending(self.p), [], "nothing to approve")

    def test_deny_message_does_not_offer_self_approval(self):
        out = self.hook("Write", {"file_path": "hub.py", "content": "x"})
        self.assertNotIn("agent-spec-risk.py approve", out.get("agent_message", ""))

    def test_tier2_is_allowed_and_recorded(self):
        self.assertEqual(self.hook("StrReplace", {"file_path": "mid.py", "old_string": "a", "new_string": "b"})["permission"], "allow")
        with open(os.path.join(self.p, ".agent-spec", "metrics", "risk.jsonl")) as fh:
            self.assertEqual(json.loads(fh.readline())["event"], "warned")

    def test_enforce_off_and_warn(self):
        for mode in ("off", "warn"):
            with open(os.path.join(self.p, ".agent-spec", "risk.json"), "w") as fh:
                json.dump({"enforce": mode}, fh)
            self.assertEqual(self.hook("Write", {"file_path": "hub.py", "content": "x"})["permission"], "allow", mode)

    def test_classifier_error_fails_open(self):
        with open(os.path.join(self.p, ".agent-spec", "bin", "agent-spec-risk.py"), "w") as fh:
            fh.write("raise RuntimeError('broken classifier')\n")
        self.assertEqual(self.hook("Write", {"file_path": "hub.py", "content": "x"})["permission"], "allow")
        with open(os.path.join(self.p, ".agent-spec", "metrics", "risk.jsonl")) as fh:
            row = json.loads(fh.readline())
        self.assertEqual(row["event"], "error")
        self.assertIn("broken classifier", row["error"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
