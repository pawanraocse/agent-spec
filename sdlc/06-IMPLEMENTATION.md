# Stage 6: Implementation

> **Skill**: `/implement`
> **Input**: `.agent-spec/sdlc/05-lld.md`
> **Output**: Source Code + `.agent-spec/SESSION-SNAPSHOT.md`

## The Goal
Translate the Low Level Design into production-ready, test-backed code. This stage invokes the **6-Gate Pipeline**, which enforces strict controls on how the agent modifies the codebase.

## The 6-Gate Implementation Pipeline

When `/implement` is invoked, the agent enters Gate 1 of the implementation pipeline. It cannot jump straight to writing code.

*Note: Stages 1-5 of the SDLC map to Gates 1-3 of the implementation pipeline conceptually, but the 6-Gate pipeline is the micro-process used during actual coding sessions.*

### [GATE 1: DISCOVERY](../pipeline/GATE-1-DISCOVERY.md)
The agent loads the LLD, the Project Index, and the Knowledge Graph to establish context. It explicitly confirms the scope of the files to be modified.

### [GATE 2: SPEC](../pipeline/GATE-2-SPEC.md)
The agent reviews the Acceptance Criteria from the PRD to ensure the planned code will actually meet the business requirements.

### [GATE 3: ARCHITECTURE](../pipeline/GATE-3-ARCHITECTURE.md)
The agent performs a final SOLID check on the proposed LLD classes.

### [GATE 4: TASKS](../pipeline/GATE-4-TASKS.md)
The agent breaks the LLD into atomic, 30-minute tasks (e.g., "1. Write Token Entity", "2. Write Token Repository"). It creates a rollback plan for each.

### [GATE 5: IMPLEMENTATION](../pipeline/GATE-5-IMPLEMENTATION.md)
**The code is finally written.**
- **Test-First (TDD)**: The agent writes a failing test, writes the implementation, gets the test to pass, and refactors.
- **Style Enforcement**: The agent applies language-specific rules from `coding-standards/languages/`.

### [GATE 6: VERIFICATION](../pipeline/GATE-6-VERIFICATION.md)
The agent audits its work against the Anti-Hallucination checklist. It updates the Project Index and Knowledge Graph, and writes the final `SESSION-SNAPSHOT.md`.

---

> **For detailed instructions on the coding phase, see the `pipeline/` directory.**
