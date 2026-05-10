# The 6-Gate Development Pipeline

> **Rule: The agent cannot write code until Gate 5.**

This pipeline governs the execution phase of development (Stage 6 of the SDLC). It is designed to physically block the AI agent from "vibe coding" — jumping straight into modifying files without understanding the context, architecture, or risks.

---

## The 6 Gates

1. **[DISCOVERY](GATE-1-DISCOVERY.md)**: Establish context. Load index, graph, and snapshot. Select persona.
2. **[SPEC](GATE-2-SPEC.md)**: Review acceptance criteria. No code without a testable spec.
3. **[ARCHITECTURE](GATE-3-ARCHITECTURE.md)**: SOLID check. Graph updates. No God objects.
4. **[TASKS](GATE-4-TASKS.md)**: Atomic task breakdown (≤30 mins). Rollback plans.
5. **[IMPLEMENTATION](GATE-5-IMPLEMENTATION.md)**: Test-First (TDD). Language style rules applied.
6. **[VERIFICATION](GATE-6-VERIFICATION.md)**: Hallucination audit. Update docs. Write snapshot.

---

## How Gates Work

A Gate is a mandatory checkpoint. The agent MUST complete the checklist defined in the Gate's document before it is allowed to proceed to the next Gate.

If the developer interrupts the agent or context is lost, the agent must re-verify the current Gate before continuing.
