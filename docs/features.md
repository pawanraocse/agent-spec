# What agent-spec actually does

Back-link: [README](../README.md)

## Graphify — memory that survives a new chat

`./.agent-spec/bin/agent-spec-index` scans the codebase and writes a machine-readable JSON
knowledge graph, a Mermaid summary and an observed-conventions file. Only files whose
mtime or size moved are re-parsed, so re-indexing a large repository is cheap. The agent
queries that map before writing code, instead of re-reading the tree every session.

It records more than imports. Each file carries a **layer** (controller, service, data,
integration, contract, config, util) and the **service** that owns it — one per manifest
below the root. On top of the import edges it recovers the coupling no import graph can
see: HTTP calls matched to a service name, and Kafka, Rabbit or SQS topics matched from
producer to consumer. Two services that talk over a broker share no line of code; without
those edges they look unrelated.

Query it without loading it — this is the `/query-graph` skill:

| Question | Command |
|---|---|
| Which files does this task need? | `context --task "<description>"` |
| What breaks if I change this? | `query --file <path> --depth 2` |
| How does a request flow through? | `flow --from <entry-point>` |
| Which services talk to what? | `services` |
| What is the HTTP surface? | `endpoints` |
| Is the layering holding? | `layers` |
| Where is X? | `search <keyword>` |

## `/onboard` — learn the project once

On the first session after install, `.agent-spec/.onboarding-needed` triggers `/onboard`.
It reads the graph, the build manifest and the commit log — not the source tree — and
writes `PROJECT-INDEX.md` and `CONSTITUTION.md` from what is actually in the repo: stack,
build and test commands, layering, conventions, hard constraints. Then it deletes the
marker and never runs again. Anything it cannot evidence is tagged
`[NEEDS CLARIFICATION]` rather than guessed.

Every later session reads those two files instead of rediscovering the project.

## 10 expert personas

Default agents are yes-men. These are not.

- `@ARCHITECT` — enforces SOLID, blocks God Objects.
- `@SECURITY` — zero-trust; demands parameterised queries, rejects hardcoded secrets.
- `@QA` — TDD; no code without a failing test first.
- `@DATA` — obsesses over normalisation, rejects lossy migrations.
- `@REFACTOR` — cleans debt without changing behaviour.

Full roster in `personas/`. Each has hard rules the agent may not violate on request.

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
never produced its artifact. `/sdlc` reads that state, runs the one gate that is due and
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
  default rather than something `/raw-code` has to be typed to get, session after session.

`bin/agent-spec-bench.sh` prints what all of that actually costs, so the claim can be
checked.

## Auto-logged technical debt

A code smell the agent was not asked to fix does not become a `// TODO`. `/debt` logs it
to `.agent-spec/TECH-DEBT-REGISTER.md`.

## Built-in coding standards

Clean Code, SOLID, Simplicity-First, Java (Spring Boot) and Angular templates ship in
`.agent-spec/coding-standards/`. The agent reviews its own output against them before
showing it to you.
