#!/usr/bin/env python3
"""Tests for log retention (H-041): oversized logs keep recent rows, old rows move to dated
archives, nothing is lost, and appends during the rewrite survive.

Run: python3 tests/test_retention.py
"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin"))
from aspec_platform import retention  # noqa: E402


def iso(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


class RetentionTest(unittest.TestCase):
    def setUp(self):
        self.project = tempfile.mkdtemp()
        self.spec = os.path.join(self.project, ".agent-spec")
        os.makedirs(os.path.join(self.spec, "metrics"))
        os.makedirs(os.path.join(self.spec, "graph"))
        with open(os.path.join(self.spec, "retention.json"), "w") as fh:
            json.dump({"days": 30, "max_bytes": 40}, fh)
        self.events = os.path.join(self.spec, "metrics", "events.jsonl")

    def tearDown(self):
        shutil.rmtree(self.project)

    def write_events(self, rows, tail=b""):
        with open(self.events, "wb") as fh:
            for r in rows:
                fh.write((json.dumps(r) + "\n").encode())
            fh.write(tail)

    def test_under_cap_is_untouched(self):
        with open(os.path.join(self.spec, "retention.json"), "w") as fh:
            json.dump({"days": 30, "max_bytes": 10 ** 9}, fh)
        self.write_events([{"ts": iso(400), "id": 1}])
        self.assertEqual(retention.apply(self.project), [])

    def test_old_rows_move_to_dated_archive(self):
        rows = [{"ts": iso(120), "id": "old1"}, {"ts": iso(100), "id": "old2"},
                {"ts": iso(1), "id": "new"}, {"id": "undated"}]
        self.write_events(rows, tail=b'{"ts": "partial')
        plan = retention.plan(self.project)
        self.assertEqual(plan[0]["archived_rows"], 2)
        with open(self.events, "rb") as fh:
            before = fh.read()
        retention.apply(self.project)
        with open(self.events, "rb") as fh:
            after = fh.read()
        self.assertNotEqual(before, after)
        kept = [json.loads(l) for l in after.splitlines()[:-1]]
        self.assertEqual([r["id"] for r in kept], ["new", "undated"])
        self.assertTrue(after.endswith(b'{"ts": "partial'), "a half-written last line is carried over")
        archived = []
        for a in retention.archives(self.project):
            with open(os.path.join(self.spec, a["path"])) as fh:
                archived += [json.loads(l)["id"] for l in fh]
        self.assertEqual(sorted(archived), ["old1", "old2"])

    def test_offset_timestamps_parse(self):
        self.assertIsNotNone(retention._row_time({"ts": "2026-11-15T12:57:19+0530"}))
        self.assertIsNotNone(retention._row_time({"ts": 1_700_000_000_000}))
        self.assertIsNone(retention._row_time({"ts": "garbage"}))

    def test_rewrite_keeps_bytes_appended_after_the_read(self):
        self.write_events([{"ts": iso(1), "id": "a"}])
        upto = os.path.getsize(self.events)
        with open(self.events, "ab") as fh:
            fh.write(b'{"ts": "x", "id": "late"}\n')
        retention._rewrite(self.events, [b'{"id": "a"}\n'], upto)
        with open(self.events) as fh:
            self.assertEqual([json.loads(l)["id"] for l in fh], ["a", "late"])

    def test_history_is_capped(self):
        old = retention.MAX_HISTORY
        retention.MAX_HISTORY = 3
        try:
            hist = os.path.join(self.spec, "graph", "stats-history.jsonl")
            with open(hist, "w") as fh:
                for i in range(5):
                    fh.write(json.dumps({"n": i}) + "\n")
            retention.apply(self.project)
            with open(hist) as fh:
                self.assertEqual([json.loads(l)["n"] for l in fh], [2, 3, 4])
        finally:
            retention.MAX_HISTORY = old

    def test_old_payload_files_are_archived_not_deleted(self):
        folder = os.path.join(self.spec, "metrics", "hook-payloads")
        os.makedirs(folder)
        old, new = os.path.join(folder, "old.json"), os.path.join(folder, "new.json")
        for p in (old, new):
            with open(p, "w") as fh:
                fh.write("{}")
        stamp = time.time() - 60 * 86400
        os.utime(old, (stamp, stamp))
        retention.apply(self.project)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(new))
        self.assertTrue(any(a["path"].endswith("old.json") for a in retention.archives(self.project)))


if __name__ == "__main__":
    unittest.main(verbosity=1)
