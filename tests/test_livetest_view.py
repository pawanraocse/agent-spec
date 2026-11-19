#!/usr/bin/env python3
"""Live tests page: /api/livetest reads the runner's JSON, the POST launches one run at a time,
and the runner's matrix definition stays well formed. Stdlib only; no model is called."""
import http.client
import importlib.util
import json
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(os.path.dirname(HERE), "bin")
sys.path.insert(0, BIN)
sys.path.insert(0, HERE)
from aspec_platform import livetest_view  # noqa: E402
from _api_support import ApiCase  # noqa: E402


def load_runner():
    spec = importlib.util.spec_from_file_location("livetest", os.path.join(BIN, "agent-spec-livetest.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def report(run_id, passed=3, failed=0):
    return {"schema": 1, "run_id": run_id, "started": "2026-11-19T00:00:00Z", "finished": "2026-11-19T00:01:00Z",
            "models": ["m:7b"], "full": False, "summary": {"PASS": passed, "FAIL": failed, "SKIP": 1},
            "host": {"platform": "x", "python": "3.12", "wsl": False}, "ollama": {"url": None, "models": []},
            "cases": [{"id": "L01", "status": "PASS", "title": "t", "seconds": 0.1}]}


class LiveTestApi(ApiCase):
    def write(self, name, obj):
        d = os.path.join(self.project, ".agent-spec", "eval", "live")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, name), "w") as fh:
            json.dump(obj, fh)
        return d

    def post(self, body):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/livetest", body=json.dumps(body), headers={
            "Content-Type": "application/json", "X-Agent-Spec-Token": self.token,
            "Origin": "http://127.0.0.1:%d" % self.port, "Host": "127.0.0.1:%d" % self.port})
        resp = conn.getresponse()
        out = resp.status, json.loads(resp.read() or b"{}")
        conn.close()
        return out

    def test_empty_project(self):
        out = self.get_json("/api/livetest")
        self.assertIsNone(out["latest"])
        self.assertEqual(out["history"], [])
        self.assertIsNone(out["running"])
        self.assertTrue(out["available"])

    def test_latest_and_history(self):
        self.write("20261119T000000-aaaaaa.json", report("20261119T000000-aaaaaa", 2, 1))
        self.write("20261119T000100-bbbbbb.json", report("20261119T000100-bbbbbb"))
        self.write("latest.json", report("20261119T000100-bbbbbb"))
        self.write("20261119T000200-cccccc.json", {"broken": True})  # no summary: left out
        out = self.get_json("/api/livetest")
        self.assertEqual(out["latest"]["run_id"], "20261119T000100-bbbbbb")
        self.assertEqual([r["run_id"] for r in out["history"]], ["20261119T000000-aaaaaa", "20261119T000100-bbbbbb"])
        self.assertNotIn("cases", out["history"][0])

    def test_stale_running_file_is_cleared(self):
        d = self.write("running.json", {"pid": 2 ** 22 + 7, "started": "x", "tier": "live"})
        self.assertIsNone(self.get_json("/api/livetest")["running"])
        self.assertFalse(os.path.exists(os.path.join(d, "running.json")))

    def test_post_rejects_a_bad_tier(self):
        status, out = self.post({"tier": "everything"})
        self.assertEqual(status, 400)
        self.assertIn("tier", out["error"])

    def test_post_launches_once(self):
        fake = mock.Mock(pid=os.getpid())  # a live pid, so the run counts as in progress
        with mock.patch.object(livetest_view.subprocess, "Popen", return_value=fake) as popen:
            status, out = self.post({"tier": "quick", "all_models": True})
            self.assertEqual(status, 200, out)
            argv = popen.call_args[0][0]
            self.assertIn("--only", argv)
            self.assertEqual(argv[-2:], ["--models", "all"])
            self.assertEqual(out["live"]["running"]["tier"], "quick")
            status, out = self.post({"tier": "live"})
            self.assertEqual(status, 409)
            self.assertEqual(popen.call_count, 1)

    def test_post_needs_origin_and_token(self):
        status, _, _ = self.request("/api/livetest", method="POST", token=False)
        self.assertIn(status, (401, 403))


class RunnerMatrix(unittest.TestCase):
    def test_cases_are_unique_and_bound(self):
        mod = load_runner()
        ids = [c[0] for c in mod.CASES]
        self.assertEqual(len(ids), len(set(ids)))
        for cid, tier, per_model, area, owed, title, criterion in mod.CASES:
            self.assertIn(tier, ("smoke", "live", "full"))
            self.assertTrue(callable(getattr(mod.Run, cid)), cid)
            self.assertTrue(title and criterion)
            self.assertTrue(not owed or owed.startswith("H-"))

    def test_tier_selection(self):
        mod = load_runner()
        args = mock.Mock(only=None, full=False)
        self.assertNotIn("L17", [c[0] for c in mod.selected(args)])
        args.full = True
        self.assertIn("L17", [c[0] for c in mod.selected(args)])
        args.only = "l06,L09"
        self.assertEqual([c[0] for c in mod.selected(args)], ["L06", "L09"])

    def test_markdown_escapes_pipes(self):
        mod = load_runner()
        r = report("r1")
        r["cases"] = [{"id": "L01", "owed": "", "title": "t", "model": None, "status": "FAIL", "seconds": 1.0,
                       "error": "a | b\nc"}]
        md = mod.markdown(r)
        self.assertIn("a \\| b c", md)


if __name__ == "__main__":
    unittest.main()
