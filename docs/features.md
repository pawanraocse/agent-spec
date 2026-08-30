# What agent-spec actually does

Back-link: [README](../README.md)

## Graphify — memory that survives a new chat

`./.agent-spec/bin/agent-spec-index` scans the codebase and writes a machine-readable JSON
knowledge graph, a Mermaid summary and an observed-conventions file. Only files whose
mtime or size moved are re-parsed, so re-indexing a large repository is cheap. The agent
queries that map before writing code, instead of re-reading the tree every session.

It is built for real repositories: `.gitignore` directories are excluded on top of the
built-in list, files over 1 MB and minified or generated ones are skipped as written by a
tool rather than a person, symlink loops terminate, and hitting the file ceiling is
reported rather than silently producing a partial graph.

It records more than imports. Each file carries a **layer** (controller, service, data,
integration, contract, config, util) and the **service** that owns it — one per manifest
below the root. On top of the import edges it recovers the coupling no import graph can
see: HTTP calls matched to a service name, and Kafka, Rabbit or SQS topics matched from
producer to consumer. Two services that talk over a broker share no line of code; without
those edges they look unrelated.

Query it without loading it — this is the `/agent-spec-query-graph` skill:

| Question | Command |
|---|---|
| Which files does this task need? | `context --task "<description>"` |
| What breaks if I change this? | `query --file <path> --depth 2` |
| How does a request flow through? | `flow --from <entry-point>` |
| Which services talk to what? | `services` |
| What is the HTTP surface? | `endpoints` |
| Is the layering holding? | `layers` |
| Where is X? | `search <keyword>` |

## `/agent-spec-onboard` — learn the project once

On the first session after install, `.agent-spec/.onboarding-needed` triggers `/agent-spec-onboard`.
It reads the graph, the build manifest and the commit log — not the source tree — and
writes `PROJECT-INDEX.md` and `CONSTITUTION.md` from what is actually in the repo: stack,
build and test commands, layering, conventions, hard constraints. Then it deletes the
marker and never runs again. Anything it cannot evidence is tagged
`[NEEDS CLARIFICATION]` rather than guessed.

Every later session reads those two files instead of rediscovering the project.

## The router

`/agent-spec` picks the skill. Choosing between 25 of them is itself a decision, and
choosing wrong is expensive — `/agent-spec-implement` on a defect whose cause is unknown
burns a session on edit-test-edit. The router reads the pipeline state, matches the
request against an ordered table whose top rows exist to prevent exactly those mistakes,
fetches the file list from the graph, and hands off to **one** skill. It never does the
work itself, and it never chains two skills on one request.

## Project memory

Two kinds, deliberately separate.

**Facts** — `.agent-spec/memory/facts/`, one per file, typed `constraint`, `decision`,
`gotcha` or `reference`, each dated and sourced. The `SessionStart` hook prints them all,
constraints first, under a byte cap. A fact recorded once is known by every later session
without anyone opening a file. Capped at forty and pruned deliberately, because memory
that grows without limit becomes the problem it was meant to solve.

**Narrative** — `SESSION-SNAPSHOT.md`, append-only, one dated section per session, holding
the corrections and reversed decisions that are its most valuable content. Append-only is
not unbounded: past about 12 KB whatever loads it truncates, silently, oldest first.
`agent-spec-memory.py rotate` moves the older sections into `memory/snapshots/` where they
remain readable on purpose. Nothing is deleted.

`/agent-spec-remember` says what does **not** belong in memory: anything the repository
already answers. A copy of something the graph knows goes stale silently.

## 10 expert personas

One skill, `/agent-spec-persona <role>`, ten roles. Default agents are yes-men. These are
not.

- `@ARCHITECT` — enforces SOLID, blocks God Objects.
- `@SECURITY` — zero-trust; demands parameterised queries, rejects hardcoded secrets.
- `@QA` — TDD; no code without a failing test first.
- `@DATA` — obsesses over normalisation, rejects lossy migrations.
- `@REFACTOR` — cleans debt without changing behaviour.

Full roster in `personas/`, one file each. The **Absolute Rules** section of that file is
binding and does not relax on request — not for "just this once", not for a test, not
because the user asked.

## Anti-hallucination protocol

Every claim carries a `[CONFIDENCE]` score. If the agent has not read the file in the
current session it is forbidden from claiming `HIGH`. "I don't know, let me check" is
explicitly the correct answer; guessing is not.

## The nine-gate SDLC pipeline

`Requirements → Tech Spec → PRD → HLD → LLD → Development → Review → Testing →
Validation`. Each gate produces a markdown artifact under `.agent-spec/sdlc/`, so intent
has a lineage. The agent is blocked from implementation until the LLD is signed off —
which forces edge cases, data structures and SOLID to be considered before the first line
of code.

The ordering is not remembered, it is stored. `.agent-spec/sdlc/STATE.json` holds the
current gate, and `bin/agent-spec-gate.py check <n>` refuses a gate whose predecessor
never produced its artifact. `/agent-spec-sdlc` reads that state, runs the one gate that is due and
stops; one gate per approval, never two chained on a single "yes".

The last gate is the only one that looks all the way back to the first.
`agent-spec-gate.py trace` follows every `REQ-`, `NFR-` and `US-` identifier from gate 0
through every downstream document and exits non-zero on one that reached nothing. Each
handoff being locally consistent is exactly how a requirement disappears without anyone
noticing; this is the check that notices.

## Pre-change declaration

Before modifying a file the agent must state what it will change, what breaks if it is
wrong, and the exact command that verifies it. Confidence `LOW` or `UNKNOWN` stops the
change and asks.

## Context budgeting

Loading 10,000 files into a 200k window destroys reasoning. Three mechanisms keep it
down:

- **`context --task`** returns the file list a task needs — name matches plus one hop of
  neighbours, capped — so the agent reads that list instead of grepping its way through
  the tree.
- **The `SessionStart` hook** puts a ~600-byte digest in front of every session: stack,
  graph size, current gate, last session's summary. It replaces the old protocol of
  opening four files to work out where things stand.
- **An `agent-spec` output style**, installed into `settings.json`, makes dense output the
  default rather than something `/agent-spec-raw-code` has to be typed to get, session after session.

`bin/agent-spec-bench.sh` prints what all of that costs as an estimate, and
`bin/agent-spec-bench.sh --session` measures the real thing from the session transcript.
The order of leverage is not what the tooling ecosystem advertises — turns and context
size dominate, and prose compression is worth about 2% — so
[token efficiency](token-efficiency.md) carries the numbers and their sources.

## Auto-logged technical debt

A code smell the agent was not asked to fix does not become a `// TODO`. `/agent-spec-debt` logs it
to `.agent-spec/TECH-DEBT-REGISTER.md`.

## Built-in coding standards

Clean Code, SOLID, Simplicity-First, Java (Spring Boot) and Angular templates ship in
`.agent-spec/coding-standards/`. The agent reviews its own output against them before
showing it to you.
