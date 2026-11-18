#!/usr/bin/env python3
"""P3-006 / P3-007: the Repos page API lists mesh members with drift and edges per repo pair,
answers a file query, and adds or removes a member behind the POST guards, logging each run.

Run: python3 tests/test_mesh_api.py
"""
import http.client
import json
import os
import shutil
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from _api_support import ApiCase  # noqa: E402

DEMO = os.path.join(REPO, "examples", "mesh-demo")


class MeshApiTest(ApiCase):
    def post(self, body, token=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=300)
        raw = json.dumps(body).encode()
        headers = {"Host": "127.0.0.1:%d" % self.port, "Content-Type": "application/json", "Content-Length": str(len(raw))}
        if token:
            headers["X-Agent-Spec-Token"] = self.token
        conn.request("POST", "/api/mesh", body=raw, headers=headers)
        resp = conn.getresponse()
        out = resp.status, json.loads(resp.read() or b"{}")
        conn.close()
        return out

    def test_add_query_remove(self):
        self.assertEqual(self.get_json("/api/mesh")["repos"], [])
        self.assertEqual(self.post({"action": "add", "path": os.path.join(DEMO, "acme-common")}, token=False)[0], 401)
        self.assertEqual(self.post({"action": "add", "path": "/definitely/not/here"})[0], 400)
        for name in ("acme-common", "orders-api"):
            status, body = self.post({"action": "add", "path": os.path.join(DEMO, name), "repo_id": name})
            self.assertEqual(status, 200, body)
        data = self.get_json("/api/mesh")
        self.assertEqual(sorted(r["repo_id"] for r in data["repos"]), ["acme-common", "orders-api"])
        self.assertEqual(data["pairs"][0]["source"], "orders-api")
        self.assertEqual(data["pairs"][0]["by_type"], {"imports": 2})
        q = self.get_json("/api/mesh/query?file=acme-common:acme_common/money.py")
        self.assertIn("orders-api", q["repos_affected"])
        self.assertEqual(self.post({"action": "remove", "repo_id": "../x"})[0], 400)
        status, body = self.post({"action": "remove", "repo_id": "orders-api"})
        self.assertEqual(status, 200, body)
        self.assertEqual([r["repo_id"] for r in body["mesh"]["repos"]], ["acme-common"])
        with open(os.path.join(self.project, ".agent-spec", "metrics", "automation.jsonl")) as fh:
            names = [json.loads(l)["name"] for l in fh]
        self.assertEqual(names.count("mesh-add"), 2)
        self.assertIn("mesh-remove", names)


if __name__ == "__main__":
    unittest.main(verbosity=1)
