# CURSOR.md — Cursor Configuration

> **Rules for Cursor AI when working in any project initialized with agent-spec.**
> These rules are loaded via `.cursor/rules/` and apply to all Cursor AI interactions.

---

## 🧭 Session Start

The `SessionStart` hook has already put a digest in your context: stack, graph size,
current pipeline gate, and what the last session did. **Do not re-read
`PROJECT-INDEX.md`, `KNOWLEDGE-GRAPH.md` or `SESSION-SNAPSHOT.md` to learn those
facts — you already have them.**

Two things the digest does not carry, because they are only needed sometimes:

- `.agent-spec/CONSTITUTION.md` — read before the first code edit of the session.
- Structure — query it, do not read it:
  `./.agent-spec/bin/graphify-cli.py query --file <path>`

If the digest says **ONBOARDING NEEDED**, run `/onboard` before anything else.
If there is no digest and no `.agent-spec/` directory, tell the user to run `bin/install.sh`.


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
