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
