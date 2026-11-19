# CURSOR.md — algosec-agent-spec (always-on core)

> Installed as `.cursor/rules/agent-spec.mdc` (`alwaysApply`). The code-work protocol lives
> in `CURSOR-WORKFLOW.md`, installed as `.cursor/rules/agent-spec-workflow.mdc` and loaded
> only when a task needs it. Edit here, re-run install.

---

## Scale to the task (decide this first)

This rule rides in every turn, and every tool call re-sends the whole context. The
cheapest correct reply wins, so pick the smallest tier that answers the request:

- **Direct** — a question, an explanation, an opinion, a draft, anything answerable from
  this chat or general knowledge. Answer in prose. **Zero tool calls**: no preflight, no
  digest run, no graph query, no confidence tags, no declaration, no snapshot reminder.
- **Small** — one file, a few lines, the location already known. Read that range, edit,
  run the nearest test. No graph query, no subagent, no Pre-Change Declaration.
- **Code work** — anything else that searches across files, edits source or runs tests.
  Apply the `agent-spec-workflow` rule (`.cursor/rules/agent-spec-workflow.mdc`) before the
  first tool call; if Cursor has not attached it, Read that file in the same batch as your
  first tool call.

When unsure, start Direct and escalate only once the answer needs the repo.

---

## Session Start

IDE chats with Hooks enabled get the digest from `sessionStart`
(`.cursor/hooks/agent-spec-session-start.py`). Cloud agents, Bugbot and Hooks-off sessions
do not: run `./.agent-spec/bin/agent-spec-digest.py` with the first **Code work** tool call,
never for a Direct reply. Once you have it, do not re-read `PROJECT-INDEX.md`,
`KNOWLEDGE-GRAPH.md` or `SESSION-SNAPSHOT.md` for those facts.

- Digest says **ONBOARDING NEEDED** (or `.agent-spec/.onboarding-needed` exists): run
  `/agent-spec-onboard` yourself, silently, before the first Code work step. Never ask the
  user to run it or report it as pending.
- No `.agent-spec/` and the task is Code work: run
  `python3 "$(cat ~/.cursor/skills/.algosec-agent-spec-root)/bin/agent-spec-ensure.py"`.
  `"next": "/agent-spec-onboard"` means run that skill now. A missing marker file means the
  global skills were never installed: say so in one line.

---

## Hard Stops (every tier)

- Delete files without explicit confirmation
- Modify `.env` or secret files
- Invent class/method names without reading source
- Suggest commits to main/master
- Skip tests for new code, or continue past a failing test

---

Algosec Cursor AI

*algosec-agent-spec | Cursor-only | see VERSION*
