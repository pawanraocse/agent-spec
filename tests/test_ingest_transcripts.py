#!/usr/bin/env python3
"""Tests for `ingest transcripts` (D-002, P2.4): requests/steps, idempotency, redaction, privacy.

Run: python3 tests/test_ingest_transcripts.py
"""
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ingest_support import IngestCase, ingest  # noqa: E402


class TranscriptIngestTest(IngestCase):
    def setUp(self):
        super().setUp()
        self.write("big.txt", "x" * 25000)
        self.write("skills/demo/SKILL.md", "# demo\n")
        self.path = self.transcript("sess-1", self.fixture("basic.jsonl"))

    def rows(self, sql, *args):
        conn = self.conn()
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def test_requests_and_steps_from_fixture(self):
        report = self.run_ingest("transcripts")["transcripts"]
        self.assertEqual((report["requests"], report["steps"]), (2, 7))  # thinking block not counted
        self.assertEqual(report["errors"], 1)   # the malformed line
        self.assertEqual(report["skipped"], 1)  # the role-less status line
        first, second = self.rows("SELECT * FROM requests ORDER BY ordinal")
        self.assertEqual((first["ordinal"], second["ordinal"]), (0, 1))
        self.assertEqual((first["status"], second["status"]), ("success", "error"))
        self.assertEqual(first["session_id"], "sess-1")
        self.assertEqual(first["started"], "2026-10-29T12:16:00.000Z")  # 5:46 PM at UTC+5:30
        self.assertEqual(first["tokens_estimated"], 1)
        self.assertGreater(first["tokens_input"], 0)
        self.assertGreater(first["tokens_output"], 0)
        self.assertEqual(second["prompt_redacted"], "Second prompt")
        kinds = [(r["kind"], r["name"]) for r in
                 self.rows("SELECT kind, name FROM steps WHERE request_id = ? ORDER BY ordinal", first["request_id"])]
        self.assertEqual(kinds, [("message", "assistant"), ("skill", "demo"), ("tool", "Read"), ("tool", "Read"),
                                 ("tool", "Shell"), ("subagent", "explore")])

    def test_whole_file_reads_use_size_and_range_keys(self):
        self.run_ingest("transcripts")
        reads = self.rows("SELECT bytes_in, whole_file FROM steps WHERE name = 'Read' ORDER BY ordinal")
        self.assertEqual([(r[0], r[1]) for r in reads], [(25000, 1), (0, 0)])  # whole read, ranged read
        skill = self.rows("SELECT whole_file FROM steps WHERE kind = 'skill'")[0]
        self.assertEqual(skill[0], 0)  # small file

    def test_thinking_is_dropped_everywhere(self):
        self.run_ingest("transcripts")
        self.assertNotIn("SYNTHETIC-PRIVATE-REASONING-SENTINEL", self.dump())
        self.assertNotIn("thinking", self.dump().lower().replace("thinking blocks", ""))

    def test_secrets_are_redacted_in_stored_prompts_and_tool_input(self):
        self.run_ingest("transcripts")
        dump = self.dump()
        for secret in ("hunter22xyz", "abc123.def456-ghi", "sk_live_abcdef123456"):
            self.assertNotIn(secret, dump)
        prompt = self.rows("SELECT prompt_redacted FROM requests ORDER BY ordinal")[0][0]
        self.assertIn("Fix the login", prompt)
        self.assertIn("«redacted:", prompt)

    def test_prompt_is_truncated_to_2000_chars(self):
        long = {"role": "user", "message": {"content": [{"type": "text", "text": "a b " * 2000}]}}
        self.transcript("sess-long", json.dumps(long) + "\n")
        self.run_ingest("transcripts")
        sizes = [len(r[0]) for r in self.rows("SELECT prompt_redacted FROM requests WHERE session_id = 'sess-long'")]
        self.assertEqual(sizes, [2001])  # 2000 chars + the ellipsis marker

    def test_second_run_is_identical(self):
        self.run_ingest("transcripts")
        before = {t: self.count(t) for t in ("requests", "steps", "subagent_runs")}
        second = self.run_ingest("transcripts")["transcripts"]
        self.assertEqual({t: self.count(t) for t in before}, before)
        self.assertEqual((second["requests"], second["steps"], second["unchanged"]), (0, 0, 1))

    def test_append_continues_from_offset(self):
        self.run_ingest("transcripts")
        steps_before = self.count("steps")
        extra = [{"role": "assistant", "message": {"content": [{"type": "text", "text": "late reply"}]}},
                 {"role": "user", "message": {"content": [{"type": "text", "text": "third prompt"}]}},
                 {"role": "assistant", "message": {"content": [{"type": "tool_use", "name": "Glob",
                                                                "input": {"glob_pattern": "*.py"}}]}}]
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(e) + "\n" for e in extra))
        report = self.run_ingest("transcripts")["transcripts"]
        self.assertEqual((report["requests"], report["steps"], report["rewritten"]), (1, 2, 0))
        self.assertEqual(self.count("requests"), 3)
        self.assertEqual(self.count("steps"), steps_before + 2)
        # the late assistant line joined the previous (second) request, with the next ordinal
        late = self.rows("SELECT r.ordinal AS ro, s.ordinal AS so FROM steps s JOIN requests r USING (request_id) "
                         "WHERE s.name = 'assistant' AND s.detail_json LIKE '%late reply%'")[0]
        self.assertEqual((late["ro"], late["so"]), (1, 1))
        self.assertEqual(self.run_ingest("transcripts")["transcripts"]["steps"], 0)

    def test_partial_last_line_waits_until_complete(self):
        text = json.dumps({"role": "user", "message": {"content": [{"type": "text", "text": "one"}]}}) + "\n"
        part = json.dumps({"role": "user", "message": {"content": [{"type": "text", "text": "two"}]}})
        path = self.transcript("sess-partial", text + part[:20])
        self.run_ingest("transcripts")
        self.assertEqual(self.count("requests"), 3)  # basic(2) + "one"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(part[20:] + "\n")
        self.run_ingest("transcripts")
        self.assertEqual(self.count("requests"), 4)
        self.run_ingest("transcripts")
        self.assertEqual(self.count("requests"), 4)

    def test_rewritten_file_is_reingested_from_zero(self):
        self.run_ingest("transcripts")
        rewritten = json.dumps({"role": "user", "message": {"content": [{"type": "text", "text": "brand new"}]}}) + "\n"
        self.transcript("sess-1", rewritten)
        report = self.run_ingest("transcripts")["transcripts"]
        self.assertEqual((report["rewritten"], report["requests"]), (1, 1))
        rows = self.rows("SELECT request_id, prompt_redacted FROM requests")
        self.assertEqual([r[1] for r in rows], ["brand new"])
        self.assertEqual(self.count("steps"), 0)  # old steps cascaded away

    def test_truncated_file_is_reingested(self):
        self.run_ingest("transcripts")
        first_line = self.fixture("basic.jsonl").splitlines(True)[0]
        self.transcript("sess-1", first_line)
        self.assertEqual(self.run_ingest("transcripts")["transcripts"]["rewritten"], 1)
        self.assertEqual(self.count("requests"), 1)

    def test_rebuild_recreates_the_database(self):
        self.run_ingest("transcripts")
        counts = (self.count("requests"), self.count("steps"))
        self.run_ingest("transcripts", rebuild=True)
        self.assertEqual((self.count("requests"), self.count("steps")), counts)

    def test_flat_layout_and_missing_root_and_garbage_are_tolerated(self):
        with open(os.path.join(self.root, "flat-1.jsonl"), "w", encoding="utf-8") as fh:
            fh.write('[1, 2]\n\n"just a string"\n{"role": "user", "message": null}\n')
        self.run_ingest("transcripts")
        self.assertEqual(self.count("requests"), 3)  # basic(2) + the null-message user line
        os.environ["AGENT_SPEC_TRANSCRIPT_ROOT"] = os.path.join(self.tmp, "nowhere")
        report = self.run_ingest("transcripts")["transcripts"]
        self.assertEqual((report["requests"], report["errors"]), (0, 0))

    def test_default_root_uses_cursor_slug_rule(self):
        os.environ.pop("AGENT_SPEC_TRANSCRIPT_ROOT")
        root = ingest.transcript_root("/Users/a.b/dev/my.proj")
        self.assertTrue(root.endswith(os.path.join(".cursor", "projects", "Users-a-b-dev-my-proj", "agent-transcripts")))

    def test_performance_1000_lines_under_two_seconds(self):
        lines = []
        for i in range(250):
            lines.append({"role": "user", "message": {"content": [{"type": "text", "text": "prompt %d token=abc%d" % (i, i)}]}})
            lines.append({"role": "assistant", "message": {"content": [
                {"type": "thinking", "thinking": "hmm"}, {"type": "text", "text": "ok " * 30},
                {"type": "tool_use", "name": "Grep", "input": {"pattern": "p%d" % i, "path": "/x"}}]}})
            lines.append({"role": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"path": "big.txt", "limit": 10}}]}})
            lines.append({"type": "turn_ended", "status": "success"})
        self.transcript("sess-perf", "".join(json.dumps(x) + "\n" for x in lines))
        self.assertEqual(len(lines), 1000)
        start = time.time()
        report = self.run_ingest("transcripts")["transcripts"]
        elapsed = time.time() - start
        print("perf: 1000-line transcript ingested in %.3fs" % elapsed)
        self.assertEqual(report["requests"], 252)
        self.assertLess(elapsed, 2.0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
