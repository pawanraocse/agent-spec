#!/usr/bin/env python3
"""Tests for D-010: savings calculator + session compare API (synthetic data only).

Run: python3 tests/test_savings.py
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _api_support import ApiCase  # noqa: E402

from aspec_platform import db  # noqa: E402


def add_reads(path):
    """R1: two whole-file reads (40000 B + 8000 B) and one graphify query; R2: one ranged read."""
    conn = db.open_ready(path)
    conn.executescript("""
    INSERT INTO steps (step_id, request_id, ordinal, kind, name, bytes_in, whole_file)
      VALUES ('W1', 'R1', 10, 'tool', 'Read', 40000, 1), ('W2', 'R1', 11, 'tool', 'Read', 8000, 1),
             ('W3', 'R2', 10, 'tool', 'Read', 900, 0);
    INSERT INTO steps (step_id, request_id, ordinal, kind, name, detail_json)
      VALUES ('G1', 'R1', 12, 'tool', 'Shell', '{"input": {"command": "./bin/graphify-cli.py context --task x"}}');
    UPDATE requests SET transcript_path = '%s' WHERE request_id = 'R1';
    UPDATE requests SET transcript_path = '%s' WHERE request_id = 'R2';
    """ % (path + ".a.jsonl", path + ".b.jsonl"))
    conn.commit()
    conn.close()


def write_transcript(path, text):
    rows = [{"role": "user", "message": {"content": [{"type": "text", "text": "<user_query>q</user_query>"}]}},
            {"role": "assistant", "message": {"content": [{"type": "text", "text": text}]}}]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(json.dumps(r) for r in rows) + "\n")


class SavingsTest(ApiCase):
    def setUp(self):
        super().setUp()
        add_reads(self.dbpath)
        write_transcript(self.dbpath + ".a.jsonl", "x" * 400)
        write_transcript(self.dbpath + ".b.jsonl", "y" * 4000)

    def test_savings_measures_whole_file_reads(self):
        data = self.get_json("/api/savings")
        self.assertEqual(data["measured"]["whole_file_reads"], 2)
        self.assertEqual(data["measured"]["whole_file_bytes"], 48000)
        self.assertEqual(data["measured"]["graph_queries"], 1)

    def test_savings_default_weights_and_math(self):
        data = self.get_json("/api/savings")
        w = data["weights"]
        self.assertEqual((w["bytes_per_token"], w["context_bytes"]), (4.0, 152.0))
        self.assertEqual(data["naive_tokens"], 12000)          # 48000 / 4
        self.assertEqual(data["graph_tokens"], 76)             # 2 reads * 152 B / 4
        self.assertEqual(data["saved_tokens"], 11924)
        expected = 11924 * w["resend_turns"] * w["price_per_mtok"] / 1e6
        self.assertAlmostEqual(data["saved_usd"], expected, places=6)

    def test_savings_weights_are_editable(self):
        data = self.get_json("/api/savings?bytes_per_token=2&context_bytes=100&price_per_mtok=10&resend_turns=5")
        self.assertEqual(data["naive_tokens"], 24000)
        self.assertEqual(data["graph_tokens"], 100)
        self.assertAlmostEqual(data["saved_usd"], (24000 - 100) * 5 * 10 / 1e6, places=6)

    def test_savings_rejects_bad_weights(self):
        for query in ("bytes_per_token=0", "bytes_per_token=abc", "price_per_mtok=-1", "resend_turns=99999"):
            status, _, body = self.request("/api/savings?" + query)
            self.assertEqual(status, 400, query)
            self.assertNotIn(b"Traceback", body)

    def test_savings_on_empty_db_is_zero(self):
        conn = db.open_ready(self.dbpath)
        conn.execute("DELETE FROM steps")
        conn.commit()
        conn.close()
        data = self.get_json("/api/savings")
        self.assertEqual((data["naive_tokens"], data["saved_tokens"], data["saved_usd"]), (0, 0, 0))

    def test_sessions_lists_transcript_backed_sessions_without_paths(self):
        data = self.get_json("/api/sessions")
        self.assertEqual([s["session_id"] for s in data["sessions"]], ["S1"])
        self.assertNotIn("transcript_path", json.dumps(data))

    def test_compare_runs_tokens_script_on_resolved_paths(self):
        # S1 holds R1 and R2 (two transcripts); make a second session so each side is one file.
        conn = db.open_ready(self.dbpath)
        conn.execute("UPDATE requests SET session_id = 'S2' WHERE request_id = 'R2'")
        conn.commit()
        conn.close()
        data = self.get_json("/api/compare?a=S1&b=S2")
        self.assertEqual((data["a"], data["b"]), ("S1", "S2"))
        self.assertGreater(len(data["text"].strip()), 0)

    def test_compare_unknown_session_is_404_and_never_takes_paths(self):
        for query in ("a=NOPE&b=S1", "a=/etc/passwd&b=S1", "a=S1", "a=..%2F..&b=S1"):
            status, _, body = self.request("/api/compare?" + query)
            self.assertIn(status, (400, 404), query)
            self.assertNotIn(b"Traceback", body)


if __name__ == "__main__":
    unittest.main()
