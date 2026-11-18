#!/usr/bin/env python3
"""PI-009 proposals inbox: a proposed fact is remembered only on approve and through the
memory CLI; a skill proposal is published only on approve; experiences are promoted or
deprecated without touching experience.jsonl; every decision is audited; ids never become paths.

Run: python3 tests/test_proposals.py
"""
import http.client
import json
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from _api_support import ApiCase  # noqa: E402

MEMORY = os.path.join(REPO, "bin", "agent-spec-memory.py")


class ProposalsApiTest(ApiCase):
    def setUp(self):
        super().setUp()
        spec = os.path.join(self.project, ".agent-spec")
        os.makedirs(os.path.join(spec, "bin"), exist_ok=True)
        shutil.copy(MEMORY, os.path.join(spec, "bin", "agent-spec-memory.py"))

    def post(self, body):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        raw = json.dumps(body).encode()
        conn.request("POST", "/api/proposals", body=raw, headers={
            "Host": "127.0.0.1:%d" % self.port, "Content-Type": "application/json",
            "Content-Length": str(len(raw)), "X-Agent-Spec-Token": self.token})
        resp = conn.getresponse()
        out = resp.status, json.loads(resp.read() or b"{}")
        conn.close()
        return out

    def propose(self, subject="retry budget"):
        res = subprocess.run([sys.executable, MEMORY, "propose", "--type", "constraint", "--subject", subject,
                              "--evidence", "review c1: 3 repeated failures",
                              "Never retry a failing test command more than twice without changing something."],
                             cwd=self.project, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        return self.get_json("/api/proposals")["pending"][0]["id"]

    def facts(self):
        res = subprocess.run([sys.executable, MEMORY, "list"], cwd=self.project, capture_output=True, text=True)
        return res.stdout

    def test_fact_is_remembered_only_on_approve(self):
        pid = self.propose()
        self.assertNotIn("retry budget", self.facts())
        status, body = self.post({"kind": "fact", "id": pid, "decision": "approve"})
        self.assertEqual(status, 200, body)
        self.assertIn("retry budget", self.facts())
        self.assertEqual(body["proposals"]["pending"], [])
        self.assertEqual(body["proposals"]["decided"][0]["decision"], "approve")

    def test_reject_keeps_memory_clean(self):
        pid = self.propose("other rule")
        self.assertEqual(self.post({"kind": "fact", "id": pid, "decision": "reject"})[0], 200)
        self.assertNotIn("other rule", self.facts())
        self.assertTrue(os.path.isfile(os.path.join(self.project, ".agent-spec", "memory", "proposed",
                                                    "rejected", pid + ".json")))

    def test_skill_publish_and_traversal_refused(self):
        folder = os.path.join(self.project, ".agent-spec", "skill-proposals")
        os.makedirs(folder)
        with open(os.path.join(folder, "triage.md"), "w") as fh:
            fh.write("---\nname: agent-spec-wf-triage\ndescription: x\n---\n# triage\n")
        status, body = self.post({"kind": "skill", "id": "../../etc/passwd", "decision": "approve"})
        self.assertEqual(status, 400)
        status, body = self.post({"kind": "skill", "id": "triage", "decision": "reject"})
        self.assertEqual(status, 200, body)
        self.assertFalse(os.path.exists(os.path.join(self.project, ".cursor", "skills", "agent-spec-wf-triage")))

    def test_experience_promote_writes_override_only(self):
        spec = os.path.join(self.project, ".agent-spec")
        with open(os.path.join(spec, "experience.jsonl"), "w") as fh:
            fh.write(json.dumps({"exp_id": "e1", "task": "fix flaky login test", "status": "success", "retries": 0}) + "\n")
        before = open(os.path.join(spec, "experience.jsonl")).read()
        with open(os.path.join(spec, "experience-reuse.jsonl"), "w") as fh:
            for _ in range(3):
                fh.write(json.dumps({"exp_id": "e1"}) + "\n")
        self.assertEqual([p["id"] for p in self.get_json("/api/proposals")["pending"]], ["e1"])
        self.assertEqual(self.post({"kind": "experience", "id": "e1", "decision": "approve"})[0], 400)
        self.assertEqual(self.post({"kind": "experience", "id": "e1", "decision": "promote"})[0], 200)
        self.assertEqual(open(os.path.join(spec, "experience.jsonl")).read(), before)
        self.assertEqual(self.get_json("/api/proposals")["pending"], [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
