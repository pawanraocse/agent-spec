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

Summed the other way: **input is 86.7% of the bill and output is 13.2%.** Output shaping
is the smaller half of a two-part problem, and it is the half that terse-mode skills
address. Everything that decides what enters context in the first place is the other 86.7%.

---

## Every method, measured, in one table

The per-turn prompt is **95,190 bytes** on the wire (EXP-1). Anything put into context is
re-sent on every turn after it, so a thing read at turn 2 of a ten-turn session is paid
for **nine times**. That single fact is what ranks this table.

Payload sizes are measured against real files in this repository. The "×8 turns" column is
arithmetic on those measurements, not a separate experiment, and it is labelled as such.

| method | before B | after B | saved once | saved ×8 turns |
|---|---|---|---|---|
| batch 2 tool calls into 1 turn | 95,190 | 0 | **95,190** | 95,190 (once) |
| graph query instead of reading the file | 35,966 | 152 | 35,814 | **286,512** |
| `grep -n` instead of `cat` | 35,966 | 1,178 | 34,788 | **278,304** |
| read a 50-line range, not the file | 35,966 | 2,071 | 33,895 | **271,160** |
| `git diff --stat` before the full diff | 33,830 | 427 | 33,403 | **267,224** |
| filter test output | 5,117 | 107 | 5,010 | 40,080 |
| shorter skill body (`-full` → lean) | 2,975 | 1,672 | 1,303 | 10,424 |
| caveman prose | ~100 | ~100 | **0** | **0** |
| `--allowed-tools` | 95,190 | 95,190 | **0** | **0** |

Reading conclusions off it:

- **Not reading things is worth 20× more than saying things briefly.** The top five rows
  are all "do not put it in context in the first place". The bottom two are the two ideas
  this project started with.
- **A turn is the most expensive unit there is.** One avoided turn saves more than any
  single filtering decision, because the whole 95,190 bytes goes again.
- **Caveman prose earns nothing and costs body bytes.** It is in `raw-code-full` today,
  it measured zero across 26 verified runs, and the body that carries it is charged on
  every turn. Removing it is a strict improvement.
- **The skill body is real but small.** 1,303 bytes per turn between the two modes — worth
  keeping lean, not worth another day.

One caveat carried from EXP-2: 95,190 B was measured through a proxy, which disables tool
deferral, so it is an upper bound on the per-turn constant. Every row is affected equally,
so the ranking holds; the absolute savings for the turn-avoidance row would shrink if
deferral is doing work at Anthropic. That is EXP-10.

## What actually accumulates in a conversation

Measured across **138 transcripts, 7,648 assistant turns** on this machine. This counts
the conversation body only — not the system prompt, not the tool schemas — because this is
the part that grows and gets re-sent.

| what accumulates | bytes | share |
|---|---|---|
| tool results (what commands returned) | 5,591,224 | **46.1%** |
| tool call inputs (file bodies written, commands issued) | 5,546,195 | **45.7%** |
| assistant prose (the reply text) | 988,456 | **8.2%** |

**92% of a conversation is tool traffic. 8% is the assistant talking.**

That settles the split between the two modes. Shortening replies can reach 8.2% of what
accumulates; filtering what tools return and not rewriting whole files reaches the other
92%. Reply discipline is worth keeping — but for readability, which is a real benefit, not
for tokens.

The 45.7% for tool call *inputs* is the one nobody expects: it is mostly file bodies going
back out, which is `Write` where `Edit` would do. A rewrite generates every unchanged line
and then carries it in context for the rest of the session.

This is a different denominator from the 0.51% figure quoted further down. That number is
tool results as a share of the whole *weighted bill*, which includes the always-on prompt
and the 0.1× cache-read discount. Both are correct: tool traffic dominates what a
conversation accumulates, and the accumulated conversation is itself discounted once
cached. Neither figure alone is the answer.

