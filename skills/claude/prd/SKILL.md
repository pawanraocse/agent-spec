---
name: "prd"
description: >-
  SDLC gate 2: user stories and MoSCoW into 03-PRD.md. Needs 02-TECH-SPEC.md.
---

# Prd Skill

## Gate

```bash
./.agent-spec/bin/agent-spec-gate.py check 2
```

`BLOCKED` → stop. Say which gate has to run first, and why this gate cannot
substitute for it. **Never synthesise the upstream document to unblock yourself** — a
design built on an invented predecessor is worse than no design, because it looks
approved.


1. Adopt the @WRITER persona.
2. Read `.agent-spec/sdlc/01-REQUIREMENTS.md` and `02-TECH-SPEC.md`.
3. Follow the iterative Discover -> Document -> Review cycle.
4. Apply MoSCoW prioritization to all features.
5. Run the 14-point Validation Checklist defined in `.agent-spec/sdlc/03-PRD.md`.
6. Output to `.agent-spec/sdlc/03-PRD.md`.
7. **Before reporting done: run the [`self-review`](../self-review/SKILL.md) loop** on what
   you wrote — two passes, apply the fixes yourself, then give the Status Report once. Do
   not hand over a draft and wait to be asked for a review. Pay particular attention to
   coverage: every upstream requirement must have a home here.

## Next gate

`/hld` — service boundaries and data model.

State this and stop. Do not run the next gate yourself — each one is a separate approval,
and chaining two on one "yes" is how a requirement gets dropped without anyone noticing.

Record this gate before you stop:

```bash
./.agent-spec/bin/agent-spec-gate.py set 2
```
