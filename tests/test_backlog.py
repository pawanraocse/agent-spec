#!/usr/bin/env python3
"""Tests for bin/agent-spec-backlog.py (D-004.1): parse todo-plan.md, evidence-gated `set`.

Run: python3 tests/test_backlog.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(REPO, "bin", "agent-spec-backlog.py")
PLAN = os.path.join(REPO, "todo-plan.md")
GUIDE = os.path.join(REPO, "docs", "IMPLEMENTATION-GUIDE.md")


def slurp(path):
    with open(path) as fh:
        return fh.read()


def run(*args):
    return subprocess.run([sys.executable, CLI] + list(args),
                          capture_output=True, text=True)


class BacklogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.plan = os.path.join(self.tmp, "todo-plan.md")
        shutil.copy(PLAN, self.plan)
        # The live plan moves on as work completes; pin the row these tests mutate to open.
        text = slurp(self.plan)
        text = re.sub(r"(\| )`\[[x~-]\]`( \| D-004\.1 \|)", r"\1`[ ]`\2", text, count=1)
        with open(self.plan, "w") as fh:
            fh.write(text)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def cli(self, *args):
        return run("--plan", self.plan, "--guide", GUIDE, *args)

    def rows(self):
        res = self.cli("json")
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout)

    def test_parses_real_plan(self):
        rows = json.loads(run("json").stdout)  # default locations = repo root
        self.assertGreaterEqual(len(rows), 100)
        for r in rows:
            self.assertTrue(r["task_id"], r)
            self.assertIn(r["status"], ("[ ]", "[~]", "[x]", "[-]"))
        by_id = {r["task_id"]: r for r in rows}
        self.assertEqual(len(by_id), len(rows), "duplicate IDs")
        d = by_id["D-004.1"]
        self.assertEqual(d["p_number"], "P2.7")
        self.assertEqual(d["deps"], ["P2.3"])
        self.assertEqual(d["slice"], "5")
        for key in ("title", "acceptance", "effort", "evidence"):
            self.assertIn(key, d)

    def test_list_find_show(self):
        out = self.cli("list", "--status", "[ ]", "--slice", "5").stdout
        self.assertIn("D-004.1", out)
        self.assertNotIn("T-001", out)
        self.assertIn("D-004.1", self.cli("find", "backlog ingest").stdout)
        shown = self.cli("show", "D-004.1").stdout
        self.assertIn("P2.7", shown)
        self.assertIn("P2.3", shown)

    def test_done_requires_evidence(self):
        before = slurp(self.plan)
        res = self.cli("set", "D-004.1", "[x]")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("evidence", res.stderr.lower())
        self.assertEqual(slurp(self.plan), before)

    def test_set_changes_only_that_line(self):
        before = slurp(self.plan).splitlines(keepends=True)
        res = self.cli("set", "D-004.1", "[x]", "--evidence", "python3 tests/test_backlog.py: OK")
        self.assertEqual(res.returncode, 0, res.stderr)
        after = slurp(self.plan).splitlines(keepends=True)
        self.assertEqual(len(before), len(after))
        changed = [(a, b) for a, b in zip(before, after) if a != b]
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0][0].replace("`[ ]`", "`[x]`", 1), changed[0][1])
        self.assertIn("D-004.1", changed[0][0])
        row = [r for r in self.rows() if r["task_id"] == "D-004.1"][0]
        self.assertEqual(row["status"], "[x]")

    def test_evidence_file_written(self):
        self.cli("set", "D-004.1", "x", "--evidence", "cmd + result")
        ev = os.path.join(self.tmp, "docs", "evidence", "D-004.1.md")
        self.assertTrue(os.path.exists(ev))
        self.assertIn("cmd + result", slurp(ev))
        row = [r for r in self.rows() if r["task_id"] == "D-004.1"][0]
        self.assertTrue(any("cmd + result" in e for e in row["evidence"]))
        self.assertIn("cmd + result", self.cli("show", "D-004.1").stdout)

    def test_non_done_status_needs_no_evidence(self):
        res = self.cli("set", "D-004.1", "[~]")
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_unknown_id_and_status(self):
        res = self.cli("set", "NOPE-999", "[~]")
        self.assertEqual(res.returncode, 1)
        self.assertIn("NOPE-999", res.stderr)
        self.assertNotIn("Traceback", res.stderr)
        self.assertEqual(self.cli("show", "NOPE-999").returncode, 1)
        res = self.cli("set", "D-004.1", "bogus")
        self.assertEqual(res.returncode, 1)
        self.assertNotIn("Traceback", res.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
