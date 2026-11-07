#!/usr/bin/env python3
"""Tests for `ingest runs` and `ingest experiences` (O-010, L-001): run dirs and experience.jsonl -> platform.db.

Run: python3 tests/test_ingest_runs.py
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _run_helpers import Sandbox  # noqa: E402
from _ingest_support import REPO_DIR  # noqa: E402,F401  (puts bin/ on sys.path)
from aspec_platform import db, ingest  # noqa: E402


class RunsCase(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.tmp = tempfile.mkdtemp()
        self._old = os.environ.get("AGENT_SPEC_DB")
        os.environ["AGENT_SPEC_DB"] = os.path.join(self.tmp, "platform.db")
        self.addCleanup(self.cleanup)

    def cleanup(self):
        if self._old is None:
            os.environ.pop("AGENT_SPEC_DB", None)
        else:
            os.environ["AGENT_SPEC_DB"] = self._old
        self.sb.cleanup()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ingest(self, *what):
        return ingest.run(self.sb.root, list(what))

    def q(self, sql, *args):
        conn = db.connect(os.environ["AGENT_SPEC_DB"])
        try:
            return [dict(r) for r in conn.execute(sql, args)]
        finally:
            conn.close()

    def finished_run(self):
        rid = self.sb.start("fix the thing")
        self.sb.run("step-start", rid, "a", "--agent", "generalPurpose")
        self.sb.run("step-end", rid, "a", "--status", "success", "--output-json", '{"x":1}',
                    "--tokens-in", "10", "--tokens-out", "5")
        self.sb.run("step-start", rid, "b", "--agent", "generalPurpose")
        self.sb.run("step-end", rid, "b", "--status", "failed", "--error", "boom")
        code, out, err = self.sb.run("finish", rid)
        self.assertEqual(code, 0, err)
        return rid


class RunsIngestTest(RunsCase):
    def test_run_becomes_request_steps_and_events(self):
        rid = self.finished_run()
        report = self.ingest("runs")["runs"]
        self.assertEqual(report["errors"], 0, report)
        req = self.q("SELECT * FROM requests WHERE request_id = ?", rid)
        self.assertEqual(len(req), 1)
        self.assertEqual((req[0]["run_id"], req[0]["workflow_id"], req[0]["status"]), (rid, "t", "partial"))
        self.assertEqual(req[0]["prompt_redacted"], "fix the thing")
        self.assertEqual(req[0]["tokens_input"], 10)
        steps = self.q("SELECT name, status FROM steps WHERE request_id = ? ORDER BY ordinal", rid)
        self.assertEqual([(s["name"], s["status"]) for s in steps], [("a", "success"), ("b", "failed")])
        events = self.q("SELECT type FROM events WHERE run_id = ?", rid)
        self.assertEqual(len(events), len(self.sb.events(rid)))
        self.assertIn("step.finished", {e["type"] for e in events})

    def test_reingest_is_idempotent(self):
        self.finished_run()
        self.ingest("runs")
        before = [self.q("SELECT COUNT(*) AS n FROM %s" % t)[0]["n"] for t in ("requests", "steps", "events")]
        self.ingest("runs")
        after = [self.q("SELECT COUNT(*) AS n FROM %s" % t)[0]["n"] for t in ("requests", "steps", "events")]
        self.assertEqual(before, after)

    def test_run_in_progress_then_finished_updates_in_place(self):
        rid = self.sb.start("later")
        self.ingest("runs")
        self.assertEqual(self.q("SELECT status FROM requests WHERE request_id = ?", rid)[0]["status"], "running")
        self.sb.run("step-start", rid, "a")
        self.sb.run("step-end", rid, "a", "--status", "success", "--output-json", "{}")
        self.sb.run("finish", rid, "--force")
        self.ingest("runs")
        self.assertEqual(len(self.q("SELECT * FROM requests WHERE request_id = ?", rid)), 1)
        self.assertNotEqual(self.q("SELECT status FROM requests WHERE request_id = ?", rid)[0]["status"], "running")

    def test_compacted_run_still_listed_from_result_json(self):
        rid = self.finished_run()
        os.remove(os.path.join(self.sb.run_dir(rid), "events.jsonl"))
        self.ingest("runs")
        steps = self.q("SELECT name FROM steps WHERE request_id = ? ORDER BY ordinal", rid)
        self.assertEqual([s["name"] for s in steps], ["a", "b"])
        self.assertEqual(self.q("SELECT COUNT(*) AS n FROM events")[0]["n"], 0)

    def test_malformed_event_line_counted_not_raised(self):
        rid = self.finished_run()
        with open(os.path.join(self.sb.run_dir(rid), "events.jsonl"), "a") as fh:
            fh.write("{not json\n")
        report = self.ingest("runs")["runs"]
        self.assertEqual(report["errors"], 1)
        self.assertEqual(len(self.q("SELECT * FROM requests")), 1)

    def test_runs_is_part_of_all(self):
        self.finished_run()
        self.assertIn("runs", self.ingest("all"))


class ExperienceIngestTest(RunsCase):
    def write_lines(self, *rows):
        path = os.path.join(self.sb.root, ".agent-spec", "experience.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write((r if isinstance(r, str) else json.dumps(r)) + "\n")

    def test_experience_rows_and_idempotency(self):
        row = {"schema": 1, "exp_id": "session:s1", "kind": "session", "ts": "2026-10-30T10:00:00",
               "task": "add export", "status": "success", "tokens": {"input": 5, "output": 2, "cache_read": 1},
               "retries": 0, "corrections": 1, "facts_injected": 3, "run_id": None}
        self.write_lines(row, {**row, "exp_id": "workflow:r1", "kind": "workflow", "status": "partial"}, "{bad")
        rep = self.ingest("experiences")["experiences"]
        self.assertEqual((rep["added"], rep["errors"]), (2, 1))
        rows = self.q("SELECT * FROM experiences ORDER BY exp_id")
        self.assertEqual([r["exp_id"] for r in rows], ["session:s1", "workflow:r1"])
        self.assertEqual((rows[0]["title"], rows[0]["successes"], rows[1]["successes"]), ("add export", 1, 0))
        self.assertEqual(json.loads(rows[0]["record_json"])["corrections"], 1)
        self.ingest("experiences")
        self.assertEqual(len(self.q("SELECT * FROM experiences")), 2)

    def test_later_line_for_same_exp_id_wins_but_keeps_uses(self):
        self.write_lines({"exp_id": "session:s1", "ts": "2026-10-30T10:00:00", "task": "a", "status": "failed"})
        self.ingest("experiences")
        conn = db.connect(os.environ["AGENT_SPEC_DB"])
        conn.execute("UPDATE experiences SET uses = 4, tier = 'trusted'")
        conn.commit()
        conn.close()
        self.write_lines({"exp_id": "session:s1", "ts": "2026-10-30T10:00:00", "task": "a", "status": "success"})
        self.ingest("experiences")
        row = self.q("SELECT * FROM experiences")[0]
        self.assertEqual((row["successes"], row["uses"], row["tier"]), (1, 4, "trusted"))

    def test_workflow_finish_appends_experience_line(self):
        rid = self.finished_run()
        path = os.path.join(self.sb.root, ".agent-spec", "experience.jsonl")
        lines = [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]
        self.assertEqual(len(lines), 1)
        self.assertEqual((lines[0]["exp_id"], lines[0]["kind"], lines[0]["status"], lines[0]["run_id"]),
                         ("workflow:" + rid, "workflow", "partial", rid))
        self.assertEqual(lines[0]["task"], "fix the thing")


if __name__ == "__main__":
    unittest.main()
