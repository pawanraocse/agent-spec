#!/usr/bin/env python3
"""H-051: the offline demo setup prepares every beat of the 5-minute story.

Run: python3 tests/test_demo_setup.py   (HOME is a temp dir, so the real registry is untouched)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP = os.path.join(ROOT, "examples", "mesh-demo", "demo-setup.sh")


class DemoSetupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="aspec-demo-")
        cls.home = os.path.join(cls.tmp, "home")
        os.makedirs(cls.home)
        cls.demo = os.path.join(cls.tmp, "demo")
        cls.env = dict(os.environ, HOME=cls.home, AGENT_SPEC_CURSOR_STORE="0")
        cls.env.pop("AGENT_SPEC_DB", None)
        proc = subprocess.run(["bash", SETUP, cls.demo], env=cls.env, capture_output=True, text=True, timeout=600)
        cls.out, cls.code, cls.err = proc.stdout, proc.returncode, proc.stderr
        cls.hub = os.path.join(cls.demo, "orders-api")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def py(self, code):
        proc = subprocess.run([sys.executable, "-c", code], cwd=self.hub, env=self.env, capture_output=True,
                              text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_setup_finishes_every_step(self):
        self.assertEqual(self.code, 0, self.err[-2000:])
        self.assertIn("7/7", self.out)
        self.assertIn("6 cross-repo edges", self.out)

    def test_package_examples_are_not_written(self):
        status = subprocess.run(["git", "status", "--porcelain", "examples/mesh-demo"], cwd=ROOT,
                                capture_output=True, text=True).stdout
        self.assertNotIn(".agent-spec", status)

    def test_every_beat_has_its_data(self):
        data = self.py("""
import json, os, sys
sys.path.insert(0, '.agent-spec/bin')
from aspec_platform import audit_export, db, proposals, risk_view
p = os.getcwd()
conn = db.connect(db.db_path(p), readonly=True)
print(json.dumps({
  "risk": [x["file"] for x in risk_view.overview(p)["pending"]],
  "proposals": len(proposals.overview(p)["pending"]),
  "audit": len(audit_export.build(p, conn, "conv-recorded-1")),
}))
""")
        self.assertEqual(data["risk"], ["orders_api/routes.py"])
        self.assertEqual(data["proposals"], 1)
        self.assertGreater(data["audit"], 0)

    def test_first_chat_records_what_the_digest_injected(self):
        # H-005: a freshly registered project has no metrics/ before its first hook runs.
        path = os.path.join(self.hub, ".agent-spec", "metrics", "injections.jsonl")
        rows = [json.loads(l) for l in open(path, encoding="utf-8")]
        mine = [r for r in rows if r["conversation_id"] == "conv-recorded-1"]
        self.assertTrue(mine)
        self.assertTrue(any("routes are a public contract" in f for f in mine[-1]["facts"]))

    def test_digest_is_not_an_onboarding_notice(self):
        out = subprocess.run([sys.executable, ".agent-spec/bin/agent-spec-digest.py"], cwd=self.hub, env=self.env,
                             capture_output=True, text=True).stdout
        self.assertNotIn("ONBOARDING NEEDED", out)

    def test_dry_run_drives_every_beat(self):
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "examples", "mesh-demo", "demo-dryrun.py"),
                               "--runs", "1", "--json", "--allow-network"], env=self.env, capture_output=True,
                              text=True, timeout=600)
        run = json.loads(proc.stdout)[0]
        self.assertTrue(run["ok"], [b for b in run["beats"] if not b["ok"]])
        self.assertEqual(len(run["beats"]), 10)

    def test_refuses_to_clear_a_directory_it_did_not_make(self):
        foreign = os.path.join(self.tmp, "foreign")
        os.makedirs(foreign)
        open(os.path.join(foreign, "keep.txt"), "w").close()
        proc = subprocess.run(["bash", SETUP, foreign], env=self.env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertTrue(os.path.isfile(os.path.join(foreign, "keep.txt")))

    def test_recall_cites_the_other_repo(self):
        proc = subprocess.run([sys.executable, ".agent-spec/bin/agent-spec-recall.py", "worker processes orders.created twice",
                               "--json", "--no-log"], cwd=self.hub, env=self.env, capture_output=True, text=True)
        rows = json.loads(proc.stdout)["matches"]
        self.assertEqual(rows[0]["citation"], "orders-worker:.agent-spec/experience.jsonl:1")


if __name__ == "__main__":
    unittest.main()
