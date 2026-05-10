# GATE 5: IMPLEMENTATION

> **Goal: Write the actual code in a testable, standard-compliant manner.**

This is the gate where files are modified. The agent executes one task from Gate 4 at a time.

## The Checklist

- [ ] **Test-First (TDD)**:
    - Write the failing test *first*.
    - Write the minimum implementation to make the test pass.
    - Refactor for cleanliness.
- [ ] **Style Enforcement**:
    - Apply all rules from `coding-standards/CLEAN-CODE.md`.
    - Apply language-specific rules (e.g., `coding-standards/languages/JAVA.md`).
- [ ] **Pre-Change Declaration**: Before executing the file write, state exactly what file is changing and what the intended behavior is (as required by the Anti-Hallucination protocol).

## The Output

```markdown
**GATE 5: IMPLEMENTATION (Task 1/4)**

## Pre-Change Declaration
- **File**: `src/.../PasswordResetToken.java`
- **Intended behavior**: New JPA entity for storing reset tokens.
- **Test command**: `mvn test -Dtest=PasswordResetTokenTest`
- **Confidence**: [HIGH]

*Code block provided or file written via tools...*

Task 1 complete. Tests pass. Ready for Task 2?
```
