# The Full AI-SDLC Pipeline

> **Software Development Life Cycle for AI Agents.**
> Never jump straight from a vague idea to writing code.

Code generation is the *easiest* part for modern LLMs. Reasoning about architecture and intent is the hardest. `agent-spec` enforces a strict, multi-stage pipeline to force the AI to do the reasoning *before* it touches source code.

---

## The 9 SDLC Stages

| Gate | Stage | Skill | Artifact |
|---|---|---|---|
| 0 | **[Requirements](01-REQUIREMENTS.md)** — raw idea to structured requirements, with `REQ-` identifiers | `/agent-spec-requirements` | `01-REQUIREMENTS.md` |
| 1 | **[Tech spec](02-TECH-SPEC.md)** — feasibility, constraints, stack, NFRs | `/agent-spec-tech-spec` | `02-TECH-SPEC.md` |
| 2 | **[PRD](03-PRD.md)** — what and why, user stories, MoSCoW | `/agent-spec-prd` | `03-PRD.md` |
| 3 | **[HLD](04-HLD.md)** — service boundaries, data model, API contracts | `/agent-spec-hld` | `04-HLD.md` |
| 4 | **[LLD](05-LLD.md)** — classes, schemas, sequence flows | `/agent-spec-lld` | `05-LLD.md` |
| 5 | **[Development](06-DEVELOPMENT.md)** — the six implementation gates | `/agent-spec-implement` | code + tests |
| 6 | **[Review](07-REVIEW.md)** — blockers first, style last | `/agent-spec-review` | `06-REVIEW.md` |
| 7 | **[Testing](08-TESTING.md)** — the whole suite, failures verbatim | `/agent-spec-testing` | `07-TEST-REPORT.md` |
| 8 | **[Validation](09-VALIDATION.md)** — one verdict per requirement | `/agent-spec-validation` | `08-VALIDATION.md` |

`/agent-spec-sdlc` routes between them: it reads `STATE.json`, runs the gate that is due, and stops.
One gate per approval — chaining two on a single "yes" is how a requirement gets dropped,
which is precisely what gate 8 exists to catch, after the cost has been paid.

Note the offset: stage documents are numbered from 01, gates from 0.

---

## How It Works

This directory (`.agent-spec/sdlc/`) stores the output of each stage.

When you trigger a skill (e.g., `/agent-spec-prd`), the agent will:
1. Read the outputs of the previous stages (Requirements, Tech Spec).
2. Generate the artifact for the current stage (PRD).
3. Save it to `.agent-spec/sdlc/03-PRD.md`.

This creates a **lineage of intent**. If the agent is implementing code (gate 5) and gets confused about a business rule, it can read the PRD (gate 2) to regain context. `agent-spec-gate.py trace` checks that lineage mechanically: every `REQ-`, `NFR-` and `US-` identifier from gate 0, and which downstream artifacts still mention it.

## Iterative Cycle

Documents are not carved in stone. If during LLD (Stage 5) you discover that a feature is too expensive to build, you can ask the agent to go back and update the PRD (Stage 3) to descope it, and then regenerate the HLD and LLD.

Always maintain the chain of documents so they reflect reality.
