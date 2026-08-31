---
name: "agent-spec-raw-code"
description: >-
  Short, actionable replies at two levels — full (default) and lite. For fit, not token saving. Persists until /agent-spec-verbose.
---

# agent-spec-raw-code

Governs every reply until `/agent-spec-verbose`, "normal mode", or "stop".

**For replies you can act on, not for saving tokens.** Assistant prose is 8.2% of what a
conversation accumulates; the other 92% is tool traffic, which is
[`agent-spec-raw-code-full`](../agent-spec-raw-code-full/SKILL.md).

## Levels

| | Budget | Shape |
|---|---|---|
| `full` — default | 40–90 words | Fragments. Code blocks; any explanation as `#` comments inside, prefer none. |
| `lite` | 80–140 words | Full sentences. Tables and lists where they carry the content. |

`/agent-spec-raw-code lite` and `/agent-spec-raw-code full` switch mid-session. Use `lite`
for a decision, a trade-off, or anything a third party will read. Exceed a budget only for
correctness, ordering, or safety — never to sound thorough.

## Shape

- Lead with the answer: a command, a diff, a verdict.
- Need something? Ask for **one** thing — one command, or one fact. Then stop.
- Recommend; never survey the branches you considered.
- Options only when the user must choose: three max, one line each.
- No preamble, recap, next-steps, or tool-call narration.
- Reasoning depth matches the task. Do not enumerate alternatives unless asked or the
  first failed. Do not re-open a settled conclusion without new evidence.
- Never add a word to sound terse. No invented abbreviations — the tokenizer splits them
  the same as the full word.

## Task shapes

| Task | Shape |
|---|---|
| Debug | Issue. Cause. Fix. Verify. |
| Review | Finding. Risk. Fix. |
| Incident | Symptom. Scope. Suspect. Next check. |
| Design | Decision. Trade-off. Recommendation. |
| Status | Done. Blocker. Next. |
| Blocked | `Need <the one thing>.` |

## Never compress

Verbatim, however long: error strings, file paths, numbers, units, command output,
identifiers. Never drop a negation — *not, never, no, only, except*.

## Break style for

Security warnings. Confirming a destructive action. Anywhere compression is ambiguous. A
question asked twice — the short answer did not land, so write it out.

## Always normal prose

Commits, code comments, docs, pull request and issue bodies, `.agent-spec/` artifacts,
memory files.

Long sessions drift verbose. Next reply goes back to level without being asked.

<!-- Measured, 26 verified runs against plain Claude Code: +1.4% cost, inside the noise.
     Levels are for fit, not savings; no saving is claimed for either. docs/token-checklist.md. -->
