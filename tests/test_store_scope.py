#!/usr/bin/env python3
"""Cursor's local store is machine-wide; a project's dashboard keeps only its own chats.

Run: python3 tests/test_store_scope.py
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ingest_support import REPO_DIR  # noqa: E402,F401  (puts bin/ on sys.path)
from aspec_platform import cursor_sessions, db, ingest, traces  # noqa: E402


class StoreScopeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aspec-scope-")
        self.project = os.path.join(self.tmp, "proj")
        os.makedirs(os.path.join(self.project, ".agent-spec", "metrics"))
        self.convs = [
            {"composer_id": "mine", "workspace": self.project, "bubbles": []},
            {"composer_id": "sub", "workspace": os.path.join(self.project, "pkg"), "bubbles": []},
            {"composer_id": "other", "workspace": os.path.join(self.tmp, "other"), "bubbles": []},
            {"composer_id": "prefix", "workspace": self.project + "-old", "bubbles": []},
            {"composer_id": "none", "workspace": None, "bubbles": []},
        ]

    def test_only_this_projects_chats_are_kept(self):
        kept = [c["composer_id"] for c in ingest.store_for_project(self.convs, self.project)]
        self.assertEqual(kept, ["mine", "sub"])

    def test_ingest_scopes_unless_all(self):
        orig, seen = cursor_sessions.store_conversations, []
        orig_build = traces.build_from_store
        cursor_sessions.store_conversations = lambda *a, **k: self.convs
        traces.build_from_store = lambda convs: (seen.append([c["composer_id"] for c in convs]) or ([], []))
        old = os.environ.get("AGENT_SPEC_CURSOR_STORE")
        conn = db.open_ready(os.path.join(self.tmp, "p.db"))
        try:
            for mode in ("1", "all"):
                os.environ["AGENT_SPEC_CURSOR_STORE"] = mode
                ingest.ingest_traces(conn, self.project)
        finally:
            conn.close()
            cursor_sessions.store_conversations = orig
            traces.build_from_store = orig_build
            if old is None:
                os.environ.pop("AGENT_SPEC_CURSOR_STORE", None)
            else:
                os.environ["AGENT_SPEC_CURSOR_STORE"] = old
        self.assertEqual(seen[0], ["mine", "sub"])
        self.assertEqual(len(seen[1]), 5)


if __name__ == "__main__":
    unittest.main()
