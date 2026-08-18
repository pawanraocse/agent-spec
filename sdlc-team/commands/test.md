---
description: Write and run tests mapped to the PRD's acceptance criteria (SDLC stage 6)
argument-hint: <feature slug, or what to test>
---

Use the Agent tool with `subagent_type: tester` to build and run tests for: **$ARGUMENTS**

Tell the agent to:
- detect the existing test framework, naming and layout before writing anything, and
  never introduce a second framework
- read `docs/sdlc/<slug>/01-prd.md` and map every `AC-n` to a named test
- write the mapping table to `docs/sdlc/<slug>/06-test-plan.md` before writing tests
- run the suite and report real results, including failures
- never weaken or skip a test to get green
- run its handoff self-check against the PRD and append the validation block

When it returns, present tests added by level, the coverage tally against acceptance
criteria, actual pass/fail results, and its verdict.
