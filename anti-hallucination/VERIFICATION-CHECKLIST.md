# Verification Checklist

> **Location**: `anti-hallucination/VERIFICATION-CHECKLIST.md`
> This checklist must be run during Gate 6 (Verification) before a task is considered complete. It ensures that the agent catches its own hallucinations.

---

## 1. Context Verification
- [ ] Are all the files I modified actually tracked in `PROJECT-INDEX.md` or `KNOWLEDGE-GRAPH.md`? If I created new files, did I update the index?
- [ ] Did I write the `SESSION-SNAPSHOT.md` reflecting the exact current state?

## 2. API & Dependency Verification
- [ ] Did I introduce any new third-party library method calls?
- [ ] *If yes*: Did I verify the method signature exists in the current version of the library (Confidence: HIGH)? If not, have I warned the user that this might fail at runtime?

## 3. Code Integrity Verification
- [ ] Do all my changes compile/build without errors?
- [ ] Did I leave any `// TODO` or `[NEEDS CLARIFICATION]` tags in the code? If so, did I explicitly tell the user about them?
- [ ] Did I accidentally delete existing imports or methods that were unrelated to my task (Amnesia deletion)?

## 4. Acceptance Criteria Verification
- [ ] Does the code I wrote satisfy the *exact* Acceptance Criteria defined in Gate 2 (Spec)?
- [ ] Have I tested the "unhappy paths" (nulls, timeouts, bad input)?

## Output Format
If any checks fail, the agent must not declare Gate 6 complete. It must return to Gate 5 and fix the errors.

If all checks pass, the agent states:
> *"Gate 6 Anti-Hallucination Audit passed. No unresolved assumptions. Code is ready."*
