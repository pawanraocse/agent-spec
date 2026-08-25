---
name: "index-project"
description: >-
  Rebuild the dependency graph and PROJECT-INDEX.md from the current tree. Run it after adding files, moving modules or changing architecture — every other skill's structural answers are only as fresh as this. Use when the graph is stale, at the end of a session, or when a query returns something that contradicts the code.
---

# index-project

## Run

```bash
./.agent-spec/bin/agent-spec-index
```

It walks the tree, extracts imports, **resolves each one to a file in the graph**, and
writes:

- `.agent-spec/graph/knowledge-graph.json` — nodes, resolved edges, external package counts
- `.agent-spec/graph/KNOWLEDGE-GRAPH.md` — the human-readable summary
- `.agent-spec/PROJECT-INDEX.md` — only if absent; an existing one is left alone so human
  notes survive

## Read the output

The last line is the health check:

```
91 files, 225 internal edges (42% of imports are internal), 33 external packages, 0 cycles
```

- **0 internal edges** on a codebase that obviously has them means resolution failed —
  usually an unindexed language. Check the extension is in `ALLOWED_EXTS`.
- **Cycles > 0** is an architecture finding. Surface it; do not silently continue.
- **Stack: Unknown** means no manifest was found at the root or one level down.

## Rules

- Never hand-edit `knowledge-graph.json`. It is generated; edits vanish on the next run.
- Never simulate the indexer by reading the tree yourself. If `python3` is missing, say so
  and stop — a hand-built graph is worse than no graph, because everything downstream
  trusts it.
- Re-run after any change that moves or renames files, then re-check the queries that
  informed the current task.
