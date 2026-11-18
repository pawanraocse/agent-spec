#!/usr/bin/env python3
"""Hash-chained session audit export (P3-011): every line links to the one before it, so an
edited, removed or reordered line is caught by `verify`; risk decisions join the session.

Run: python3 tests/test_audit_export.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "bin"))
from aspec_platform import audit_export, traces  # noqa: E402
from test_traces import hook_rows  # noqa: E402


class AuditExportTest(unittest.TestCase):
    def setUp(self):
        self.project = tempfile.mkdtemp()
        metrics = os.path.join(self.project, ".agent-spec", "metrics")
        os.makedirs(metrics)
        rows = hook_rows()
        rows[0] = dict(rows[0], prompt="deploy with token ghp_abcdefghijklmnopqrstuvwxyz0123456789")
        with open(os.path.join(metrics, "events.jsonl"), "w") as fh:
            fh.write("\n".join(json.dumps(r) for r in rows) + "\n")
        with open(os.path.join(metrics, "risk.jsonl"), "w") as fh:
            fh.write(json.dumps({"ts": "2023-11-14T22:13:21Z", "event": "blocked", "key": "k1", "tier": 3,
                                 "tool": "Write", "target": "hub.py", "session": "conv-1"}) + "\n")
            fh.write(json.dumps({"ts": "2023-11-14T22:13:22Z", "event": "approved", "key": "k1", "tier": 3,
                                 "by": "dashboard"}) + "\n")
            fh.write(json.dumps({"ts": "2023-11-14T22:13:22Z", "event": "blocked", "key": "other",
                                 "session": "conv-2"}) + "\n")
        self.env = os.environ.get("AGENT_SPEC_CURSOR_STORE")
        os.environ["AGENT_SPEC_CURSOR_STORE"] = "0"
        traces._CACHE.clear()

    def tearDown(self):
        if self.env is None:
            os.environ.pop("AGENT_SPEC_CURSOR_STORE", None)
        else:
            os.environ["AGENT_SPEC_CURSOR_STORE"] = self.env
        shutil.rmtree(self.project)

    def export(self):
        rows = audit_export.build(self.project, None, "conv-1")
        self.assertTrue(rows)
        return audit_export.to_jsonl(rows)

    def test_chain_verifies_and_covers_the_session(self):
        text = self.export()
        self.assertTrue(audit_export.verify(text)["ok"])
        rows = [json.loads(l) for l in text.splitlines()]
        types = [r["type"] for r in rows]
        self.assertEqual(types[0], "header")
        for t in ("request", "action", "outcome", "risk"):
            self.assertIn(t, types)
        risk = [r["event"] for r in rows if r["type"] == "risk"]
        self.assertEqual(risk, ["blocked", "approved"], "the other session's event is excluded")
        self.assertNotIn("ghp_abcdefghijklmnopqrstuvwxyz", text, "prompts are redacted")

    def test_any_edit_is_detected(self):
        lines = self.export().splitlines()
        edited = json.loads(lines[2])
        edited["status"] = "tampered"
        bad = "\n".join(lines[:2] + [json.dumps(edited)] + lines[3:])
        self.assertEqual(audit_export.verify(bad)["line"], 3)
        dropped = "\n".join(lines[:2] + lines[3:])
        self.assertIn("broken link", audit_export.verify(dropped)["error"])
        swapped = "\n".join([lines[0], lines[2], lines[1]] + lines[3:])
        self.assertFalse(audit_export.verify(swapped)["ok"])
        self.assertFalse(audit_export.verify("")["ok"])

    def test_cli_round_trip(self):
        out = os.path.join(self.project, "audit.jsonl")
        cli = os.path.join(REPO, "bin", "agent-spec-platform.py")
        env = dict(os.environ, AGENT_SPEC_DB=os.path.join(self.project, "none.db"))
        res = subprocess.run([sys.executable, cli, "audit", "--project", self.project, "--session", "conv-1",
                              "--out", out], capture_output=True, text=True, env=env)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(subprocess.run([sys.executable, cli, "audit", "--verify", out], capture_output=True).returncode, 0)
        with open(out) as fh:
            text = fh.read().replace('"status":"', '"status":"x', 1)
        with open(out, "w") as fh:
            fh.write(text)
        self.assertEqual(subprocess.run([sys.executable, cli, "audit", "--verify", out], capture_output=True).returncode, 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
