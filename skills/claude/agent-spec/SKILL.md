---
name: "agent-spec"
description: >-
  Router. Picks the right agent-spec skill for the job and runs one of them. Use when unsure which command applies.
---

# agent-spec

The framework is 25 skills. Choosing between them is itself a decision, and choosing
wrong is expensive — `/agent-spec-implement` on a bug whose cause is unknown burns a whole
session on edit-test-edit. This skill makes that choice, once, and hands off.

**It routes. It does not do the work.** Pick exactly one skill, say why in one line, invoke
it, and stop.

## 1. Read the state first

```bash
./.agent-spec/bin/agent-spec-gate.py status
```

The `SessionStart` digest already carries the stack, the graph size, the current gate and
the last session's summary. Do not re-read `PROJECT-INDEX.md` or `SESSION-SNAPSHOT.md` to
recover them.

If the digest says **ONBOARDING NEEDED**, the answer is `/agent-spec-onboard`, whatever
was asked. One pass now pays for every later session.

## 2. Route

Take the first row that matches. Order matters: the rows above the line prevent the most
expensive mistakes.

| The request | Route to | Why this and not the obvious one |
|---|---|---|
| "why is X happening", a failed first attempt, a symptom with no known cause | `/agent-spec-investigate` | Editing before the mechanism is known is the most expensive loop there is |
| A feature, anything with a "should" or a stakeholder | `/agent-spec-sdlc` | It reads the gate state and runs only the gate that is due |
| Structure: what breaks, what calls what, where is X | `/agent-spec-query-graph` | Answered in hundreds of tokens; reading the tree costs tens of thousands |
| Files moved, renamed or added; a query looks stale | `/agent-spec-index-project` | Everything downstream trusts the graph |
| First session in this repository | `/agent-spec-onboard` | |
| A named bug with a known cause, or a small scoped change | `/agent-spec-implement` | Small-change mode, said out loud |
| "review this", a diff, a pull request | `/agent-spec-review` | |
| One file, SOLID only | `/agent-spec-solid-check` | Audit-only; it cannot edit |
| Tests failing, coverage, "does this work" | `/agent-spec-testing` | |
| "did we build what was asked" | `/agent-spec-validation` | The only gate that checks back to requirement one |
| A defect found outside the current task's scope | `/agent-spec-debt` | Log it; do not widen the task |
| A fact worth keeping — a decision, a constraint, a gotcha | `/agent-spec-remember` | |
| End of session, or context past 70% | `/agent-spec-snapshot` | |
| Long session, at a task boundary | `/agent-spec-compact` | Writes state to disk, then a fresh session. Works in Cursor. |
| A specific lens is wanted — security, architecture, data | `/agent-spec-persona <role>` | Then continue with the skill that was already running |
| Output is too long, or too terse | `/agent-spec-raw-code [lite\|full]` (output only), `/agent-spec-raw-code-full` (everything), `/agent-spec-verbose` | |
| "what is this session costing" | `./.agent-spec/bin/agent-spec-tokens.py session` | Measured, not estimated |

## 3. Ambiguous requests

- **Two rows match** → run the one higher in the table, and say which you skipped.
- **Nothing matches** → this is ordinary work, not a pipeline task. Say so and do it
  directly. Not everything needs a gate, and routing a one-line question through a skill
  is worse than answering it.
- **A request spanning several skills** ("build and test and review this") → run the first
  one only, then stop and name the next. Chaining is how a gate gets skipped.

## 4. Before handing off

For anything that will touch code, get the file list from the graph rather than letting
the next skill find it by walking the tree:

```bash
./.agent-spec/bin/graphify-cli.py context --task "<the request, verbatim>"
```

Pass that list on. It is the single largest token saving in the framework.

## Hard stops

- **Never run two skills on one request.** One route, one handoff, then stop.
- Never do the routed skill's work inline "to save a step". Its gates and hard stops are
  the reason it exists; running its job without it means running without them.
- Never route to `/agent-spec-implement` when the cause of a defect is unknown. That row
  is at the top of the table for a reason.
- Never invent a skill name. Everything available is in the table.
