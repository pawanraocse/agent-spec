# 🚀 agent-spec

> **Stop "vibe coding." Start engineering.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Framework: Agnostic](https://img.shields.io/badge/Framework-Agnostic-success.svg)](#)
[![Agents: Claude | Cursor | Antigravity](https://img.shields.io/badge/Agents-Claude%20|%20Cursor%20|%20Antigravity-blueviolet)](#)

A framework that installs into your repo and turns a hallucination-prone coding assistant
into a disciplined engineer: a queryable map of your architecture, a gated SDLC pipeline,
project memory that survives a new chat, strict confidence scoring, and 24 prefixed skills
that work in Claude Code, Cursor and Antigravity.

---

## Status

Unreleased work on `main`, on top of 1.0.0. What is in place today:

| | |
|---|---|
| **Router** | `/agent-spec` reads the pipeline state and hands off to exactly one skill |
| **Graph** | services, layers, HTTP and broker edges, incremental indexing — not just imports |
| **Pipeline** | nine gates with state on disk, and requirement traceability from gate 0 to gate 8 |
| **Memory** | a bounded fact store read at every session start, plus a rotating narrative snapshot |
| **Token cost** | ~2,190 tokens of always-on context; the session digest replaced a four-file read |
| **Tests** | `bin/agent-spec-selftest.sh` — 73 assertions across Python, Java-microservice and Node fixtures |
| **Measurement** | `bin/agent-spec-tokens.py` reads the real session transcript — measured buckets, not bytes ÷ 4 |
| **Subagents** | `agent-spec-search` and `agent-spec-verify`, pinned to a cheap model, so broad sweeps and noisy test output never enter the main context |

Known gaps, stated rather than hidden:

- Layer classification is a path and filename heuristic. It is reported, never enforced.
- HTTP integration edges resolve only when the called host matches a detected service
  name. A gateway, a config-driven base URL, or a discovery name that differs from the
  directory name is invisible. Broker edges have no such limitation.
- `from pkg import a` resolves to `pkg/__init__.py`, not `pkg/a.py`.
- Whether Claude Code picks up `outputStyle: "agent-spec"` from a freshly written
  `settings.json` has not been observed in a live session.

See [CHANGELOG.md](CHANGELOG.md) for the full list.

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

Installing also writes an output style, two cheap-model subagents and a `SessionStart`
hook into each `.claude` home, merged into any existing `settings.json` without touching what is already there.
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
| **Token budget** | `/agent-spec-raw-code` (output only) `-raw-code-full` (everything) `-verbose` |

24 skills. Installed machine-wide for both Claude Code and Cursor by the same command.

## Docs

- [What it actually does](docs/features.md) — Graphify, personas, the nine gates, context budgeting
- [Token efficiency](docs/token-efficiency.md) — where the tokens actually go, measured, and why the popular savings claims do not hold
- [Daily workflow](docs/workflow.md) — starting a feature, managing tokens, ending a session
- [Agent compatibility](docs/agents.md) — where files land, the WSL two-homes problem
- [Why this exists](docs/why.md)

## Maintaining

```bash
bin/agent-spec-selftest.sh   # 53 assertions: three language fixtures, gates, memory, upgrade path
bin/agent-spec-bench.sh      # always-on and per-skill cost, estimated at 4 bytes per token
bin/agent-spec-bench.sh --session   # measured, from the real session transcript
bin/agent-spec-benchmark.sh --repeats 3   # compare two modes over a verified task suite
```

Both must pass before anything is merged. The self-test builds throwaway fixtures and
asserts the failures that have actually shipped here before — edges resolving to nothing,
an indexer overwriting its own output, a gate running without its predecessor, an upgrade
leaving duplicate skills behind.

## Contributing

New personas, specialised skills and pipeline refinements are all welcome — open a PR.
Skills are authored once in `skills/claude/agent-spec-<name>/SKILL.md`; every agent reads
that same shape, so there is nothing to regenerate. The directory name and the frontmatter
`name` must match, and both must carry the `agent-spec-` prefix — the self-test enforces
it. See
[`skills/third-party/README.md`](skills/third-party/README.md) for community extensions.

## License

MIT — see [LICENSE](LICENSE).
