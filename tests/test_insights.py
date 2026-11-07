#!/usr/bin/env python3
"""Tests for the dashboard read models and the proof-pack export (D-012, D-014, D-021, D-022).

Run: python3 tests/test_insights.py
"""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _api_support import REPO_DIR, ApiCase  # noqa: E402
from aspec_platform import db, insights  # noqa: E402

NOW = "2026-10-31T12:00:00.000Z"
SECRET_PROMPT = "please open /Users/alice/secret-project/payroll.py"


def seed_extra(path):
    """On top of the base seed (R1, R2): a graph-less whole-file read, a spike, a workflow run, events."""
    conn = db.open_ready(path)
    conn.executescript("""
    UPDATE steps SET whole_file = 1, bytes_in = 40000 WHERE step_id = 'T1';
    UPDATE requests SET prompt_redacted = '%s' WHERE request_id = 'R1';
    INSERT INTO requests (request_id, run_id, source, status, started, workflow_id, tokens_input, tokens_output)
      VALUES ('W1', 'W1', 'ide', 'partial', '2026-10-31T11:30:00.000Z', 'rca', 30, 10);
    INSERT INTO steps (step_id, request_id, ordinal, kind, name, status, duration_ms, tokens_input, tokens_output)
      VALUES ('W1:fetch', 'W1', 0, 'ai', 'fetch', 'success', 1200, 20, 5),
             ('W1:rca', 'W1', 1, 'ai', 'rca', 'failed', 800, 10, 5);
    INSERT INTO subagent_runs (id, parent_request_id, agent, status, latency_ms)
      VALUES ('SA1', 'W1', 'agent-spec-search', 'success', 900), ('SA2', 'W1', 'generalPurpose', 'failed', 100);
    INSERT INTO events (event_id, run_id, ts, seq, type, step_id, tokens_input)
      VALUES ('E1', 'W1', '2026-10-31T11:30:01.000Z', 0, 'step.started', 'fetch', 0),
             ('E2', 'W1', '2026-10-31T11:30:02.000Z', 1, 'step.finished', 'fetch', 20);
    INSERT INTO quarantine_events (ts, tool, pattern, path_redacted) VALUES
      ('2026-10-31T09:00:00.000Z', 'Read', '.env', '[path]');
    INSERT INTO graph_stats (ts, files, edges, symbols, cycles, sha, age_s)
      VALUES ('2026-10-31T08:00:00.000Z', 120, 300, 50, 0, 'abc', 3600);
    INSERT INTO experiences (exp_id, title, created, successes, record_json) VALUES
      ('session:a', 't', '2026-10-30T10:00:00.000Z', 1, '{"corrections": 2, "tokens": {"input": 100, "output": 0}}'),
      ('session:b', 't', '2026-10-31T10:00:00.000Z', 1, '{"corrections": 0, "tokens": {"input": 50, "output": 0}}');
    """ % SECRET_PROMPT)
    conn.commit()
    conn.close()


class InsightsCase(ApiCase):
    def setUp(self):
        super().setUp()
        seed_extra(self.dbpath)

    def conn(self):
        return db.connect(self.dbpath, readonly=True)


class HomeTest(InsightsCase):
    def test_home_kpis(self):
        c = self.conn()
        h = insights.home(c, now=NOW)
        c.close()
        self.assertEqual(h["today"]["runs"], 3)
        self.assertEqual(h["today"]["tokens"], 150 + 300 + 40)
        self.assertEqual(h["last_7d"]["runs"], 3)
        self.assertEqual(h["graph"]["files"], 120)
        self.assertEqual(h["graph"]["age_s"], 3600 + 4 * 3600)  # snapshot age + time since it was taken
        self.assertGreater(h["saved_vs_baseline"]["saved_tokens"], 0)

    def test_learning_trend_is_per_day(self):
        c = self.conn()
        h = insights.home(c, now=NOW)
        c.close()
        trend = {d["day"]: d for d in h["learning"]}
        self.assertEqual(trend["2026-10-30"]["corrections"], 2)
        self.assertEqual(trend["2026-10-31"]["experiences"], 1)
        self.assertEqual(trend["2026-10-31"]["avg_tokens"], 50)

    def test_empty_database_does_not_raise(self):
        path = os.path.join(self.tmp, "empty.db")
        conn = db.open_ready(path)
        h = insights.home(conn, now=NOW)
        conn.close()
        self.assertEqual((h["today"]["runs"], h["graph"], h["learning"]), (0, None, []))


