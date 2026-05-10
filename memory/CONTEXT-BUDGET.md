# Context Budgeting Rules

> **Goal: Prevent context window exhaustion and "needle in a haystack" degradation.**

AI agents have finite context windows. More importantly, as the context window fills up, the agent's ability to accurately follow instructions degrades. `agent-spec` enforces strict context budgeting.

## 1. Never Load the Whole Project
The agent must **never** attempt to load the entire `src/` directory into its context, even if the model supports 200K+ tokens.

## 2. Load by Graph Distance
To select which files to read, the agent must use `KNOWLEDGE-GRAPH.md`.
1. **Target Node**: The file being modified (Distance 0).
2. **Immediate Dependencies**: The files the target imports/uses (Distance 1).
3. **Immediate Dependents**: The files that use the target (Distance -1).

**Rule**: Load *only* Distance 0, 1, and -1 files into context. Do not load Distance 2+ unless specifically hunting a deep bug.

## 3. Use Token Reduction Skills
When discussing architectural plans or reviewing large codebases, the agent should be instructed to use token-reduction skills:

- `/caveman`: Emits code only. Zero explanation. Good for rapid iterations where the developer already knows the "why".
- `/defluffer`: Removes conversational filler ("Certainly!", "I'd be happy to!"). Reduces output tokens by 40%.
- `/dense`: Uses abbreviations, tables, and bullet points.

## 4. The 70% Warning
If the agent detects that the conversation has consumed >70% of the available context window, it must autonomously issue a warning:

> ⚠️ **CONTEXT BUDGET WARNING**: We are approaching the limit of the effective context window. I recommend running `/snapshot` to save our state, and starting a new chat session to prevent logic degradation.
