---
description: Review the current diff against the LLD and repo conventions (SDLC stage 5)
argument-hint: [feature slug, PR number, or git range]
---

Use the Agent tool with `subagent_type: code-reviewer` to review: **$ARGUMENTS**

If no target is given, review the current branch against the main branch.

Tell the agent to:
- read the full diff and the surrounding code, not only the changed lines
- check it against `docs/sdlc/<slug>/03-lld.md` where one exists
- rank findings by severity, each with a location and a concrete failure scenario
- write to `docs/sdlc/<slug>/05-review.md`
- **not fix anything it finds** — findings go back to the developer

When it returns, present the verdict, the severity tally, and every Critical and High
finding in one line each.
