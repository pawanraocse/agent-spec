# Stage 7: Review

> **Skill**: `/review`
> **Input**: the diff from stage 6, plus `05-LLD.md`
> **Output**: `.agent-spec/sdlc/06-REVIEW.md`

## The Goal

Find the defects before the tests do, in the order that costs least: correctness first,
style last. A style nit costs minutes; a correctness defect costs a decision made on a
wrong number.

## What the gate covers

- One real case traced end to end. Files that are individually correct with a wrong
  handoff between them is the defect class that reading in isolation never finds.
- The project's own hard rules — whatever `CLAUDE.md` and `.agent-spec/rules/` declare
  non-negotiable. Those are blockers by definition.
- Failure paths: does an error path invent a plausible value instead of failing loudly?
- Duplicated logic, dead code left behind by a removed feature, scope creep.

## Exit criteria

Every finding tagged `[BLOCKER]`, `[MINOR]` or `[NIT]` with `file:line` and a concrete
failure scenario, most severe first. Fixes applied, not merely listed. A finding that
cannot be demonstrated is a `[NIT]`.

Record the gate and stop:

```bash
./.agent-spec/bin/agent-spec-gate.py set 6
```
