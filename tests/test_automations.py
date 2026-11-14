#!/usr/bin/env python3
"""Tests for the Automations panel API (HA-006): counts measured from automation.jsonl, and a
switch that writes .agent-spec/automation.json behind the same guards as every other POST.

Run: python3 tests/test_automations.py
"""
import http.client
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _api_support import ApiCase  # noqa: E402


class AutomationsApiTest(ApiCase):
    def post(self, body, token=True, origin=None, ctype="application/json"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        raw = json.dumps(body).encode()
        headers = {"Host": "127.0.0.1:%d" % self.port, "Content-Type": ctype, "Content-Length": str(len(raw))}
        if token:
            headers["X-Agent-Spec-Token"] = self.token
        if origin:
            headers["Origin"] = origin
        conn.request("POST", "/api/automations", body=raw, headers=headers)
        resp = conn.getresponse()
        out = resp.status, json.loads(resp.read() or b"{}")
        conn.close()
        return out

    def log(self, *rows):
        metrics = os.path.join(self.project, ".agent-spec", "metrics")
        os.makedirs(metrics, exist_ok=True)
        with open(os.path.join(metrics, "automation.jsonl"), "a") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
            fh.write("not json\n")

    def test_empty_project_lists_every_automation_enabled(self):
        data = self.get_json("/api/automations")
        ids = [a["id"] for a in data["automations"]]
        self.assertEqual(ids, ["register", "graph-refresh", "snapshot-rotate", "snapshot-followup", "context-nudge"])
        self.assertTrue(all(a["enabled"] and a["runs"] == 0 and a["last"] is None for a in data["automations"]))
        self.assertEqual(data["totals"]["runs"], 0)

    def test_counts_come_from_the_log(self):
        self.log({"ts": "2026-11-14T01:00:00Z", "name": "graph-refresh", "status": "started"},
                 {"ts": "2026-11-14T02:00:00Z", "name": "graph-refresh", "status": "failed"},
                 {"ts": "2026-11-14T03:00:00Z", "name": "snapshot-rotate", "status": "ok", "duration_ms": 40},
                 {"ts": "2026-11-14T03:00:01Z", "name": "not-an-automation", "status": "ok"})
        data = self.get_json("/api/automations")
        by = {a["id"]: a for a in data["automations"]}
        self.assertEqual((by["graph-refresh"]["runs"], by["graph-refresh"]["succeeded"], by["graph-refresh"]["failed"]), (2, 1, 1))
        self.assertEqual(by["graph-refresh"]["last"]["status"], "failed")
        self.assertEqual(by["snapshot-rotate"]["duration_ms_total"], 40)
        self.assertEqual(data["totals"]["runs"], 3, "unknown names and bad lines are ignored")
        self.assertEqual(data["recent"][0]["name"], "snapshot-rotate", "newest first")

    def test_switch_writes_config_and_round_trips(self):
        status, data = self.post({"id": "graph-refresh", "enabled": False})
        self.assertEqual(status, 200)
        cfg = json.load(open(os.path.join(self.project, ".agent-spec", "automation.json")))
        self.assertEqual(cfg, {"disabled": ["graph-refresh"]})
        self.assertFalse({a["id"]: a for a in data["automations"]}["graph-refresh"]["enabled"])
        status, data = self.post({"id": "graph-refresh", "enabled": True})
        self.assertEqual(json.load(open(os.path.join(self.project, ".agent-spec", "automation.json"))), {"disabled": []})

    def test_switch_is_guarded(self):
        self.assertEqual(self.post({"id": "graph-refresh", "enabled": False}, token=False)[0], 401)
        self.assertEqual(self.post({"id": "graph-refresh", "enabled": False}, origin="http://evil.example")[0], 403)
        self.assertEqual(self.post({"id": "graph-refresh", "enabled": False}, ctype="text/plain")[0], 415)
        self.assertEqual(self.post({"id": "../../etc", "enabled": False})[0], 400)
        self.assertEqual(self.post({"id": "graph-refresh", "enabled": "no"})[0], 400)
        self.assertFalse(os.path.exists(os.path.join(self.project, ".agent-spec", "automation.json")))

    def test_environment_switch_wins(self):
        os.environ["AGENT_SPEC_CONTEXT_NUDGE"] = "0"
        self.addCleanup(os.environ.pop, "AGENT_SPEC_CONTEXT_NUDGE", None)
        by = {a["id"]: a for a in self.get_json("/api/automations")["automations"]}
        self.assertFalse(by["context-nudge"]["enabled"])
        self.assertTrue(by["context-nudge"]["env_off"] and not by["context-nudge"]["switched_off"])


if __name__ == "__main__":
    unittest.main()
