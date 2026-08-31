# Token-saving checklist

Everything we have collected — the two YouTube playbooks, the RTK/Caveman/TokenSave
article, the JetBrains benchmark, and our own transcripts — reduced to one list, with the
status of each item **in this repository** and the command that re-tests it.

Nothing here is marked DONE on a vendor's claim. `MEASURED` means we counted it,
`UNKNOWN` means we have not, and `UNKNOWN` is never upgraded by argument.

---

## The metric

**Cost per verified task. Not tokens per run, and not tokens at all.**

Our own three-arm run makes the difference concrete:

| arm | total tokens per run | cost per verified task |
|---|---|---|
| plain (no skill) | 91,429 | $0.0876 |
| `/agent-spec-raw-code` | 86,849 (−5.0%) | $0.0888 (+1.4%) |
| `/agent-spec-raw-code-full` | 81,834 (−10.5%) | $0.0896 (+2.3%) |

**Both modes used fewer tokens and cost more.** Cache reads bill at 0.1×, cache writes at
1.25×, output at 5×. Shifting work from the cheap bucket to the expensive one lowers the
token count and raises the bill. Any checklist item that reports a token saving without a
cost saving has not saved anything.

Second rule, from the JetBrains study and our own task 03: a mode that fails more often is
worse even when cheaper. A 30% shorter prompt that causes one retry is a loss.

## Where the money actually is

Corpus: 20 sessions, 4 projects, 6,377 turns, 252,494,557 weighted tokens.

| bucket | share of cost |
|---|---|
| cache re-reads | 56.7% |
| cache writes | 30.0% |
| output | 13.2% |
| fresh input | ~0% |
| **everything tools returned** | **0.51%** |

---

## Tier 1 — the buckets that hold the money

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Prompt caching is on and the prefix is stable | **MEASURED, DONE** | cache reads are 56–69% of the bill, which only happens when caching works |
| 2 | Keep the session warm; do not restart for no reason | **UNKNOWN** | cache TTL reported as ~1h; never measured here |
| 3 | Do not switch model or effort mid-session | **DONE** | `claude-opus-5`, `CLAUDE_EFFORT=high`, no auto-switching mode in use |
| 4 | Compact or reset a long session | **MEASURED, LARGEST** | 480,083 → 53,191 (−88.9%); 308,223 → 46,101 (−85.0%) |
| 4b | Whether compact beats a clean reset | **UNKNOWN** | the summary's own output cost has never been isolated |
| 5 | Filter tool output at source (`head`, `--stat`, `-q`) | **MEASURED, NOT WORTH IT HERE** | tool results are 0.51% of the corpus, 0.05% of this session |
| 6 | Never read a whole file when a range will do | **PARTLY** | in `raw-code-full`; untested — every benchmark task is too short to punish it |
| 7 | Do not let the agent loop; set a done condition | **DONE** | `--max-budget-usd`, verify script as arbiter |
| 8 | Do not ask the model what code can answer | **DONE** | graphify, `agent-spec-tokens.py`, the SessionStart digest |

## Tier 2 — architecture

| # | Item | Status | Evidence |
|---|---|---|---|
| 9 | Keep the always-on prompt small | **MEASURED, DONE** | 12,760 B ≈ 3,190 tok: CLAUDE.md 4,912, output style 2,267, 24 skill frontmatters 3,836, digest 1,745 |
| 9b | A skill body is charged every turn once invoked | **MEASURED** | `raw-code-full` was 6,770 B and lost its own benchmark; now 2,855 B, capped by test |
| 10 | Route cheap work to a cheap model | **DONE, UNMEASURED** | both subagents pinned `haiku`/`effort: low`; never benchmarked against not using them |
| 11 | Control reasoning effort per task | **NOT REACHABLE** | a skill cannot set effort for the session it runs in |
| 12 | Retrieve relevant context, not maximum context | **DONE** | graphify `context --task`, 225/225 edges resolving |
| 13 | Structured output; return IDs, not objects | **DONE** | `--output-format json`, `agent-spec-tokens.py`, gate `--json` |
| 14 | Hard iteration and token budgets | **DONE** | `--max-budget-usd 5` per benchmark run |
| 15 | Working memory separate from permanent memory | **DONE** | `agent-spec-memory.py`, `SESSION-SNAPSHOT.md`, `.agent-spec/sdlc/STATE.json` |
| 16 | Scheduled work must not fire past the cache TTL | **N/A** | no cron, no scheduled tasks, no background jobs |
| 17 | MCP tool deferral active, no gateway | **DONE** | 0 MCP servers; `ANTHROPIC_BASE_URL=https://api.anthropic.com`, which is not a proxy |

