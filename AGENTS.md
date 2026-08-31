# AGENTS.md — Master Agent Configuration

> **This file governs ALL AI agents working in this project.**
> Every agent reads this file first. No exceptions.

---

## 🧭 Session Start

Claude Code is handed a digest automatically by its `SessionStart` hook. **Every other
agent has no session hook**, so if no digest is already in your context, your first
action in a new session is to run it yourself:

```bash
./.agent-spec/bin/agent-spec-digest.py
```

It prints about 1,700 bytes: stack, graph size, current pipeline gate, what the last
session did, and the remembered constraints. Either way, once you have it, **do not
re-read `PROJECT-INDEX.md`, `KNOWLEDGE-GRAPH.md` or `SESSION-SNAPSHOT.md` to learn those
facts — you already have them.** Reading those three costs 30,560 bytes to learn what the
digest gave you for 1,700.

Two things the digest does not carry, because they are only needed sometimes:

- `.agent-spec/CONSTITUTION.md` — read before the first code edit of the session.
- Structure — query it, do not read it:
  `./.agent-spec/bin/graphify-cli.py query --file <path>`

If the digest says **ONBOARDING NEEDED**, run `/agent-spec-onboard` before anything else.
If there is no digest and no `.agent-spec/` directory, tell the user to run `bin/install.sh`.


## 🚦 The SDLC Pipeline

Nine gates. State lives in `.agent-spec/sdlc/STATE.json`, not in anyone's memory:

```bash
./.agent-spec/bin/agent-spec-gate.py status      # where are we
./.agent-spec/bin/agent-spec-gate.py check <n>   # may this gate run yet
./.agent-spec/bin/agent-spec-gate.py set <n>     # record a gate as passed
./.agent-spec/bin/agent-spec-gate.py trace       # did every requirement survive
```

| Gate | Skill | Produces |
|---|---|---|
| 0 REQUIREMENTS | `/agent-spec-requirements` | `01-REQUIREMENTS.md` — assigns the `REQ-` identifiers |
| 1 TECH-SPEC | `/agent-spec-tech-spec` | `02-TECH-SPEC.md` |
| 2 PRD | `/agent-spec-prd` | `03-PRD.md` |
| 3 HLD | `/agent-spec-hld` | `04-HLD.md` |
| 4 LLD | `/agent-spec-lld` | `05-LLD.md`, one per service |
| 5 DEVELOPMENT | `/agent-spec-implement` | code + tests |
| 6 REVIEW | `/agent-spec-review` | `06-REVIEW.md` |
| 7 TESTING | `/agent-spec-testing` | `07-TEST-REPORT.md` |
| 8 VALIDATION | `/agent-spec-validation` | `08-VALIDATION.md` |

`/agent-spec-sdlc` routes: it reads the state, runs the one gate that is due, and stops.

**One gate per approval. Never chain two.** A change too small for a design pass runs in
small-change mode — `/agent-spec-implement` directly, said out loud, with no gate recorded.

`/agent-spec-implement` has its own internal six gates (placement, tests first, build, boundary,
clean, self-review). Those are inside gate 5, not a second pipeline.


## 🎭 Personas

Default: **@REVIEWER** — skeptical, precise, asks before assuming.

`/agent-spec-persona <role>` switches: `architect` `security` `qa` `data` `devops` `perf`
`refactor` `api` `writer` `reviewer`. Each loads `.agent-spec/personas/<ROLE>.md`, whose
**Absolute Rules** section is binding and does not relax on request.

A persona changes the lens, not the task, and never overrides the rules in this file.


## 🛡️ Anti-Hallucination Protocol

Every agent MUST follow the confidence scoring system:

```
[CONFIDENCE: HIGH]    → Verified from code read in this session
[CONFIDENCE: MEDIUM]  → Known pattern, not verified in this codebase
[CONFIDENCE: LOW]     → Inference — validate before acting
[CONFIDENCE: UNKNOWN] → Agent doesn't know — must ask developer
```

**Before making any code change, state:**
1. Which file(s) will change (exact path)
2. Current behavior (quote actual code if possible)
3. Intended behavior (from acceptance criteria)
4. What could break (explicit risk)
5. How to verify (exact test command)

See `.agent-spec/anti-hallucination/` for the full protocol.

---

## ⚡ Skills

Every skill is installed machine-wide in `~/.claude/skills/<name>/SKILL.md`, and the
harness already lists each one with its description at session start. That list is the
index — this file does not repeat it, because a second copy is one more thing to drift.

Reach for `/agent-spec-sdlc` to run a feature through the lifecycle, `/agent-spec-investigate` before fixing
anything whose cause is unknown, and `/agent-spec-query-graph` instead of reading the tree.


## 📏 Absolute Rules (Non-Negotiable)

```
NEVER delete files without explicit developer confirmation
NEVER commit to main/master directly
NEVER skip writing tests for new code
NEVER invent an API signature — read the source or ask
NEVER modify .env or secrets files
NEVER make a breaking change without a linked ADR
NEVER continue past a failing test
NEVER add a dependency without discussing tradeoffs
NEVER over-engineer — minimum code for the stated problem only
NEVER modify code outside the current task scope without permission
```

Full rules: `.agent-spec/rules/ABSOLUTE-RULES.md`

---

## 🗣️ Communication Standards

```
ALWAYS cite exact file path + line when referencing code
ALWAYS prefix uncertain claims with [CONFIDENCE: level]
ALWAYS structure responses: Summary → Detail → Action Required
ALWAYS flag which pipeline gate you are currently in
ALWAYS write a Session Snapshot at the end of a session
NEVER present multiple solutions without a clear recommendation
```

Full rules: `.agent-spec/rules/COMMUNICATION-RULES.md`

---

## 🚧 Autonomy Limits

```
CANNOT deploy to any environment without human approval
CANNOT delete database records or run destructive migrations
CANNOT change auth/authorization logic unilaterally
CANNOT modify secrets or API keys
CANNOT merge pull requests
CANNOT make privacy or data-retention decisions
```

Full rules: `.agent-spec/rules/AUTONOMY-LIMITS.md`

---

## 📁 Key File Locations

```
.agent-spec/PROJECT-INDEX.md        Living project index (update after every session)
.agent-spec/CONSTITUTION.md         Project-specific rules
.agent-spec/SESSION-SNAPSHOT.md     Latest session state
.agent-spec/graph/knowledge-graph.json  Graphify index
.agent-spec/sdlc/                   SDLC stage outputs
.agent-spec/coding-standards/SOLID-PRINCIPLES.md   SOLID reference
.agent-spec/coding-standards/languages/JAVA.md     Java standards
.agent-spec/coding-standards/languages/ANGULAR.md  Angular standards
```

---

*Version: 1.0.0 | Ratified: 2026-05-09 | Framework: agent-spec*
