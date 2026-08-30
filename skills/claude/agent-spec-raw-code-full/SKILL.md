---
name: "agent-spec-raw-code-full"
description: >-
  Full token discipline: fewer turns, smaller context, cheaper writes. For long sessions. Persists until /agent-spec-verbose.
---

# agent-spec-raw-code-full

Governs every reply and tool call until `/agent-spec-verbose`, "normal mode", or "stop".

**Use on long sessions only.** This body is itself re-read every turn; on short tasks it
costs more than it saves. Measured — see the comment at the end.

## 1. Fewer turns

- Batch independent tool calls into one message.
- Never poll. Background long commands and collect once.
- Never split one edit across three calls.
- Never re-read a file to confirm an edit landed. `Edit` fails loudly.

## 2. Smaller context

Context cannot be compressed — a cache read is cheap *because* the bytes are unchanged.
Reset instead.

- `./.agent-spec/bin/agent-spec-tokens.py context` says when a reset pays. Usually now.
- Reset at each task boundary: `/agent-spec-snapshot`, then a new session.
- `graphify-cli.py context --task "<task>"` before opening any file. Then `query --file`.
- Read line ranges. Never whole files.
- Broad sweep → `agent-spec-search` subagent. Test suite, build, linter →
  `agent-spec-verify`. Their context is discarded; yours is re-read.

## 3. Cheaper writes

- Targeted `Edit`, never a rewrite — a rewrite generates every unchanged line too.
- Never echo a file back to show what changed.

## 4. Cap tool output

`| head -50`. `--stat` before a full diff. `-q` on builds. `2>/dev/null` on expected
failures.

## 5. Caveman prose

Drop articles, copulas, connectives. "Edge resolution broken, 0 of 475 resolved, cause:
import string written as target."

The never-compress list below overrides this. Always.

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

<!-- Ordering is by measured share of cost: cache re-reads 56-69%, cache writes 13-30%,
     output 13-21%, tool results under 1%. Sections 1-2 exist because turn count times
     context size dominates everything else. The benchmark, the published figures this
     contradicts, and the reason section 5 is last: docs/token-efficiency.md. All of it
     is kept out of this file because a skill body is re-read every turn — the first
     version of this skill was 6,770 bytes and lost its own benchmark by 5% because of
     exactly that. -->
