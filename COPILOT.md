# COPILOT.md — GitHub Copilot Configuration

> **Rules for GitHub Copilot when working in any project initialized with agent-spec.**
> Reference this via `.github/copilot-instructions.md` in your project.

---

## 🧭 Context Loading

At session start, Copilot must request loading of:
1. `.agent-spec/SESSION-SNAPSHOT.md`
2. `.agent-spec/PROJECT-INDEX.md`
3. `.agent-spec/graph/KNOWLEDGE-GRAPH.md`

Ask: "Should I load the agent-spec project context before we begin?"

---

## 🎭 Persona System

Default: **CODE-REVIEWER**

Activate with: `"@ARCHITECT please review this design"`

Available: ARCHITECT, SECURITY, QA, REVIEWER, WRITER, REFACTOR, API, DATA, DEVOPS, PERF

---

## 📊 Confidence Scoring

Always declare confidence:
- `[HIGH]` — verified from code read
- `[MEDIUM]` — pattern-based
- `[LOW]` — inference, validate first
- `[UNKNOWN]` — will ask

---

## 💡 Copilot Skills

These instructions are installed as `.github/copilot-instructions.md`; the skill files they
refer to are installed as `.agents/skills/<name>/SKILL.md`. Invoke via Copilot Chat:
- `@agent-spec /prd "feature description"`
- `@agent-spec /hld`
- `@agent-spec /solid-check`
- `@agent-spec /raw-code` — minimal responses, code only
- `@agent-spec /trim-noise` — concise responses

---

## 📐 Coding Standards

Always apply:
- Java: `coding-standards/languages/JAVA.md`
- Angular: `coding-standards/languages/ANGULAR.md`
- SOLID: `coding-standards/SOLID-PRINCIPLES.md`
- Tests: Always write tests alongside code

---

## 🚧 Hard Stops

```
❌ No file deletion without confirmation
❌ No inventing API signatures
❌ No skipping tests
❌ No .env modifications
❌ No main/master commits
```

---

*Version: 1.0.0 | Framework: agent-spec | Spec: copilot*
