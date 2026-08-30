# 🚀 agent-spec

> **Stop "vibe coding." Start engineering.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Framework: Agnostic](https://img.shields.io/badge/Framework-Agnostic-success.svg)](#)
[![Agents: Claude | Cursor | Antigravity](https://img.shields.io/badge/Agents-Claude%20|%20Cursor%20|%20Antigravity-blueviolet)](#)

A framework that installs into your repo and turns a hallucination-prone coding assistant
into a disciplined engineer: a queryable map of your architecture, a gated SDLC pipeline,
strict confidence scoring, and 25 prefixed skills that work in Claude Code, Cursor
and Antigravity.

---

## Install

One command. No Python or Node dependencies.

```bash
curl -sSL https://raw.githubusercontent.com/pawanraocse/agent-spec/main/bin/install.sh | bash
```

It installs skills **machine-wide** — every project on the box gets them — and sets up
`.agent-spec/` in the current directory. Run it in an empty directory and you get a new
project, git and all.

**Update:** re-run the exact same command.

Installing also writes an output style and a `SessionStart` hook into each `.claude`
home, merged into any existing `settings.json` without touching what is already there.
The hook puts a short project digest — stack, graph size, current gate, last session — in
front of every session, so no session begins by reading four files to work out where it is.

Then restart your agent (skills are read at session start) and type **`/agent-spec-onboard`**. It
reads the graph and the manifest, writes `PROJECT-INDEX.md` and `CONSTITUTION.md` from
what is actually in your repo, and never runs again — so no later session has to
rediscover the project.

<details>
<summary>Options</summary>

| Flag | Effect |
|---|---|
| `--skills-only` | Machine-wide skills, touch nothing in this directory |
| `--project-only` | This directory only |
| `--project-skills` | Also commit skills into `.claude/` and `.cursor/` (team repos) |
| `--lean` | Skip the 5 SDLC-design skills |
| `--force` | Overwrite existing project files |

</details>

---

## Skills

Every command is prefixed `agent-spec-`, so it is obvious in a transcript which tool ran
and where it came from.

| | |
|---|---|
| **Router** | `/agent-spec` — picks the right skill for the job when you are not sure |
| **Onboarding** | `/agent-spec-onboard` |
| **SDLC pipeline** | `/agent-spec-sdlc` routes; `-requirements` `-tech-spec` `-prd` `-hld` `-lld` `-implement` `-review` `-testing` `-validation` |
| **Diagnosis** | `/agent-spec-investigate` |
| **Review** | `/agent-spec-review` `-self-review` `-solid-check` `-debt` |
| **Graph** | `/agent-spec-index-project` `/agent-spec-query-graph` |
| **Memory** | `/agent-spec-remember` `/agent-spec-snapshot` |
| **Personas** | `/agent-spec-persona <role>` — architect, security, qa, data, devops, perf, refactor, api, writer, reviewer |
| **Token budget** | `/agent-spec-raw-code` `-dense` `-trim-noise` `-verbose` |

25 skills. Installed machine-wide for both Claude Code and Cursor by the same command.

## Docs

- [What it actually does](docs/features.md) — Graphify, personas, the nine gates, context budgeting
- [Daily workflow](docs/workflow.md) — starting a feature, managing tokens, ending a session
- [Agent compatibility](docs/agents.md) — where files land, the WSL two-homes problem
- [Why this exists](docs/why.md)

## Maintaining

```bash
bin/agent-spec-selftest.sh   # fixtures for Python, Java microservices and Node; 16 assertions
bin/agent-spec-bench.sh      # always-on context cost, per-skill cost, graph query cost
```

## Contributing

New personas, specialised skills and pipeline refinements are all welcome — open a PR.
Skills are authored once in `skills/claude/<name>/SKILL.md`; every agent reads that same
shape, so there is nothing to regenerate. See
[`skills/third-party/README.md`](skills/third-party/README.md) for community extensions.

## License

MIT — see [LICENSE](LICENSE).
