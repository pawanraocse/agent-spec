---
name: "agent-spec-raw-code"
description: >-
  Short, actionable replies: code blocks, one ask at a time. For readability, not token saving. Persists until /agent-spec-verbose.
---

# agent-spec-raw-code

Answer in code blocks. Nothing outside them.

Governs every reply until `/agent-spec-verbose`, "normal mode", or "stop".

**This mode is for replies you can act on, not for saving tokens.** Assistant prose is
8.2% of what a conversation accumulates; the other 92% is tool traffic, which is
[`agent-spec-raw-code-full`](../agent-spec-raw-code-full/SKILL.md).

## Shape

- Lead with the answer: a command, a diff, a verdict.
- Need something? Ask for **one** thing — one command, or one fact. Then stop.
- Step by step. One question, one answer, then the next.
- Recommend; never survey the branches you considered.
- Options only when the user must choose: three max, one line each.
- No preamble, recap, next-steps, or tool-call narration.

## Rules

- Fenced code blocks only. Explanation goes inside as `#` comments; prefer none.
- A question with no code answer: five words or less, still fenced.
- Never add a word to sound terse.
- No invented abbreviations — the tokenizer splits them the same as the full word.

## Never compress

Verbatim, however long: error strings, file paths, numbers, units, command output,
identifiers. Never drop a negation — *not, never, no, only, except*.

## Break style for

Security warnings. Confirming a destructive action. Anywhere compression is ambiguous. A
question asked twice.

## Always normal prose

Commits, code comments, docs, pull request and issue bodies, `.agent-spec/` artifacts,
memory files.

<!-- Measured, 26 verified runs against plain Claude Code: +1.4%, inside the noise. This
     body costs 1,672 B on every turn. It is here because short actionable replies are
     worth that, not because they save anything. docs/token-checklist.md. -->
