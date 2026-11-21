---
name: "agent-spec-snapshot"
description: >-
  Append a dated section to SESSION-SNAPSHOT.md, rotate the old ones, promote durable facts to memory. Use at session end.
---

# agent-spec-snapshot

## When to run

- **Session end** — you are about to close the chat.
- **Context at ~70%** — prevents silent truncation of the history the next session needs.
- **Before `/agent-spec-compact`** — state must be written to disk before the context is reset.
  A compact without a snapshot loses everything the session learned.

## Steps

1. Review the chat history for the current session.
2. Summarise completed tasks, modified files, and next steps.
3. **Append a new dated section to `.agent-spec/SESSION-SNAPSHOT.md`; do not overwrite the
   file.** The snapshot is a running record — corrections to earlier work, decisions locked
   and later reversed, and the reasoning behind them are its most valuable content, and an
   overwrite destroys all of it.
4. **One snapshot file per repository.** Its location is the project's call (`.agent-spec/`
   by default, repository root where `AGENTS.md` says so) — but creating a second copy in
   the other place fragments the history across two files, which is the failure this rule
   prevents. Check `AGENTS.md` before writing.

Record: what was built, what broke, decisions locked or still open, **corrections made to
your own earlier work**, and which files the next session should load.

Use this shape. The `sessionStart` digest lifts the heading, the first three `### Open`
bullets and the `### Load next session` line into every new chat, so a section without
them resumes with a title and nothing else:

```markdown
## YYYY-MM-DD — <one-line theme>

### Done
- <what was built, with commit hashes when committed>

### Corrections
- <what you got wrong earlier in the session, and the fix>

### Open
- <most important unfinished item first; one bullet each, one or two sentences>

### Load next session
`path/one.py`, `path/two.md`
```

## Promote the durable facts

A snapshot section is read by a human catching up. A fact is read by every session
automatically. Anything from this session that will still be true in three months belongs
in both:

The cheapest way to add the section: Write it, and only it, to `.agent-spec/HANDOFF.md`,
then one call puts it above the archive index, records the picked bullets and rotates:

```bash
./.agent-spec/bin/agent-spec-memory.py handoff --promote 2,4 --type decision
```

That never reads or edits the large snapshot file. For a section already in the file:

```bash
./.agent-spec/bin/agent-spec-memory.py promote                 # numbers the new section's bullets
./.agent-spec/bin/agent-spec-memory.py promote --pick 2,4 --type decision
```

`promote` reads the fact text from the section you just wrote, so each fact is written once
and never passes through shell quoting. Typing the fact into an `add` command instead puts
backticks inside double quotes: a shell runs them as commands and the fact is saved mangled,
and a permission-gated agent has the call refused. If you must use `add`, single-quote the
text: `add --type gotcha --subject 'short' 'one sentence'`.

Promote sparingly — a decision and its reason, a constraint someone imposed, a trap that
cost time. Not the narrative. See [`agent-spec-remember`](../agent-spec-remember/SKILL.md).

## Rotate

```bash
./.agent-spec/bin/agent-spec-memory.py rotate
```

Append-only and unbounded are different things. Past about 12 KB the file stops being
loadable in full, and whatever loads it truncates — silently, oldest first. `rotate` moves
the older sections into `.agent-spec/memory/snapshots/` where they can still be read on
purpose. Nothing is deleted.

Run it after appending. It is a no-op below the threshold.

## Hard stops

- Never overwrite the file, and never delete a section. Rotation moves; it does not remove.
- Never write a snapshot that reports work as done when it is not. The next session
  believes this file.
- Never promote a guess to memory. A wrong fact is read as established every session.
