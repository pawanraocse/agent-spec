---
name: "agent-spec-solid-check"
description: >-
  Audit one file for SOLID violations, checked against SIMPLICITY-FIRST so it invents no abstractions.
allowed-tools:
  - "Read"
  - "Grep"
  - "Glob"
  - "Bash"
---

# Solid-check Skill

1. Adopt the @ARCHITECT persona.
2. Read the specified file.
3. Audit against the five checks below, then sanity-check every finding against
   `.agent-spec/coding-standards/SIMPLICITY-FIRST.md`. SOLID pushes toward abstraction —
   unchecked, it produces a Strategy pattern for a one-off calculation.
   **A "violation" that only a speculative abstraction would fix is not a violation.**
4. If a real violation survives step 3, suggest the refactor — state the concrete change it
   makes possible, not the principle it satisfies.

## The five checks

**S — Single Responsibility**
Ask: does this class have more than one reason to change?
Symptom: the class has two clearly distinct conceptual "sections" (e.g., parsing *and* persisting).
Fix direction: extract the second responsibility into a collaborator the original class calls.

**O — Open/Closed**
Ask: adding a new case — would that require modifying this class?
Symptom: a `switch` or `if-elif` chain on a type enum, growing with each new type.
Fix direction: replace the chain with polymorphism or a registry; new types add files, not edits.

**L — Liskov Substitution**
Ask: would swapping a subclass for its parent silently break a caller?
Symptom: an overridden method throws `NotImplemented`, narrows a parameter type, or weakens a postcondition.
Fix direction: if the subclass can't honour the contract, it should not inherit — prefer composition.

**I — Interface Segregation**
Ask: does an implementor receive methods it never uses?
Symptom: stub methods that throw `NotImplemented`, or a large interface with only partial use by any one caller.
Fix direction: split the interface; each implementor takes only what it needs.

**D — Dependency Inversion**
Ask: does a high-level module import a concrete low-level class directly?
Symptom: `new ConcreteEmailService()` or `import StripeClient` inside a business-logic class.
Fix direction: inject the dependency (constructor, factory, or DI container); the high-level module names an interface, not an impl.

## Hard stops

- Never flag a violation whose only fix is an abstraction not yet justified by a second
  use case. SIMPLICITY-FIRST beats SOLID when they conflict.
- Report findings in priority order: behavioural risks (L, D) before structural ones (S, O, I).
- If the file is under 50 lines, a SOLID audit is almost certainly unnecessary — say so.
