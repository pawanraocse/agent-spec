---
name: "agent-spec-raw-code-full"
description: >-
  Fewer turns, less context, cheaper writes, capped tool output, stable prefix. The 92% of a conversation that is tool traffic. Persists until /agent-spec-verbose.
---

# agent-spec-raw-code-full

Governs every reply and tool call until `/agent-spec-verbose`, "normal mode", or "stop".

The tool discipline itself (batch calls, never poll, graph before reading, `grep -n` then a
ranged Read, capped output, targeted edits, subagents for sweeps, snapshot and compact at task
boundaries) is the always-on rule `.cursor/rules/agent-spec.mdc`. This skill makes it binding
and adds only what that rule does not carry. Anything in context is re-sent on every later call.

## Preflight

Before the first reply, from the opened workspace, run once:
`python3 "$(cat ~/.cursor/skills/.algosec-agent-spec-root)/bin/agent-spec-ensure.py"`.
`"next": "/agent-spec-onboard"` → run that procedure yourself. `"registered": "failed"` or
`"refused"`, or no marker file → report the `error` in one line and continue without the
harness. Never ask the user to install or onboard. Skip in the package clone itself or a
workspace with no source files.

## Beyond the always-on rule

- Text search: if `rg` is on PATH, `rg -n --max-columns 200`; otherwise `grep -n`. Never
  install it or retry on failure.
- Never echo a file back to show what changed.
- Keep the prefix stable: do not edit an always-on file (`CURSOR.md`, `.cursor/rules/`, a
  skill body) mid-session unless that edit is the task. Cache reads bill at 0.1x only while
  the bytes are unchanged; an edit re-writes the prefix at 1.25x.

## Shape

- Lead with the answer. Ask for **one** thing at a time, then stop.
- Recommend; never survey branches. Options: three max, one line each.
- No preamble, recap, next-steps, or tool-call narration.
- Verbatim, never compressed: error strings, file paths, numbers, units, command output,
  identifiers. Never drop a negation (*not, never, no, only, except*).
- Full prose for security warnings, confirming a destructive action, anything compression
  would make ambiguous, and a question asked twice. Commits, code comments, docs, PR and issue
  bodies, `.agent-spec/` artifacts and memory files are always normal prose.

## Complexity Override

This mode cuts filler, not reasoning. When a non-trivial algorithm (crypto, consensus, state
machine, novel data structure) failed its own tests once, write the reasoning out: say
"complexity override", then "resuming raw-code-full" once it is green.
