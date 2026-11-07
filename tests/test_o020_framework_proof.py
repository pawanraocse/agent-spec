#!/usr/bin/env python3
"""O-020 framework proof (automated): example workflow -> run dir -> ingest -> dashboard read model.

Proves Step 1 (run plumbing) and Step 3 (reference workflow) without a live Cursor hub-runner chat.
Live Cursor still owed for O-003…O-018 hub-runner behaviour; this test is the regression gate.

Run: python3 tests/test_o020_framework_proof.py
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _api_support import ApiCase  # noqa: E402
from _ingest_support import REPO_DIR  # noqa: E402,F401
from _run_helpers import EXAMPLE_WF, RUN_PY, Sandbox, read_json  # noqa: E402
from aspec_platform import db, ingest, insights  # noqa: E402


class O020ProofTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.tmp = tempfile.mkdtemp()
        self._old = os.environ.get("AGENT_SPEC_DB")
        os.environ["AGENT_SPEC_DB"] = os.path.join(self.tmp, "platform.db")
        self.addCleanup(self.cleanup)

    def cleanup(self):
        if self._old is None:
            os.environ.pop("AGENT_SPEC_DB", None)
        else:
            os.environ["AGENT_SPEC_DB"] = self._old
        self.sb.cleanup()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_example_workflow_engine_ingest_and_dashboard(self):
        code, out, err = self.sb.run("validate", EXAMPLE_WF)
        self.assertEqual(code, 0, err)
        self.assertTrue(out.get("ok"), out)

        code, out, err = self.sb.run(
            "start", "--workflow", "example", "--request",
            "framework proof: locate agent-spec-run.py", "--workflow-file", EXAMPLE_WF)
        self.assertEqual(code, 0, err)
        rid = out["run_id"]
        trace = read_json(os.path.join(self.sb.run_dir(rid), "run.json"))["trace_id"]
        steps = [
            ("gather", "agent-spec-search", '{"files":[{"path":"bin/agent-spec-run.py","why":"plumbing"}]}'),
            ("analyze", "generalPurpose", '{"findings":[],"confidence":"HIGH"}'),
            ("summarize", "generalPurpose", '{"summary":"ok","citations":["bin/agent-spec-run.py:1"]}'),
        ]
        for sid, agent, payload in steps:
            ready = self.sb.run("status", rid)[1]["ready"]
            self.assertIn(sid, ready, ready)
            self.sb.run("step-start", rid, sid, "--agent", agent)
            code, _, err = self.sb.run(
                "step-end", rid, sid, "--status", "success", "--output-json", payload,
                "--tokens-in", "40", "--tokens-out", "20")
            self.assertEqual(code, 0, err)

        code, finish, err = self.sb.run("finish", rid)
        self.assertEqual(code, 0, err)
        self.assertEqual(finish["status"], "success")
        result = read_json(os.path.join(self.sb.run_dir(rid), "result.json"))
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["workflow_id"], "example")
        for ev in self.sb.events(rid):
            self.assertEqual(ev["trace_id"], trace)

        report = ingest.run(self.sb.root, ["runs"])["runs"]
        self.assertEqual(report["errors"], 0, report)

        conn = db.connect(os.environ["AGENT_SPEC_DB"], readonly=True)
        try:
            detail = insights.run_detail(conn, rid)
            self.assertIsNotNone(detail)
            self.assertEqual([s["name"] for s in detail["steps"]], ["gather", "analyze", "summarize"])
            self.assertEqual(detail["run"]["status"], "success")
            self.assertEqual(detail["run"]["workflow_id"], "example")
            self.assertGreaterEqual(len(detail["events"]), 3)
            self.assertEqual(detail["waterfall"][-1]["name"], "summarize")
        finally:
            conn.close()


class O020ApiSmokeTest(ApiCase):
    """After ingest, the stdlib dashboard API serves the same run (transparency path)."""

    def _run_cli(self, *args):
        import subprocess
        proc = subprocess.run(
            [sys.executable, RUN_PY] + [str(a) for a in args], cwd=self.project,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        out = json.loads(proc.stdout) if proc.stdout.strip() else None
        return proc.returncode, out, proc.stderr

    def test_run_detail_endpoint_matches_ingested_workflow(self):
        code, out, err = self._run_cli(
            "start", "--workflow", "example", "--request", "api smoke",
            "--workflow-file", EXAMPLE_WF)
        self.assertEqual(code, 0, err)
        rid = out["run_id"]
        for sid in ("gather", "analyze", "summarize"):
            self._run_cli("step-start", rid, sid)
            self._run_cli("step-end", rid, sid, "--status", "success", "--output-json", "{}")
        self._run_cli("finish", rid)
        ingest.run(self.project, ["runs"])

        data = self.get_json("/api/runs/%s" % rid)
        self.assertEqual(data["run"]["request_id"], rid)
        self.assertEqual(len(data["steps"]), 3)
        self.assertIn("waterfall", data)


if __name__ == "__main__":
    unittest.main(verbosity=1)
