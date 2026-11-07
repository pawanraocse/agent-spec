#!/usr/bin/env python3
"""Tests for the dashboard JSON API (D-020): read-only endpoints over a seeded platform.db.

Run: python3 tests/test_api.py
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _api_support import REPO_DIR, ApiCase  # noqa: E402


class ApiTest(ApiCase):
    def test_health_reports_schema_and_counts(self):
        data = self.get_json("/api/health")
        self.assertEqual(data["ok"], True)
        self.assertGreaterEqual(data["schema"], 1)
        self.assertEqual(data["rows"]["requests"], 2)
        self.assertEqual(data["rows"]["tasks"], 2)

    def test_runs_list_newest_first_with_token_totals(self):
        data = self.get_json("/api/runs")
        ids = [r["request_id"] for r in data["runs"]]
        self.assertEqual(ids, ["R2", "R1"])
        r1 = data["runs"][1]
        self.assertEqual(r1["tokens_total"], 150)
        self.assertEqual(r1["step_count"], 2)

    def test_runs_filter_by_status_and_limit(self):
        data = self.get_json("/api/runs?status=failed")
        self.assertEqual([r["request_id"] for r in data["runs"]], ["R2"])
        data = self.get_json("/api/runs?limit=1")
        self.assertEqual(len(data["runs"]), 1)

    def test_run_detail_has_ordered_steps(self):
        data = self.get_json("/api/runs/R1")
        self.assertEqual(data["run"]["request_id"], "R1")
        self.assertEqual([s["name"] for s in data["steps"]], ["Read", "agent-spec-implement"])

    def test_unknown_run_is_404_json(self):
        status, headers, body = self.request("/api/runs/NOPE")
        self.assertEqual(status, 404)
        self.assertIn("application/json", headers["content-type"])

    def test_sql_injection_in_params_is_inert(self):
        data = self.get_json("/api/runs?status=%27%3B%20DROP%20TABLE%20requests%3B--")
        self.assertEqual(data["runs"], [])
        self.assertEqual(self.get_json("/api/health")["rows"]["requests"], 2)

    def test_tasks_endpoint(self):
        data = self.get_json("/api/tasks")
        self.assertEqual({t["task_id"] for t in data["tasks"]}, {"D-001", "D-020"})
        data = self.get_json("/api/tasks?status=open")
        self.assertEqual([t["task_id"] for t in data["tasks"]], ["D-020"])

    def test_missing_database_gives_503_not_traceback(self):
        os.remove(self.dbpath)
        status, _, body = self.request("/api/health")
        self.assertEqual(status, 503)
        self.assertNotIn(b"Traceback", body)

    def test_index_served_with_token_and_has_no_external_urls(self):
        status, headers, body = self.request("/?token=%s" % self.token, token=False)
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["content-type"])
        self.assertIsNone(re.search(rb"(?:src|href)=[\"']https?://", body))

    def test_server_module_imports_stdlib_only(self):
        with open(os.path.join(REPO_DIR, "bin", "aspec_platform", "serve.py"), encoding="utf-8") as fh:
            text = fh.read()
        mods = set(re.findall(r"^(?:from|import)\s+([A-Za-z_][\w]*)", text, re.M))
        allowed = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else None
        local = {"common", "db", "aspec_platform"}
        for mod in mods - local - {"__future__"}:
            if allowed is not None:
                self.assertIn(mod, allowed, mod)
            self.assertNotIn(mod, {"flask", "fastapi", "requests", "uvicorn", "aiohttp"})


    def test_v2_index_injects_aspec_token_meta(self):
        dist = os.path.join(REPO_DIR, "bin", "aspec_platform", "ui", "dist", "index.html")
        if not os.path.isfile(dist):
            self.skipTest("ui dist not built; run: (cd ui-src && npm run build)")
        status, _, body = self.request("/?token=%s" % self.token, token=False)
        self.assertEqual(status, 200)
        self.assertIn(b'name="aspec-token"', body)
        self.assertIn(self.token.encode(), body)

    def test_spa_fallback_serves_index_on_client_route(self):
        dist = os.path.join(REPO_DIR, "bin", "aspec_platform", "ui", "dist", "index.html")
        if not os.path.isfile(dist):
            self.skipTest("ui dist not built; run: (cd ui-src && npm run build)")
        status, headers, body = self.request("/sessions")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("content-type", ""))
        self.assertIn(b'id="root"', body)

    def test_status_bar_endpoint(self):
        data = self.get_json("/api/status_bar")
        self.assertIn("graph", data)
        self.assertIn("hooks", data)
        self.assertIn("doctor", data)
        self.assertIn("active_jobs", data)



if __name__ == "__main__":
    unittest.main()
