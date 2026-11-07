---
name: "agent-spec-compact"
description: >-
  Portable context reset: write state to disk, then start a fresh Cursor chat. The summary survives the session.
---

# agent-spec-compact

Cutting a long session is the largest saving measured in this framework:
**480,083 tokens to 53,191, and 308,223 to 46,101.**

In Cursor there is no Claude `/compact` product surface. This skill writes state to disk
and tells the user to open a **new chat** so the next session starts lean.

## 1. Write the state down

Follow `agent-spec-snapshot`: append a dated section to `.agent-spec/SESSION-SNAPSHOT.md`
(what was built, what broke, decisions, corrections, files for next session). Append;
never overwrite.

Promote durable facts:

```bash
./.agent-spec/bin/agent-spec-memory.py add --type constraint "<one sentence>"
```

Rotate if the snapshot file is large:

```bash
./.agent-spec/bin/agent-spec-memory.py rotate
```

## 2. Start the new Cursor chat

Tell the user, in one line, to open a **new Cursor chat** in this workspace (or restart
the agent). With Hooks enabled, `sessionStart` re-injects the digest (~1,700 bytes). If
Hooks are off or this is a cloud agent, the first action in the new chat is:

```bash
./.agent-spec/bin/agent-spec-digest.py
```

## What this is not

Not compression of the current thread. The only two moves are carry context or start
again; this is how you start again without losing what you knew. Use at **task
boundaries**. Mid-task, keep the thread if the working conversation matters more than
tokens.
