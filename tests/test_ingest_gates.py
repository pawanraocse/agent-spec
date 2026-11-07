#!/usr/bin/env python3
"""Tests for `ingest gates` (D-004, P2.6): STATE.json history -> gate_events.

Run: python3 tests/test_ingest_gates.py
"""
import json
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ingest_support import IngestCase  # noqa: E402


def state(feature, history, artifacts=None):
    return json.dumps({"feature": feature, "gate": 0, "gate_name": "X",
                       "artifacts": artifacts or {}, "history": history})


H0 = {"gate": 0, "name": "REQUIREMENTS", "at": "2026-10-29T10:00:00"}
H1 = {"gate": 1, "name": "TECH-SPEC", "at": "2026-10-29T11:00:00"}


class GateIngestTest(IngestCase):
    def rows(self):
        conn = self.conn()
        try:
            return conn.execute("SELECT * FROM gate_events ORDER BY ts, gate").fetchall()
        finally:
            conn.close()

    def test_history_entries_become_rows_with_artifact_and_utc_ts(self):
        self.write(".agent-spec/sdlc/STATE.json",
                   state("login", [H0, H1], {"01-REQUIREMENTS.md": "2026-10-29T10:00:00"}))
        report = self.run_ingest("gates")["gates"]
        self.assertEqual((report["added"], report["errors"]), (2, 0))
        first, second = self.rows()
        self.assertEqual((first["feature"], first["gate"], first["gate_name"]), ("login", 0, "REQUIREMENTS"))
        self.assertEqual(first["artifact"], "01-REQUIREMENTS.md")
        self.assertEqual(second["artifact"], "")
        self.assertTrue(first["ts"].endswith("Z"))
        self.assertEqual(datetime.strptime(first["ts"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=__import__("datetime").timezone.utc).timestamp(),
            datetime.fromisoformat(H0["at"]).timestamp())

    def test_second_run_is_idempotent_and_growth_adds_one(self):
        path = self.write(".agent-spec/sdlc/STATE.json", state("login", [H0]))
        self.run_ingest("gates")
        report = self.run_ingest("gates")["gates"]
        self.assertEqual((report["added"], report["skipped"], len(self.rows())), (0, 1, 1))
        self.write(".agent-spec/sdlc/STATE.json", state("login", [H0, H1]))
        self.assertEqual(self.run_ingest("gates")["gates"]["added"], 1)
        self.assertEqual(len(self.rows()), 2)
        self.assertTrue(os.path.isfile(path))

    def test_per_feature_pipeline_directories(self):
        self.write(".agent-spec/pipeline/checkout/STATE.json", state(None, [H0]))
        self.write(".agent-spec/pipeline/search/STATE.json", state("search-v2", [H0, H1]))
        self.run_ingest("gates")
        self.assertEqual(sorted({r["feature"] for r in self.rows()}), ["checkout", "search-v2"])
        self.assertEqual(len(self.rows()), 3)

    def test_malformed_state_and_entries_are_counted_not_raised(self):
        self.write(".agent-spec/sdlc/STATE.json", "{not json")
        self.write(".agent-spec/pipeline/f/STATE.json", state("f", [H0, {"gate": "x"}, {"name": "no gate"}, "str"]))
        report = self.run_ingest("gates")["gates"]
        self.assertEqual((report["added"], report["errors"]), (1, 4))

    def test_missing_state_files_are_fine(self):
        self.assertEqual(self.run_ingest("gates")["gates"], {"added": 0, "skipped": 0, "errors": 0})


if __name__ == "__main__":
    unittest.main(verbosity=1)
