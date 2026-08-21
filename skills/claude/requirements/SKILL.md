---
name: "requirements"
description: "Elicit and structure raw customer needs. Output to .agent-spec/sdlc/01-REQUIREMENTS.md"
allowed-tools:
  - "Read"
  - "Write"
  - "Bash"
---

# Requirements Skill

1. Adopt the @WRITER persona.
2. Read the user's raw input.
3. Structure it according to `.agent-spec/sdlc/01-REQUIREMENTS.md`.
4. Use `[NEEDS CLARIFICATION]` tags for missing information.
5. Ask the user questions to fill the gaps — one at a time, in plain language, and stop
   for the answer. A batch of five gets skimmed and half-answered.
6. **Before reporting done: run the [`self-review`](../self-review/SKILL.md) loop** on what
   you wrote — two passes, apply the fixes yourself, report once. Do not hand over a draft
   and wait to be asked for a review.
