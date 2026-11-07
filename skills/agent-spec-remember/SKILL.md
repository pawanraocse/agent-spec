---
name: "agent-spec-remember"
description: >-
  Record one durable project fact — a decision, a constraint, a gotcha, a reference. Read back at every session start.
---

# agent-spec-remember

The snapshot is a narrative: right for a human catching up, wrong for an agent that needs
one fact. This is the other half. Each fact is one file, typed and sourced, and the whole
set is put in front of every session by the `SessionStart` digest — so a fact recorded once
is known from then on, without anyone reading anything.

```bash
./.agent-spec/bin/agent-spec-memory.py add \
  --type constraint --subject "push policy" --source "SESSION-SNAPSHOT 2026-08-26" \
  "Pushing to main is allowed here at the user's explicit instruction, overriding the Hard Stops list."
```

## The four types

| Type | Is | Is not |
|---|---|---|
| `constraint` | something that makes work wrong if unknown — a policy, a hard limit, a compliance rule | a preference |
| `decision` | a choice made and the reason, so it is not relitigated every session | a plan |
| `gotcha` | a trap that has already cost someone time | a bug to fix — that is `/agent-spec-debt` |
| `reference` | where an external thing lives: a dashboard, a ticket, a runbook | a file path the graph already knows |

`constraint` is never pruned by age. The other three are.

## Record

- A fact the **code cannot show**. Anything derivable from the repository is not a fact,
  it is a lookup — the graph, `git log` and `CONVENTIONS.md` already answer those, and
  storing them creates a copy that goes stale silently.
- A **decision and its reason**, especially one that reversed an earlier decision.
- A **correction**: something that was believed, turned out wrong, and would otherwise be
  believed again next session.
- One sentence, at most three. Longer than 600 characters is refused — that is a snapshot
  section, not a fact.

## Do not record

- Anything the repository already records: structure, past fixes, commit history, the
  contents of `CLAUDE.md`.
- Anything true only inside this conversation.
- A guess. A remembered fact is read as established every session; a wrong one is wrong
  forever, and cheaper never written than corrected later.

Always cite `--source`: a file and line, a commit, a URL, or `conversation`. A fact whose
origin nobody can check cannot be re-verified when it starts to look wrong.

## Read back

```bash
./.agent-spec/bin/agent-spec-memory.py list [--type constraint]
./.agent-spec/bin/agent-spec-memory.py search <keyword>
./.agent-spec/bin/agent-spec-memory.py show <id>
```

## Keep it bounded

Forty facts is the cap. Past it the digest drops the oldest, by age rather than by
importance, which is the wrong thing to lose. When `list` says the store is over:

```bash
./.agent-spec/bin/agent-spec-memory.py prune --older-than 180 --dry-run
```

Read what it would remove before removing it.

## Hard stops

- Never record a fact you cannot source.
- Never edit a fact file by hand to change what it says. Facts are a record; a wrong one
  is deleted and replaced, so the correction is visible rather than silent.
- Never use this for anything the code answers. If in doubt, ask the graph first.
