#!/usr/bin/env python3
"""Tests for `ingest graph` and `ingest quarantine` (D-006, P2.9), plus the graphify-build trend line.

Run: python3 tests/test_ingest_graph.py
"""
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ingest_support import IngestCase, REPO_DIR  # noqa: E402

LINE1 = {"ts": "2026-10-29T10:00:00", "files": 10, "edges": 7, "symbols": 0, "cycles": 1, "sha": "abc", "age_s": 0}
LINE2 = {"ts": "2026-10-29T11:00:00", "files": 12, "edges": 9, "symbols": 0, "cycles": 0, "sha": "def", "age_s": 0}


def jsonl(*items):
    return "".join((i if isinstance(i, str) else json.dumps(i)) + "\n" for i in items)


class GraphIngestTest(IngestCase):
    def rows(self, table):
        conn = self.conn()
        try:
            return conn.execute("SELECT * FROM %s ORDER BY ts" % table).fetchall()
        finally:
            conn.close()

    def test_graph_history_rows_and_idempotency(self):
        self.write(".agent-spec/graph/stats-history.jsonl", jsonl(LINE1, LINE2, "{bad", {"files": 1}))
        report = self.run_ingest("graph")["graph"]
        self.assertEqual((report["added"], report["errors"]), (2, 2))
        first = self.rows("graph_stats")[0]
        self.assertEqual((first["files"], first["edges"], first["cycles"], first["sha"]), (10, 7, 1, "abc"))
        self.assertTrue(first["ts"].endswith("Z"))
        again = self.run_ingest("graph")["graph"]
        self.assertEqual((again["added"], again["skipped"], self.count("graph_stats")), (0, 2, 2))

    def test_missing_sha_does_not_duplicate_on_rerun(self):
        no_sha = dict(LINE1)
        del no_sha["sha"]
        self.write(".agent-spec/graph/stats-history.jsonl", jsonl(no_sha))
        self.run_ingest("graph")
        self.run_ingest("graph")
        self.assertEqual(self.count("graph_stats"), 1)

    def test_appended_history_adds_only_new_rows(self):
        path = self.write(".agent-spec/graph/stats-history.jsonl", jsonl(LINE1))
        self.run_ingest("graph")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(jsonl(LINE2))
        self.assertEqual(self.run_ingest("graph")["graph"]["added"], 1)

    def test_absent_files_are_fine(self):
        self.assertEqual(self.run_ingest("graph", "quarantine")["graph"]["added"], 0)

    def test_quarantine_events_redact_path_and_are_idempotent(self):
        event = {"ts": "2026-10-29T10:00:00", "tool": "Read", "pattern": ".env*",
                 "path_redacted": "/p/.env?password=hunter22xyz", "session_id": "s1"}
        no_session = {"ts": "2026-10-29T10:05:00", "tool": "Shell", "pattern": "~/.ssh", "path": "/home/u/.ssh/id_rsa"}
        self.write(".agent-spec/metrics/quarantine.jsonl", jsonl(event, no_session, "nope", {"tool": "x"}))
        report = self.run_ingest("quarantine")["quarantine"]
        self.assertEqual((report["added"], report["errors"]), (2, 2))
        first, second = self.rows("quarantine_events")
        self.assertNotIn("hunter22xyz", first["path_redacted"])
        self.assertEqual((first["tool"], first["pattern"], first["session_id"]), ("Read", ".env*", "s1"))
        self.assertEqual(second["path_redacted"], "/home/u/.ssh/id_rsa")
        self.run_ingest("quarantine")
        self.assertEqual(self.count("quarantine_events"), 2)

    def test_graphify_build_appends_one_history_line_per_build(self):
        proj = os.path.join(self.tmp, "mini")
        os.makedirs(os.path.join(proj, ".agent-spec"))
        with open(os.path.join(proj, "a.py"), "w") as fh:
            fh.write("import b\n")
        with open(os.path.join(proj, "b.py"), "w") as fh:
            fh.write("X = 1\n")
        script = os.path.join(REPO_DIR, "bin", "graphify-build.py")
        history = os.path.join(proj, ".agent-spec", "graph", "stats-history.jsonl")
        for expected in (1, 2):
            res = subprocess.run([sys.executable, script, "--quiet"], cwd=proj, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stderr)
            with open(history, encoding="utf-8") as fh:
                lines = [json.loads(line) for line in fh]
            self.assertEqual(len(lines), expected)
        last = lines[-1]
        self.assertEqual(set(last), {"ts", "files", "edges", "symbols", "cycles", "sha", "age_s"})
        self.assertEqual((last["files"], last["edges"], last["symbols"], last["age_s"]), (2, 1, 0, 0))
        self.assertEqual(len(last["sha"]), 40)
        ingested = __import__("aspec_platform.ingest", fromlist=["x"]).run(proj, ["graph"])["graph"]
        self.assertEqual(ingested["added"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
