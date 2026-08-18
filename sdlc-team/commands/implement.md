---
description: Implement code from an approved LLD (SDLC stage 4)
argument-hint: <feature slug, or what to implement>
---

Use the Agent tool with `subagent_type: developer` to implement: **$ARGUMENTS**

Tell the agent to:
- detect the repo's stack and conventions first — `CLAUDE.md`, lockfile, linter, test
  framework and layout, naming, commit style
- read `docs/sdlc/<slug>/03-lld.md` and build exactly what it specifies, no more
- run the repo's lint, format and test commands, and report actual results
- write a change summary to `docs/sdlc/<slug>/04-implementation.md`
- run its handoff self-check against the LLD and append the validation block
- not commit or push

When it returns, present files changed, any deviation from the LLD and why, real test
and lint results, and its verdict.
