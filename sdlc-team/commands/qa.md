---
description: Independently validate the implementation against the PRD before sign-off (SDLC stage 7)
argument-hint: <feature slug>
---

Use the Agent tool with `subagent_type: qa-validator` to validate: **$ARGUMENTS**

Tell the agent to:
- read `docs/sdlc/<slug>/01-prd.md` **first** and list what it will check before looking
  at any implementation
- verify each criterion independently, recording how it was verified and what was
  observed — a green suite is evidence, not proof
- check NFRs specifically, and non-goals for scope violations
- mark anything it could not verify as `UNVERIFIED`, never as `PASS`
- write to `docs/sdlc/<slug>/07-qa-signoff.md`
- not edit code, tests, or the PRD

When it returns, present the verdict, the criteria tally, and every failing criterion.
Do not soften a `FAIL` — if the user wants to ship anyway, that is their explicit call.
