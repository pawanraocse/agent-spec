#!/usr/bin/env python3
"""P4-013: step-end checks a successful step's output against its typed handoff schema.
P4-015: step-start hands a typed step only its handoff input, and records the saving.

Run: python3 tests/test_handoff_step.py
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _run_helpers import Sandbox, read_json  # noqa: E402

GOOD = {"files_changed": ["a.py"], "tests": {"command": "pytest", "verdict": "PASS"}, "summary": "done"}


class HandoffStepTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.rid = self.sb.start()

    def tearDown(self):
        self.sb.cleanup()

    def end(self, output, skill="agent-spec-implement"):
        args = ["step-start", self.rid, "a"] + (["--skill", skill] if skill else [])
        self.assertEqual(self.sb.run(*args)[0], 0)
        return self.sb.run("step-end", self.rid, "a", "--status", "success", "--output-json", json.dumps(output))

    def test_matching_output_succeeds(self):
        code, out, _ = self.end(GOOD)
        self.assertEqual(code, 0)
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], "success")

    def test_mismatch_fails_step_with_actionable_error(self):
        code, out, _ = self.end({"summary": "done"})
        self.assertEqual(code, 4)
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], "failed")
        self.assertIn("handoff schema agent-spec-implement", out["error"])
        self.assertIn("files_changed", out["error"])
        self.assertIn("agents/handoffs/agent-spec-implement.json", out["error"])
        saved = read_json(os.path.join(self.sb.run_dir(self.rid), "steps", "a", "output.json"))
        self.assertEqual(saved["status"], "failed")
        finished = [e for e in self.sb.events(self.rid) if e.get("type") == "step.finished"]
        self.assertEqual(finished[-1]["payload"]["status"], "failed")

    def test_wrong_enum_value_fails(self):
        bad = dict(GOOD, tests={"command": "pytest", "verdict": "GREEN"})
        code, out, _ = self.end(bad)
        self.assertEqual(code, 4)
        self.assertIn("verdict", out["error"])

    def test_untyped_step_is_not_checked(self):
        code, out, _ = self.end({"anything": 1}, skill=None)
        self.assertEqual(code, 0)
        self.assertTrue(out["ok"])

    def test_failed_status_is_not_checked(self):
        self.assertEqual(self.sb.run("step-start", self.rid, "a", "--skill", "agent-spec-implement")[0], 0)
        code, out, _ = self.sb.run("step-end", self.rid, "a", "--status", "failed", "--error", "boom")
        self.assertEqual(code, 0)
        self.assertTrue(out["ok"])


class ContextPruningTest(unittest.TestCase):
    """P4-015. Workflow a -> b; b runs as agent-spec-search (input: question, scope)."""

    def setUp(self):
        self.sb = Sandbox()
        self.rid = self.sb.start()

    def tearDown(self):
        self.sb.cleanup()

    def upstream(self, output):
        self.assertEqual(self.sb.run("step-start", self.rid, "a")[0], 0)
        self.assertEqual(self.sb.run("step-end", self.rid, "a", "--status", "success",
                                     "--output-json", json.dumps(output))[0], 0)

    def start_b(self, *extra):
        code, out, err = self.sb.run("step-start", self.rid, "b", *extra)
        self.assertEqual(code, 0, err)
        return out

    def test_typed_step_gets_only_its_input_fields(self):
        self.upstream({"question": "who calls emit?", "scope": "bin/", "notes": "x" * 4000})
        out = self.start_b("--agent", "agent-spec-search")
        self.assertEqual(out["context"], {"question": "who calls emit?", "scope": "bin/"})
        stats = out["context_stats"]
        self.assertTrue(stats["pruned"])
        self.assertEqual(stats["schema"], "agent-spec-search")
        self.assertGreater(stats["passthrough_bytes"], 4000)
        self.assertLess(stats["context_bytes"], 100)
        started = [e for e in self.sb.events(self.rid) if e["type"] == "step.started" and e["step_id"] == "b"]
        self.assertEqual(started[-1]["payload"]["context"], stats)

    def test_explicit_inputs_win_over_upstream(self):
        self.upstream({"question": "old", "scope": "bin/"})
        out = self.start_b("--agent", "agent-spec-search", "--inputs-json", '{"question": "new", "extra": 1}')
        self.assertEqual(out["context"], {"question": "new", "scope": "bin/"})

    def test_missing_required_field_falls_back_to_passthrough(self):
        self.upstream({"notes": "no question here"})
        out = self.start_b("--agent", "agent-spec-search")
        stats = out["context_stats"]
        self.assertFalse(stats["pruned"])
        self.assertIn("question", stats["reason"])
        self.assertEqual(stats["context_bytes"], stats["passthrough_bytes"])
        self.assertEqual(out["context"]["upstream"]["a"], {"notes": "no question here"})

    def test_untyped_step_has_no_context(self):
        self.upstream({"question": "q"})
        out = self.start_b("--agent", "generalPurpose")
        self.assertNotIn("context", out)

    def test_run_detail_reports_the_saving(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin"))
        import tempfile
        from aspec_platform import db, ingest, insights
        self.upstream({"question": "who calls emit?", "notes": "x" * 2000})
        self.start_b("--agent", "agent-spec-search")
        self.sb.run("step-end", self.rid, "b", "--status", "success", "--output-json",
                    json.dumps({"answer": "bin/agent-spec-run.py:410", "files": []}))
        path = os.path.join(tempfile.mkdtemp(dir=self.sb.root), "platform.db")
        old = os.environ.get("AGENT_SPEC_DB")
        os.environ["AGENT_SPEC_DB"] = path
        try:
            ingest.run(self.sb.root, ["runs"])
            conn = db.connect(path)
            try:
                detail = insights.run_detail(conn, self.rid)
            finally:
                conn.close()
        finally:
            if old is None:
                os.environ.pop("AGENT_SPEC_DB", None)
            else:
                os.environ["AGENT_SPEC_DB"] = old
        step_b = [s for s in detail["steps"] if s["name"] == "b"][0]
        self.assertTrue(step_b["context"]["pruned"])
        self.assertEqual(detail["context"]["steps"], 1)
        self.assertLess(detail["context"]["context_bytes"], detail["context"]["passthrough_bytes"])


if __name__ == "__main__":
    unittest.main()
