# Claude Code head-to-head: bare vs the agent-spec harness

Run `20261121T105115-ad8ad1`, 2026-11-21T05:21:15.213Z. Not Cursor: Claude Code `2.1.328 (Claude Code)`, model `claude-haiku-5-5`, 1 task(s) x 10 turn(s), 3 repeat(s), Linux 6.6.87.2-microsoft-standard-WSL2.

**Cost gate: FAIL** — cost $0.0662 is over the limit $0.0639 (base $0.0639 +0.0%).

| Metric | Bare | Harness | Change |
|---|---|---|---|
| Cost (USD, Claude Code's own) | 0.0639 | 0.0662 | +4% |
| Correct | 27/30 | 30/30 | |
| Input tokens (uncached) | 164 | 152 | -7% |
| Cache-read tokens | 3,108,857 | 2,978,924 | -4% |
| Cache-write tokens | 118,740 | 130,264 | +10% |
| All input (uncached + cache) | 3,227,761 | 3,109,340 | -4% |
| Output tokens | 19,093 | 20,686 | +8% |
| Tool calls | 59 | 52 | -12% |
| Graph calls (graphify-cli) | 0 | 0 | — |
| Subagent calls | 0 | 0 | — |
| Workflow rule reads (turns) | 0 | 0 | — |
| Invented file names | 0 | 0 | — |
| Turns citing an invented file | 0 | 0 | — |
| Wall time (s) | 338.0 | 371.3 | +10% |

Per feature (all input tokens, wall time, correct turns, chats that used the graph, invented files):

| Feature | Bare tokens | Harness tokens | Change | Bare s | Harness s | Bare correct | Harness correct | Bare graph chats | Harness graph chats | Bare invented | Harness invented |
|---|---|---|---|---|---|---|---|---|---|---|---|
| compact | 3,227,761 | 3,109,340 | -4% | 338.0 | 371.3 | 27/30 | 30/30 | 0/3 | 0/3 | 0 | 0 |

Accuracy by turn position (correct / scored, turns citing an invented file):

| Turns | Bare | Harness |
|---|---|---|
| turns 1-2 | 6/6, 0 invented | 6/6, 0 invented |
| turns 3-5 | 9/9, 0 invented | 9/9, 0 invented |
| turns 6+ | 12/15, 0 invented | 15/15, 0 invented |

Per task (cost, correct turns):

| Task | Bare | Harness | Change |
|---|---|---|---|
| long-dashboard-compact | $0.0639 (27/30) | $0.0662 (30/30) | +4% |

Paired by chat (the same task and repeat in both arms):

| Metric | Chats | Harness cheaper | Harness dearer | Total change | 95% CI (bootstrap) | Sign test p |
|---|---|---|---|---|---|---|
| Cost (USD) | 3 | 2 | 1 | +3.5% | -8.0% to +26.5% | 1 |
| All input tokens | 3 | 2 | 1 | -3.7% | -13.3% to +16.9% | 1 |
| Uncached input | 3 | 2 | 1 | -7.3% | -16.1% to +4.2% | 1 |
| Cache-write tokens | 3 | 1 | 2 | +9.7% | -8.8% to +29.4% | 1 |
| Output tokens | 3 | 1 | 2 | +8.3% | -0.5% to +29.7% | 1 |

Correctness, 30 turns scored in both arms: right only without the harness 0, right only with it 3 (exact McNemar p = 0.25).

- Digest found in the saved chat in 30 of 30 harness-arm turn(s) (it is injected once, at the start of each chat), and in 0 bare-arm turn(s).
- Bare: the project's files only, no CLAUDE.md, no .agent-spec/, no hooks. Harness: CURSOR.md as CLAUDE.md, the project's .agent-spec/ (graph, memory, bins; not run state), the digest from a SessionStart hook, the agent-spec-search and agent-spec-verify subagents in .claude/agents/. No skill in either arm; no PreToolUse hook; no MCP server. --setting-sources project.
- Tasks by the harness feature they exercise: compact (long-dashboard-compact). They were picked where the harness has something to offer, so this measures that case, not an average coding chat.
- Invented file names: file names an answer cites that exist nowhere in the project or the task's prompts. Workflow rule reads: turns with a tool call naming agent-spec-workflow.mdc; Cursor can also attach it without a visible read.
- n = 3 chats per arm: a smoke test, not a benchmark.
