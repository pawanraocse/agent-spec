---
description: Write a PRD for a feature (SDLC stage 1)
argument-hint: <feature description>
---

Use the Agent tool with `subagent_type: prd-writer` to write a PRD for: **$ARGUMENTS**

Tell the agent to:
- derive a kebab-case slug and write to `docs/sdlc/<slug>/01-prd.md`
- read `CLAUDE.md` for product and technical constraints
- ask at most three clarifying questions if the request is genuinely ambiguous, then
  proceed with recorded assumptions
- run its handoff self-check and append the validation block

When it returns, present the summary and its verdict, and note that `/hld` is the next
stage if the user wants to continue.
