# Claude Code head-to-head: bare vs the agent-spec harness

Run `20261121T083158-7b6a09`, 2026-11-21T03:01:58.411Z. Not Cursor: Claude Code `2.1.328 (Claude Code)`, model `claude-haiku-5-5`, 8 task(s) x 34 turn(s), 3 repeat(s), Linux 6.6.87.2-microsoft-standard-WSL2.

**Cost gate: FAIL** — cost $0.2599 is over the limit $0.2538 (base $0.2538 +0.0%); correct turns fell from 98 to 96.

| Metric | Bare | Harness | Change |
|---|---|---|---|
| Cost (USD, Claude Code's own) | 0.2538 | 0.2599 | +2% |
| Correct | 98/102 | 96/102 | |
| Input tokens (uncached) | 538 | 584 | +9% |
| Cache-read tokens | 10,457,997 | 11,136,079 | +6% |
| Cache-write tokens | 554,279 | 513,299 | -7% |
| All input (uncached + cache) | 11,012,814 | 11,649,962 | +6% |
| Output tokens | 76,705 | 91,637 | +19% |
| Tool calls | 207 | 225 | +9% |
| Graph calls (graphify-cli) | 0 | 8 | — |
| Subagent calls | 0 | 0 | — |
| Workflow rule reads (turns) | 0 | 3 | — |
| Invented file names | 3 | 3 | +0% |
| Turns citing an invented file | 2 | 3 | +50% |
| Wall time (s) | 1,276.4 | 1,491.2 | +17% |

Per feature (all input tokens, wall time, correct turns, chats that used the graph, invented files):

| Feature | Bare tokens | Harness tokens | Change | Bare s | Harness s | Bare correct | Harness correct | Bare graph chats | Harness graph chats | Bare invented | Harness invented |
|---|---|---|---|---|---|---|---|---|---|---|---|
| graph | 2,014,018 | 1,828,143 | -9% | 249.7 | 252.0 | 13/15 | 13/15 | 0/9 | 8/9 | 0 | 0 |
| long-chat | 2,004,506 | 2,415,646 | +21% | 230.4 | 268.4 | 26/27 | 27/27 | 0/3 | 0/3 | 0 | 0 |
| compact | 3,405,985 | 3,643,176 | +7% | 336.2 | 440.1 | 29/30 | 26/30 | 0/3 | 0/3 | 0 | 0 |
| search | 449,190 | 462,307 | +3% | 59.6 | 121.4 | 6/6 | 6/6 | 0/3 | 0/3 | 0 | 0 |
| other | 3,139,115 | 3,300,690 | +5% | 400.5 | 409.3 | 24/24 | 24/24 | 0/6 | 0/6 | 3 | 3 |

Accuracy by turn position (correct / scored, turns citing an invented file):

| Turns | Bare | Harness |
|---|---|---|
| turns 1-2 | 43/45, 2 invented | 43/45, 3 invented |
| turns 3-5 | 30/30, 0 invented | 30/30, 0 invented |
| turns 6+ | 25/27, 0 invented | 23/27, 0 invented |

Per task (cost, correct turns):

| Task | Bare | Harness | Change |
|---|---|---|---|
| views-blast | $0.0156 (4/6) | $0.0144 (4/6) | -8% |
| savings-importers | $0.0186 (3/3) | $0.0126 (3/3) | -33% |
| long-dashboard | $0.0364 (26/27) | $0.0401 (27/27) | +10% |
| long-dashboard-compact | $0.0704 (29/30) | $0.0742 (26/30) | +5% |
| env-sweep | $0.0130 (6/6) | $0.0140 (6/6) | +7% |
| edit-redact | $0.0443 (15/15) | $0.0485 (15/15) | +9% |
| fix-bug | $0.0278 (9/9) | $0.0282 (9/9) | +1% |
| traceback-fix | $0.0278 (6/6) | $0.0280 (6/6) | +1% |

Paired by chat (the same task and repeat in both arms):

| Metric | Chats | Harness cheaper | Harness dearer | Total change | 95% CI (bootstrap) | Sign test p |
|---|---|---|---|---|---|---|
| Cost (USD) | 24 | 9 | 15 | +2.4% | -4.2% to +8.5% | 0.307 |
| All input tokens | 24 | 11 | 13 | +5.8% | -2.4% to +14.4% | 0.839 |
| Uncached input | 24 | 7 | 9 | +8.6% | -0.4% to +16.8% | 0.804 |
| Cache-write tokens | 24 | 14 | 10 | -7.4% | -13.3% to -1.2% | 0.541 |
| Output tokens | 24 | 8 | 15 | +19.5% | +5.5% to +33.2% | 0.21 |

Correctness, 102 turns scored in both arms: right only without the harness 4, right only with it 2 (exact McNemar p = 0.688).

- Digest found in the saved chat in 102 of 102 harness-arm turn(s) (it is injected once, at the start of each chat), and in 0 bare-arm turn(s).
- Bare: the project's files only, no CLAUDE.md, no .agent-spec/, no hooks. Harness: CURSOR.md as CLAUDE.md, the project's .agent-spec/ (graph, memory, bins; not run state), the digest from a SessionStart hook, the agent-spec-search and agent-spec-verify subagents in .claude/agents/. No skill in either arm; no PreToolUse hook; no MCP server. --setting-sources project.
- Tasks by the harness feature they exercise: compact (long-dashboard-compact), graph (views-blast, savings-importers, traceback-fix), long-chat (long-dashboard), search (env-sweep). They were picked where the harness has something to offer, so this measures that case, not an average coding chat.
- Invented file names: file names an answer cites that exist nowhere in the project or the task's prompts. Workflow rule reads: turns with a tool call naming agent-spec-workflow.mdc; Cursor can also attach it without a visible read.