class GapsTest(InsightsCase):
    def gaps(self, project=None):
        c = self.conn()
        out = insights.gaps(c, now=NOW, project=project)
        c.close()
        return out

    def rules(self, project=None):
        return {g["rule"] for g in self.gaps(project=project)}

    def test_failed_step_and_run_and_quarantine_are_flagged(self):
        rules = self.rules()
        self.assertTrue({"step_failed", "run_failed", "secret_path_blocked"} <= rules, rules)

    def test_ai_review_findings_loaded_when_present(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            rev_dir = os.path.join(tmpdir, ".agent-spec", "metrics", "reviews")
            os.makedirs(rev_dir, exist_ok=True)
            with open(os.path.join(rev_dir, "S1.json"), "w", encoding="utf-8") as fh:
                json.dump({"improvements": ["Delegate search to subagent"], "model": "gemini-2.5-flash"}, fh)
            flags = [g for g in self.gaps(project=tmpdir) if g["rule"] == "ai_review_finding"]
            self.assertEqual(len(flags), 1)
            self.assertEqual(flags[0]["detail"], "Delegate search to subagent")
            self.assertEqual(flags[0]["kind"], "ai_judged")

    def test_flags_carry_no_prompt_text(self):
        self.assertNotIn("payroll", json.dumps(self.gaps()))


class ApiRoutesTest(InsightsCase):
    def test_home_and_gaps_routes(self):
        self.assertIn("today", self.get_json("/api/home"))
        self.assertIn("gaps", self.get_json("/api/gaps"))

    def test_run_detail_adds_tools_subagents_and_events(self):
        d = self.get_json("/api/runs/W1")
        self.assertEqual([s["name"] for s in d["steps"]], ["fetch", "rca"])
        self.assertEqual({a["agent"]: a["status"] for a in d["subagents"]},
                         {"agent-spec-search": "success", "generalPurpose": "failed"})
        self.assertEqual([e["type"] for e in d["events"]], ["step.started", "step.finished"])
        self.assertEqual(d["tools"][0]["name"], "fetch")
        self.assertEqual(d["waterfall"][0]["tokens"], 25)

    def test_run_detail_for_ide_session_groups_tool_cost(self):
        d = self.get_json("/api/runs/R1")
        names = {t["name"]: t for t in d["tools"]}
        self.assertEqual(names["Read"]["whole_file_reads"], 1)
        self.assertEqual(d["subagents"], [])


class ExportTest(InsightsCase):
    def export(self, *extra):
        out = os.path.join(self.tmp, "pack")
        env = dict(os.environ, AGENT_SPEC_DB=self.dbpath)
        proc = subprocess.run([sys.executable, os.path.join(REPO_DIR, "bin", "agent-spec-platform.py"), "export",
                               "--project", self.project, "--out", out] + list(extra),
                              capture_output=True, text=True, env=env)
        return proc, out

    def test_proof_pack_files_and_totals(self):
        proc, out = self.export()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(sorted(os.listdir(out)), ["gaps.csv", "runs.csv", "summary.json", "tools.csv"])
        rows = list(csv.DictReader(open(os.path.join(out, "runs.csv"), encoding="utf-8")))
        self.assertEqual({r["request_id"] for r in rows}, {"R1", "R2", "W1"})
        self.assertEqual(next(r for r in rows if r["request_id"] == "R1")["tokens_total"], "150")
        summary = json.load(open(os.path.join(out, "summary.json"), encoding="utf-8"))
        self.assertEqual(summary["totals"]["runs"], 3)
        self.assertIn("saved_vs_baseline", summary)
        self.assertEqual(summary["estimate"], True)

    def test_no_prompts_paths_or_transcripts_leave_the_machine(self):
        proc, out = self.export()
        text = "".join(open(os.path.join(out, f), encoding="utf-8").read() for f in os.listdir(out))
        for leak in ("payroll", "alice", "first prompt", "second prompt", "transcript"):
            self.assertNotIn(leak, text)

    def test_json_format_writes_one_file(self):
        proc, out = self.export("--format", "json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(os.listdir(out), ["proof-pack.json"])
        data = json.load(open(os.path.join(out, "proof-pack.json"), encoding="utf-8"))
        self.assertEqual(set(data), {"summary", "runs", "tools", "gaps"})

    def test_missing_database_is_one_line_error(self):
        env = dict(os.environ, AGENT_SPEC_DB=os.path.join(self.tmp, "nope.db"))
        proc = subprocess.run([sys.executable, os.path.join(REPO_DIR, "bin", "agent-spec-platform.py"), "export",
                               "--project", self.project, "--out", os.path.join(self.tmp, "x")],
                              capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
