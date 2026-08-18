---
description: Produce a low level design from an approved HLD (SDLC stage 3)
argument-hint: <feature slug, or path to the HLD>
---

Use the Agent tool with `subagent_type: lld-designer` to produce a detailed design
for: **$ARGUMENTS**

Tell the agent to:
- read `docs/sdlc/<slug>/02-hld.md` and `01-prd.md` (if the HLD is missing, say so
  rather than inventing an architecture — offer `/hld` first)
- read the real signatures of everything it integrates with, never assume them
- write to `docs/sdlc/<slug>/03-lld.md`
- give every migration a rollback, and every PRD criterion a traceability entry
- run its handoff self-check against the HLD and append the validation block

When it returns, present the interfaces added or changed, data model changes, error-case
count, anything it could not detail, and its verdict.
