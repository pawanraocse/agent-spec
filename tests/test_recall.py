#!/usr/bin/env python3
"""P3-014: a fix recorded in repo A is returned by recall in repo B, citing repo A.

Run: python3 tests/test_recall.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECALL = os.path.join(ROOT, "bin", "agent-spec-recall.py")


def write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def exp(exp_id, task, status="success", retries=0, tokens=100):
    return {"exp_id": exp_id, "kind": "session", "task": task, "status": status, "retries": retries,
            "corrections": 0, "gates": 0, "tokens": {"input": tokens, "output": 0}}


class RecallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aspec-recall-")
        self.home = os.path.join(self.tmp, "home")
        self.a = os.path.join(self.tmp, "orders-svc")
        self.b = os.path.join(self.tmp, "billing-svc")
        os.makedirs(os.path.join(self.home, ".cursor", "skills"))
        write_jsonl(os.path.join(self.a, ".agent-spec", "experience.jsonl"), [
            exp("session:a1", "Fix NullPointerException in OrderService checkout when cart is empty"),
            exp("session:a2", "Rename logging helper")])
        write_jsonl(os.path.join(self.b, ".agent-spec", "experience.jsonl"), [
            exp("session:b1", "Add invoice PDF export")])
        # B is the mesh hub and lists A as a member.
        with open(os.path.join(self.b, ".agent-spec", "mesh.json"), "w") as fh:
            json.dump({"version": 1, "repos": [{"repo_id": "orders", "path": self.a}]}, fh)
        with open(os.path.join(self.home, ".cursor", "skills", ".agent-spec-projects"), "w") as fh:
            fh.write("%s\n%s\n" % (self.a, self.b))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_recall(self, cwd, *args):
        env = dict(os.environ, HOME=self.home)
        proc = subprocess.run([sys.executable, RECALL, *args, "--json"], cwd=cwd, env=env,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)["matches"]

    def test_hub_recalls_a_members_fix_with_a_citation(self):
        rows = self.run_recall(self.b, "checkout throws NullPointerException for an empty cart")
        self.assertEqual(rows[0]["exp_id"], "session:a1")
        self.assertEqual(rows[0]["repo"], "orders")
        self.assertEqual(rows[0]["citation"], "orders:.agent-spec/experience.jsonl:1")
        self.assertFalse(rows[0]["local"])

    def test_member_recalls_the_hubs_experience_through_the_registry(self):
        rows = self.run_recall(self.a, "invoice PDF export is blank")
        self.assertEqual([r["exp_id"] for r in rows], ["session:b1"])
        self.assertEqual(rows[0]["repo"], "billing-svc")

    def test_reuse_is_logged_locally_and_peers_are_never_written(self):
        before = open(os.path.join(self.a, ".agent-spec", "experience.jsonl")).read()
        self.run_recall(self.b, "NullPointerException checkout")
        reuse = [json.loads(l) for l in open(os.path.join(self.b, ".agent-spec", "experience-reuse.jsonl"))]
        self.assertEqual((reuse[0]["exp_id"], reuse[0]["repo"]), ("session:a1", "orders"))
        self.assertEqual(open(os.path.join(self.a, ".agent-spec", "experience.jsonl")).read(), before)
        self.assertFalse(os.path.exists(os.path.join(self.a, ".agent-spec", "experience-reuse.jsonl")))

    def test_deprecated_in_its_own_repo_is_skipped(self):
        write_jsonl(os.path.join(self.a, ".agent-spec", "experience-overrides.jsonl"),
                    [{"exp_id": "session:a1", "status": "deprecated"}])
        self.assertEqual(self.run_recall(self.b, "NullPointerException checkout", "--no-log"), [])

    def test_local_wins_a_tie_and_success_beats_failure(self):
        write_jsonl(os.path.join(self.b, ".agent-spec", "experience.jsonl"), [
            exp("session:b2", "checkout NullPointerException retry", status="failed"),
            exp("session:b3", "checkout NullPointerException guard")])
        rows = self.run_recall(self.b, "checkout NullPointerException", "--no-log", "--limit", "5")
        self.assertEqual([r["exp_id"] for r in rows], ["session:b3", "session:a1", "session:b2"])

    def test_unrelated_project_sees_no_peers(self):
        lone = os.path.join(self.tmp, "lone")
        write_jsonl(os.path.join(lone, ".agent-spec", "experience.jsonl"), [exp("session:l1", "unrelated")])
        self.assertEqual(self.run_recall(lone, "NullPointerException checkout", "--no-log"), [])

    def test_paths_and_single_shared_words_do_not_match(self):
        lone = os.path.join(self.tmp, "lone2")
        write_jsonl(os.path.join(lone, ".agent-spec", "experience.jsonl"), [
            exp("session:p1", "Edit /tmp/claude-1000/scratch/notes.md with the string-replace tool"),
            exp("session:p2", "hi"),
            exp("session:p3", "Bench billing double counts resumed sessions")])
        rows = self.run_recall(lone, "fix bench billing for resumed claude sessions", "--no-log")
        self.assertEqual([r["exp_id"] for r in rows], ["session:p3"])


if __name__ == "__main__":
    unittest.main()
