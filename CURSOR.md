# CURSOR.md — algosec-agent-spec (canonical always-on rules)

> Loaded into `.cursor/rules/agent-spec.mdc` (`alwaysApply: true`) by `./install.sh`.
> Edit this file in the **package**, then re-run install/register to refresh projects.
> Do not maintain a second copy in AGENTS.md.

---

## Session Start

IDE chats with Hooks enabled get the digest from `sessionStart`
(`.cursor/hooks/agent-spec-session-start.py`). **Cloud agents / Bugbot / Hooks-off
sessions do not** — then your first action is:

```bash
./.agent-spec/bin/agent-spec-digest.py
```

~1,700 bytes: stack, graph size, pipeline gate, last session, remembered constraints.
**Once you have it, do not re-read** `PROJECT-INDEX.md`, `KNOWLEDGE-GRAPH.md`, or
`SESSION-SNAPSHOT.md` for those facts.

Also needed sometimes:

- `.agent-spec/CONSTITUTION.md` — before the first code edit of the session.
- Structure — query, do not read whole files:
  `./.agent-spec/bin/graphify-cli.py query --file <path>`

If the digest says **ONBOARDING NEEDED** (or `.agent-spec/.onboarding-needed` exists), the
agent runs `/agent-spec-onboard` itself, silently, before answering. Never ask the user to
run it or report it as pending.
If there is no `.agent-spec/`, install it yourself, then onboard (never ask the user):

```bash
"$(cat ~/.cursor/skills/.algosec-agent-spec-root)/install.sh" --register "<absolute path of the opened Cursor folder>"
```

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
report their real output. Typo or comment-only edits: declaration only.

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

Prefer graph/query and ranged reads over whole-file dumps. Broad sweeps → Task
`agent-spec-search`. Noisy builds/tests → Task `agent-spec-verify`. At task boundaries
run `/agent-spec-snapshot` then `/agent-spec-compact` (new Cursor chat — not Claude
`/compact`).

### Tool discipline

1. Structure before content: `graphify-cli.py query --file <path>` before reading a file you
   have not seen; `context --task "<task>"` before touching several files.
2. Never read a file over ~20 KB whole — `grep -n`, then Read with `offset`/`limit`.
3. `git diff --stat` before any full diff; `--name-only` to list files.
4. Batch independent tool calls in one message; do not poll.
5. Edit with a targeted replace; never rewrite a file to change a few lines.
6. Cap noisy output (`| head -50`, `-q`); build/test runs go to `agent-spec-verify`.
7. Do not re-read a file to confirm an edit landed, or re-read the digest facts.

`preToolUse` may nudge once toward cheaper tool use; retry as-is if intentional. A team can
make it a hard stop with `AGENT_SPEC_READ_HARD_CAP_KB=<n>` (rangeless Read ≥ n KB denied).

---

## Session End

Remind the developer to run `/agent-spec-snapshot` before ending the session.

---

Algosec Cursor AI

*algosec-agent-spec | Cursor-only | see VERSION*
