# Cursor Skill: index-project

**Description**: Run Graphify to build or update the KNOWLEDGE-GRAPH.md

## Instructions for Cursor
1. Run the indexer from the repo root:
   `./.agent-spec/bin/agent-spec-index`
   It auto-detects the stack, rebuilds `.agent-spec/graph/knowledge-graph.json`, and regenerates
   `.agent-spec/graph/KNOWLEDGE-GRAPH.md`. `PROJECT-INDEX.md` is preserved — it holds human notes.
2. Verify the outputs refreshed: both files under `.agent-spec/graph/` should carry a current
   `generated` / `Last indexed` timestamp, and the run should report file + dependency counts.
3. Only if the script is genuinely unavailable, fall back to
   `python3 .agent-spec/bin/graphify-build.py`, or manually update
   `.agent-spec/graph/knowledge-graph.json` + `.agent-spec/graph/KNOWLEDGE-GRAPH.md`.

**Paths matter here.** The graph files live under `.agent-spec/graph/`, not the repo root. The
entrypoint installed into a project is `.agent-spec/bin/agent-spec-index` — a bash wrapper around
`graphify-build.py`. The `.sh` suffix exists only in the agent-spec source repo; the installer
strips it (`agent-spec-init.sh`), so `bin/agent-spec-index.sh` never resolves inside a project.
