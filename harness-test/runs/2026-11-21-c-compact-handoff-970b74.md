# Claude Code head-to-head: bare vs the agent-spec harness

Run `20261121T103820-970b74`, 2026-11-21T05:08:20.648Z. Not Cursor: Claude Code `2.1.328 (Claude Code)`, model `claude-haiku-5-5`, 1 task(s) x 10 turn(s), 3 repeat(s), Linux 6.6.87.2-microsoft-standard-WSL2.

**Cost gate: FAIL** — cost $0.0674 is over the limit $0.0626 (base $0.0626 +0.0%).

| Metric | Bare | Harness | Change |
|---|---|---|---|
| Cost (USD, Claude Code's own) | 0.0626 | 0.0674 | +8% |
| Correct | 30/30 | 30/30 | |
| Input tokens (uncached) | 154 | 174 | +13% |
| Cache-read tokens | 2,943,012 | 3,267,900 | +11% |
| Cache-write tokens | 119,669 | 115,264 | -4% |
| All input (uncached + cache) | 3,062,835 | 3,383,338 | +10% |
| Output tokens | 18,442 | 23,223 | +26% |
| Tool calls | 51 | 61 | +20% |
| Graph calls (graphify-cli) | 0 | 3 | — |
| Subagent calls | 0 | 0 | — |
| Workflow rule reads (turns) | 0 | 0 | — |
| Invented file names | 0 | 9 | — |
| Turns citing an invented file | 0 | 3 | — |
| Wall time (s) | 325.8 | 383.0 | +18% |

Per feature (all input tokens, wall time, correct turns, chats that used the graph, invented files):

| Feature | Bare tokens | Harness tokens | Change | Bare s | Harness s | Bare correct | Harness correct | Bare graph chats | Harness graph chats | Bare invented | Harness invented |
|---|---|---|---|---|---|---|---|---|---|---|---|
| compact | 3,062,835 | 3,383,338 | +10% | 325.8 | 383.0 | 30/30 | 30/30 | 0/3 | 1/3 | 0 | 9 |

Accuracy by turn position (correct / scored, turns citing an invented file):

| Turns | Bare | Harness |
|---|---|---|
| turns 1-2 | 6/6, 0 invented | 6/6, 0 invented |
| turns 3-5 | 9/9, 0 invented | 9/9, 0 invented |
| turns 6+ | 15/15, 0 invented | 15/15, 3 invented |

Per task (cost, correct turns):

| Task | Bare | Harness | Change |
|---|---|---|---|
| long-dashboard-compact | $0.0626 (30/30) | $0.0674 (30/30) | +8% |

Paired by chat (the same task and repeat in both arms):

| Metric | Chats | Harness cheaper | Harness dearer | Total change | 95% CI (bootstrap) | Sign test p |
|---|---|---|---|---|---|---|
| Cost (USD) | 3 | 2 | 1 | +7.6% | -4.4% to +34.1% | 1 |
| All input tokens | 3 | 2 | 1 | +10.5% | -3.6% to +42.0% | 1 |
| Uncached input | 3 | 0 | 2 | +13.0% | +0.0% to +37.5% | 0.5 |
| Cache-write tokens | 3 | 2 | 1 | -3.7% | -14.2% to +15.6% | 1 |
| Output tokens | 3 | 0 | 3 | +25.9% | +6.5% to +53.2% | 0.25 |

Correctness, 30 turns scored in both arms: right only without the harness 0, right only with it 0 (exact McNemar p = 1).

- Digest found in the saved chat in 30 of 30 harness-arm turn(s) (it is injected once, at the start of each chat), and in 0 bare-arm turn(s).
- Bare: the project's files only, no CLAUDE.md, no .agent-spec/, no hooks. Harness: CURSOR.md as CLAUDE.md, the project's .agent-spec/ (graph, memory, bins; not run state), the digest from a SessionStart hook, the agent-spec-search and agent-spec-verify subagents in .claude/agents/. No skill in either arm; no PreToolUse hook; no MCP server. --setting-sources project.
- Tasks by the harness feature they exercise: compact (long-dashboard-compact). They were picked where the harness has something to offer, so this measures that case, not an average coding chat.
- Invented file names: file names an answer cites that exist nowhere in the project or the task's prompts. Workflow rule reads: turns with a tool call naming agent-spec-workflow.mdc; Cursor can also attach it without a visible read.
- n = 3 chats per arm: a smoke test, not a benchmark.
