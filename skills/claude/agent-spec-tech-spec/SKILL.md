---
name: "agent-spec-tech-spec"
description: >-
  SDLC gate 1: feasibility, stack and NFRs into 02-TECH-SPEC.md. Needs 01-REQUIREMENTS.md.
---

# Tech-spec Skill

## Gate

```bash
./.agent-spec/bin/agent-spec-gate.py check 1
```

`BLOCKED` → stop. Say which gate has to run first, and why this gate cannot
substitute for it. **Never synthesise the upstream document to unblock yourself** — a
design built on an invented predecessor is worse than no design, because it looks
approved.


1. Adopt the @ARCHITECT persona.
2. Read `.agent-spec/sdlc/01-REQUIREMENTS.md` and `.agent-spec/PROJECT-INDEX.md`.
   **If the project already locks a stack, read it and stop re-deriving one** — a spec that
   reopens a settled stack decision is how a deleted architecture comes back.
3. Assess technical feasibility and define NFRs.
4. Output to `.agent-spec/sdlc/02-TECH-SPEC.md` following the template.
5. **Before reporting done: run the [`self-review`](../agent-spec-self-review/SKILL.md) loop** on what
   you wrote — two passes, apply the fixes yourself, report once. Recompute every NFR
   figure; a stated budget that its own table exceeds is the defect this catches.

## Next gate

`/agent-spec-prd` — user stories and MoSCoW, built on this spec.

State this and stop. Do not run the next gate yourself — each one is a separate approval,
and chaining two on one "yes" is how a requirement gets dropped without anyone noticing.

Record this gate before you stop:

```bash
./.agent-spec/bin/agent-spec-gate.py set 1
```
