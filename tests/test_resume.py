#!/usr/bin/env python3
"""O-002.1 / §5: crash recovery, drift refusal, idempotent reuse, needs ordering.

Run: python3 tests/test_resume.py
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _run_helpers import Sandbox, workflow_text, read_json, read_text  # noqa: E402


class ResumeTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.sb.write_workflow(workflow_text(steps=[("a", []), ("b", []), ("c", ["a", "b"])]))

    def tearDown(self):
        self.sb.cleanup()

    def finish_step(self, rid, step, out='{"v": 1}'):
        self.assertEqual(self.sb.run("step-start", rid, step)[0], 0)
        self.assertEqual(self.sb.run("step-end", rid, step, "--status", "success", "--output-json", out)[0], 0)

    def test_crash_reruns_running_step_but_not_finished_one(self):
        rid = self.sb.start()
        self.finish_step(rid, "b")
        self.sb.run("step-start", rid, "a")  # crash: no step-end for a
        code, plan, _ = self.sb.run("resume", rid)
        self.assertEqual(code, 0, plan)
        self.assertEqual(plan["finished"], ["b"])
        self.assertEqual(plan["rerun"], ["a"])
        self.assertEqual(plan["pending"], ["c"])
        self.assertEqual(plan["ready"], ["a"])
        # a is re-run (not reused) and attempts are counted
        code, out, _ = self.sb.run("step-start", rid, "a")
        self.assertEqual(code, 0)
        self.assertFalse(out["reuse"])
        self.assertEqual(out["attempt"], 2)
        # finished b is reused, never re-run
        code, out, _ = self.sb.run("step-start", rid, "b")
        self.assertEqual(code, 0)
        self.assertTrue(out["reuse"])
        self.assertTrue(os.path.isfile(out["output"]))

    def test_idempotent_reuse_depends_on_key_inputs(self):
        rid = self.sb.start()
        self.assertEqual(self.sb.run("step-start", rid, "a", "--inputs-json", '{"q": 1}')[0], 0)
        self.sb.run("step-end", rid, "a", "--status", "success", "--output-json", '{"v": 1}')
        _, same, _ = self.sb.run("step-start", rid, "a", "--inputs-json", '{"q": 1}')
        self.assertTrue(same["reuse"])
        _, other, _ = self.sb.run("step-start", rid, "a", "--inputs-json", '{"q": 2}')
        self.assertFalse(other["reuse"])
        self.assertNotEqual(same["key"], other["key"])

    def test_key_changes_when_upstream_output_changes(self):
        r1, r2 = self.sb.start(), self.sb.start()
        self.finish_step(r1, "a", '{"v": 1}')
        self.finish_step(r1, "b")
        self.finish_step(r2, "a", '{"v": 2}')
        self.finish_step(r2, "b")
        k1 = self.sb.run("step-start", r1, "c", "--needs", "a,b")[1]["key"]
        k2 = self.sb.run("step-start", r2, "c", "--needs", "a,b")[1]["key"]
        self.assertNotEqual(k1, k2)

    def test_step_start_refuses_when_needs_not_finished(self):
        rid = self.sb.start()
        code, out, err = self.sb.run("step-start", rid, "c", "--needs", "a,b")
        self.assertEqual(code, 3)
        self.assertIn("a", out["error"])
        self.sb.run("step-start", rid, "a")  # running is not finished
        self.assertEqual(self.sb.run("step-start", rid, "c", "--needs", "a")[0], 3)
        self.finish_step(rid, "a")
        # the workflow plan also requires b, whatever --needs says
        self.assertEqual(self.sb.run("step-start", rid, "c", "--needs", "a")[0], 3)
        self.finish_step(rid, "b")
        self.assertEqual(self.sb.run("step-start", rid, "c", "--needs", "a")[0], 0)

    def test_drift_refused_unless_accepted(self):
        rid = self.sb.start()
        self.finish_step(rid, "a")
        self.sb.write_workflow(workflow_text(steps=[("a", []), ("b", []), ("c", ["a", "b"])],
                                             extra="\nedited\n"))
        code, out, err = self.sb.run("resume", rid)
        self.assertEqual(code, 3)
        self.assertIn("workflow_sha", out["error"])
        self.assertIn("--accept-drift", out["error"])
        code, plan, _ = self.sb.run("resume", rid, "--accept-drift")
        self.assertEqual(code, 0, plan)
        self.assertEqual(plan["finished"], ["a"])
        self.assertTrue(plan["drift_accepted"])
        drift_events = [e for e in self.sb.events(rid) if e["type"] == "decision"]
        self.assertEqual(len(drift_events), 1)

    def test_resume_refuses_finished_run_and_unknown_run(self):
        rid = self.sb.start()
        self.sb.run("finish", rid, "--force")
        self.assertEqual(self.sb.run("resume", rid)[0], 3)
        self.assertEqual(self.sb.run("resume", "01NOSUCHRUN")[0], 3)

    def test_unknown_step_refused_and_failed_dependency_blocks(self):
        rid = self.sb.start()
        self.assertEqual(self.sb.run("step-start", rid, "zzz")[0], 3)
        self.sb.run("step-start", rid, "a")
        self.sb.run("step-end", rid, "a", "--status", "failed", "--error", "boom")
        self.assertEqual(self.sb.run("step-start", rid, "c", "--needs", "a")[0], 3)
        checkpoint = read_json(os.path.join(self.sb.run_dir(rid), "checkpoint.json"))
        self.assertEqual(checkpoint["a"]["error"], "boom")


if __name__ == "__main__":
    unittest.main(verbosity=1)
