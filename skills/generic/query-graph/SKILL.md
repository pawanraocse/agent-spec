---
name: "query-graph"
description: "Run the Graphify CLI to query the architecture instead of loading the whole graph."
allowed-tools:
  - "Read"
  - "Write"
  - "Bash"
---

# Query-graph

## Execution Prompt
1. Run `./.agent-spec/bin/graphify-cli.py --help` to see available commands.
2. Use `query --file <path>` to see file imports and blast radius.
3. Use `search <keyword>` to find domain components.
4. Use `stats` for an overview.
