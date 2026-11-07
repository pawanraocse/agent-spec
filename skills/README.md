# Skills (Cursor)

On-demand workflows installed to `~/.cursor/skills/<name>/SKILL.md`. Standing rules:
`.cursor/rules/agent-spec.mdc` (from `CURSOR.md`).

## Daily use

| Skill | When |
|---|---|
| `/agent-spec-sdlc` | Gate routing (four tracks) |
| `/agent-spec-implement` | Build with test-first discipline |
| `/agent-spec-query-graph` | Structure without file walks |
| `/agent-spec-raw-code-full` | Tool-traffic discipline |
| `/agent-spec-investigate` | Diagnose before edit |
| `/agent-spec-snapshot` | Session state on disk |
| `/agent-spec-compact` | Snapshot + new Cursor chat |

## Session boundaries

| Skill | When |
|---|---|
| `/agent-spec-onboard` | Once per new project |
| `/agent-spec-index-project` | After structural moves |
| `/agent-spec-remember` | Durable facts |
| `/agent-spec-verbose` | Exit terse modes |

## SDLC pipeline

`/agent-spec-intent` (optional) → requirements → tech-spec → prd → hld → lld → implement →
review → testing → webapp-testing → validation.

Gate skills: `/agent-spec-requirements` `/agent-spec-tech-spec` `/agent-spec-prd`
`/agent-spec-hld` `/agent-spec-lld` `/agent-spec-implement` `/agent-spec-review`
`/agent-spec-testing` `/agent-spec-validation` · UI: `/agent-spec-webapp-testing`.

## Workflows

- `/agent-spec-hub-runner` — run a workflow skill step by step with Task subagents; run state via `bin/agent-spec-run.py`
- `/agent-spec-wf-example` — read-only fixture workflow (gather → analyze → summarize)
- `/agent-spec-wf-rca <KEY>` — Jira (MCP) → graph + blast radius → log parse → cited root cause
- `/agent-spec-wf-pr-review <branch|PR>` — diff → review → validate each finding
- `/agent-spec-wf-fix-plan <rca run id>` — RCA follow-on: test-first fix plan behind a human gate
- `/agent-spec-wf-eval` — golden-ticket score of the RCA workflow vs the BugBot baseline (`evals/`)
- `/agent-spec-learn distill|recall|propose` — experience store to facts, recall, skill proposals
- `/agent-spec-synthesize-routine` — synthesize repeated task patterns into parameterized `agent-spec-wf-*` workflows
- New workflows: `skills/agent-spec-wf-<name>/SKILL.md` with a ```steps block; check with `agent-spec-run.py validate`

## Context modes

- `/agent-spec-raw-code` — short actionable replies (`full` / `lite`)
- `/agent-spec-raw-code-full` — batch, graph, Edit, cap output; Complexity Override for hard algorithms
- `/agent-spec-compact` — snapshot then new chat
- `/agent-spec-verbose` — normal prose

## Router and specialists

- `/agent-spec` — picks one skill from pipeline state
- `/agent-spec-persona <role>` — expert lens with Absolute Rules
- `/agent-spec-self-review` `/agent-spec-solid-check` `/agent-spec-debt`
- `/agent-spec-doc-coauthoring` `/agent-spec-prompt-audit` `/agent-spec-skill-creator` `/agent-spec-mcp-builder`

## Authoring

Skills live under `skills/<name>/SKILL.md`. `./install.sh` copies to `~/.cursor/skills/`.
`--project-skills` also writes `<workspace>/.cursor/skills/`.

See [docs/QUICKSTART.md](../docs/QUICKSTART.md) and [docs/QUICKSTART.md](../docs/QUICKSTART.md).