## Tier 1 — the buckets that hold the money

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Prompt caching is on and the prefix is stable | **MEASURED, DONE** | cache reads are 56–69% of the bill, which only happens when caching works |
| 2 | Keep the session warm; do not restart for no reason | **UNKNOWN** | cache TTL reported as ~1h; never measured here |
| 3 | Do not switch model or effort mid-session | **DONE** | `claude-opus-5`, `CLAUDE_EFFORT=high`, no auto-switching mode in use |
| 3b | Enforce input discipline rather than asking for it | **SHIPPED, EFFECT UNKNOWN** | `hooks/pre-tool-use.py` refuses a rangeless `Read`, a `Write` over an existing file, `git diff` without `--stat` and `cat` of a large file — once per target per session, so the retry always passes |
| 4 | Compact or reset a long session | **MEASURED, LARGEST** | 480,083 → 53,191 (−88.9%); 308,223 → 46,101 (−85.0%) |
| 4b | Whether compact beats a clean reset | **UNKNOWN** | the summary's own output cost has never been isolated |
| 5 | Filter tool output at source (`head`, `--stat`, `-q`) | **MEASURED, NOT WORTH IT HERE** | tool results are 0.51% of the corpus, 0.05% of this session |
| 6 | Never read a whole file when a range will do | **ENFORCED, EFFECT UNKNOWN** | asked for in `raw-code-full`, enforced by `hooks/pre-tool-use.py`; still untested — every benchmark task is too short to punish it |
| 7 | Do not let the agent loop; set a done condition | **DONE** | `--max-budget-usd`, verify script as arbiter |
| 8 | Do not ask the model what code can answer | **DONE** | graphify, `agent-spec-tokens.py`, the SessionStart digest |

## Tier 2 — architecture

| # | Item | Status | Evidence |
|---|---|---|---|
| 9 | Keep the always-on prompt small | **MEASURED, DONE** | 12,760 B ≈ 3,190 tok: CLAUDE.md 4,912, output style 2,267, 24 skill frontmatters 3,836, digest 1,745 |
| 9b | A skill body is charged every turn once invoked | **MEASURED** | `raw-code-full` was 6,770 B and lost its own benchmark; now 2,855 B, capped by test |
| 10 | Route cheap work to a cheap model | **DONE, UNMEASURED** | both subagents pinned `haiku`/`effort: low`; never benchmarked against not using them |
| 11a | Set reasoning effort programmatically | **NOT REACHABLE** | a skill cannot set effort for the session it runs in |
| 11b | Ask for reasoning discipline in prose | **SHIPPED, UNKNOWN** | "minimum sufficient reasoning" in `raw-code`, "carry conclusions forward, do not re-plan after every tool call" in `raw-code-full`; adopted from an external lean-output framework, never measured there or here |
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

## Why a hook and not a skill

Items 3b and 6 moved from a skill body to `hooks/pre-tool-use.py` for a reason that the
rest of this document makes unavoidable. A skill is text the model reads and may or may
not act on; every reading rule in `raw-code-full` has always been a request. A hook runs
in the harness before the tool call happens, so it is the only mechanism that can decline
one. Both skill bodies are also at their 3,000 byte cap, which means any further input
discipline had nowhere else to go.

It refuses each target once per session and lets the retry through. A genuine full read or
a genuine full rewrite stays possible; the cheap path simply becomes the default one. What
this buys in practice is unmeasured, and the row above says so.

## What is actually left

Four items, in order of how much they could still be worth.

1. **Item 4b — is compact better than a clean reset?** The largest measured lever is
   sitting next to an unanswered question about its own cost.
2. **Item 2 — does keeping a session warm beat resetting it?** The second playbook says
   yes and directly contradicts our own "reset early" advice. Neither has been measured
   against the other here.
3. **Items 6 and 10 — reading discipline and cheap subagents.** Both are untested because
   every benchmark task runs eight turns against a small context.
   `04-long-session.task` exists for exactly this and has never completed a run.

4. **Input quality, which nothing here addresses.** Every item above makes the input
   smaller. None of them makes it better, and the rule at the foot of this document says
   the two are not the same: a shorter prompt that causes one retry is a loss. The
   benchmark harness already records completion rate per arm, so the instrument exists —
   what is missing is an arm that varies the *quality* of the task statement rather than
   the verbosity of the reply, and measures cost per verified task across the two. Until
   that runs, "better input" is an argument, not a finding.

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
