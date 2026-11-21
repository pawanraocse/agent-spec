# Claude Code head-to-head: bare vs the agent-spec harness

Run `20261121T180024-c82667`, 2026-11-21T12:30:24.911Z. Not Cursor: Claude Code `2.1.328 (Claude Code)`, model `claude-haiku-5-5`, 1 task(s) x 5 turn(s), 1 repeat(s), Linux 6.6.87.2-microsoft-standard-WSL2.

**Cost gate: FAIL** — cost $0.0351 is over the limit $0.0139 (base $0.0139 +0.0%).

| Metric | Bare | Harness | Change |
|---|---|---|---|
| Cost (USD, Claude Code's own) | 0.0139 | 0.0351 | +153% |
| Correct | 5/5 | 5/5 | |
| Input tokens (uncached) | 26 | 42 | +62% |
| Cache-read tokens | 570,084 | 1,038,243 | +82% |
| Cache-write tokens | 28,785 | 39,391 | +37% |
| All input (uncached + cache) | 598,895 | 1,077,676 | +80% |
| Output tokens | 4,866 | 11,414 | +135% |
| Tool calls | 12 | 28 | +133% |
| Graph calls (graphify-cli) | 0 | 2 | — |
| Subagent calls | 0 | 3 | — |
| Workflow rule reads (turns) | 0 | 1 | — |
| Invented file names | 0 | 1 | — |
| Turns citing an invented file | 0 | 1 | — |
| Wall time (s) | 290.8 | 349.6 | +20% |

Per feature (all input tokens, wall time, correct turns, chats that used the graph, invented files):

| Feature | Bare tokens | Harness tokens | Change | Bare s | Harness s | Bare correct | Harness correct | Bare graph chats | Harness graph chats | Bare invented | Harness invented |
|---|---|---|---|---|---|---|---|---|---|---|---|
| subagent | 598,895 | 1,077,676 | +80% | 290.8 | 349.6 | 5/5 | 5/5 | 0/1 | 1/1 | 0 | 1 |

Accuracy by turn position (correct / scored, turns citing an invented file):

| Turns | Bare | Harness |
|---|---|---|
| turns 1-2 | 2/2, 0 invented | 2/2, 0 invented |
| turns 3-5 | 3/3, 0 invented | 3/3, 1 invented |
| turns 6+ | — | — |

Per task (cost, correct turns):

| Task | Bare | Harness | Change |
|---|---|---|---|
| verify-suite | $0.0139 (5/5) | $0.0351 (5/5) | +153% |

Correctness, 5 turns scored in both arms: right only without the harness 0, right only with it 0 (exact McNemar p = 1).

- Digest found in the saved chat in 5 of 5 harness-arm turn(s) (it is injected once, at the start of each chat), and in 0 bare-arm turn(s).
- Bare: the project's files only, no CLAUDE.md, no .agent-spec/, no hooks. Harness: CURSOR.md as CLAUDE.md, the project's .agent-spec/ (graph, memory, bins; not run state), the digest from a SessionStart hook, the agent-spec-search and agent-spec-verify subagents in .claude/agents/, and Cursor's preToolUse hook on Bash calls only (it sends test and build runs to agent-spec-verify). No skill in either arm; no MCP server. --setting-sources project.
- Tasks by the harness feature they exercise: subagent (verify-suite). They were picked where the harness has something to offer, so this measures that case, not an average coding chat.
- Invented file names: file names an answer cites that exist nowhere in the project or the task's prompts. Workflow rule reads: turns with a tool call naming agent-spec-workflow.mdc; Cursor can also attach it without a visible read.
- n = 1 chats per arm: a smoke test, not a benchmark.
