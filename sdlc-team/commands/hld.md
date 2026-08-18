---
description: Produce a high level design from an approved PRD (SDLC stage 2)
argument-hint: <feature slug, or path to the PRD>
---

Use the Agent tool with `subagent_type: hld-architect` to produce a high level design
for: **$ARGUMENTS**

Tell the agent to:
- read `docs/sdlc/<slug>/01-prd.md` (if no PRD exists, say so rather than inventing
  requirements — offer `/prd` first)
- explore the actual repository before proposing anything
- write to `docs/sdlc/<slug>/02-hld.md` with a Mermaid diagram per primary journey
- decompose every NFR into a budget, and flag any that cannot be met
- run its handoff self-check against the PRD and append the validation block

When it returns, present the design shape, each technology decision in one line, any
unmeetable NFR, and its verdict.
