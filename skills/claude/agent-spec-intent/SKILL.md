---
name: "agent-spec-intent"
description: >-
  Pre-pipeline: capture an idea in the originator's own words into 00-INTENT.md, before gate 0 turns it into REQ- syntax. Use when an idea has to survive a handoff.
---

# intent

An idea reaches engineering as a line in someone's scrollback or a ticket a third person
rewrote. Each rewrite moves it further from what the originator actually meant. This
captures it once — what is wanted, why, under which constraints, in their own language —
and commits it as `00-INTENT.md` before any of it is turned into requirement syntax.

## When to skip

Capturing intent is not free; a document that repeats what a sentence already said is
ceremony. Skip it when:

- The change is small enough to need no design pass. Say "small-change mode", go straight
  to `/agent-spec-implement`.
- You are both the originator and the builder and the idea already fits in one
  requirement. Type it into gate 0 directly.

Capture intent when the idea has to **survive a handoff** — the person with the idea is
not the person who will build it — or when it needs a brainstorm before it holds still.

## What this is not

Not requirements. **No `REQ-`/`NFR-`/`US-` identifiers, no MoSCoW, no acceptance
criteria** — those are gate 0's job, and writing them here produces two documents that
drift. Intent is the originator's voice; `01-REQUIREMENTS.md` is the structured spec built
*from* it. If you find yourself assigning identifiers, you are doing gate 0, not this.

## Steps

1. Describe the problem conversationally with the originator. Do not structure it yet.
2. Brainstorm until the idea stops moving — options considered, constraints, non-goals.
3. Write `.agent-spec/sdlc/00-INTENT.md` (sections below). Plain language, their framing.
4. Read it back to them and correct anything you introduced that they did not mean.
5. Commit it, so the intent has provenance:

   ```bash
   git add .agent-spec/sdlc/00-INTENT.md && git commit -m "intent: <short name>"
   ```

6. **Before reporting done: run the [`self-review`](../agent-spec-self-review/SKILL.md) loop** —
   two passes, apply the fixes yourself, report once.

## The artifact — 00-INTENT.md

| Section | What goes in it |
|---|---|
| What | The thing wanted, one paragraph, in the originator's words |
| Why | The problem it solves or the value it creates — not the solution restated |
| Constraints | Hard limits: deadline, stack, budget, compliance. What is fixed before design starts |
| Non-goals | What this explicitly does **not** do, so scope does not creep at gate 0 |
| Open questions | Knowns-unknowns, left for gate 0 to resolve — do not guess answers here |

## Next

`/agent-spec-requirements` — gate 0 reads `00-INTENT.md` and structures it into
`01-REQUIREMENTS.md` with the identifiers gate 8 traces.

State this and stop. This is not a pipeline gate — it records nothing in `STATE.json` and
runs before gate 0.
