# Stage 6: Implementation

> **Skill**: `/agent-spec-implement`
> **Input**: `.agent-spec/sdlc/05-LLD.md`
> **Output**: Source Code + `.agent-spec/SESSION-SNAPSHOT.md`

## The Goal
Translate the Low Level Design into production-ready, test-backed code. This stage invokes the **6-Gate Pipeline**, which enforces strict controls on how the agent modifies the codebase.

## The implementation gates

`/agent-spec-implement` runs six gates inside this stage: **placement, tests first, build, verify the
boundary, verify clean, self-review**. It cannot jump straight to writing code.

The executable definition is `skills/claude/agent-spec-implement/SKILL.md`; `pipeline/README.md`
summarises it. Where they disagree, the skill is right.

> **The gate checklists live in the skill itself — see `/agent-spec-implement`.**
