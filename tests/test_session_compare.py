#!/usr/bin/env python3
"""PI-010: session comparison — signals, quality and context side by side, with provenance.

Run: python3 tests/test_session_compare.py
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ingest_support import REPO_DIR  # noqa: E402,F401  (puts bin/ on sys.path)
from aspec_platform import session_compare  # noqa: E402


def trace(tid, session, start, source="hook", skills=()):
    return {"trace_id": tid, "session_id": session, "start": start, "source": source, "skills": list(skills)}


def span(tid, sid, kind, name, start, status="ok", **attrs):
    return {"span_id": sid, "trace_id": tid, "kind": kind, "name": name, "start": start, "seq": 0,
            "status": status, "attributes": attrs}


def loaded():
    traces = [trace("t1", "A", "2026-11-18T10:00:00Z", skills=["agent-spec-raw-code-full"]),
              trace("t2", "A", "2026-11-18T10:05:00Z"),
              trace("t3", "B", "2026-11-18T11:00:00Z", source="transcript")]
    spans = [
        span("t1", "e1", "edit", "Write", "2026-11-18T10:00:01Z", file_path="/p/a.py"),
        span("t1", "v1", "tool", "Shell", "2026-11-18T10:00:02Z", target="pytest -q"),
        span("t1", "r1", "response", "r", "2026-11-18T10:00:03Z", input_tokens=100, output_tokens=20,
             cache_read_tokens=50, cache_write_tokens=0),
        span("t2", "e2", "edit", "Write", "2026-11-18T10:05:01Z", file_path="/p/a.py"),
        span("t2", "f1", "tool", "Read", "2026-11-18T10:05:02Z", status="error", file_path="/p/b.py"),
        span("t3", "s1", "subagent", "agent-spec-search", "2026-11-18T11:00:01Z"),
    ]
    return traces, spans


class SessionCompareTest(unittest.TestCase):
    def setUp(self):
        self.project = tempfile.mkdtemp(prefix="aspec-cmp-")
        metrics = os.path.join(self.project, ".agent-spec", "metrics")
        os.makedirs(os.path.join(metrics, "reviews"))
        with open(os.path.join(metrics, "reviews", "A.json"), "w") as fh:
            json.dump({"overall": 4, "dimensions": {"relevance": {"score": 4, "evidence": ["e1"]},
                                                   "verification": {"score": None}}}, fh)
        with open(os.path.join(metrics, "injections.jsonl"), "w") as fh:
            fh.write(json.dumps({"conversation_id": "A", "digest_bytes": 1700,
                                 "facts": ["- [constraint] risk gate state is agent-proof: x"]}) + "\n")
        self.addCleanup(shutil.rmtree, self.project, True)

    def test_summary_counts_signals_tokens_quality_and_context(self):
        row = session_compare.summarize(self.project, None, "A", loaded())
        self.assertEqual(row["provenance"], "measured")
        self.assertEqual((row["requests"], row["tool_calls"], row["tool_failures"]), (2, 4, 1))  # edits count as tool calls
        self.assertEqual(row["files_edited"], 1)
        self.assertEqual((row["requests_with_edits"], row["verified_requests"]), (2, 1))
        self.assertEqual(row["rework_files"], 1, "a.py edited in t1 and again in t2")
        self.assertEqual(row["tokens"]["total"], 170)
        self.assertEqual(row["skills"], ["agent-spec-raw-code-full"])
        self.assertEqual(row["quality"], {"provenance": "ai_judged", "overall": 4,
                                          "dimensions": {"relevance": 4, "verification": None}})
        self.assertEqual(row["context"]["digest_bytes"], 1700)
        self.assertEqual(row["context"]["facts_injected"], 1)
        self.assertEqual(row["context"]["facts"], ["risk gate state is agent-proof"])

    def test_missing_data_is_none_not_zero(self):
        row = session_compare.summarize(self.project, None, "B", loaded())
        self.assertEqual(row["provenance"], "estimated")
        self.assertIsNone(row["tokens"])
        self.assertIsNone(row["quality"])
        self.assertIsNone(row["context"])
        self.assertEqual(row["subagents"], 1)

    def test_compare_returns_both_rows_and_delta(self):
        orig = session_compare.tr.all_traces
        session_compare.tr.all_traces = lambda project, conn: loaded()
        try:
            out = session_compare.compare(self.project, None, "A", "B")
        finally:
            session_compare.tr.all_traces = orig
        self.assertEqual((out["a"]["session_id"], out["b"]["session_id"]), ("A", "B"))
        self.assertEqual(out["delta"]["tool_calls"], 4)
        self.assertNotIn("tokens_total", out["delta"], "no delta when one side has no tokens")
        self.assertIsNone(out["text"])

    def test_unknown_or_malformed_session_is_a_lookup_error(self):
        orig = session_compare.tr.all_traces
        session_compare.tr.all_traces = lambda project, conn: loaded()
        try:
            for a, b in (("A", "NOPE"), ("../etc", "A"), ("", "A")):
                with self.assertRaises(LookupError):
                    session_compare.compare(self.project, None, a, b)
        finally:
            session_compare.tr.all_traces = orig


if __name__ == "__main__":
    unittest.main()
