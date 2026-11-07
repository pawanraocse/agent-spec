#!/usr/bin/env python3
"""Tests for `ingest memory` (D-005, P2.8): fact files and receipts -> memory_facts / meta.

Run: python3 tests/test_ingest_memory.py
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ingest_support import IngestCase  # noqa: E402

V1 = "---\nid: 20261028-alpha-aaaaaa\ntype: decision\nsubject: alpha\ncreated: 2026-10-28\nsource: x\n---\nBody of alpha.\n"
V2 = ("---\nid: 20261029-beta-bbbbbb\ntype: constraint\nsubject: beta\ncreated: 2026-10-29\n"
      "confidence: high\nstatus: stale\nexpires: 2027-01-01\n---\nBody of beta.\n")


class MemoryIngestTest(IngestCase):
    def facts(self):
        conn = self.conn()
        try:
            return {r["fact_id"]: r for r in conn.execute("SELECT * FROM memory_facts")}
        finally:
            conn.close()

    def test_local_facts_with_and_without_v2_fields(self):
        self.write(".agent-spec/memory/facts/a.md", V1)
        self.write(".agent-spec/memory/facts/b.md", V2)
        report = self.run_ingest("memory")["memory"]
        self.assertEqual((report["facts"], report["added"], report["errors"]), (2, 2, 0))
        facts = self.facts()
        alpha, beta = facts["20261028-alpha-aaaaaa"], facts["20261029-beta-bbbbbb"]
        self.assertEqual((alpha["type"], alpha["subject"], alpha["scope"], alpha["status"]),
                         ("decision", "alpha", "local", "active"))
        self.assertIsNone(alpha["confidence"])
        self.assertIsNone(alpha["expires"])
        self.assertEqual(alpha["bytes"], len(V1.encode()))
        self.assertEqual((beta["confidence"], beta["status"], beta["expires"]), ("high", "stale", "2027-01-01"))
        self.assertEqual(beta["updated"], "2026-10-29")
        self.assertEqual(alpha["source_path"], os.path.join(".agent-spec", "memory", "facts", "a.md"))

    def test_team_facts_flat_and_nested_and_id_collision(self):
        self.write(".agent-spec/memory/facts/a.md", V1)
        self.write(".agent-spec/team-facts/facts/t.md", V1)  # same id as the local fact
        self.write(".agent-spec/team-facts/facts/u.md", V2.replace("beta", "gamma"))
        self.run_ingest("memory")
        facts = self.facts()
        self.assertEqual(len(facts), 3)
        self.assertEqual(facts["20261028-alpha-aaaaaa"]["scope"], "local")
        self.assertEqual(facts["team:20261028-alpha-aaaaaa"]["scope"], "team")

    def test_file_without_frontmatter_uses_stem_and_idempotent_mirror(self):
        self.write(".agent-spec/memory/facts/plain.md", "no header at all\n")
        gone = self.write(".agent-spec/memory/facts/a.md", V1)
        self.run_ingest("memory")
        self.assertIn("plain", self.facts())
        again = self.run_ingest("memory")["memory"]
        self.assertEqual((again["facts"], again["added"], again["removed"]), (2, 0, 0))
        os.remove(gone)  # the DB mirrors the files: a deleted fact disappears
        report = self.run_ingest("memory")["memory"]
        self.assertEqual((report["facts"], report["removed"]), (1, 1))
        self.assertEqual(list(self.facts()), ["plain"])

    def test_receipts_record_counts_in_meta_without_inventing_injections(self):
        self.write(".agent-spec/metrics/receipts/s1.json", json.dumps({"session_id": "s1", "facts_injected": 4, "ts": "t"}))
        self.write(".agent-spec/metrics/receipts/s2.json", json.dumps({"session_id": "s2", "facts_injected": None}))
        self.write(".agent-spec/metrics/receipts/s3.json", "{broken")
        report = self.run_ingest("memory")["memory"]
        self.assertEqual(report["receipts"], 1)
        conn = self.conn()
        meta = dict(conn.execute("SELECT key, value FROM meta WHERE key LIKE 'receipt:%'").fetchall())
        conn.close()
        self.assertEqual(json.loads(meta["receipt:s1"])["facts_injected"], 4)
        self.assertEqual(list(meta), ["receipt:s1"])
        self.assertEqual(self.count("fact_injections"), 0)

    def test_absent_directories_are_fine(self):
        self.assertEqual(self.run_ingest("memory")["memory"]["facts"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
