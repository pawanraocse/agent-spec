#!/usr/bin/env python3
"""O-002 / O-012: run directory layout, event schema, trace ids, ULIDs, redaction, compact.

Run: python3 tests/test_run_dir.py
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _run_helpers import Sandbox, EXAMPLE_WF, read_json, read_text  # noqa: E402

EVENT_KEYS = {"schema", "event_id", "ts", "run_id", "trace_id", "span_id", "parent_span_id", "source",
              "type", "actor", "step_id", "payload", "tokens", "cost_usd", "duration_ms"}


class RunDirTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()

    def tearDown(self):
        self.sb.cleanup()

    def test_start_creates_layout_and_envelope(self):
        code, out, _ = self.sb.run("start", "--workflow", "example", "--request", "hello",
                                   "--workflow-file", EXAMPLE_WF, "--budget-usd", "2.5")
        self.assertEqual(code, 0, out)
        rd = self.sb.run_dir(out["run_id"])
        self.assertTrue(os.path.isfile(os.path.join(rd, "run.json")))
        self.assertTrue(os.path.isfile(os.path.join(rd, "events.jsonl")))
        self.assertTrue(os.path.isdir(os.path.join(rd, "steps")))
        env = read_json(os.path.join(rd, "run.json"))
        for key in ("run_id", "trace_id", "workflow_id", "workflow_version", "workflow_sha", "request",
                    "status", "started"):
            self.assertIn(key, env)
        self.assertEqual(env["status"], "running")
        self.assertEqual(len(env["workflow_sha"]), 64)
        self.assertEqual(env["budgets"]["max_cost_usd"], 2.5)
        self.assertEqual([e["type"] for e in self.sb.events(out["run_id"])], ["run.received"])
        self.assertFalse([n for n in os.listdir(rd) if n.endswith(".tmp")])

    def test_events_follow_schema_and_carry_trace_ids(self):
        rid = self.sb.start()
        self.sb.run("step-start", rid, "a", "--agent", "agent-spec-search", "--model", "fast")
        self.sb.run("step-end", rid, "a", "--status", "success", "--output-json", '{"x": 1}',
                    "--tokens-in", "10", "--tokens-out", "5")
        self.sb.run("event", rid, "decision", "--payload-json", '{"choice": "go"}')
        events = self.sb.events(rid)
        self.assertEqual([e["type"] for e in events],
                         ["run.received", "step.started", "step.finished", "decision"])
        trace = read_json(os.path.join(self.sb.run_dir(rid), "run.json"))["trace_id"]
        for ev in events:
            self.assertEqual(set(ev), EVENT_KEYS)
            self.assertEqual(ev["schema"], 1)
            self.assertEqual(ev["source"], "ide")
            self.assertEqual(ev["run_id"], rid)
            self.assertEqual(ev["trace_id"], trace)
            self.assertTrue(ev["span_id"].startswith("s-"))
            self.assertTrue(ev["ts"].endswith("Z"))
        started, finished = events[1], events[2]
        self.assertEqual(started["span_id"], finished["span_id"])
        self.assertEqual(started["actor"]["agent"], "agent-spec-search")
        self.assertEqual(started["actor"]["model"], "fast")
        self.assertEqual(started["step_id"], "a")
        self.assertTrue(started["tokens"]["estimated"])
        self.assertEqual(finished["tokens"]["input"], 10)
        self.assertFalse(finished["tokens"]["estimated"])
        self.assertIsInstance(finished["duration_ms"], int)

    def test_ulids_are_sortable_in_event_order(self):
        rid = self.sb.start()
        for i in range(6):
            self.sb.run("event", rid, "decision", "--payload-json", json.dumps({"i": i}))
        ids = [e["event_id"] for e in self.sb.events(rid)]
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(ids, sorted(ids))
        for value in ids + [rid]:
            self.assertEqual(len(value), 26)

    def test_atomic_files_leave_no_tmp_and_output_written(self):
        rid = self.sb.start()
        self.sb.run("step-start", rid, "a")
        code, out, _ = self.sb.run("step-end", rid, "a", "--status", "success", "--output-json", '{"k": "v"}')
        self.assertEqual(code, 0, out)
        rd = self.sb.run_dir(rid)
        output = read_json(os.path.join(rd, "steps", "a", "output.json"))
        self.assertEqual(output["output"], {"k": "v"})
        checkpoint = read_json(os.path.join(rd, "checkpoint.json"))
        self.assertEqual(checkpoint["a"]["status"], "success")
        self.assertEqual(len(checkpoint["a"]["output_sha"]), 64)
        for base, _dirs, names in os.walk(rd):
            self.assertFalse([n for n in names if n.endswith(".tmp")], base)

    def test_secrets_are_redacted_in_request_and_payload(self):
        rid = self.sb.start(request="deploy with password=hunter2 and Bearer abc.def.ghi key AKIAABCDEFGHIJKLMNOP")
        self.sb.run("event", rid, "decision", "--payload-json",
                    '{"api_key": "zzz", "note": "token: s3cr3t-value", "ok": "fine"}')
        text = read_text(os.path.join(self.sb.run_dir(rid), "run.json"))
        text += read_text(os.path.join(self.sb.run_dir(rid), "events.jsonl"))
        for leaked in ("hunter2", "abc.def.ghi", "AKIAABCDEFGHIJKLMNOP", "zzz", "s3cr3t-value"):
            self.assertNotIn(leaked, text)
        self.assertIn("fine", text)

    def test_event_command_refuses_script_owned_and_unknown_types(self):
        rid = self.sb.start()
        self.assertEqual(self.sb.run("event", rid, "step.finished")[0], 2)
        self.assertEqual(self.sb.run("event", rid, "bogus")[0], 2)
        self.assertEqual(self.sb.run("event", rid, "decision", "--payload-json", "{not json")[0], 2)

    def test_list_and_compact(self):
        rid = self.sb.start()
        self.sb.run("step-start", rid, "a")
        self.sb.run("step-end", rid, "a", "--status", "success", "--output-json", "{}")
        self.sb.run("finish", rid)
        code, out, _ = self.sb.run("list")
        self.assertEqual(code, 0)
        self.assertEqual(out["runs"][0]["run_id"], rid)
        code, out, _ = self.sb.run("compact", "--days", "0")
        self.assertEqual(code, 0, out)
        rd = self.sb.run_dir(rid)
        self.assertTrue(os.path.isfile(os.path.join(rd, "run.json")))
        self.assertTrue(os.path.isfile(os.path.join(rd, "result.json")))
        self.assertFalse(os.path.exists(os.path.join(rd, "steps")))
        self.assertFalse(os.path.exists(os.path.join(rd, "events.jsonl")))

    def test_compact_keeps_unfinished_runs_and_recent_runs(self):
        rid = self.sb.start()
        code, out, _ = self.sb.run("compact", "--days", "0")
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.sb.run_dir(rid), "events.jsonl")))
        done = self.sb.start()
        self.sb.run("finish", done)
        self.sb.run("compact", "--days", "7")
        self.assertTrue(os.path.isfile(os.path.join(self.sb.run_dir(done), "events.jsonl")))

    def test_usage_errors_exit_2(self):
        self.assertEqual(self.sb.run()[0], 2)
        self.assertEqual(self.sb.run("start", "--workflow", "t")[0], 2)

    def test_error_sanitization_and_cap(self):
        rid = self.sb.start()
        self.sb.run("step-start", rid, "a", "--agent", "generalPurpose")
        giant_error = (
            "<html><body><h1>500 Internal Error</h1>"
            + "Traceback (most recent call last):\n"
            + "  File 'server.py', line 42, in handle\n"
            + "    secret_key = 'sk-ant-api03-abcdef1234567890abcdef12'\n"
            + ("  File 'lib.py', line 10, in run\n    do_something()\n" * 150)
            + "ZeroDivisionError: division by zero"
            + "</body></html>"
        )
        code, out, _ = self.sb.run("step-end", rid, "a", "--status", "failed", "--error", giant_error)
        self.assertEqual(code, 0, out)
        step_out = read_json(os.path.join(self.sb.run_dir(rid), "steps", "a", "output.json"))
        err = step_out["error"]
        self.assertIsNotNone(err)
        self.assertLessEqual(len(err), 1000)
        self.assertNotIn("<html>", err)
        self.assertNotIn("<body>", err)
        self.assertNotIn("<h1>", err)
        self.assertNotIn("sk-ant-api03", err)
        self.assertIn("[truncated", err)
        self.assertIn("Traceback", err)
        self.assertIn("ZeroDivisionError: division by zero", err)

        # Check events.jsonl also recorded the sanitized error
        finished_ev = [e for e in self.sb.events(rid) if e["type"] == "step.finished"][0]
        self.assertEqual(finished_ev["payload"]["error"], err)



if __name__ == "__main__":
    unittest.main(verbosity=1)
