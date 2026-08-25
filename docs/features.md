# What agent-spec actually does

Back-link: [README](../README.md)

## Graphify — memory that survives a new chat

`./.agent-spec/bin/agent-spec-index --graphify` scans the codebase and writes a
machine-readable JSON knowledge graph plus a Mermaid diagram. The agent queries that map
before writing code, instead of re-reading the tree every session.

Query it without loading it: `./.agent-spec/bin/graphify-cli.py query --file <path>`
returns imports and blast radius. `search <keyword>` finds domain components. `stats`
gives the bird's-eye view. That is the `/query-graph` skill.

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

## The 6-gate SDLC pipeline

`Requirements → Tech Spec → PRD → HLD → LLD → Implementation`. Each gate produces a
markdown artifact under `.agent-spec/sdlc/`, so intent has a lineage. The agent is
blocked from implementation until the LLD is signed off — which forces edge cases, data
structures and SOLID to be considered before the first line of code.

## Pre-change declaration

Before modifying a file the agent must state what it will change, what breaks if it is
wrong, and the exact command that verifies it. Confidence `LOW` or `UNKNOWN` stops the
change and asks.

## Context budgeting

Loading 10,000 files into a 200k window destroys reasoning. Using the Graphify map the
agent loads the target file, its direct imports (distance 1) and its dependents
(distance −1). Nothing else.

## Auto-logged technical debt

A code smell the agent was not asked to fix does not become a `// TODO`. `/debt` logs it
to `.agent-spec/TECH-DEBT-REGISTER.md`.

## Built-in coding standards

Clean Code, SOLID, Simplicity-First, Java (Spring Boot) and Angular templates ship in
`.agent-spec/coding-standards/`. The agent reviews its own output against them before
showing it to you.

## The `sdlc-team` plugin

`sdlc-team/` is a standalone Claude Code plugin — nine subagents covering the full
lifecycle, no `agent-spec` install required. See [`sdlc-team/README.md`](../sdlc-team/README.md).
