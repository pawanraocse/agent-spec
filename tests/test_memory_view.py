#!/usr/bin/env python3
"""Memory controls on the dashboard: add, edit (supersede), forget and prune go through the
memory CLI, are reflected in the listing at once, re-ingested, and audited; team facts and
unknown ids are refused; a prune without apply deletes nothing.

Run: python3 tests/test_memory_view.py
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
TEXT = "Route handlers are a public contract; changing a path needs a deprecation window."


class MemoryApiTest(ApiCase):
    def setUp(self):
        super().setUp()
        self.spec = os.path.join(self.project, ".agent-spec")
        os.makedirs(os.path.join(self.spec, "bin"), exist_ok=True)
        shutil.copy(MEMORY, os.path.join(self.spec, "bin", "agent-spec-memory.py"))

    def post(self, body):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        raw = json.dumps(body).encode()
        conn.request("POST", "/api/memory", body=raw, headers={
            "Host": "127.0.0.1:%d" % self.port, "Content-Type": "application/json",
            "Content-Length": str(len(raw)), "X-Agent-Spec-Token": self.token})
        resp = conn.getresponse()
        out = resp.status, json.loads(resp.read() or b"{}")
        conn.close()
        return out

    def listing(self):
        return self.get_json("/api/memory")["facts"]

    def add(self, subject="routes contract", text=TEXT, kind="constraint"):
        status, body = self.post({"action": "add", "type": kind, "subject": subject, "text": text})
        self.assertEqual(status, 200, body)
        return next(f for f in body["memory"]["facts"] if f["subject"] == subject)

    def audit(self):
        with open(os.path.join(self.spec, "metrics", "proposals.jsonl"), encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def test_add_lists_the_text_and_audits(self):
        fact = self.add()
        self.assertEqual(fact["body"], TEXT)
        self.assertEqual(fact["status"], "active")
        self.assertEqual(self.audit()[-1]["decision"], "add")
        self.assertIn(fact["fact_id"], [f["fact_id"] for f in self.listing()])

    def test_edit_supersedes_and_keeps_history(self):
        old = self.add()
        status, body = self.post({"action": "edit", "id": old["fact_id"], "type": "constraint",
                                  "subject": "routes are a contract", "text": TEXT})
        self.assertEqual(status, 200, body)  # same text, new subject: an edit, not a duplicate
        by_id = {f["fact_id"]: f for f in body["memory"]["facts"]}
        self.assertEqual(by_id[old["fact_id"]]["status"], "superseded")
        new = next(f for f in by_id.values() if f["subject"] == "routes are a contract")
        self.assertEqual(new["supersedes"], old["fact_id"])
        with open(os.path.join(self.spec, "memory", "INDEX.md"), encoding="utf-8") as fh:
            index = fh.read()
        self.assertNotIn(old["fact_id"].rsplit("-", 1)[-1], index)  # the index lists active facts only
        status, body = self.post({"action": "edit", "id": new["fact_id"], "type": "constraint",
                                  "subject": "routes are a contract", "text": TEXT})
        self.assertEqual((status, body.get("error")), (400, "nothing changed"))

    def test_forget_moves_the_file_out(self):
        fact = self.add()
        status, body = self.post({"action": "forget", "id": fact["fact_id"]})
        self.assertEqual(status, 200, body)
        self.assertNotIn(fact["fact_id"], [f["fact_id"] for f in body["memory"]["facts"]])
        self.assertTrue(os.path.isfile(os.path.join(self.spec, "memory", "forgotten", fact["fact_id"] + ".md")))
        self.assertEqual(self.post({"action": "forget", "id": fact["fact_id"]})[0], 400)

    def test_prune_preview_deletes_nothing(self):
        fact = self.add(kind="gotcha")
        path = os.path.join(self.spec, "memory", "facts", fact["fact_id"] + ".md")
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(raw.replace("created: %s" % fact["created"], "created: 2020-01-01"))
        status, body = self.post({"action": "prune", "older_than": 30})
        self.assertEqual(status, 200, body)
        self.assertTrue(body["preview"])
        self.assertEqual([f["fact_id"] for f in body["facts"]], [fact["fact_id"]])
        self.assertTrue(os.path.isfile(path))
        status, body = self.post({"action": "prune", "older_than": 30, "apply": True})
        self.assertEqual(status, 200, body)
        self.assertFalse(os.path.isfile(path))
        self.assertEqual(self.post({"action": "prune", "older_than": "x"})[0], 400)

    def test_refusals(self):
        self.assertEqual(self.post({"action": "drop-table"})[0], 400)
        self.assertEqual(self.post({"action": "forget", "id": "../../etc/passwd"})[0], 400)
        self.assertEqual(self.post({"action": "add", "type": "constraint", "subject": "x", "text": TEXT})[0], 400)
        self.assertEqual(self.post({"action": "add", "type": "rumour", "subject": "ok subject", "text": TEXT})[0], 400)
        team = os.path.join(self.spec, "team-facts")
        os.makedirs(team)
        with open(os.path.join(team, "t1.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nid: t1\ntype: constraint\nsubject: team rule\n---\nA team rule that is long enough.\n")
        self.assertEqual(self.listing()[0]["scope"], "team")
        status, body = self.post({"action": "forget", "id": "t1"})
        self.assertEqual(status, 400)
        self.assertIn("team facts", body["error"])

    def test_subject_newline_cannot_forge_frontmatter(self):
        res = subprocess.run([sys.executable, MEMORY, "add", "--type", "gotcha", "--subject", "a\nstatus: expired",
                              TEXT], cwd=self.project, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        fact = self.listing()[0]
        self.assertEqual((fact["subject"], fact["status"]), ("a status: expired", "active"))


if __name__ == "__main__":
    unittest.main()
