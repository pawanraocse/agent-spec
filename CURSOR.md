# CURSOR.md — Cursor Configuration

> **Rules for Cursor AI when working in any project initialized with agent-spec.**
> These rules are loaded via `.cursor/rules/` and apply to all Cursor AI interactions.

---

## 🧭 Session Start Protocol

At the start of every session:

```
0. If .agent-spec/.onboarding-needed exists → run the `onboard` skill FIRST.
1. Read: .agent-spec/SESSION-SNAPSHOT.md
2. Read: .agent-spec/PROJECT-INDEX.md
3. Read: .agent-spec/graph/KNOWLEDGE-GRAPH.md
4. State what was loaded before proceeding.
```

---

## 🎭 Persona System

Default: **CODE-REVIEWER**

Activate by mentioning in chat: `"Activate: @ARCHITECT"` etc.

See `AGENTS.md` and `personas/` for persona details and hard rules.

---

## 📊 Confidence Scoring

All non-trivial claims must include confidence rating:
- `[CONFIDENCE: HIGH]` — verified in this session
- `[CONFIDENCE: MEDIUM]` — pattern-based
- `[CONFIDENCE: LOW]` — inference, validate first
- `[CONFIDENCE: UNKNOWN]` — ask developer

---

## 💡 Cursor Skills

Skills are installed machine-wide in `~/.cursor/skills/<name>/SKILL.md` and load on
demand. `.cursor/rules/` holds one always-on file, `agent-spec.mdc` — these standing
rules. Reference a skill in chat by describing the task:
- "Run requirements skill for: [description]"
- "Run prd skill using the requirements doc"
- "Run solid-check on UserService.java"
- "Switch to raw-code mode" / "Switch to trim-noise mode"

Cursor loads the matching `SKILL.md` on demand and follows it.
The always-on rules live alongside them in `.cursor/rules/agent-spec-rules.md`.

---

## 📐 Always-On Coding Rules

These apply to every file Cursor generates or modifies:

**Java:**
- Follow `coding-standards/languages/JAVA.md`
- Controllers delegate only — zero business logic
- Custom exceptions always — never raw `RuntimeException`
- All public methods documented with Javadoc

**Angular:**
- Follow `coding-standards/languages/ANGULAR.md`
- Smart/dumb component separation
- All subscriptions cleaned up in `ngOnDestroy`
- No direct DOM manipulation

---

## 🚧 Hard Stops

Cursor will not:
```
❌ Delete files without confirmation
❌ Skip tests
❌ Invent class/method names without reading source
❌ Modify .env files
❌ Suggest main branch commits
```

---

## 📋 Session End

Remind developer to run `/snapshot` (or describe snapshot task) before ending session.

---

*Version: 1.0.0 | Framework: agent-spec | Spec: cursor*
