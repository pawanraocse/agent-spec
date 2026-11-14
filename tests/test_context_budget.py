#!/usr/bin/env python3
"""Context budget: reset arithmetic, Cursor's context counters, and /api/context.

Run: python3 tests/test_context_budget.py
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_DIR)
from _api_support import ApiCase  # noqa: E402
from aspec_platform import context_budget as cb, cursor_sessions, traces  # noqa: E402

BREAKDOWN = [{"id": "system_prompt", "estimatedTokens": 500}, {"id": "tools", "estimatedTokens": 8500},
             {"id": "rules", "estimatedTokens": 5600}, {"id": "skills", "estimatedTokens": 3400},
             {"id": "conversation", "estimatedTokens": 102000}]


def make_store(user_dir, chats):
    os.makedirs(os.path.join(user_dir, "globalStorage"), exist_ok=True)
    db = sqlite3.connect(os.path.join(user_dir, "globalStorage", "state.vscdb"))
    db.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value BLOB)")
    for cid, data in chats.items():
        db.execute("INSERT OR REPLACE INTO cursorDiskKV VALUES (?, ?)", ("composerData:" + cid, json.dumps(data)))
    db.execute("INSERT OR REPLACE INTO cursorDiskKV VALUES ('composerData:broken', 'not json')")
    db.commit()
    db.close()


class ArithmeticTest(unittest.TestCase):
    def test_reset_breakeven_matches_agent_spec_tokens(self):
        # carry 12,000; reset once 22,500; after 1,800; saving 10,200 -> 2.2 calls
        b = cb.budget(120000, 18000, 200000)
        self.assertEqual((b["carry_per_call"], b["reset_once"], b["saving_per_call"]), (12000, 22500, 10200))
        self.assertEqual((b["breakeven_calls"], b["verdict"], b["percent"], b["growth"]), (2.2, "reset", 60.0, 6.67))
        self.assertEqual(b["carried_tokens"], 102000)

    def test_small_chats_carry_and_fresh_chats_are_fresh(self):
        self.assertEqual(cb.budget(30000, 18000)["verdict"], "carry")   # 22,500 / 1,200 = 18.8 calls
        self.assertEqual(cb.budget(18000, 18000)["verdict"], "fresh")
        self.assertEqual(cb.budget(10000, 18000)["floor"], 10000, "floor never exceeds the context")
        self.assertIsNone(cb.budget(None, 18000))
        self.assertIsNone(cb.budget(0, 18000))

    def test_fixed_tokens_excludes_only_the_conversation(self):
        bd = {c["id"]: c["estimatedTokens"] for c in BREAKDOWN}
        self.assertEqual(cb.fixed_tokens(bd), 18000)
        self.assertIsNone(cb.fixed_tokens({}))

    def test_request_series_dedupes_and_never_reads_requests_as_context(self):
        row = {"event": "afterAgentResponse", "conversation_id": "c", "generation_id": "g1", "ts": "2",
               "input_tokens": 157633, "cache_read_tokens": 134144, "output_tokens": 10}
        early = dict(row, generation_id="g0", ts="1", input_tokens=36176, cache_read_tokens=22016)
        rows = [row, dict(row), early, dict(row, conversation_id="other")]
        pts = cb.request_series(rows, "c")
        self.assertEqual([p["input"] for p in pts], [36176, 157633])
        s = cb.series_summary(pts)
        self.assertEqual((s["requests"], s["input_total"], s["cache_read_share"]), (2, 193809, 0.806))
        self.assertEqual(cb.request_tokens({"input_tokens": 100, "cache_read_tokens": 500}), 600)  # disjoint buckets


class StoreTest(unittest.TestCase):
    def test_context_usage_reads_counters_and_excludes_subagents(self):
        user = tempfile.mkdtemp()
        make_store(user, {
            "big": {"contextTokensUsed": 120000, "contextTokenLimit": 200000, "contextUsagePercent": 60.0,
                    "name": "Long chat", "subagentComposerIds": ["sub"],
                    "promptTokenBreakdown": {"categories": BREAKDOWN}},
            "small": {"contextTokensUsed": 19000},
            "sub": {"contextTokensUsed": 4000},
            "empty": {"contextTokensUsed": 0}})
        u = cursor_sessions.context_usage(os.path.join(user, "globalStorage", "state.vscdb"))
        self.assertEqual(sorted(u["by_id"]), ["big", "small"])
        self.assertEqual(u["floor"], 19000, "a subagent is not a fresh chat")
        big = u["by_id"]["big"]
        self.assertEqual((big["used"], big["limit"], big["name"], big["breakdown"]["conversation"]),
                         (120000, 200000, "Long chat", 102000))

    def test_unreadable_store_is_empty(self):
        self.assertEqual(cursor_sessions.context_usage("/nonexistent/state.vscdb"), {})


class ContextApiTest(ApiCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ("AGENT_SPEC_CURSOR_STORE", "AGENT_SPEC_CURSOR_USER_DIR")}
        self.user = tempfile.mkdtemp()
        make_store(self.user, {
            "conv-1": {"contextTokensUsed": 120000, "contextTokenLimit": 200000, "name": "Long chat",
                       "promptTokenBreakdown": {"categories": BREAKDOWN}},
            "conv-2": {"contextTokensUsed": 25000, "name": "Short chat"}})
        os.environ["AGENT_SPEC_CURSOR_USER_DIR"] = self.user
        os.environ["AGENT_SPEC_CURSOR_STORE"] = "1"
        traces._USAGE["at"] = 0.0
        super().setUp()
        metrics = os.path.join(self.project, ".agent-spec", "metrics")
        os.makedirs(metrics, exist_ok=True)
        base = {"conversation_id": "conv-1", "cursor_version": "2.1.0"}
        with open(os.path.join(metrics, "events.jsonl"), "w") as fh:
            for i, (gen, tokens) in enumerate((("gen-1", 36176), ("gen-2", 157633))):
                b = dict(base, generation_id=gen)
                fh.write(json.dumps(dict(b, id="p%d" % i, ts="2026-11-13T10:0%d:00Z" % i, event="beforeSubmitPrompt",
                                         prompt="hi")) + "\n")
                fh.write(json.dumps(dict(b, id="r%d" % i, ts="2026-11-13T10:0%d:30Z" % i, event="afterAgentResponse",
                                         text="ok", input_tokens=tokens, output_tokens=5,
                                         cache_read_tokens=tokens // 2)) + "\n")
        open(os.path.join(self.project, ".agent-spec", ".context-nudged-conv-1"), "w").close()

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        traces._USAGE["at"] = 0.0
        super().tearDown() if hasattr(super(), "tearDown") else None

    def test_overview_ranks_chats_and_uses_the_chats_own_fixed_part(self):
        body = self.get_json("/api/context")
        self.assertEqual((body["chats"], body["by_verdict"]["reset"], body["provenance"]), (2, 1, "measured"))
        top = body["top"][0]
        self.assertEqual((top["session_id"], top["name"]), ("conv-1", "Long chat"))
        b = top["budget"]
        self.assertEqual((b["floor"], b["verdict"], b["nudged"]), (18000, "reset", True))
        self.assertEqual(top["billed"]["points"], [36176, 157633])
        short = body["top"][1]["budget"]
        self.assertEqual((short["floor"], short["floor_source"]), (18000, "smallest chat on this machine"))

    def test_conversation_and_request_carry_the_budget(self):
        conv = next(c for c in self.get_json("/api/conversations")["conversations"] if c["session_id"] == "conv-1")
        self.assertEqual(conv["context"]["budget"]["used"], 120000)
        detail = self.get_json("/api/requests/gen-2")
        self.assertEqual(detail["context"]["billed"]["generations"], ["gen-1", "gen-2"])
        resp = next(s for s in detail["spans"] if s["kind"] == "response")
        self.assertEqual(resp["attributes"]["input_tokens"], 157633)


if __name__ == "__main__":
    unittest.main()
