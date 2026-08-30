---
name: "agent-spec-snapshot"
description: >-
  Append a dated section to SESSION-SNAPSHOT.md, rotate the old ones, promote durable facts to memory. Use at session end.
---

# agent-spec-snapshot

1. Review the chat history for the current session.
2. Summarise completed tasks, modified files, and next steps.
3. **Append a new dated section to `.agent-spec/SESSION-SNAPSHOT.md`; do not overwrite the
   file.** The snapshot is a running record — corrections to earlier work, decisions locked
   and later reversed, and the reasoning behind them are its most valuable content, and an
   overwrite destroys all of it.
4. **One snapshot file per repository.** Its location is the project's call (`.agent-spec/`
   by default, repository root where `CLAUDE.md` says so) — but creating a second copy in
   the other place fragments the history across two files, which is the failure this rule
   prevents. Check `CLAUDE.md` before writing.

Record: what was built, what broke, decisions locked or still open, **corrections made to
your own earlier work**, and which files the next session should load.

## Promote the durable facts

A snapshot section is read by a human catching up. A fact is read by every session
automatically. Anything from this session that will still be true in three months belongs
in both:

```bash
./.agent-spec/bin/agent-spec-memory.py add --type decision --subject "<short>" \
  --source "SESSION-SNAPSHOT <date>" "<one sentence>"
```

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
