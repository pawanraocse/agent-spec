---
name: "agent-spec-ask"
description: >-
  Answer a question about this project or its past AI sessions from the local index — code, docs, rules, memory, request traces, reviews — with a citation on every claim. Use for "why was X done", "what changed last session", "which skill built Y", "have we done this before", or the dashboard's Ask in Cursor button.
dashboard:
  category: Project
  icon: message-square-text
  emits: [answer]
---

# agent-spec-ask

The project index is local SQLite (`.agent-spec/platform/platform.db`) built from the
working tree, `.agent-spec/` artifacts, every request trace of this workspace and the AI
session reviews. Retrieve from it first; answer only from what you retrieved.

## 1. Retrieve

```bash
./.agent-spec/bin/agent-spec-platform.py ask "<question>" --sources 800
```

(In the package repo itself the CLI is `bin/agent-spec-platform.py`.) The command refreshes the
index incrementally, then prints numbered hits (`[n] kind ref`), related files from the import
graph and, with `--sources`, each hit's text. Narrow it when the question names a scope:

| Question shape | Add |
|---|---|
| about past sessions, prompts, what Cursor did | `--kind request,review` and `--since <ISO date>` |
| about a module or folder | `--path <prefix>` |
| about rules, skills, instructions | `--kind rule` |
| about a decision or constraint | `--kind memory,doc` |
| one conversation | `--session <conversation_id>` |

For one request's tools, edits and failures, follow a `request <id>` hit with
`agent-spec-platform.py trace --request <id>`; for its measured outcome,
`agent-spec-platform.py signals --request <id>`. For structure (callers, blast radius) use
`graphify-cli.py`, not more searches.

At most three retrieval calls. If the hits do not answer the question, say so.

## 2. Answer

- Lead with the answer in two to five sentences, then the evidence.
- Every claim cites a hit: `path:start-end` for code and docs, `request <id>` or
  `review <conversation_id>` for history. Read a cited range before quoting it.
- Separate what the sources show from what you infer; mark inference as such.
- Never cite a path, function, span or session the commands above did not return.

## Hard stops

- No answer without at least one cited hit.
- Prompt and response text from past sessions stays paraphrased; never repeat a
  secret-shaped value even if the index shows one redacted.
- Read-only: this skill changes no file. A fix it suggests is a separate request.
