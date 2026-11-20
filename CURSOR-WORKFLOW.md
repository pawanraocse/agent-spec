# CURSOR-WORKFLOW.md — agent-spec (code-work protocol)

> Installed as `.cursor/rules/agent-spec-workflow.mdc` (Agent Requested, not always-on).
> `CURSOR.md` sends a task here once it is **Code work**: it searches across files, edits
> source or runs tests. A Direct reply never needs it. Edit here, re-run install.

---

## Personas

Default: **@REVIEWER** — skeptical, precise, asks before assuming.

`/agent-spec-persona <role>`: `architect` `ai-architect` `security` `qa` `data` `devops`
`perf` `refactor` `api` `writer` `reviewer`. Loads `.agent-spec/personas/<ROLE>.md`;
**Absolute Rules** are binding.

## Confidence Scoring

Tag claims about this codebase:

- `[CONFIDENCE: HIGH]` — verified in this session
- `[CONFIDENCE: MEDIUM]` — pattern-based
- `[CONFIDENCE: LOW]` — inference; validate first
- `[CONFIDENCE: UNKNOWN]` — ask the developer

---

## Coding Rules

**Java** — `coding-standards/languages/JAVA.md`: controllers delegate only; custom
exceptions (never raw `RuntimeException`); Javadoc on public methods.

**Angular** — `coding-standards/languages/ANGULAR.md`: smart/dumb split; clean up
subscriptions in `ngOnDestroy`; no direct DOM manipulation.

**Code change** — a request that edits source beyond the Small tier runs the
`/agent-spec-implement` gates unasked: read `.agent-spec/CONSTITUTION.md` once; graph first
(`context --task`, `query --file`) before editing; post a Pre-Change Declaration (file,
quoted current behaviour, change, test command, confidence — LOW/UNKNOWN: ask); failing
test first; surgical diff; run the tests and report their real output. When tests verify
green, advance Gate 5 (`./.agent-spec/bin/agent-spec-gate.py set 5` if SDLC in flight) and
prompt for `/agent-spec-review`. Typo or comment-only edits: declaration only.

---

## Context discipline

Prefer graph/query and ranged reads over whole-file dumps. At task boundaries
run `/agent-spec-snapshot` then `/agent-spec-compact` (new Cursor chat — not Claude
`/compact`).

### Subagent auto-delegation

A subagent starts cold and re-sends its own system prompt, so delegate only when its
output would be larger than that. Each contract lives in `.cursor/agents/<name>.md`:

- Search across ≥3 files, or a symbol/caller sweep → Task `agent-spec-search`.
- Test suite, build, or any command over ~30 lines → Task `agent-spec-verify`.
- Session compliance audit → Task `agent-spec-reviewer`.

### Tool discipline

1. Find code with `./.agent-spec/bin/graphify-cli.py` before grep or Read (commands in
   the digest).
2. Over ~20 KB: `grep -n`, then a ranged Read. `git diff --stat` before a full diff.
3. Batch independent tool calls; never poll; cap output (`| head -50`, `-q`).
4. Targeted replace, never a rewrite. Never re-read to confirm an edit landed.

`preToolUse` may nudge once toward cheaper tool use; retry as-is if intentional. Cursor hides a
Read's range and reports an edit as a full Write, so those two are measured, never nudged.

---

## Session End

After Code work that changed files, remind the developer once to run `/agent-spec-snapshot`.

Digest says **learning candidate:** — at the end of a Code work reply, ask once:
`"I noticed a learning candidate from last session: '<candidate>'. Save as memory fact? [Yes / No]"`.
Yes → `agent-spec-memory.py add` (or `/agent-spec-learn distill`).
