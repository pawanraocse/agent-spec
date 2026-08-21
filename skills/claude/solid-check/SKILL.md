---
name: "solid-check"
description: "Audit a file specifically for SOLID principle violations, sanity-checked against SIMPLICITY-FIRST so it does not manufacture abstractions."
allowed-tools:
  - "Read"
  - "Write"
  - "Bash"
---

# Solid-check Skill

1. Adopt the @ARCHITECT persona.
2. Read the specified file.
3. Audit against the 5 principles in `.agent-spec/coding-standards/SOLID-PRINCIPLES.md`,
   then sanity-check every finding against
   `.agent-spec/coding-standards/SIMPLICITY-FIRST.md`. SOLID pushes toward abstraction and,
   unchecked, produces a Strategy pattern for a one-off calculation.
   **A "violation" that only a speculative abstraction would fix is not a violation.**
4. If a real violation survives step 3, suggest the refactor — and state the concrete
   change it makes possible, not the principle it satisfies.
