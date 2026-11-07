---
name: "agent-spec-query-graph"
description: >-
  Answer structural questions from the dependency graph, not file reads. Blast radius, service wiring, layers, endpoints, context selection.
---

# query-graph

Every answer here costs a few hundred tokens. The equivalent file reads cost tens of
thousands, and are less accurate — a grep finds the string, the graph finds the edge.

```bash
CLI=./.agent-spec/bin/graphify-cli.py
```

## Pick the verb by the question

| Question | Command |
|---|---|
| What breaks if I change this file? | `$CLI query --file <path> --depth 2` |
| Which files does this task need? | `$CLI context --task "<description>"` |
| How does a request flow through? | `$CLI flow --from <entry-point>` |
| Which services are there, what talks to what? | `$CLI services` |
| What is the HTTP surface? | `$CLI endpoints [--service <name>]` |
| Is the architecture holding? | `$CLI layers` |
| Where is X? | `$CLI search <keyword>` |
| How coupled is this directory? | `$CLI module <path>` |
| Overview | `$CLI stats` |
| Any import cycles? | `$CLI cycles` |

## `context` is the one to reach for first

Before opening a single file for a new task:

```bash
./.agent-spec/bin/graphify-cli.py context --task "add a discount to order pricing" --budget 12
```

It returns the file list and stops. Read those files. **Do not then walk the tree
anyway** — if the list looks wrong, the task description was vague; sharpen it and
re-run, or raise `--budget`. Widening by hand is how a 2,000-token task becomes a
40,000-token one.

## Integration edges

`type=imports` is a source dependency. `type=http` and `type=message` are recovered from
call sites and broker annotations — two services that talk over Kafka share no import, so
these are the only edges that show the coupling at all. Treat a `message` edge as real
and an `http` edge as strong evidence: it is matched on a service name appearing in a URL.

## Rules

- **Never invent a dependency the graph does not show.** If `query` returns `(none)`,
  report `(none)` — do not guess from the filename.
- A stale graph is worse than no graph. If the file you are asking about is not in it,
  run `/agent-spec-index-project` and ask again.
- `layers` reports a heuristic classification. A violation is a finding to raise, not a
  fact to act on unilaterally.
