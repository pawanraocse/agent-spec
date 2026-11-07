#!/usr/bin/env python3
"""Tests for hooks/cursor-event.py (AF-001)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK_SCRIPT = os.path.join(REPO, "hooks", "cursor-event.py")
FIXTURES = os.path.join(REPO, "tests", "fixtures", "hooks")


class CursorEventHookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, ".agent-spec", "metrics"), exist_ok=True)
        self.events_file = os.path.join(self.tmp, ".agent-spec", "metrics", "events.jsonl")

    def run_hook(self, payload_dict: dict, event_flag: str = "postToolUse"):
        proc = subprocess.run(
            [sys.executable, HOOK_SCRIPT, f"--{event_flag}"],
            input=json.dumps(payload_dict),
            text=True,
            capture_output=True,
            cwd=self.tmp,
            timeout=5,
        )
        self.assertEqual(proc.returncode, 0)

    def read_events(self):
        if not os.path.isfile(self.events_file):
            return []
        with open(self.events_file, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def test_post_tool_use_event(self):
        with open(os.path.join(FIXTURES, "postToolUse.json"), encoding="utf-8") as fh:
            fixture = json.load(fh)
        self.run_hook(fixture, "postToolUse")
        events = self.read_events()
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["event"], "postToolUse")
        self.assertEqual(ev["session_id"], "sess-1234")
        self.assertEqual(ev["tool"], "Read")
        self.assertEqual(ev["status"], "success")
        self.assertEqual(ev["duration_ms"], 45)

    def test_post_tool_use_failure(self):
        with open(os.path.join(FIXTURES, "postToolUseFailure.json"), encoding="utf-8") as fh:
            fixture = json.load(fh)
        self.run_hook(fixture, "postToolUseFailure")
        events = self.read_events()
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["status"], "failed")
        self.assertIn("error", ev)

    def test_subagent_events(self):
        with open(os.path.join(FIXTURES, "subagentStart.json"), encoding="utf-8") as fh:
            fixture = json.load(fh)
        self.run_hook(fixture, "subagentStart")

        with open(os.path.join(FIXTURES, "subagentStop.json"), encoding="utf-8") as fh:
            fixture2 = json.load(fh)
        self.run_hook(fixture2, "subagentStop")

        events = self.read_events()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["event"], "subagentStart")
        self.assertEqual(events[1]["event"], "subagentStop")
        self.assertEqual(events[1]["duration_ms"], 1450)

    def test_fail_open_on_malformed_input(self):
        proc = subprocess.run(
            [sys.executable, HOOK_SCRIPT],
            input="invalid json {[[",
            text=True,
            capture_output=True,
            cwd=self.tmp,
            timeout=5,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(self.read_events(), [])


if __name__ == "__main__":
    unittest.main()
