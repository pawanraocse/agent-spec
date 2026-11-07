#!/usr/bin/env python3
"""Tests for Cursor Workspaces and Session Intelligence API."""
import os
import sys
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_DIR, "bin"))
from aspec_platform import cursor_sessions


class CursorSessionsTest(unittest.TestCase):
    def test_list_workspaces_structure(self):
        res = cursor_sessions.get_cursor_workspaces()
        self.assertIn("workspaces", res)
        self.assertIn("total_sessions", res)
        self.assertIsInstance(res["workspaces"], list)
        if res["workspaces"]:
            first_ws = res["workspaces"][0]
            self.assertIn("name", first_ws)
            self.assertIn("session_count", first_ws)
            self.assertIn("sessions", first_ws)

    def test_load_session_review_honest_by_construction(self):
        import json
        import tempfile

        # Unreviewed session returns None (honest by construction, no invented scores)
        self.assertIsNone(cursor_sessions.load_session_review("nonexistent-session-id"))

        # When an AI review file exists in .agent-spec/metrics/reviews/<id>.json, load it
        with tempfile.TemporaryDirectory() as tmpdir:
            rev_dir = os.path.join(tmpdir, ".agent-spec", "metrics", "reviews")
            os.makedirs(rev_dir, exist_ok=True)
            sample_rev = {
                "session_id": "test-sess-1",
                "grade": "A",
                "score": 92,
                "provenance": "ai_judged",
                "pros": ["Delegated to agent-spec-search"],
                "improvements": []
            }
            with open(os.path.join(rev_dir, "test-sess-1.json"), "w", encoding="utf-8") as fh:
                json.dump(sample_rev, fh)

            loaded = cursor_sessions.load_session_review("test-sess-1", project=tmpdir)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["grade"], "A")
            self.assertEqual(loaded["provenance"], "ai_judged")


if __name__ == "__main__":
    unittest.main()
