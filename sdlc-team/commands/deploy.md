---
description: Prepare a release plan, rollback and notes (SDLC stage 8) - prepares only, never deploys
argument-hint: <feature slug>
---

Use the Agent tool with `subagent_type: deployment-engineer` to prepare a release
for: **$ARGUMENTS**

Tell the agent to:
- check `docs/sdlc/<slug>/07-qa-signoff.md` first and stop if the verdict is `FAIL`
- read the existing CI/CD setup and extend it rather than adding a second mechanism
- write to `docs/sdlc/<slug>/08-deployment.md`: version bump, migration ordering
  (expand/contract), release notes, rollback plan, post-deploy checks
- **prepare only — never run a deploy, push a tag, or trigger a pipeline**

When it returns, present the proposed version and why, migration reversibility, the
rollback trigger and command, and any new configuration required.

Executing the release is the user's decision. Give them the commands and stop.
