---
name: "index-project"
description: >-
  Rebuild the dependency graph, service map and conventions. Use after adding, moving or renaming files, and when a query looks stale.
---

# index-project

## Run

```bash
./.agent-spec/bin/agent-spec-index
```

Incremental: only files whose mtime or size moved are re-parsed. Pass `--rebuild` to the
builder directly after changing an extraction pattern, which the cache cannot detect.

It walks the tree, extracts imports and **resolves each one to a file in the graph**,
classifies every file into a layer, detects one service per manifest, and recovers the
integration edges no import graph can see — HTTP calls, Kafka and Rabbit topics, and the
served endpoint list. It writes:

- `.agent-spec/graph/knowledge-graph.json` — nodes with layer and service, resolved edges,
  integration edges, topics, layer violations, conventions
- `.agent-spec/graph/KNOWLEDGE-GRAPH.md` — the human-readable summary
- `.agent-spec/graph/CONVENTIONS.md` — observed conventions, services, HTTP surface,
  layer violations. Feeds `/onboard`; it is evidence, not yet rules.
- `.agent-spec/PROJECT-INDEX.md` — only if absent; an existing one is left alone so human
  notes survive

## Read the output

```
91 files (12 re-parsed), 225 internal edges (42% of imports are internal), 33 external packages, 0 cycles
4 services, 17 integration edges, 61 endpoints, 6 topics, 3 layer violations
```

- **0 internal edges** on a codebase that obviously has them means resolution failed —
  usually an unindexed language. Check the extension is in `ALLOWED_EXTS`.
- **Cycles > 0** is an architecture finding. Surface it; do not silently continue.
- **Layer violations > 0** is a finding too, and a heuristic one: report it with the
  offending edge so a human can judge it. Never "fix" one as a side effect of another task.
- **0 services** on a repository that has several means no manifest was found below the
  root. Say so rather than reporting a monolith.
- **Stack: Unknown** means no manifest was found at the root or one level down.

## Rules

- Never hand-edit `knowledge-graph.json`. It is generated; edits vanish on the next run.
- Never simulate the indexer by reading the tree yourself. If `python3` is missing, say so
  and stop — a hand-built graph is worse than no graph, because everything downstream
  trusts it.
- Re-run after any change that moves or renames files, then re-check the queries that
  informed the current task.
