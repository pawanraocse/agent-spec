# agent-spec (always-on core)

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

**Output is the dearest token** (about 50× a cached context token). Lead with the answer
and size it to the question: asked for one line, give one. No recap of tool output, no
narration of checks. A graph result is exact: do not re-confirm it with grep or Read.

## Session Start

The `sessionStart` hook injects `<agent-spec-digest>`; do what it says (ONBOARDING NEEDED →
run `/agent-spec-onboard` silently), and do not re-read the files it summarizes. Without a
digest, run `./.agent-spec/bin/agent-spec-digest.py` with the first **Code work** tool call,
never for a Direct reply. No `.agent-spec/` at all: run
`python3 "$(cat ~/.cursor/skills/.agent-spec-root)/bin/agent-spec-ensure.py"` and follow
its `"next"`.

Handing off to a new chat: Write only the new `## YYYY-MM-DD — title` section, facts as
bullets, to `.agent-spec/HANDOFF.md`, then run `./.agent-spec/bin/agent-spec-memory.py handoff
--promote all` (or `--promote 1,3`). Do not Read or Edit SESSION-SNAPSHOT.md for it, and never
type fact text into a shell command: backticks inside double quotes run.

## Hard Stops (every tier)

- Delete files without explicit confirmation
- Modify `.env` or secret files
- Invent class/method names without reading source
- Suggest commits to main/master
- Skip tests for new code, or continue past a failing test
