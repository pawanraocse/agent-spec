"""DV-002: Cursor's hook log as a recording source (bin/aspec_platform/hook_logs.py)."""
import json
import os
import re
import sys
import tempfile
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_DIR, "bin"))
from aspec_platform import hook_logs  # noqa: E402

BAR = "═" * 40
PROJECT = "/home/dev/app"


def block(ts, step, cmd, code, payload, stderr="", ms=40):
    return (
        "[%s.000Z] Running hook 1 with timeout 3000ms\n%s\n%s\n%s\nCommand: %s (%dms) exit code: %d\n\n"
        "INPUT:\n%s\n\nOUTPUT:\n(empty)\n\nSTDERR:\n\n%s\n%s\n"
        % (ts, BAR, step, BAR, cmd, ms, code, json.dumps(payload, indent=2), stderr, BAR)
    )


def payload(event, gen, root="/Ubuntu-22.04" + PROJECT, **extra):
    d = {"hook_event_name": event, "conversation_id": "c1", "generation_id": gen, "model": "m",
         "cursor_version": "3.6.21", "workspace_roots": [root], "user_email": "someone@corp.io"}
    d.update(extra)
    return d


LOG = "".join([
    "[2026-11-13T10:34:06.729Z] Initializing Cursor Hooks Service...\n",
    block("2026-11-13T10:34:37", "beforeSubmitPrompt", "python3 .cursor/hooks/agent-spec-cursor-event.py", 1,
          payload("beforeSubmitPrompt", "g1", prompt="fix /home/dev/app/x.py api_key=abc123",
                  attachments=[{"type": "rule", "file_path": "\\\\wsl.localhost\\U\\home\\dev\\app\\AGENTS.md"}]),
          "execution error: spawn powershell ENOENT"),
    block("2026-11-13T10:34:37", "sessionStart", "~/.claude/hooks/agent-spec-session-start.sh", 0,
          payload("sessionStart", "g1"), "execution error: spawn powershell ENOENT"),
    block("2026-11-13T10:34:38", "sessionStart", "C:\\plugins\\postman/hooks/session-start", 0,
          payload("sessionStart", "g1")),
    block("2026-11-13T10:34:40", "stop", "python3 .cursor/hooks/agent-spec-cursor-event.py", 1,
          payload("stop", "g1", status="completed"), "execution error: spawn powershell ENOENT"),
    block("2026-11-13T10:34:40", "stop", "python3 .cursor/hooks/agent-spec-session-end.py", 1,
          payload("stop", "g1", status="completed"), "execution error: spawn powershell ENOENT"),
    block("2026-11-13T10:35:00", "stop", "python3 .cursor/hooks/agent-spec-cursor-event.py", 0,
          payload("stop", "g9", root="/home/other/repo")),
])


class HookLogsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.log = os.path.join(self.tmp, "cursor.hooks.ws.log")
        with open(self.log, "w", encoding="utf-8") as fh:
            fh.write(LOG)
        self.entries = hook_logs.harvest(PROJECT, files=[self.log])

    def test_parse_reads_every_block_with_timestamp(self):
        parsed = hook_logs.parse_log(LOG)
        self.assertEqual(len(parsed), 6)
        self.assertEqual(parsed[0]["step"], "beforeSubmitPrompt")
        self.assertEqual(parsed[0]["exit_code"], 1)
        self.assertEqual(parsed[0]["stderr"], "execution error: spawn powershell ENOENT")
        self.assertEqual(parsed[0]["epoch"], 1794566077)

    def test_harvest_keeps_only_our_hooks_for_this_project(self):
        cmds = [e["command"] for e in self.entries]
        self.assertEqual(len(cmds), 4)
        self.assertFalse(any("postman" in c for c in cmds))
        self.assertFalse(any(e["input"]["generation_id"] == "g9" for e in self.entries))

    def test_diagnose_counts_unstarted_exit_zero_as_failed_and_names_the_fix(self):
        report = hook_logs.diagnose(self.entries)
        self.assertEqual(report["failed"], 4)
        self.assertEqual(report["reasons"], {"execution error: spawn powershell ENOENT": 4})
        self.assertIn("cursor --remote wsl+Ubuntu-22.04 /home/dev/app", report["fix"])
        self.assertEqual(report["events"], ["beforeSubmitPrompt", "sessionStart", "stop"])

    def test_coverage_is_registered_minus_fired_with_a_hint_per_gap(self):
        proj = tempfile.mkdtemp()
        os.makedirs(os.path.join(proj, ".cursor"))
        with open(os.path.join(proj, ".cursor", "hooks.json"), "w") as fh:
            json.dump({"version": 1, "hooks": {e: [] for e in
                       ("stop", "sessionStart", "subagentStart", "preCompact", "afterFileEdit")}}, fh)
        cov = hook_logs.coverage(self.entries, proj)
        self.assertEqual((cov["registered"], cov["fired"]), (5, 2))
        self.assertEqual(cov["missing"], ["afterFileEdit", "preCompact", "subagentStart"])
        self.assertIn("compacts", cov["hints"]["preCompact"])
        self.assertIn("/agent-spec-hook-probe", cov["hints"]["afterFileEdit"])
        self.assertEqual(hook_logs.coverage(self.entries, self.tmp)["registered"], 0)  # no hooks.json

    def test_a_failure_stays_current_until_the_same_event_succeeds(self):
        # Cursor 3.30.8: sessionEnd on window_close cannot start, while every other hook works.
        later = "".join([
            block("2026-11-13T10:50:00", "sessionEnd", "python3 .cursor/hooks/agent-spec-session-end.py", 0,
                  payload("sessionEnd", "g1")),
            block("2026-11-13T11:00:00", "stop", "python3 .cursor/hooks/agent-spec-cursor-event.py", 0,
                  payload("stop", "g2")),
            block("2026-11-13T11:05:00", "sessionEnd", "python3 .cursor/hooks/agent-spec-session-end.py", -1,
                  payload("sessionEnd", "g2"), "Error: MainThreadShellExec not initialized"),
            block("2026-11-13T11:06:00", "stop", "python3 .cursor/hooks/agent-spec-cursor-event.py", 0,
                  payload("stop", "g3")),
        ])
        report = hook_logs.diagnose(self.entries + hook_logs.parse_log(later))
        self.assertEqual((report["failing_now"], report["failing_events"]), (1, ["sessionEnd"]))
        self.assertIn("stop hook writes the same receipt", report["fix"])
        self.assertNotIn("cursor --remote", report["fix"], "a UNC-style root alone is not the WSL case")

    def test_a_later_success_clears_the_fix(self):
        ok = block("2026-11-13T11:00:00", "stop", "python3 .cursor/hooks/agent-spec-cursor-event.py", 0,
                   payload("stop", "g2", root=PROJECT))
        entries = hook_logs.harvest(PROJECT, files=[self.log]) + hook_logs.parse_log(ok)
        report = hook_logs.diagnose(entries)
        self.assertEqual((report["failed"], report["failing_now"], report["fix"]), (4, 0, ""))

    def test_fixture_scrub_masks_email_paths_and_secrets(self):
        out = os.path.join(self.tmp, "fixtures")
        hook = hook_logs.load_hook(PROJECT, REPO_DIR)
        hook_logs.write_payloads(self.entries, out, hook._redact, PROJECT, fixture=True)
        self.assertEqual(sorted(os.listdir(out)), ["beforeSubmitPrompt.json", "sessionStart.json", "stop.json"])
        with open(os.path.join(out, "beforeSubmitPrompt.json"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("someone@corp.io", text)
        self.assertNotIn("/home/dev", text)
        self.assertNotIn("abc123", text)
        data = json.loads(text)
        self.assertEqual(data["workspace_roots"], ["/workspace/project"])
        self.assertEqual(data["attachments"][0]["file_path"], "/workspace/project/AGENTS.md")
        self.assertEqual(data["generation_id"], "gen-recorded-1")

    def test_recorded_fixtures_are_scrubbed_and_parse_through_the_hook(self):
        rec = os.path.join(REPO_DIR, "tests", "fixtures", "hooks", "recorded")
        hook = hook_logs.load_hook(PROJECT, REPO_DIR)
        names = sorted(n for n in os.listdir(rec) if n.endswith(".json"))
        self.assertTrue(names)
        for name in names:
            with open(os.path.join(rec, name), encoding="utf-8") as fh:
                text = fh.read()
            for leak in (os.path.expanduser("~") + "/", "wsl.localhost"):
                self.assertNotIn(leak, text, name)
            emails = set(re.findall(r"[\\w.+-]+@[\\w-]+\\.[\\w.-]+", text))
            self.assertLessEqual(emails, {"developer@example.com"}, name)
            data = json.loads(text)
            if data["hook_event_name"] in hook.EVENTS:
                row = hook.handle_event(text)
                self.assertEqual(row["event"], data["hook_event_name"])
                self.assertEqual(row["conversation_id"], "conv-recorded-1")

    def test_backfill_skips_rows_the_live_hook_wrote_and_keeps_same_second_calls(self):
        """Review fix: the live hook stamps milliseconds and the log whole seconds, so a
        successful invocation must not be appended twice; two different tool calls in the
        same second of one generation are both kept."""
        hook = hook_logs.load_hook(PROJECT, REPO_DIR)
        cmd = "python3 .cursor/hooks/agent-spec-cursor-event.py"
        calls = [payload("postToolUse", "g2", tool_name="Grep", tool_use_id="tu-%d" % i,
                         tool_input={"pattern": "p%d" % i}, tool_output="", duration=5) for i in (1, 2)]
        log = os.path.join(self.tmp, "same-second.log")
        with open(log, "w", encoding="utf-8") as fh:
            fh.write("".join(block("2026-11-13T11:00:00", "postToolUse", cmd, 0, c) for c in calls))
        entries = hook_logs.harvest(PROJECT, files=[log])
        events = os.path.join(self.tmp, "metrics", "events.jsonl")
        os.makedirs(os.path.dirname(events))
        live = hook.handle_event(json.dumps(calls[0]), "postToolUse", now=1794567600.437)  # 11:00:00.437Z
        with open(events, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(live) + "\n")
        self.assertEqual(hook_logs.backfill(entries, events, hook), 1)
        with open(events, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh]
        self.assertEqual(sorted(r["tool_use_id"] for r in rows), ["tu-1", "tu-2"])

    def test_backfill_writes_one_row_per_step_and_is_idempotent(self):
        events = os.path.join(self.tmp, "metrics", "events.jsonl")
        hook = hook_logs.load_hook(PROJECT, REPO_DIR)
        self.assertEqual(hook_logs.backfill(self.entries, events, hook), 2)
        self.assertEqual(hook_logs.backfill(self.entries, events, hook), 0)
        with open(events, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh]
        self.assertEqual([r["event"] for r in rows], ["beforeSubmitPrompt", "stop"])
        self.assertTrue(all(r["ts"].startswith("2026-11-13T10:34") for r in rows))
        self.assertNotIn("abc123", rows[0].get("prompt", ""))


if __name__ == "__main__":
    unittest.main()
