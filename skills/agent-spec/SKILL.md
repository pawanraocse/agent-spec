---
name: "agent-spec"
description: >-
  Router. Picks the right agent-spec skill for the job and runs one of them. Use when unsure which command applies.
---

# agent-spec

Routes; does not do the work. Pick exactly one skill, say why in one line, invoke it, stop.

## 1. State first

```bash
./.agent-spec/bin/agent-spec-gate.py status
```

The sessionStart digest already has stack, graph, gate and last session. Do not re-read
`PROJECT-INDEX.md` or `SESSION-SNAPSHOT.md`. No `.agent-spec/` in the workspace → run
`"$(cat ~/.cursor/skills/.algosec-agent-spec-root)/install.sh" --register "<ws>"` yourself
first. If it says **ONBOARDING NEEDED** → run
`/agent-spec-onboard` yourself, silently, whatever was asked. Never ask the user to.

## 2. Route (first match wins)

| The request | Skill |
|---|---|
| "why is X happening", a failed first attempt, unknown cause | `/agent-spec-investigate` |
| A feature, anything with a "should" or a stakeholder | `/agent-spec-sdlc` |
| What breaks, what calls what, where is X | `/agent-spec-query-graph` |
| Files moved/renamed/added; a query looks stale | `/agent-spec-index-project` |
| First session in this repo | `/agent-spec-onboard` |
| Named bug with known cause, or small scoped change | `/agent-spec-implement` |
| "review this", a diff, a pull request | `/agent-spec-review` |
| One file, SOLID only | `/agent-spec-solid-check` |
| Tests failing, coverage, "does this work" | `/agent-spec-testing` |
| "did we build what was asked" | `/agent-spec-validation` |
| Defect outside the current task's scope | `/agent-spec-debt` |
| A fact worth keeping | `/agent-spec-remember` |
| End of session, or context past 70% | `/agent-spec-snapshot` |
| Long session, task boundary | `/agent-spec-compact` |
| A lens — security, architecture, data | `/agent-spec-persona <role>` |
| Output too long / too terse | `/agent-spec-raw-code` / `/agent-spec-verbose` |
| "what is this session costing" | `./.agent-spec/bin/agent-spec-tokens.py session` |

## 3. Ambiguous

- Two rows match → take the higher one, say which you skipped.
- Nothing matches → ordinary work; do it directly. Not everything needs a gate.
- Several skills ("build, test, review") → run the first, name the next, stop.

## 4. Before handing off

For code changes, pass the file list from the graph, not a tree walk:

```bash
./.agent-spec/bin/graphify-cli.py context --task "<the request, verbatim>"
```

## Hard stops

- One route, one handoff. Never two skills on one request.
- Never do the routed skill's work inline; its gates are the reason it exists.
- Never route to `/agent-spec-implement` when a defect's cause is unknown.
- Never invent a skill name; everything available is in the table.
