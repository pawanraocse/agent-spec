# The implementation gates

> These six gates run **inside** SDLC gate 5. They are not a second pipeline.

The nine SDLC gates are the lifecycle: requirements through validation, one artifact each,
state in `.agent-spec/sdlc/STATE.json`. The six below are the micro-process `/agent-spec-implement`
follows while writing the code for gate 5.

`skills/claude/agent-spec-implement/SKILL.md` is the executable definition. This file exists so the
gates have a name in the documentation; **if the two ever disagree, the skill is right**.
Six per-gate documents used to live here and drifted out of step with the skill three
times, so they were removed rather than maintained twice.

## The six

| Gate | Name | What it settles |
|---|---|---|
| G1 | Placement | Which layer or module owns this. Spanning two means it is two changes; a new service or language means an ADR, not a commit. |
| G2 | Tests first | The failing test before the fix, including the cases that must return "unknown" with a stated reason. A bug's red test is kept as the regression lock. |
| G3 | Build it | Only what the task requires. Match the surrounding style; do not touch adjacent code. |
| G4 | Verify the boundary | The tests that enforce architecture — layering, purity, import direction. A structural break fails here, not in production. |
| G5 | Verify clean | Tests, linter, type checker. All green, and the real command output pasted. |
| G6 | Self-review, then report | The `self-review` loop over the diff, then one honest report: what was built, what was skipped, what is unverified. |

Do not proceed to the next gate until the current one's checklist is complete.

Before G1, `/agent-spec-implement` also reads the project's hard rules, the coding standards, and the
graph — `context --task` for the file list and `query --file` for the blast radius — and
posts a Pre-Change Declaration. Confidence LOW or UNKNOWN stops the change and asks.
