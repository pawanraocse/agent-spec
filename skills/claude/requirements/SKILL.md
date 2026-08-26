---
name: "requirements"
description: >-
  SDLC gate 1: structure raw needs into 01-REQUIREMENTS.md.
---

# Requirements Skill

## Gate

```bash
test -f .agent-spec/sdlc/00-RAW-REQUIREMENTS.md && echo present || echo "none — use what the user typed"
```

This is the first gate, so a missing raw-requirements file is fine: work from what the
user said. Everything downstream depends on this being honest about what is *not* known.


1. Adopt the @WRITER persona.
2. Read the user's raw input.
3. Structure it according to `.agent-spec/sdlc/01-REQUIREMENTS.md`.
4. Use `[NEEDS CLARIFICATION]` tags for missing information.
5. Ask the user questions to fill the gaps — one at a time, in plain language, and stop
   for the answer. A batch of five gets skimmed and half-answered.
6. **Before reporting done: run the [`self-review`](../self-review/SKILL.md) loop** on what
   you wrote — two passes, apply the fixes yourself, report once. Do not hand over a draft
   and wait to be asked for a review.

## Next gate

`/tech-spec` — feasibility and NFRs, once the open `[NEEDS CLARIFICATION]` tags are answered.

State this and stop. Do not run the next gate yourself — each one is a separate approval,
and chaining two on one "yes" is how a requirement gets dropped without anyone noticing.
