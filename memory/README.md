# Agent Memory System

> **A stateless agent is a hallucinating agent.**

The `agent-spec` memory system solves the "amnesia" problem where language models lose the context of the project between chat sessions. By maintaining a strict set of explicit state files, the agent can always reconstruct its understanding of the codebase.

---

## Core Components

1. **[PROJECT-INDEX.md](PROJECT-INDEX.md)**: The human-readable narrative of the project. Tells the agent *what* the project is, what the modules do, and what the major architectural decisions are.
2. **[KNOWLEDGE-GRAPH.md](KNOWLEDGE-GRAPH.md)**: The machine-readable dependency map (Graphify). Tells the agent *how* components interact, preventing circular dependencies and incorrect assumptions about structure.
3. **[SESSION-SNAPSHOT.md](SESSION-SNAPSHOT.md)**: The point-in-time capture of current work. Tells the agent *where* we left off in the previous session.

## Context Budgeting

Loading the entire project into the context window for every prompt is inefficient and degrades performance (the "needle in a haystack" problem).

See **[CONTEXT-BUDGET.md](CONTEXT-BUDGET.md)** for rules on how the agent must select which files to read based on the `KNOWLEDGE-GRAPH.md`, rather than reading everything.

## RAG Integration

For very large codebases (>1000 files), explicit indexing is not enough. See **[RAG-SPEC.md](RAG-SPEC.md)** for integrating vector search (e.g., via MCP servers) into the agent's memory retrieval process.
