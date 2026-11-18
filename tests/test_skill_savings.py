#!/usr/bin/env python3
"""Per-chat raw-code savings (skill_savings.py): mode timeline, levers, the re-send multiplier,
the like-for-like comparison gate, and the API fields that carry them."""
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "bin"))

from aspec_platform import skill_savings, traces, views  # noqa: E402


def ev(n, event, conv, gen, **kw):
    return dict(id="e%d" % n, ts="2026-11-15T10:00:%02d.000Z" % n, event=event, conversation_id=conv,
                generation_id=gen, model="claude", cursor_version="3.30.14", **kw)


class SkillSavingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.project = os.path.join(self.tmp, "proj")
        os.makedirs(os.path.join(self.project, ".agent-spec", "metrics"))
        os.makedirs(os.path.join(self.project, "src"))
        with open(os.path.join(self.project, "src", "big.py"), "w") as fh:
            fh.write("x" * 4000)                       # 4,000 B file
        rows = [
            # request 1: raw-code-full on; a ranged read of 400 of 4,000 B, then a 40-char edit
            ev(1, "beforeSubmitPrompt", "c1", "g1", prompt="/agent-spec-raw-code-full fix big"),
            ev(2, "postToolUse", "c1", "g1", tool_name="Read", target="src/big.py", ranged=True, read_chars=400, status="ok"),
            ev(3, "afterFileEdit", "c1", "g1", file_path=os.path.join(self.project, "src", "big.py"), edit_count=1,
               chars_added=20, chars_removed=20),
            ev(4, "stop", "c1", "g1", status="completed"),
            # request 2, same chat: two plain tool calls (later model calls), then verbose turns the mode off
            ev(5, "beforeSubmitPrompt", "c1", "g2", prompt="next step"),
            ev(6, "postToolUse", "c1", "g2", tool_name="Grep", target="pattern=x", status="ok"),
            ev(7, "postToolUse", "c1", "g2", tool_name="Grep", target="pattern=y", status="ok"),
            ev(8, "stop", "c1", "g2", status="completed"),
            ev(9, "beforeSubmitPrompt", "c1", "g3", prompt="/agent-spec-verbose"),
            ev(10, "stop", "c1", "g3", status="completed"),
        ]
        with open(os.path.join(self.project, ".agent-spec", "metrics", "events.jsonl"), "w") as fh:
            fh.writelines(json.dumps(r) + "\n" for r in rows)
        self.traces, self.spans = traces.all_traces(self.project, None)

    def session(self):
        by = {}
        for s in self.spans:
            by.setdefault(s["trace_id"], []).append(s)
        return skill_savings.for_session(self.project, None, [t for t in self.traces if t["session_id"] == "c1"], by)

    def test_levers_and_mode(self):
        s = self.session()
        self.assertEqual(s["by_lever"]["ranged_reads"], 900)        # (4000 - 400) / 4
        self.assertEqual(s["by_lever"]["writes"], 990)              # (4000 - 40) / 4
        self.assertEqual(s["kept_out"], 1890)
        self.assertEqual([r["raw_code"] for r in s["requests"]], [True, True, False])   # on until /agent-spec-verbose
        self.assertEqual(s["raw_code"]["since_request"], 1)
        self.assertEqual(s["raw_code"]["requests_on"], 2)

    def test_skill_cost_is_netted_out(self):
        s = self.session()
        cost = skill_savings.skill_bytes("agent-spec-raw-code-full") // 4
        self.assertGreater(cost, 0)
        self.assertEqual(s["skill_cost"]["tokens"], cost)            # invoked once, in request 1
        self.assertEqual(s["skill_cost"]["resend"], cost * 4)        # and re-sent on the 4 later calls
        self.assertEqual(s["net_kept_out"], 1890 - cost)
        self.assertEqual(s["net_resend_avoided"], (1890 - cost) * 4)

    def test_resend_multiplier_counts_later_calls(self):
        s = self.session()
        # after request 1: 2 tool calls in request 2 + 2 later requests = 4 later model calls
        self.assertEqual(s["requests"][0]["later_calls"], 4)
        self.assertEqual(s["resend_avoided"], 1890 * 4)

    def test_overview_gates_the_ratio_on_sample_size(self):
        o = skill_savings.overview(self.project, None, self.traces, self.spans)
        self.assertEqual(o["kept_out"], 1890)
        self.assertEqual(o["chats_with_raw_code"], 1)
        self.assertIsNone(o["compare"]["lift"])                     # 2 vs 0 comparable requests: no ratio
        self.assertEqual(o["top"][0]["session_id"], "c1")

    def test_api_fields(self):
        detail = views.request_detail(self.project, None, "g2")
        self.assertEqual(detail["session_savings"]["kept_out"], 1890)
        convs = views.list_conversations(self.project, None, {})
        self.assertEqual(convs["conversations"][0]["savings"]["kept_out"], 1890)
        self.assertTrue(convs["conversations"][0]["savings"]["raw_code"]["active"])


if __name__ == "__main__":
    unittest.main()
