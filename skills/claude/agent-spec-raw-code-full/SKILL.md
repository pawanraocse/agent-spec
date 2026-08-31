---
name: "agent-spec-raw-code-full"
description: >-
  Fewer turns, less context, cheaper writes, capped tool output, stable prefix. The 92% of a conversation that is tool traffic. Persists until /agent-spec-verbose.
---

# agent-spec-raw-code-full

Governs every reply and tool call until `/agent-spec-verbose`, "normal mode", or "stop".

Anything put into context is re-sent on **every** turn after it. Ordered by measured size.

## 1. Fewer turns — 95,190 B each

- Batch independent tool calls into one message.
- Never poll. Background long commands and collect once.
- Never split one edit across three calls.
- Never re-read a file to confirm an edit landed. `Edit` fails loudly.
- Carry conclusions forward. Do not re-plan after every tool call.

## 2. Do not read what you can query — 35,814 B per file avoided

- `graphify-cli.py context --task "<task>"`, then `query --file`. 152 B, not 35,966 B.
- `grep -n` for the line, then read a range around it. Never a whole file.
- `git diff --stat` before any full diff.
- Broad sweep → `agent-spec-search` subagent. Noisy command → `agent-spec-verify`.
  Their context is discarded; yours is re-read.

## 3. Cheaper writes — 45.7% of everything a conversation accumulates

Tool call inputs are mostly file bodies going back out.

- Targeted `Edit`, never a rewrite. A rewrite generates every unchanged line, then carries
  it for the rest of the session.
- Never echo a file back to show what changed.

## 4. Cap what tools return — 46.1%

`| head -50`. `-q` on builds. `2>/dev/null` on expected failures. A test run is 5,117 B
raw and 107 B as a verdict plus failures.

## 5. Keep the prefix stable — cache reads are 56.7% of the bill

A cache read bills at 0.1x only while the bytes are unchanged. Do not edit an always-on
file — `CLAUDE.md`, the output style, a skill body — mid-session unless that edit is the
task. It invalidates the prefix and re-writes it at 1.25x.

## 6. Reset — the largest single move

`/agent-spec-snapshot`, then a new session, at each task boundary. `/compact` keeps the
thread and is usually the better trade mid-task — measured 480,083 to 53,191 tokens.

## Shape

- Lead with the answer. Ask for **one** thing at a time, then stop.
- Recommend; never survey branches. Options: three max, one line each.
- No preamble, recap, next-steps, or tool-call narration.

## Never compress

Verbatim, however long: error strings, file paths, numbers, units, command output,
identifiers. Never drop a negation — *not, never, no, only, except*.

## Break style for

Security warnings. Confirming a destructive action. Anywhere compression is ambiguous. A
question asked twice.

## Always normal prose

Commits, code comments, docs, pull request and issue bodies, `.agent-spec/` artifacts,
memory files.

<!-- Figures: docs/token-checklist.md. Caveman prose measured 0 and was removed. -->