## Tier 3 — output shaping, where we started and where the least money is

| # | Item | Status | Evidence |
|---|---|---|---|
| 18 | Terse output discipline (`/agent-spec-raw-code`) | **NO MEASURABLE DIFFERENCE** | 26 verified runs vs plain: +1.4%, ranges overlap on every task |
| 19 | Caveman prose (`/agent-spec-raw-code-full`) | **NO MEASURABLE DIFFERENCE** | +2.3% vs plain; output went *up* 133 tok in the two-arm run |
| 20 | RTK-style tool-result rewriting | **DISPROVED ELSEWHERE** | JetBrains, 425 trials: advertised 60–90%, measured **+7.6% more expensive**, p=0.004 |
| 21 | Caveman, as published | **DISPROVED ELSEWHERE** | advertised −65%, measured −8.5% |
| 22 | Remove filler, examples, formatting from prompts | **DONE** | the always-on trim above |

---

## What is actually left

Three items, in order of how much they could still be worth.

1. **Item 4b — is compact better than a clean reset?** The largest measured lever is
   sitting next to an unanswered question about its own cost.
2. **Item 2 — does keeping a session warm beat resetting it?** The second playbook says
   yes and directly contradicts our own "reset early" advice. Neither has been measured
   against the other here.
3. **Items 6 and 10 — reading discipline and cheap subagents.** Both are untested because
   every benchmark task runs eight turns against a small context.
   `04-long-session.task` exists for exactly this and has never completed a run.

Everything else is either done, measured to be worthless, or unreachable from a skill.

---

## Testing without burning the budget

The last three suites cost real tokens and two of them died on a usage limit. Most of what
we need to test is **behaviour**, not price, and behaviour can be tested locally.

**What a local model can measure:** turn count, tool-call count, output length, completion
rate, whether a skill changes what the agent *does*. Items 6, 7, 10, 14 and 18–19 are all
behavioural.

**What it cannot:** anything about cost. Ollama has no prompt caching, so the 56–69% of the
bill that is cache reads does not exist there, and `total_cost_usd` is meaningless. Worse,
pointing Claude Code at a proxy is exactly the gateway condition from the audit — it turns
tool deferral off, so the local run is not the same configuration.

**So the split is:**

| stage | where | what it answers |
|---|---|---|
| harness development | stubbed `claude` (already in the self-test, costs nothing) | does the runner work |
| behaviour | local model via an Anthropic-compatible proxy | does the skill change what the agent does |
| **cost** | **Anthropic, once, at the end** | **the only number anyone should quote** |

Ollama is not installed on this machine, and neither is a proxy. Setting it up means:

```
ollama serve && ollama pull qwen2.5-coder:7b
pip install 'litellm[proxy]'
litellm --model ollama/qwen2.5-coder:7b --port 4000
ANTHROPIC_BASE_URL=http://localhost:4000 bin/agent-spec-benchmark.sh --repeats 3
```

A 7B model will fail tasks a frontier model passes, so completion rate is not comparable
across the two — only arm against arm within one local run.

---

## The rule

**Do not optimise for fewer tokens. Optimise for fewer unnecessary tokens without lowering
the chance of a correct first pass, and measure the result in cost per verified task.**

Our own numbers are the best argument for it: the mode that used 10.5% fewer tokens cost
2.3% more.
