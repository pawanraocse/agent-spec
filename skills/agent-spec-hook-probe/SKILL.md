---
name: "agent-spec-hook-probe"
description: >-
  One command proves every registered Cursor hook fires: it triggers the events, harvests the real payloads and reports coverage, with no steps for the user. Use for live hook verification, after a Cursor upgrade, or when the dashboard shows "hooks firing" below full.
dashboard:
  category: Project
  icon: radar
  emits: [hook-payloads]
---

# agent-spec-hook-probe

The user types `/agent-spec-hook-probe` once. You do everything else; never hand the user a
list of steps. `afterAgentResponse` and `stop` fire only after your turn ends, so the `stop`
hook sends `/agent-spec-hook-probe collect` back into this chat by itself.

`P` is `bin/agent-spec-platform.py` in the package repo, `./.agent-spec/bin/agent-spec-platform.py`
in a registered project.

## No argument — fire

1. `python3 P hooks`. If it prints a `fix:` line, hooks cannot start from this window. If
   `command -v cursor` succeeds, run the `cursor --remote ...` command from that line yourself
   and tell the user to rerun the probe in the window that opens. Otherwise give them that
   one command. Stop either way.
2. If it prints `coverage: ... — complete`, say so in one line and stop.
3. Write `.agent-spec/.hook-probe-pending` (contents: UTC time). Then, in one message, make
   these calls in parallel:
   - Read `.cursor/hooks.json` (`preToolUse`, `postToolUse`)
   - Read `.agent-spec/metrics/hook-probe-missing.txt`, which must not exist (`postToolUseFailure`)
   - Write `.agent-spec/metrics/hook-probe.txt` with the UTC time (`afterFileEdit`)
   - Task → `agent-spec-search`: "Return the path of `.cursor/hooks.json`. Nothing else."
     (`subagentStart`, `subagentStop`)
4. Reply with one line: "Probe fired — collecting automatically." End the turn.

## `collect` — harvest and report

1. Package repo: `python3 P hooks --fixtures tests/fixtures/hooks/recorded`. Registered
   project: `python3 P hooks --payloads`. Delete `.agent-spec/metrics/hook-probe.txt` and
   `.agent-spec/.hook-probe-pending` if either is left.
2. Reply with the `coverage:` line and its `missing` lines verbatim, then one sentence. Full
   coverage: "Every registered hook fires; the dashboard status bar now shows it." Only
   `preCompact` missing: it fires when Cursor compacts a long chat, and the dashboard backfills
   it within 60 s, so nothing is owed now. Anything else missing: quote the reason line from the
   output; do not guess a cause.

## Rules

- Never edit hook code, `hooks.json` or fixtures by hand here, and never mark a backlog row
  done.
- If `collect` arrives with no pending marker and no probe file, run step 1 anyway; it is safe.
- Never paste raw hook-log entries; the CLI writes scrubbed payloads only.
