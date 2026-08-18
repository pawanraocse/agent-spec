---
description: Run the full SDLC pipeline for a feature, pausing for confirmation between every stage
argument-hint: <feature description>
---

Run the complete SDLC pipeline for: **$ARGUMENTS**

Load the `pipeline-orchestration` skill and follow it. You are the orchestrator, running
in the main conversation — this is deliberate, because subagents cannot pause to ask the
user anything, and this pipeline requires confirmation between stages.

Stages, in order:

1. `prd-writer` → `01-prd.md`
2. `hld-architect` → `02-hld.md`
3. `lld-designer` → `03-lld.md`
4. `developer` → code + `04-implementation.md`
5. `code-reviewer` → `05-review.md`
6. `tester` → tests + `06-test-plan.md`
7. `qa-validator` → `07-qa-signoff.md`
8. `deployment-engineer` → `08-deployment.md`

Before starting: derive a kebab-case slug, check whether `docs/sdlc/<slug>/` already
exists (offer to resume rather than restart), create the directory, and restate the
feature in one sentence for the user to confirm.

After **every** stage, stop and present:
- what the stage produced, in two or three sentences
- its handoff-validation verdict, with any unreconciled items listed explicitly
- anything needing a human decision
- the proposed next stage — then wait

Do not chain two stages on one confirmation. Do not treat silence as approval. A
`BLOCKED` verdict halts the pipeline; present the options rather than working around it.

Keep `pipeline-state.md` current after every stage so the run survives a session break.
