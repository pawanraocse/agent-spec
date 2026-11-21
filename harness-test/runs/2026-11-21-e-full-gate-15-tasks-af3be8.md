# Claude Code head-to-head: bare vs the agent-spec harness

Run `20261121T133335-af3be8`, 2026-11-21T08:03:35.859Z. Not Cursor: Claude Code `2.1.328 (Claude Code)`, model `claude-haiku-5-5`, 15 task(s) x 42 turn(s), 3 repeat(s), Linux 6.6.87.2-microsoft-standard-WSL2.

**Cost gate: PASS** — cost $0.2460 vs base $0.2524 (limit +0.0%), correct 125 vs 124.

| Metric | Bare | Harness | Change |
|---|---|---|---|
| Cost (USD, Claude Code's own) | 0.2524 | 0.2460 | -3% |
| Correct | 124/126 | 125/126 | |
| Input tokens (uncached) | 604 | 596 | -1% |
| Cache-read tokens | 7,041,495 | 6,992,295 | -1% |
| Cache-write tokens | 694,593 | 676,753 | -3% |
| All input (uncached + cache) | 7,736,692 | 7,669,644 | -1% |
| Output tokens | 85,941 | 81,341 | -5% |
| Tool calls | 216 | 212 | -2% |
| Graph calls (graphify-cli) | 0 | 10 | — |
| Subagent calls | 0 | 0 | — |
| Workflow rule reads (turns) | 0 | 0 | — |
| Invented file names | 3 | 6 | +100% |
| Turns citing an invented file | 2 | 3 | +50% |
| Wall time (s) | 877.1 | 881.8 | +1% |
| Within tool budget (max_tools) | 24/24 | 24/24 | |

Per feature (all input tokens, wall time, correct turns, chats that used the graph, invented files):

| Feature | Bare tokens | Harness tokens | Change | Bare s | Harness s | Bare correct | Harness correct | Bare graph chats | Harness graph chats | Bare invented | Harness invented |
|---|---|---|---|---|---|---|---|---|---|---|---|
| direct | 402,638 | 432,343 | +7% | 87.1 | 94.8 | 21/21 | 20/21 | 0/18 | 0/18 | 0 | 0 |
| small | 115,395 | 124,101 | +8% | 12.9 | 16.1 | 3/3 | 3/3 | 0/3 | 0/3 | 0 | 0 |
| other | 2,102,985 | 2,279,265 | +8% | 271.8 | 287.8 | 22/24 | 24/24 | 0/6 | 0/6 | 3 | 6 |
| graph | 1,201,118 | 1,072,992 | -11% | 160.7 | 128.0 | 15/15 | 15/15 | 0/9 | 9/9 | 0 | 0 |
| long-chat | 1,503,653 | 1,654,545 | +10% | 122.0 | 129.4 | 27/27 | 27/27 | 0/3 | 0/3 | 0 | 0 |
| compact | 2,166,535 | 1,845,801 | -15% | 191.0 | 193.2 | 30/30 | 30/30 | 0/3 | 1/3 | 0 | 0 |
| search | 244,368 | 260,597 | +7% | 31.6 | 32.5 | 6/6 | 6/6 | 0/3 | 0/3 | 0 | 0 |

Accuracy by turn position (correct / scored, turns citing an invented file):

| Turns | Bare | Harness |
|---|---|---|
| turns 1-2 | 69/69, 2 invented | 68/69, 3 invented |
| turns 3-5 | 28/30, 0 invented | 30/30, 0 invented |
| turns 6+ | 27/27, 0 invented | 27/27, 0 invented |

Per task (cost, correct turns):

| Task | Bare | Harness | Change |
|---|---|---|---|
| http-401-403 | $0.0055 (3/3) | $0.0063 (3/3) | +14% |
| iso-date-regex | $0.0056 (3/3) | $0.0065 (3/3) | +15% |
| nonetype-error | $0.0054 (3/3) | $0.0063 (3/3) | +15% |
| big-o | $0.0054 (3/3) | $0.0062 (2/3) | +15% |
| commit-message | $0.0057 (3/3) | $0.0064 (3/3) | +13% |
| follow-up-chat | $0.0077 (6/6) | $0.0100 (6/6) | +29% |
| shebang | $0.0061 (3/3) | $0.0071 (3/3) | +17% |
| edit-redact | $0.0364 (13/15) | $0.0405 (15/15) | +11% |
| fix-bug | $0.0259 (9/9) | $0.0247 (9/9) | -4% |
| traceback-fix | $0.0228 (6/6) | $0.0247 (6/6) | +8% |
| views-blast | $0.0112 (6/6) | $0.0084 (6/6) | -25% |
| savings-importers | $0.0170 (3/3) | $0.0079 (3/3) | -54% |
| long-dashboard | $0.0342 (27/27) | $0.0333 (27/27) | -2% |
| long-dashboard-compact | $0.0535 (30/30) | $0.0471 (30/30) | -12% |
| env-sweep | $0.0099 (6/6) | $0.0107 (6/6) | +8% |

Paired by chat (the same task and repeat in both arms):

| Metric | Chats | Harness cheaper | Harness dearer | Total change | 95% CI (bootstrap) | Sign test p |
|---|---|---|---|---|---|---|
| Cost (USD) | 45 | 13 | 32 | -2.5% | -9.0% to +4.2% | 0.00661 |
| All input tokens | 45 | 10 | 35 | -0.9% | -9.1% to +7.2% | 0.000247 |
| Uncached input | 45 | 9 | 7 | -1.3% | -7.5% to +5.0% | 0.804 |
| Cache-write tokens | 45 | 15 | 30 | -2.6% | -9.6% to +5.3% | 0.0357 |
| Output tokens | 45 | 27 | 17 | -5.4% | -16.5% to +4.7% | 0.174 |

Correctness, 126 turns scored in both arms: right only without the harness 1, right only with it 2 (exact McNemar p = 1).

- Digest found in the saved chat in 126 of 126 harness-arm turn(s) (it is injected once, at the start of each chat), and in 0 bare-arm turn(s).
- Bare: the project's files only, no CLAUDE.md, no .agent-spec/, no hooks. Harness: CURSOR.md as CLAUDE.md, the project's .agent-spec/ (graph, memory, bins; not run state), the digest from a SessionStart hook, the agent-spec-search and agent-spec-verify subagents in .claude/agents/. No skill in either arm; no PreToolUse hook; no MCP server. --setting-sources project.
- Tasks by the harness feature they exercise: compact (long-dashboard-compact), graph (traceback-fix, views-blast, savings-importers), long-chat (long-dashboard), search (env-sweep). They were picked where the harness has something to offer, so this measures that case, not an average coding chat.
- Invented file names: file names an answer cites that exist nowhere in the project or the task's prompts. Workflow rule reads: turns with a tool call naming agent-spec-workflow.mdc; Cursor can also attach it without a visible read.
