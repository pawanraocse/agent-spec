# 🚀 agent-spec

> **Stop "vibe coding." Start engineering.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Framework: Agnostic](https://img.shields.io/badge/Framework-Agnostic-success.svg)](#)
[![Agents: Claude | Cursor | Antigravity](https://img.shields.io/badge/Agents-Claude%20|%20Cursor%20|%20Antigravity-blueviolet)](#)

A framework that installs into your repo and turns a hallucination-prone coding assistant
into a disciplined engineer: a queryable map of your architecture, a gated SDLC pipeline,
strict confidence scoring, and 29 skills that work in Claude Code, Cursor and
Antigravity.

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

Then restart your agent (skills are read at session start) and type **`/onboard`**. It
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
| `--lean` | Skip the 8 SDLC-design skills |
| `--force` | Overwrite existing project files |

</details>

---

## Skills

| | |
|---|---|
| **Onboarding** | `/onboard` |
| **SDLC pipeline** | `/requirements` `/tech-spec` `/prd` `/hld` `/lld` `/implement` |
| **Diagnosis** | `/investigate` |
| **Review** | `/review` `/self-review` `/solid-check` `/debt` |
| **Memory** | `/index-project` `/query-graph` `/snapshot` |
| **Token budget** | `/raw-code` `/dense` `/trim-noise` `/verbose` |
| **Personas** | `/architect` `/security` `/qa` `/reviewer` `/refactor` `/api` `/data` `/devops` `/perf` `/writer` |

---

## Docs

- [What it actually does](docs/features.md) — Graphify, personas, the 6 gates, context budgeting
- [Daily workflow](docs/workflow.md) — starting a feature, managing tokens, ending a session
- [Agent compatibility](docs/agents.md) — where files land, the WSL two-homes problem
- [Why this exists](docs/why.md)
- [`sdlc-team/`](sdlc-team/README.md) — standalone Claude Code plugin, nine subagents, no install required

## Contributing

New personas, specialised skills and pipeline refinements are all welcome — open a PR.
Skills are authored once in `skills/claude/<name>/SKILL.md`; every agent reads that same
shape, so there is nothing to regenerate. See
[`skills/third-party/README.md`](skills/third-party/README.md) for community extensions.

## License

MIT — see [LICENSE](LICENSE).
