---
name: "query-graph"
description: >-
  Answer structural questions from the dependency graph, not file reads. Use for blast radius, coupling, cycles, "where is X".
---

# query-graph

Reading the tree to learn the structure is the single most expensive habit an agent has.
The graph already knows. Ask it.

## Commands

```bash
./.agent-spec/bin/graphify-cli.py stats                       # stack, size, hot files, cycles
./.agent-spec/bin/graphify-cli.py query --file <path>         # imports + blast radius
./.agent-spec/bin/graphify-cli.py query --file <path> --depth 3
./.agent-spec/bin/graphify-cli.py search <keyword>            # find files, ranked by dependents
./.agent-spec/bin/graphify-cli.py module <dir>                # what a directory depends on and who uses it
./.agent-spec/bin/graphify-cli.py cycles                      # import cycles
```

`--file` takes a suffix, not the full path: `query --file contracts/facts.py` resolves.
An ambiguous suffix lists the candidates rather than guessing.

## Which command answers which question

| Question | Command |
|---|---|
| What breaks if I change this? | `query --file <path>` — read the BLAST RADIUS block |
| Is this file safe to delete? | `query` — an empty blast radius means nothing imports it |
| Where does this concept live? | `search <keyword>` — ranked, so the first hit is usually the core |
| Is this module layered correctly? | `module <dir>` — DEPENDS ON should not contain higher layers |
| What is the shape of this project? | `stats` |
| Why is this hard to change? | `cycles` |

## Rules

- Run this **before** opening files, not after. The point is to open fewer.
- The blast radius is the read list. Load those files, not the directory.
- `(none)` in BLAST RADIUS means nothing internal imports it — either a genuine entry
  point, or dead code. Say which; do not assume.
- A stale graph gives confident wrong answers. If the tree has changed since the last
  index, run `/index-project` first. The CLI warns when the graph predates version 3.0.
- Markdown and config files are not indexed. `Could not find` for those is expected, not
  an error.
