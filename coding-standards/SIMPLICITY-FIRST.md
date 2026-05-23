# Simplicity First

> **SOLID tells you HOW to structure code. Simplicity First tells you WHEN to structure code.** Without this counterweight, agents will over-engineer everything they touch.

LLMs are trained on millions of examples of well-structured, heavily-abstracted code. This makes them prone to building Strategy patterns for one-off calculations, Service layers for simple CRUD operations, and configuration frameworks for a single logger. The Simplicity First standard is the counterweight.

---

## Why This Matters

The tension:
- **SOLID Principles** push toward abstraction, interfaces, and separation of concerns.
- **LLM behavior** naturally amplifies this push — models generate the kind of "textbook" code they've seen most often.
- **Result**: Massively over-engineered solutions for simple problems.

Simplicity First resolves this by answering: *"Is this complexity justified RIGHT NOW?"*

---

## The Five Rules

### Rule 1: No Bonus Features

Implement only what was asked. If the user says "add a discount function," don't also add:
- Discount history tracking
- Discount validation rules
- Discount notification emails
- Discount analytics dashboard

Build exactly what was requested. If more is needed, the user will ask.

### Rule 2: No Speculative Abstraction

Abstract only when reuse is **proven**, not predicted. Follow the **Rule of Three**:
- First use → write it inline.
- Second use → note the duplication, but don't abstract yet.
- Third use → NOW extract a shared abstraction.

Never create an interface for a single implementation. Never build a factory for a single product. Never write a strategy pattern for a single strategy.

### Rule 3: No Premature Generalization

Avoid configurability and flexibility that nobody asked for:
- Don't add config files for hardcoded values that work.
- Don't build plugin systems for a single plugin.
- Don't parameterize things that have one value.
- Don't add "extensibility points" for extensions that don't exist.

### Rule 4: No Phantom Error Handling

Don't guard against impossible scenarios:
- Don't null-check values that are always initialized.
- Don't catch exceptions that can never be thrown.
- Don't validate inputs that come from your own code.
- Don't add retry logic for operations that never fail.

Handle errors that *can actually happen*. Skip the rest.

### Rule 5: The Compression Test

After writing code, apply this test:

> *"Could this be 50% shorter without losing clarity or correctness?"*

If yes, rewrite it. Common compression opportunities:
- Replace a class with a function
- Replace a function with an expression
- Replace a config file with a constant
- Replace an abstraction with inline code

---

## The Senior Engineer Test

Before submitting any code, ask:

> *"Would a senior engineer reviewing this say it's overcomplicated?"*

Decision framework:
| Signal | Action |
|--------|--------|
| "This is a lot of code for what it does" | Simplify |
| "Why is there an interface with one implementation?" | Remove the interface |
| "This config file has one entry" | Use a constant |
| "Nobody asked for this feature" | Delete it |
| "This error can never happen" | Remove the guard |
| "Looks clean and minimal" | ✅ Ship it |

---

## When TO Abstract

Simplicity First is NOT an excuse for spaghetti code. Abstraction is justified when:

1. **Three or more concrete uses exist** — The Rule of Three has been satisfied.
2. **A clear interface boundary exists** — e.g., separating API layer from business logic.
3. **The framework demands it** — e.g., Spring's `@Service`/`@Repository` pattern, Angular's component/service split.
4. **The abstraction reduces cognitive load** — Breaking a 500-line function into 5 focused functions is simplification, not over-engineering.
5. **Tests require it** — Dependency injection for testability is justified.

The test: *"Am I abstracting because the code NEEDS it, or because I WANT to?"*

---

## Integration with SOLID

| SOLID Principle | Simplicity Check |
|----------------|------------------|
| **S**ingle Responsibility | ✅ Yes — but don't split a 20-line class into 5 classes of 4 lines each. |
| **O**pen/Closed | ⚠️ Only when extension points have been requested or are provably needed. |
| **L**iskov Substitution | ✅ Yes — but only when you actually have substitutable types. |
| **I**nterface Segregation | ⚠️ Only when you have multiple consumers with different needs. |
| **D**ependency Inversion | ✅ Yes for testability — but skip the interface if there's only one implementation and no test mocking needed. |

**The rule**: SOLID tells you HOW to structure when complexity is justified. Simplicity tells you WHEN complexity is justified. Apply Simplicity First, then SOLID.

---

*Adapted from Andrej Karpathy's behavioral guidelines (MIT License). See `ACKNOWLEDGEMENTS.md`.*
