# Claude Code head-to-head: bare vs the agent-spec harness

Run `20261121T101611-20d53a`, 2026-11-21T04:46:11.737Z. Not Cursor: Claude Code `2.1.328 (Claude Code)`, model `claude-haiku-5-5`, 1 task(s) x 10 turn(s), 3 repeat(s), Linux 6.6.87.2-microsoft-standard-WSL2.

**Cost gate: FAIL** — cost $0.0781 is over the limit $0.0634 (base $0.0634 +0.0%).

| Metric | Bare | Harness | Change |
|---|---|---|---|
| Cost (USD, Claude Code's own) | 0.0634 | 0.0781 | +23% |
| Correct | 29/30 | 29/30 | |
| Input tokens (uncached) | 156 | 198 | +27% |
| Cache-read tokens | 3,016,171 | 3,829,218 | +27% |
| Cache-write tokens | 118,006 | 126,961 | +8% |
| All input (uncached + cache) | 3,134,333 | 3,956,377 | +26% |
| Output tokens | 19,153 | 28,738 | +50% |
| Tool calls | 55 | 71 | +29% |
| Graph calls (graphify-cli) | 0 | 3 | — |
| Subagent calls | 0 | 0 | — |
| Workflow rule reads (turns) | 0 | 0 | — |
| Invented file names | 0 | 0 | — |
| Turns citing an invented file | 0 | 0 | — |
| Wall time (s) | 335.1 | 439.3 | +31% |

Per feature (all input tokens, wall time, correct turns, chats that used the graph, invented files):

| Feature | Bare tokens | Harness tokens | Change | Bare s | Harness s | Bare correct | Harness correct | Bare graph chats | Harness graph chats | Bare invented | Harness invented |
|---|---|---|---|---|---|---|---|---|---|---|---|
| compact | 3,134,333 | 3,956,377 | +26% | 335.1 | 439.3 | 29/30 | 29/30 | 0/3 | 1/3 | 0 | 0 |

Accuracy by turn position (correct / scored, turns citing an invented file):

| Turns | Bare | Harness |
|---|---|---|
| turns 1-2 | 6/6, 0 invented | 6/6, 0 invented |
| turns 3-5 | 9/9, 0 invented | 9/9, 0 invented |
| turns 6+ | 14/15, 0 invented | 14/15, 0 invented |

Per task (cost, correct turns):

| Task | Bare | Harness | Change |
|---|---|---|---|
| long-dashboard-compact | $0.0634 (29/30) | $0.0781 (29/30) | +23% |

Paired by chat (the same task and repeat in both arms):

| Metric | Chats | Harness cheaper | Harness dearer | Total change | 95% CI (bootstrap) | Sign test p |
|---|---|---|---|---|---|---|
| Cost (USD) | 3 | 0 | 3 | +23.2% | +18.8% to +25.5% | 0.25 |
| All input tokens | 3 | 0 | 3 | +26.2% | +21.8% to +32.9% | 0.25 |
| Uncached input | 3 | 0 | 3 | +26.9% | +22.2% to +32.0% | 0.25 |
| Cache-write tokens | 3 | 1 | 2 | +7.6% | -6.6% to +19.9% | 1 |
| Output tokens | 3 | 0 | 3 | +50.0% | +36.4% to +66.0% | 0.25 |

Correctness, 30 turns scored in both arms: right only without the harness 1, right only with it 1 (exact McNemar p = 1).

- Digest found in the saved chat in 30 of 30 harness-arm turn(s) (it is injected once, at the start of each chat), and in 0 bare-arm turn(s).
- Bare: the project's files only, no CLAUDE.md, no .agent-spec/, no hooks. Harness: CURSOR.md as CLAUDE.md, the project's .agent-spec/ (graph, memory, bins; not run state), the digest from a SessionStart hook, the agent-spec-search and agent-spec-verify subagents in .claude/agents/. No skill in either arm; no PreToolUse hook; no MCP server. --setting-sources project.
- Tasks by the harness feature they exercise: compact (long-dashboard-compact). They were picked where the harness has something to offer, so this measures that case, not an average coding chat.
- Invented file names: file names an answer cites that exist nowhere in the project or the task's prompts. Workflow rule reads: turns with a tool call naming agent-spec-workflow.mdc; Cursor can also attach it without a visible read.
- n = 3 chats per arm: a smoke test, not a benchmark.
