#!/usr/bin/env python3
"""Today page (/api/today): the attention queue ranks blocked before broken before improve, each
fix that needs judgement is a skill, repeated autopilot rows fold, and one unreadable source never
blanks the page. Stdlib only; no model is called."""
import json
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
sys.path.insert(0, HERE)
from aspec_platform import mission  # noqa: E402
from _api_support import ApiCase  # noqa: E402


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def write_events(project, rows):
    d = os.path.join(project, ".agent-spec", "metrics")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "events.jsonl"), "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def chat(conv, gen, prompt, ts):
    base = {"conversation_id": conv, "generation_id": gen, "ts": ts}
    return [dict(base, id=gen + "-p", event="beforeSubmitPrompt", prompt=prompt),
            dict(base, id=gen + "-s", event="stop", status="completed")]


class TodayApi(ApiCase):
    def test_shape_and_empty_project(self):
        d = self.get_json("/api/today")
        for key in ("project", "attention", "counts", "value", "pulse", "recent", "skills", "errors"):
            self.assertIn(key, d)
        self.assertEqual(len(d["pulse"]), mission.PULSE_DAYS)
        self.assertEqual(set(d["counts"]), set(mission.LEVELS))

    def test_unreviewed_chat_is_a_session_review_skill(self):
        ts = now_iso()
        write_events(self.project, chat("c1", "g1", "why does login fail", ts) + chat("c1", "g2", "and the fix?", ts))
        d = self.get_json("/api/today")
        review = [i for i in d["attention"] if i["id"] == "review"]
        self.assertEqual(len(review), 1, d["attention"])
        action = review[0]["action"]
        self.assertEqual(action["kind"], "skill")
        self.assertEqual(action["prompt"], "/agent-spec-session-review c1")
        self.assertEqual(review[0]["link"], "/chats/c1")
        self.assertEqual({r["prompt"] for r in d["recent"]}, {"why does login fail", "and the fix?"})

    def test_reviewed_chat_is_not_offered(self):
        ts = now_iso()
        write_events(self.project, chat("c2", "g1", "q1", ts) + chat("c2", "g2", "q2", ts))
        rev = os.path.join(self.project, ".agent-spec", "metrics", "reviews")
        os.makedirs(rev, exist_ok=True)
        with open(os.path.join(rev, "c2.json"), "w") as fh:
            json.dump({"conversation_id": "c2", "grade": "B", "findings": []}, fh)
        d = self.get_json("/api/today")
        self.assertFalse([i for i in d["attention"] if i["id"] == "review"])


class Ranking(unittest.TestCase):
    def test_blocked_before_broken_before_improve(self):
        items = [mission._item(lvl, lvl, lvl, "", mission._link("x", "/")) for lvl in ("improve", "blocked", "broken")]
        items.sort(key=lambda i: mission.LEVELS[i["level"]])
        self.assertEqual([i["level"] for i in items], ["blocked", "broken", "improve"])

    def test_autopilot_folds_repeats(self):
        rows = [{"name": "graph-refresh", "status": "ok", "reason": "graph already current", "ts": "3"},
                {"name": "graph-refresh", "status": "ok", "reason": "graph already current", "ts": "2"},
                {"name": "skills-sync", "status": "ok", "reason": "installed 2", "ts": "1"}]
        out = mission._autopilot(rows, {"graph-refresh": "Refresh the knowledge graph"})
        self.assertEqual([(r["id"], r["times"]) for r in out], [("graph-refresh", 2), ("skills-sync", 1)])
        self.assertEqual(out[0]["label"], "Refresh the knowledge graph")

    def test_failed_source_is_reported_not_raised(self):
        errors = []
        with mock.patch("aspec_platform.risk_view.overview", side_effect=RuntimeError("boom")):
            items = mission._attention("/nonexistent", None, errors, [])
        self.assertTrue(any(e.startswith("risk: boom") for e in errors), errors)
        self.assertIsInstance(items, list)

    def test_failing_live_test_offers_read_only_investigation(self):
        live = {"latest": {"cases": [{"id": "L07", "title": "Two-part answer", "status": "FAIL", "error": "misses x",
                                       "criterion": "names x", "model": "m"}]}, "running": None}
        errors = []
        with mock.patch("aspec_platform.livetest_view.overview", return_value=live):
            items = mission._attention("/nonexistent", None, errors, [])
        lt = [i for i in items if i["id"] == "livetest"]
        self.assertEqual(len(lt), 1)
        self.assertEqual(lt[0]["level"], "broken")
        self.assertTrue(lt[0]["action"]["console"])
        self.assertTrue(lt[0]["action"]["prompt"].startswith("/agent-spec-investigate Live test L07"))


if __name__ == "__main__":
    unittest.main()
