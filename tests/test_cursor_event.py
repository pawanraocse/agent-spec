#!/usr/bin/env python3
"""Tests for hooks/cursor-event.py (DV-001): one test per registered event, on the documented contract."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO, "hooks", "cursor-event.py")
FIXTURES = os.path.join(REPO, "tests", "fixtures", "hooks")


def fixture(name, root):
    with open(os.path.join(FIXTURES, name + ".json"), encoding="utf-8") as fh:
        data = json.load(fh)
    data["workspace_roots"] = [root]
    return data


class CursorEventTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".agent-spec"))
        self.cwd = tempfile.mkdtemp()  # deliberately not the workspace: rows must follow workspace_roots[0]
        self.events = os.path.join(self.root, ".agent-spec", "metrics", "events.jsonl")

    def run_hook(self, payload, env=None):
        proc = subprocess.run([sys.executable, HOOK], input=json.dumps(payload) if not isinstance(payload, str) else payload,
                              text=True, capture_output=True, cwd=self.cwd, timeout=10,
                              env=dict(os.environ, **(env or {})))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")
        if not os.path.isfile(self.events):
            return []
        with open(self.events, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def one(self, name):
        rows = self.run_hook(fixture(name, self.root))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["event"], name)
        self.assertEqual(row["conversation_id"], "conv-fixture-1")
        self.assertEqual(row["generation_id"], "gen-fixture-1")
        self.assertEqual(row["model"], "claude-sonnet-4-5")
        self.assertEqual(row["cursor_version"], "2.1.0")
        self.assertTrue(row["id"] and row["ts"].endswith("Z"))
        return row

    def test_before_submit_prompt_redacted(self):
        row = self.one("beforeSubmitPrompt")
        self.assertIn("/agent-spec-investigate", row["prompt"])
        self.assertNotIn("sk-test-0123456789abcdef", row["prompt"])
        self.assertEqual(row["attachments"], 1)

    def test_post_tool_use(self):
        row = self.one("postToolUse")
        self.assertEqual((row["tool_name"], row["status"], row["duration_ms"]), ("Read", "ok", 45))
        self.assertEqual(row["tool_use_id"], "tu-1")
        self.assertTrue(row["ranged"])
        self.assertIn("auth.ts", row["target"])
        self.assertGreater(row["output_bytes"], 0)

    def test_post_tool_use_failure(self):
        row = self.one("postToolUseFailure")
        self.assertEqual((row["status"], row["failure_type"], row["duration_ms"]), ("error", "timeout", 30000))
        self.assertIn("timed out", row["error_message"])

    def test_subagent_start(self):
        row = self.one("subagentStart")
        self.assertEqual((row["subagent_id"], row["subagent_type"]), ("sub-1", "agent-spec-search"))
        self.assertEqual(row["parent_conversation_id"], "conv-fixture-1")
        self.assertEqual(row["tool_call_id"], "tu-3")

    def test_subagent_stop(self):
        row = self.one("subagentStop")
        self.assertEqual((row["status"], row["duration_ms"], row["tool_call_count"]), ("completed", 1450, 4))
        self.assertIn("3 callers", row["summary"])
        self.assertEqual(row["summary_bytes"], len("3 callers: src/app.ts:12, src/cli.ts:40, tests/auth.test.ts:8"))
        self.assertTrue(row["agent_transcript_path"].endswith("sub-1.jsonl"))

    def test_after_file_edit(self):
        row = self.one("afterFileEdit")
        self.assertEqual((row["edit_count"], row["chars_removed"]), (1, len("return null")))
        self.assertTrue(row["file_path"].endswith("auth.ts"))

    def test_after_agent_response(self):
        row = self.one("afterAgentResponse")
        self.assertIn("login test fails", row["text"])
        self.assertGreater(row["text_chars"], 0)

    def test_pre_compact(self):
        row = self.one("preCompact")
        self.assertEqual((row["trigger"], row["context_tokens"], row["context_usage_percent"]), ("auto", 120000, 85))

    def test_stop(self):
        row = self.one("stop")
        self.assertEqual((row["status"], row["loop_count"]), ("completed", 0))

    def test_text_is_truncated(self):
        payload = fixture("afterAgentResponse", self.root)
        payload["text"] = "x" * 10000
        row = self.run_hook(payload)[0]
        self.assertLessEqual(len(row["text"]), 2001)
        self.assertEqual(row["text_chars"], 10000)

    def test_unharnessed_workspace_writes_nothing(self):
        payload = fixture("stop", self.cwd)
        self.assertEqual(self.run_hook(payload), [])
        self.assertFalse(os.path.exists(os.path.join(self.cwd, ".agent-spec")))

    def test_fail_open_on_garbage(self):
        self.assertEqual(self.run_hook("{not json"), [])
        self.assertEqual(self.run_hook(""), [])

    def test_record_mode_saves_payload(self):
        self.run_hook(fixture("beforeSubmitPrompt", self.root), env={"AGENT_SPEC_HOOK_RECORD": "1"})
        path = os.path.join(self.root, ".agent-spec", "metrics", "hook-payloads", "beforeSubmitPrompt.json")
        with open(path, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved["hook_event_name"], "beforeSubmitPrompt")
        self.assertNotIn("sk-test-0123456789abcdef", saved["prompt"])


if __name__ == "__main__":
    unittest.main()
