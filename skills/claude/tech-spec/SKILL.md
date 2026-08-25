---
name: "tech-spec"
description: "Define feasibility, tech stack, and NFRs. Output to .agent-spec/sdlc/02-TECH-SPEC.md"
---

# Tech-spec Skill

## Gate

```bash
test -f .agent-spec/sdlc/01-REQUIREMENTS.md && echo present || echo MISSING
```

`MISSING` → stop. Say that `/requirements` has to run first, and why this gate cannot
substitute for it. **Never synthesise the upstream document to unblock yourself** — a
design built on an invented predecessor is worse than no design, because it looks
approved.


1. Adopt the @ARCHITECT persona.
2. Read `.agent-spec/sdlc/01-REQUIREMENTS.md` and `.agent-spec/PROJECT-INDEX.md`.
   **If the project already locks a stack, read it and stop re-deriving one** — a spec that
   reopens a settled stack decision is how a deleted architecture comes back.
3. Assess technical feasibility and define NFRs.
4. Output to `.agent-spec/sdlc/02-TECH-SPEC.md` following the template.
5. **Before reporting done: run the [`self-review`](../self-review/SKILL.md) loop** on what
   you wrote — two passes, apply the fixes yourself, report once. Recompute every NFR
   figure; a stated budget that its own table exceeds is the defect this catches.

## Next gate

`/prd` — user stories and MoSCoW, built on this spec.

State this and stop. Do not run the next gate yourself — each one is a separate approval,
and chaining two on one "yes" is how a requirement gets dropped without anyone noticing.
