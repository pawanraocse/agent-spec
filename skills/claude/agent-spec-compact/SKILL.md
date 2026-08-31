---
name: "agent-spec-compact"
description: >-
  Portable context reset: write state to disk, then start a fresh session. Works in Cursor as well as Claude Code, and the summary survives the session.
---

# agent-spec-compact

Cutting a long session is the largest saving measured anywhere in this framework:
**480,083 tokens to 53,191, and 308,223 to 46,101.** Claude Code's built-in `/compact`
does it, but it exists only there and its summary dies with the session. This does the
same job with a file, so it works in Cursor too and the record outlives the thread.

## 1. Check that it pays

```bash
./.agent-spec/bin/agent-spec-tokens.py context
```

It prints the break-even in turns. Below about one turn — which is almost always — cutting
wins. If no transcript is available, cut anyway at a task boundary.

## 2. Write the state down

Follow `agent-spec-snapshot`: append a dated section to `.agent-spec/SESSION-SNAPSHOT.md`
covering what was built, what broke, decisions locked or still open, corrections to your
own earlier work, and the files the next session needs. Append; never overwrite.

Then promote the durable facts, one per call:

```bash
./.agent-spec/bin/agent-spec-memory.py add --type constraint "<one sentence>"
```

A snapshot section is for a human catching up. A fact is injected into every future
session, so it must be worth that.

## 3. Start the new session

Tell the user, in one line, to open a fresh session. In Claude Code the `SessionStart`
hook re-injects the digest — snapshot summary, remembered facts, gate, graph size — for
about 1,700 bytes. In Cursor, the first action is:

```bash
./.agent-spec/bin/agent-spec-digest.py
```

## What this is not

It is not compression. Context cannot be compressed: a cache read is cheap *because* the
bytes are unchanged, so editing them forces a full re-write at a higher price. The only
two moves are carry it or start again, and this is how you start again without losing what
you knew.

Mid-task, where the working thread matters more than the tokens, Claude Code's `/compact`
is the better trade — it keeps the conversation. Use this at task boundaries, and when the
record needs to outlive the session.
