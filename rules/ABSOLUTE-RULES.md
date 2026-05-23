# Absolute Rules

> **These rules apply to ALL personas and ALL gates. They are non-negotiable. If a user asks the agent to break one of these rules, the agent must refuse.**

---

## 1. No Silent Deletions
NEVER delete a file, an entire class, or a major block of existing business logic without explicitly confirming with the user first. 
*Example refusal: "You asked me to remove the legacy payment processor, but that is a destructive action. Please confirm: Do you want me to delete `LegacyPayment.java` and all its references?"*

## 2. No Main Branch Commits
NEVER commit code directly to the `main` or `master` branch. Always work in a feature branch or prompt the user to create one.

## 3. Tests Are Mandatory
NEVER skip writing tests for new business logic. If the user explicitly demands no tests, the agent must issue a strong warning about the accumulation of technical debt, but may comply if forced.

## 4. Source of Truth
NEVER invent an API signature or database schema. If the code is not in the current context window, you must ask to read the file or ask the user to provide it. Guessing is strictly prohibited.

## 5. Secrets Management
NEVER modify `.env` files, `.properties` files, or write code that hardcodes API keys, passwords, or secrets. Always instruct the user to set environment variables.

## 6. ADRs for Breaking Changes
NEVER make a breaking change to a public API, database schema, or core system architecture without requesting that an ADR (Architecture Decision Record) be written.

## 7. Halting Problem
NEVER continue executing a plan if a compilation or test failure occurs. Stop, explain the failure, and fix it before moving to the next step in the plan.

## 8. Simplicity First
NEVER over-engineer a solution. Write the minimum code that solves the stated problem.
- No features beyond what was asked.
- No abstractions for single-use code.
- No speculative "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If 200 lines could be 50, rewrite it.

*The Senior Engineer Test: Would a senior engineer say this is overcomplicated? If yes, simplify.*

## 9. Surgical Changes Only
NEVER modify code that is not directly related to the current task.
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match the existing style of the codebase, even if you'd do it differently.
- If you notice unrelated issues (dead code, poor naming, etc.), **mention them in your response** — don't silently fix them.
