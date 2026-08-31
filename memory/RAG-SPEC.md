# RAG Integration Specification

> **Goal: Extend agent memory to massive codebases using Retrieval-Augmented Generation.**

For codebases exceeding 1,000 files, explicit indexing via Graphify becomes unwieldy to load into a single prompt. In these environments, `agent-spec` integrates with vector databases or MCP (Model Context Protocol) servers.

## When to Use RAG

RAG should be enabled when:
- The project index exceeds 500 lines.
- The `KNOWLEDGE-GRAPH.md` becomes too large to render effectively.
- The agent is searching for implementations of abstract concepts (e.g., "Where do we handle cross-origin headers?").

## MCP (Model Context Protocol) Integration

`agent-spec` recommends using an MCP-compatible memory server (like `memory-mcp` or a custom vector indexer).

When an MCP memory server is active, the agent must alter its Gate 1 (Discovery) behavior:

### Standard Gate 1
`Agent reads PROJECT-INDEX.md`

### RAG-Enhanced Gate 1
```
Agent queries MCP Memory Server:
query: "Get architecture overview and current active tasks"
query: "Find all files related to password reset functionality"
```

## Creating a RAG-Compatible Index

If you are building a custom RAG index for an `agent-spec` project, index the following artifacts with highest priority:
1. `.agent-spec/sdlc/*` (Captures the *intent* and requirements).
2. `.agent-spec/CONSTITUTION.md` (Captures the rules).
3. `src/**` (The actual code).

By embedding the SDLC documents alongside the code, the vector search can connect a developer's vague query ("fix the password bug") to the exact business requirement defined in `03-PRD.md` and the resulting code in `PasswordResetService.java`.
