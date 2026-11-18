#!/usr/bin/env python3
"""Risk panel API (H-030, P4-016): pending tier-3 actions listed, approve/deny behind the
same POST guards as every other control action, and the decision trail in risk.jsonl.

Run: python3 tests/test_risk_api.py
"""
import http.client
import importlib.util
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _api_support import ApiCase  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("agent_spec_risk", os.path.join(REPO, "bin", "agent-spec-risk.py"))
risk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(risk)


class RiskApiTest(ApiCase):
    def post(self, body, token=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        raw = json.dumps(body).encode()
        headers = {"Host": "127.0.0.1:%d" % self.port, "Content-Type": "application/json", "Content-Length": str(len(raw))}
        if token:
            headers["X-Agent-Spec-Token"] = self.token
        conn.request("POST", "/api/risk", body=raw, headers=headers)
        resp = conn.getresponse()
        out = resp.status, json.loads(resp.read() or b"{}")
        conn.close()
        return out

    def block(self):
        r = {"tool": "Write", "target": "hub.py", "file": "hub.py", "tier": 3, "reasons": ["25 files depend on it"]}
        return r, risk.record_blocked(self.project, r, "c1")

    def test_pending_and_approve_once(self):
        r, key = self.block()
        data = self.get_json("/api/risk")
        self.assertEqual([p["key"] for p in data["pending"]], [key])
        self.assertEqual(data["counts"]["blocked"], 1)
        self.assertEqual(self.post({"key": key, "decision": "approve"}, token=False)[0], 401)
        status, body = self.post({"key": key, "decision": "approve"})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["risk"]["pending"], [])
        self.assertTrue(risk.consume_approval(self.project, r))
        self.assertEqual(self.post({"key": key, "decision": "approve"})[0], 400, "already decided")

    def test_bad_decision_rejected(self):
        _, key = self.block()
        status, body = self.post({"key": key, "decision": "maybe"})
        self.assertEqual(status, 400)
        self.assertIn("approve or deny", body["error"])

    def test_deny_is_logged_with_who(self):
        _, key = self.block()
        self.post({"key": key, "decision": "deny"})
        recent = self.get_json("/api/risk")["recent"]
        self.assertEqual(recent[0]["event"], "denied")
        self.assertEqual(recent[0]["by"], "dashboard")


if __name__ == "__main__":
    unittest.main(verbosity=1)
