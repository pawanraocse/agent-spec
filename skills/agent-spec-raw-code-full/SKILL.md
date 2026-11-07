---
name: "agent-spec-raw-code-full"
description: >-
  Fewer turns, less context, cheaper writes, capped tool output, stable prefix. The 92% of a conversation that is tool traffic. Persists until /agent-spec-verbose.
---

# agent-spec-raw-code-full

Governs every reply and tool call until `/agent-spec-verbose`, "normal mode", or "stop".

Anything put into context is re-sent on **every** turn after it. Ordered by measured size.

## 0. Preflight — install and onboarding are internal

Before the first reply, in the opened workspace root `<ws>`:

1. **No `<ws>/.agent-spec/`** → install it yourself:
   `PKG="$(cat ~/.cursor/skills/.algosec-agent-spec-root)"` then
   `"$PKG/install.sh" --register "<ws>"`. It copies the harness, indexes the graph and
   creates `.agent-spec/.onboarding-needed`. Never run it with `--force`. Never touch
   `.env` or secrets. If the root marker file is missing or `install.sh` fails, report
   the exact error in one line, then continue the request without the harness.
2. **`.agent-spec/.onboarding-needed` exists** (or the digest says **ONBOARDING NEEDED**)
   → run the `/agent-spec-onboard` procedure yourself.
3. Then continue the user's request.

Never tell the user to run install or onboard, never report either as pending. Skip the
preflight when `<ws>` is the package clone itself or has no source files (empty folder).

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
file — `CURSOR.md` / always-on rules, a skill body — mid-session unless that edit is the
task. It invalidates the prefix and re-writes it at 1.25x.

## 6. Reset — the largest single move

`/agent-spec-snapshot`, then `/agent-spec-compact` (new Cursor chat) at each task
boundary — measured 480,083 to 53,191 tokens. Mid-task, keep the thread if the working
conversation matters more than tokens.

## Shape

- Lead with the answer. Ask for **one** thing at a time, then stop.
- Recommend; never survey branches. Options: three max, one line each.
- No preamble, recap, next-steps, or tool-call narration.

## When to break this mode (Complexity Override)

This mode suppresses conversational filler, not reasoning. A fixed-ratio terse rule
applied to a genuinely complex algorithm will produce a wrong answer more cheaply.

Break into normal prose when **all three** are true:
1. The task requires non-trivial algorithmic reasoning (cryptography, distributed
   consensus, complex state machines, or novel data structures).
2. The first implementation attempt failed its own tests.
3. A brief reasoning trace would produce a correct second attempt.

Resume raw-code-full immediately after the algorithm is verified green.
Say "complexity override" at the start of the reasoning section so it is visible in
the transcript, and "resuming raw-code-full" when you return.

## Never compress

Verbatim, however long: error strings, file paths, numbers, units, command output,
identifiers. Never drop a negation — *not, never, no, only, except*.

## Break style for

Security warnings. Confirming a destructive action. Anywhere compression is ambiguous. A
question asked twice.

## Always normal prose

Commits, code comments, docs, pull request and issue bodies, `.agent-spec/` artifacts,
memory files.

<!-- Figures: docs/token-checklist.md. Caveman prose measured 0 and was removed.
     Complexity Override: inspired by TPP-diversity finding (arXiv:2605.08541) —
     fixed-ratio output rules degrade on off-distribution (high-complexity) tasks. -->
