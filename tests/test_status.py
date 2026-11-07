#!/usr/bin/env python3
"""O-017: final status derivation (success | partial | failed) and result.json merge.

Run: python3 tests/test_status.py
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _run_helpers import Sandbox, workflow_text, read_json, read_text  # noqa: E402

S, F, K, N = "success", "failed", "skipped", None  # N = never finished

MATRIX = [
    ((S, S, S), "success"),
    ((S, F, S), "partial"),
    ((S, K, K), "partial"),
    ((S, S, N), "partial"),
    ((F, F, F), "failed"),
    ((K, K, K), "failed"),
    ((F, K, N), "failed"),
    ((N, N, N), "failed"),
    ((S, F, F), "partial"),
]


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.sb.write_workflow(workflow_text(steps=[("a", []), ("b", []), ("c", [])]))

    def tearDown(self):
        self.sb.cleanup()

    def test_matrix(self):
        for outcomes, expected in MATRIX:
            rid = self.sb.start()
            for step, outcome in zip("abc", outcomes):
                if outcome is None:
                    continue
                self.sb.run("step-start", rid, step)
                self.assertEqual(self.sb.run("step-end", rid, step, "--status", outcome,
                                             "--output-json", '{"s": "%s"}' % step)[0], 0)
            code, out, _ = self.sb.run("finish", rid)
            self.assertEqual(code, 0, (outcomes, out))
            self.assertEqual(out["status"], expected, outcomes)
            result = read_json(os.path.join(self.sb.run_dir(rid), "result.json"))
            self.assertEqual(result["status"], expected)
            run = read_json(os.path.join(self.sb.run_dir(rid), "run.json"))
            self.assertEqual(run["status"], expected)
            self.assertIn("finished", run)

    def test_status_command_shows_running_then_final(self):
        rid = self.sb.start()
        _, out, _ = self.sb.run("status", rid)
        self.assertEqual(out["status"], "running")
        self.assertEqual(out["steps"]["a"]["status"], "pending")
        self.sb.run("step-start", rid, "a")
        self.assertEqual(self.sb.run("status", rid)[1]["steps"]["a"]["status"], "running")
        self.sb.run("step-end", rid, "a", "--status", "success", "--output-json", "{}",
                    "--tokens-in", "7", "--tokens-out", "3", "--cost-usd", "0.5")
        _, out, _ = self.sb.run("status", rid)
        self.assertEqual(out["counts"]["success"], 1)
        self.assertEqual(out["counts"]["pending"], 2)
        self.assertEqual(out["tokens"], {"input": 7, "output": 3})
        self.assertEqual(out["cost_usd"], 0.5)
        self.sb.run("finish", rid)
        self.assertEqual(self.sb.run("status", rid)[1]["status"], "partial")

    def test_finish_refuses_running_step_unless_forced(self):
        rid = self.sb.start()
        self.sb.run("step-start", rid, "a")
        self.assertEqual(self.sb.run("finish", rid)[0], 3)
        code, out, _ = self.sb.run("finish", rid, "--force")
        self.assertEqual(code, 0)
        self.assertEqual(out["status"], "failed")

    def test_result_merges_outputs_and_blocks_further_steps(self):
        rid = self.sb.start()
        self.sb.run("step-start", rid, "a")
        self.sb.run("step-end", rid, "a", "--status", "success", "--output-json", '{"found": 3}')
        self.sb.run("finish", rid)
        result = read_json(os.path.join(self.sb.run_dir(rid), "result.json"))
        self.assertEqual(result["steps"]["a"]["output"], {"found": 3})
        self.assertEqual(result["steps"]["b"]["status"], "pending")
        self.assertEqual(self.sb.run("step-start", rid, "b")[0], 3)

    def test_budget_exceeded_is_reported_and_evented(self):
        rid = self.sb.start("req", None, "--budget-usd", "1")
        self.sb.run("step-start", rid, "a")
        code, out, _ = self.sb.run("step-end", rid, "a", "--status", "success", "--output-json", "{}",
                                   "--cost-usd", "1.5")
        self.assertEqual(code, 0)
        self.assertTrue(out["budget_exceeded"])
        self.assertIn("budget.exceeded", [e["type"] for e in self.sb.events(rid)])


if __name__ == "__main__":
    unittest.main(verbosity=1)
