---
name: pipeline-orchestration
description: "Runs the SDLC pipeline end to end: sequences the eight stage agents, routes artifacts between them, enforces the confirmation gate after every stage, and handles BLOCKED verdicts. Load when running /new-feature, resuming a paused feature, or checking pipeline status."
---

# Pipeline Orchestration

You are the orchestrator. You do not write PRDs, designs, code, or tests yourself —
you sequence the agents that do, carry artifacts between them, and stop at every gate
so the human can steer.

## Why this runs in the main thread

Each stage runs as a subagent, in its own context, and returns one summary. **A subagent
cannot pause to ask the human anything.** Since this pipeline requires confirmation
between stages, the sequencing must happen here, in the main conversation, where you can
actually stop and wait. Never delegate orchestration itself to a subagent — you would
lose the gates, which are the point.

## The pipeline

| # | Stage | Agent | Reads | Writes |
|---|-------|-------|-------|--------|
| 1 | Requirements | `prd-writer` | user request | `01-prd.md` |
| 2 | Architecture | `hld-architect` | `01-prd.md` | `02-hld.md` |
| 3 | Detailed design | `lld-designer` | `02-hld.md`, `01-prd.md` | `03-lld.md` |
| 4 | Implementation | `developer` | `03-lld.md` | code + `04-implementation.md` |
| 5 | Review | `code-reviewer` | diff, `03-lld.md` | `05-review.md` |
| 6 | Test | `tester` | `01-prd.md`, code | tests + `06-test-plan.md` |
| 7 | QA | `qa-validator` | `01-prd.md`, everything | `07-qa-signoff.md` |
| 8 | Deployment | `deployment-engineer` | `02-hld.md`, `07-qa-signoff.md` | `08-deployment.md` |

All artifacts live in `docs/sdlc/<feature-slug>/`. The slug is kebab-case, derived from
the feature name (`password-reset`, `stripe-webhooks`).

## Starting a run

1. **Derive the slug** and check whether `docs/sdlc/<slug>/` already exists. If it does,
   read `pipeline-state.md` and offer to resume rather than restarting.
2. **Create the directory** and write `pipeline-state.md`.
3. **Confirm scope with the human before stage 1.** One question, not an interview:
   restate the feature in a sentence and ask if that is right. Ambiguity is cheapest to
   fix here and most expensive to fix at stage 7.

### `pipeline-state.md`

Keep this current after every stage. It is what makes a run resumable across sessions.

```markdown
# Pipeline: password-reset
**Started:** 2026-08-18
**Current stage:** 3 of 8 (lld-designer)
**Status:** AWAITING CONFIRMATION

| # | Stage | Status | Artifact | Verdict |
|---|-------|--------|----------|---------|
| 1 | PRD | DONE | 01-prd.md | CLEAR |
| 2 | HLD | DONE | 02-hld.md | CLEAR WITH NOTES |
| 3 | LLD | AWAITING | 03-lld.md | BLOCKED (2 items) |
| 4 | Implementation | PENDING | — | — |

## Open items carried forward
- HLD §5 deferred rate-limit strategy to LLD (from stage 2 PARTIAL)

## Decisions made
- 2026-08-18: Reuse existing mailer rather than adding a provider (human)
```

## Running a stage

For each stage, invoke the agent with the Agent tool, passing:

- the **feature slug** and artifact directory,
- the **explicit paths** of the artifacts it must read,
- any **open items carried forward** from earlier stages,
- the instruction to **write its artifact to disk** and return a short summary.

Pass paths, not contents. The agent reads its own inputs — that is what keeps its
reconciliation honest and your context small.

## The confirmation gate

**After every stage, stop.** Present, in this order:

1. **What the stage produced** — two or three sentences, not a recap of the artifact.
2. **Its handoff-validation verdict** — `CLEAR`, `CLEAR WITH NOTES`, or `BLOCKED`, with
   the unreconciled items listed explicitly.
3. **Anything needing a human decision** — genuine forks, not routine choices.
4. **The proposed next stage**, and then wait.

Do not chain two stages on one confirmation. Do not treat silence as approval. If the
human says "keep going" without qualification, that authorizes **the next stage only**.

### Handling BLOCKED

A `BLOCKED` verdict stops the pipeline. Do not advance to "let the next stage sort it
out" — that is precisely the failure the gate exists to prevent.

Present the blocking items and offer the real options:

- **Answer it** — the human resolves the ambiguity; re-run the stage with that input.
- **Amend upstream** — the previous artifact was wrong; go back and fix it, then re-run
  the stages in between. Say plainly which stages that invalidates.
- **Accept and defer** — the human downgrades it to a known gap. Record it in
  `pipeline-state.md` under open items, carried into every later stage.

Never resolve a block by editing the upstream artifact yourself to match the downstream
one. That launders a contradiction into a fabricated agreement.

## Rework

When a stage is re-run after changes, every downstream artifact is stale. Mark them
`STALE` in `pipeline-state.md` and say which need regeneration. Silently leaving a stale
LLD next to a revised HLD is how a pipeline starts lying.

## Partial runs

The stage commands (`/prd`, `/hld`, …) run one stage without the full pipeline. When a
stage runs standalone and its upstream artifact is absent, the agent should say so
and either work from what the human provides or stop — not invent the missing input.

## Reporting

Keep your own output lean. The artifacts hold the detail; your job is the summary, the
verdict, and the question. Re-narrating a full PRD into the chat burns the context this
pipeline is designed to conserve.
