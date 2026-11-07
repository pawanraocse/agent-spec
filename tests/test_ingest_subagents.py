#!/usr/bin/env python3
"""Tests for subagent linking and the retention job (D-003, P2.5).

Cursor stores subagent transcripts as `<parent>/subagents/<child>.jsonl` and writes no Task
call into the parent, so linking is by order/time; Task tool_use blocks (when present) become
runs with parent_step_id set.

Run: python3 tests/test_ingest_subagents.py
"""
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ingest_support import IngestCase, ingest  # noqa: E402


def user(text, minute):
    return {"role": "user", "message": {"content": [
        {"type": "text", "text": "<timestamp>Thursday, Oct 29, 2026, 5:%02d PM (UTC+5:30)</timestamp>\n"
                                 "<user_query>\n%s\n</user_query>" % (minute, text)}]}}


def jsonl(*entries):
    return "".join(json.dumps(e) + "\n" for e in entries)


class SubagentIngestTest(IngestCase):
    def runs(self):
        conn = self.conn()
        try:
            return conn.execute("SELECT * FROM subagent_runs ORDER BY started, id").fetchall()
        finally:
            conn.close()

    def q(self, sql, *args):
        conn = self.conn()
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def test_task_step_links_to_discovered_child(self):
        self.transcript("parent", self.fixture("basic.jsonl"))
        self.transcript("child1", self.fixture("child.jsonl"), sub_of="parent")
        report = self.run_ingest("transcripts")["transcripts"]
        self.assertEqual(report["subagent_runs"], 1)
        (run,) = self.runs()
        self.assertEqual((run["agent"], run["model"], run["status"]), ("explore", "composer-2.5", "success"))
        step = self.q("SELECT kind, request_id FROM steps WHERE step_id = ?", run["parent_step_id"])[0]
        self.assertEqual(step["kind"], "subagent")
        self.assertEqual(run["parent_request_id"], step["request_id"])
        child = self.q("SELECT parent_request_id, prompt_redacted FROM requests WHERE request_id = ?",
                       run["child_request_id"])[0]
        self.assertEqual(child["parent_request_id"], step["request_id"])
        self.assertIn("Child task", child["prompt_redacted"])

    def test_task_without_child_keeps_null_child(self):
        self.transcript("parent", self.fixture("basic.jsonl"))
        self.run_ingest("transcripts")
        (run,) = self.runs()
        self.assertIsNone(run["child_request_id"])
        self.assertEqual(run["agent"], "explore")

    def test_child_without_task_step_attaches_by_time(self):
        parent = jsonl(user("early", 46), {"role": "assistant", "message": {"content": [{"type": "text", "text": "x"}]}},
                       user("late", 50))
        self.transcript("parent", parent)
        self.transcript("child1", jsonl(user("child", 47)), sub_of="parent")  # between the two prompts
        self.run_ingest("transcripts")
        (run,) = self.runs()
        parent_prompt = self.q("SELECT prompt_redacted FROM requests WHERE request_id = ?", run["parent_request_id"])[0][0]
        self.assertEqual(parent_prompt, "early")
        self.assertIsNone(run["parent_step_id"])
        self.assertEqual(run["agent"], "")

    def test_two_children_fill_task_runs_in_order(self):
        task = {"type": "tool_use", "name": "Task", "input": {"subagent_type": "explore"}}
        parent = jsonl(user("go", 46), {"role": "assistant", "message": {"content": [task, dict(task)]}})
        self.transcript("parent", parent)
        a = self.transcript("ca", jsonl(user("first child", 47)), sub_of="parent")
        b = self.transcript("cb", jsonl(user("second child", 48)), sub_of="parent")
        os.utime(a, (1000, 1000))
        os.utime(b, (2000, 2000))
        self.run_ingest("transcripts")
        prompts = [self.q("SELECT prompt_redacted FROM requests WHERE request_id = ?", r["child_request_id"])[0][0]
                   for r in sorted(self.runs(), key=lambda r: self.q(
                       "SELECT ordinal FROM steps WHERE step_id = ?", r["parent_step_id"])[0][0])]
        self.assertEqual(prompts, ["first child", "second child"])

    def test_child_error_is_recorded(self):
        self.transcript("parent", jsonl(user("go", 46)))
        child = jsonl(user("child", 47), {"type": "turn_ended", "status": "error", "error": "user_stopped_generation"})
        self.transcript("child1", child, sub_of="parent")
        self.run_ingest("transcripts")
        (run,) = self.runs()
        self.assertEqual((run["status"], run["error"]), ("error", "user_stopped_generation"))

    def test_idempotent_and_late_parent(self):
        self.transcript("child1", self.fixture("child.jsonl"), sub_of="parent")  # parent not written yet
        self.run_ingest("transcripts")
        self.assertEqual((self.count("requests"), self.count("subagent_runs")), (1, 0))
        self.transcript("parent", self.fixture("basic.jsonl"))
        self.run_ingest("transcripts")
        before = (self.count("requests"), self.count("steps"), self.count("subagent_runs"))
        self.assertEqual(before, (3, 9, 1))
        self.assertIsNotNone(self.runs()[0]["child_request_id"])
        self.run_ingest("transcripts")
        self.assertEqual((self.count("requests"), self.count("steps"), self.count("subagent_runs")), before)

    def test_rewritten_parent_relinks_without_duplicates(self):
        self.transcript("parent", self.fixture("basic.jsonl"))
        self.transcript("child1", self.fixture("child.jsonl"), sub_of="parent")
        self.run_ingest("transcripts")
        self.transcript("parent", self.fixture("basic.jsonl").replace("Second prompt", "Changed prompt"))
        self.run_ingest("transcripts")
        (run,) = self.runs()
        self.assertIsNotNone(run["child_request_id"])
        self.assertEqual(self.count("requests"), 3)

    def test_compact_drops_detail_but_keeps_totals_and_runs(self):
        self.transcript("parent", self.fixture("basic.jsonl"))
        self.transcript("child1", self.fixture("child.jsonl"), sub_of="parent")
        self.run_ingest("transcripts")
        conn = self.conn()
        totals = conn.execute("SELECT SUM(tokens_input), SUM(tokens_output) FROM requests").fetchone()
        recent = time.mktime((2026, 10, 30, 0, 0, 0, 0, 0, -1))
        self.assertEqual(ingest.compact(conn, days=7, now=recent), 0)  # nothing is a week old yet
        old = time.mktime((2026, 12, 30, 0, 0, 0, 0, 0, -1))
        self.assertEqual(ingest.compact(conn, days=7, now=old), 3)
        conn.commit()
        self.assertEqual(ingest.compact(conn, days=7, now=old), 0)  # already compacted
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM steps WHERE detail_json IS NOT NULL").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM requests WHERE prompt_redacted IS NOT NULL").fetchone()[0], 0)
        self.assertEqual(tuple(conn.execute("SELECT SUM(tokens_input), SUM(tokens_output) FROM requests").fetchone()), tuple(totals))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM steps").fetchone()[0], 9)
        runs = conn.execute("SELECT agent, compacted FROM subagent_runs").fetchall()
        self.assertEqual([(r[0], r[1]) for r in runs], [("explore", 1)])
        conn.close()
        # a compacted transcript is not re-expanded by a normal re-ingest
        self.run_ingest("transcripts")
        self.assertEqual(self.count("requests"), 3)


if __name__ == "__main__":
    unittest.main(verbosity=1)
