#!/usr/bin/env python3
"""Tests for the Index health panel API (H-020): graph state from .status.json and git,
log sizes, and the Rebuild graph action behind the same POST guards as /api/automations.

Run: python3 tests/test_health.py
"""
import http.client
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _api_support import ApiCase  # noqa: E402


class HealthApiTest(ApiCase):
    def post(self, body, token=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        raw = json.dumps(body).encode()
        headers = {"Host": "127.0.0.1:%d" % self.port, "Content-Type": "application/json",
                   "Content-Length": str(len(raw))}
        if token:
            headers["X-Agent-Spec-Token"] = self.token
        conn.request("POST", "/api/index-health", body=raw, headers=headers)
        resp = conn.getresponse()
        out = resp.status, json.loads(resp.read() or b"{}")
        conn.close()
        return out

    def test_missing_graph_is_a_problem(self):
        data = self.get_json("/api/index-health")
        self.assertEqual(data["graph"]["state"], "missing")
        self.assertIn("graph not built", data["problems"])
        names = [entry["name"] for entry in data["logs"]]
        self.assertIn("events", names)
        self.assertEqual(data["provenance"], "measured")

    def test_failed_status_is_reported(self):
        gdir = os.path.join(self.project, ".agent-spec", "graph")
        os.makedirs(gdir, exist_ok=True)
        with open(os.path.join(gdir, "knowledge-graph.json"), "w") as fh:
            fh.write("{}")
        with open(os.path.join(gdir, ".status.json"), "w") as fh:
            json.dump({"state": "failed", "finished": "2026-11-18T10:00:00", "error": "OSError: disk full",
                       "last_failure": {"finished": "2026-11-18T10:00:00", "error": "OSError: disk full"}}, fh)
        data = self.get_json("/api/index-health")
        self.assertEqual(data["graph"]["state"], "failed")
        self.assertEqual(data["graph"]["error"], "OSError: disk full")

    def test_post_requires_token_and_known_action(self):
        self.assertEqual(self.post({"action": "rebuild-graph"}, token=False)[0], 401)
        status, body = self.post({"action": "rm -rf"})
        self.assertEqual(status, 400)
        self.assertIn("unknown action", body["error"])

    def test_rebuild_graph_runs_and_is_logged(self):
        with open(os.path.join(self.project, "a.py"), "w") as fh:
            fh.write("import os\n")
        status, body = self.post({"action": "rebuild-graph"})
        self.assertEqual(status, 200, body)
        self.assertTrue(body["ok"], body)
        self.assertEqual(body["health"]["graph"]["state"] in ("current", "behind"), True, body["health"]["graph"])
        with open(os.path.join(self.project, ".agent-spec", "metrics", "automation.jsonl")) as fh:
            rows = [json.loads(line) for line in fh]
        self.assertEqual(rows[-1]["name"], "graph-refresh")
        self.assertEqual(rows[-1]["status"], "built")
        self.assertEqual(rows[-1]["source"], "dashboard")


if __name__ == "__main__":
    unittest.main(verbosity=1)
