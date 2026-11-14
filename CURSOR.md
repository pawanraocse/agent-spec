# CURSOR.md — algosec-agent-spec (canonical always-on rules)

> Installed as `.cursor/rules/agent-spec.mdc` (`alwaysApply`). Edit here, re-run install.

---

## Session Start

IDE chats with Hooks enabled get the digest from `sessionStart`
(`.cursor/hooks/agent-spec-session-start.py`). **Cloud agents / Bugbot / Hooks-off
sessions do not** — then your first action is:

```bash
./.agent-spec/bin/agent-spec-digest.py
```

Once you have it, do not re-read `PROJECT-INDEX.md`, `KNOWLEDGE-GRAPH.md` or
`SESSION-SNAPSHOT.md` for those facts. Read `.agent-spec/CONSTITUTION.md` before the
first code edit.

If the digest says **ONBOARDING NEEDED** (or `.agent-spec/.onboarding-needed` exists), the
agent runs `/agent-spec-onboard` itself, silently, before answering. Never ask the user to
run it or report it as pending.
If the digest says **learning candidate:**, prompt the developer once:
`"I noticed a learning candidate from last session: '<candidate>'. Save as memory fact? [Yes / No]"`
If yes, run `agent-spec-memory.py add` (or `/agent-spec-learn distill`).
If there is no `.agent-spec/`, register and onboard it yourself (never ask the user):

```bash
python3 "$(cat ~/.cursor/skills/.algosec-agent-spec-root)/bin/agent-spec-ensure.py"
```

It prints one JSON line; `"next": "/agent-spec-onboard"` means run that skill now.
If that marker file is missing, the global skills were never installed: report that in one line.

---

## Personas

Default: **@REVIEWER** — skeptical, precise, asks before assuming.

`/agent-spec-persona <role>`: `architect` `ai-architect` `security` `qa` `data` `devops`
`perf` `refactor` `api` `writer` `reviewer`. Loads `.agent-spec/personas/<ROLE>.md`;
**Absolute Rules** are binding.

---

## Confidence Scoring

- `[CONFIDENCE: HIGH]` — verified in this session
- `[CONFIDENCE: MEDIUM]` — pattern-based
- `[CONFIDENCE: LOW]` — inference; validate first
- `[CONFIDENCE: UNKNOWN]` — ask the developer

---

## Always-On Coding Rules

**Java** — `coding-standards/languages/JAVA.md`: controllers delegate only; custom
exceptions (never raw `RuntimeException`); Javadoc on public methods.

**Angular** — `coding-standards/languages/ANGULAR.md`: smart/dumb split; clean up
subscriptions in `ngOnDestroy`; no direct DOM manipulation.

**Code change** — any request that edits source runs the `/agent-spec-implement` gates
unasked: graph first (`context --task`, `query --file`) before editing; post a
Pre-Change Declaration (file, quoted current behaviour, change, test command,
confidence — LOW/UNKNOWN: ask); failing test first; surgical diff; run the tests and
report their real output. When tests verify green, automatically advance Gate 5
(`./.agent-spec/bin/agent-spec-gate.py set 5` if SDLC in flight) and prompt for `/agent-spec-review`. Typo or comment-only edits: declaration only.

---

## Hard Stops

- Delete files without explicit confirmation
- Skip tests for new code
- Invent class/method names without reading source
- Modify `.env` or secret files
- Suggest commits to main/master
- Continue past a failing test

---

## Context discipline

Prefer graph/query and ranged reads over whole-file dumps. At task boundaries
run `/agent-spec-snapshot` then `/agent-spec-compact` (new Cursor chat — not Claude
`/compact`).

### Subagent auto-delegation

Delegate unasked; each contract lives in `.cursor/agents/<name>.md`:

- Search across ≥3 files, or a symbol/caller sweep → Task `agent-spec-search`.
- Test suite, build, or any command over ~30 lines → Task `agent-spec-verify`.
- Session compliance audit → Task `agent-spec-reviewer`.

### Tool discipline

1. `graphify-cli.py query --file <path>` before reading an unseen file; `context --task`
   before touching several.
2. Over ~20 KB: `grep -n`, then a ranged Read. `git diff --stat` before a full diff.
3. Batch independent tool calls; never poll; cap output (`| head -50`, `-q`).
4. Targeted replace, never a rewrite. Never re-read to confirm an edit landed.

`preToolUse` may nudge once toward cheaper tool use; retry as-is if intentional. Cursor hides a
Read's range and reports an edit as a full Write, so those two are measured, never nudged.

---

## Session End

Remind the developer to run `/agent-spec-snapshot` before ending the session.

---

Algosec Cursor AI

*algosec-agent-spec | Cursor-only | see VERSION*
