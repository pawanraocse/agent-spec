---
name: "snapshot"
description: >-
  Append a dated section to SESSION-SNAPSHOT.md. Never overwrites. Use at session end, or past 70% context.
---

# Snapshot Skill

1. Review the chat history for the current session.
2. Summarize completed tasks, modified files, and next steps.
3. **Append a new dated section to `SESSION-SNAPSHOT.md`; do not overwrite the file.** The
   snapshot is a running record — corrections to earlier work, decisions locked and later
   reversed, and the reasoning behind them are its most valuable content, and an overwrite
   destroys all of it.
4. **One snapshot file per repo.** Its location is the project's call (`.agent-spec/` by
   default, repo root where `CLAUDE.md` says so) — but creating a second copy in the other
   place fragments the history across two files, which is the failure this rule prevents.
   Check `CLAUDE.md` before writing.

Record: what was built, what broke, decisions locked or still open, **corrections made to
your own earlier work**, and which files the next session should load.
