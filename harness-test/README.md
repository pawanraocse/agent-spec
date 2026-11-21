# Harness test: agent-spec against a bare agent

This folder keeps the head-to-head tests run on 2026-11-21 and their results, so they can be
shown and re-checked later. Every number below comes from a report in `runs/` or a row in
`data/results-2026-11-21.jsonl`; nothing here is estimated.

## The question

Does the agent-spec harness (rules, a project digest at chat start, a dependency graph, a
memory store, a handoff command) let a coding agent answer the same questions correctly
without costing more than the same agent with none of it?

## Result

On the final run (`af3be8`, 15 tasks, 3 repeats, 126 scored turns per arm) the harness passed
the cost gate. It was 2.5% cheaper than the bare agent in total and got one more turn right.

| Metric | Bare | Harness | Change |
|---|---|---|---|
| Cost (USD, as billed by Claude Code) | 0.2524 | 0.2460 | -2.5% |
| Correct turns | 124 / 126 | 125 / 126 | +1 |
| Output tokens | 85,941 | 81,341 | -5% |
| All input tokens | 7,736,692 | 7,669,644 | -1% |
| Tool calls | 216 | 212 | -2% |
| Dependency-graph calls | 0 | 10 | used in 9 of 9 graph-task chats |
| Wall time (s) | 877.1 | 881.8 | +1% |

Where it gains, and where it pays:

| Kind of task | Tasks | Cost change | Why |
|---|---|---|---|
| Structural questions ("what imports X", blast radius) | `savings-importers`, `views-blast` | -54%, -25% | one graph query replaces a grep-and-read sweep |
| Hand off to a new chat, then recall | `long-dashboard-compact` | -12% | `agent-spec-memory.py handoff` saves the facts in one call; the next chat finds them |
| Long chat | `long-dashboard` | -2% | |
| Bug fix | `fix-bug` | -4% | |
| Edits and searches | `edit-redact`, `traceback-fix`, `env-sweep` | +8% to +11% | the harness's fixed start-of-chat context; `edit-redact` was also right 15/15 against 13/15 |
| One-line questions that need no code | 7 short prompts | +13% to +29% (about $0.0003 to $0.0008 a chat) | the same fixed context, with nothing to save on |

## Savings by mechanism

Figures are from the final run (`af3be8`, 3 chats per arm) unless a row names another run.
Both arms answered every one of these tasks correctly unless stated.

### 1. Dependency graph instead of grep and file reads

Questions about structure ("which modules import X", "what breaks if I change X"). Bare
answers by grepping and opening files; the harness asks the graph (`graphify-cli.py`) once.

| Task | Tool calls | Input tokens | Output tokens | Cost |
|---|---|---|---|---|
| `savings-importers` ("if I change savings.py, what imports it?") | 10 → 3 | 261,110 → 124,792 (-52%) | 5,936 → 1,871 (-68%) | $0.0170 → $0.0079 (**-54%**) |
| `views-blast` (importers of views.py, then its imports) | 10 → 3 | 294,609 → 188,351 (-36%) | 3,850 → 1,501 (-61%) | $0.0112 → $0.0084 (**-25%**) |

- The graph was used in 9 of 9 harness chats on graph tasks, and never by bare.
- The same two tasks saved 33% and 8% on the older version (`7b6a09`), so the direction
  repeats across runs; the size varies.
- Where the graph does not pay: `traceback-fix` (find and fix a bug from a traceback) used the
  graph but cost 8% more (20 → 27 tool calls), because the fix still needs the file read and
  edited. The graph wins on questions about structure, not on every task that mentions code.

### 2. Hand off and start a new chat instead of carrying a long one

Task `long-dashboard-compact`: 5 questions, a handoff ("save what this chat established"),
then a new chat with 4 more questions, 2 of which ask for facts from the first chat.

| Measure | Bare | Harness | Change |
|---|---|---|---|
| Average context per turn in the new chat (turns 7-10) | 97,443 tokens | 59,726 tokens | **-39%** |
| Cost of the new chat (turns 7-10) | $0.0295 | $0.0174 | **-41%** |
| Cost of the handoff turn itself | $0.0065 | $0.0091 | +40% (it also writes memory) |
| Whole task | $0.0535 | $0.0471 | **-12%** |

The new-chat turns were cheaper with the harness in all 5 runs with a report that include
this task: `7b6a09` -6%, `20d53a` -17%, `970b74` -11%, `ad8ad1` -1%, `af3be8` -41%. The handoff turn is where the harness pays: before the
`handoff` command it cost 2.6 times bare's handoff ($0.0227 against $0.0087, run `20d53a`);
now it costs 1.4 times.

### 3. No wrong answers about earlier chats

Turn 10 asks, in the new chat, for a fact the first chat established: the default size of
one graph answer, which is 152 bytes. Across every run today with the current digest
(`c965b0`, `20d53a`, `7f1938`, `970b74`, `ad8ad1`, `af3be8`):

| Arm | Chats | Wrong on the recall turn |
|---|---|---|
| Bare | 15 | **5 (33%)** |
| Harness | 15 | **0** |

The bare agent, with no memory of the first chat, answered from the code. It confidently gave
a different number, "4.0 bytes per token", which is a real default in the same file but not
the fact the first chat established. To its credit, it said each time that it could not see
the earlier chat. The harness answered from the saved facts.

This depends on the save working. On the old version (`7b6a09`) the memory save was refused
by the permission gate, and the harness missed the recall turn in 3 of 3 chats, inventing
answers from `impact.py`. That failure is what the `handoff` command fixed.

What this does not show: fewer invented file names in general. On the final run the harness's
answers cited 6 file names that do not exist against bare's 3, all on `fix-bug` turn 1, with
the same names in both arms (`token.json`, `api_token.ts`, `secret_scan.py`). On that measure
the two arms are the same.

### 4. Subagents for test runs: measured, and they cost more

The harness ships two subagents, `agent-spec-search` (broad sweeps that return paths and line
numbers, not file contents) and `agent-spec-verify` (runs tests or builds and returns only the
failures). The idea is that long tool output stays in the subagent and never enters the main
chat's context, which is re-sent on every later turn.

Left to itself, the model never called them: 0 subagent calls in 392 harness turns over the 7
runs of the day. A preToolUse hook now asks for `agent-spec-verify` when a test suite or build
is about to run in the main chat. Task `verify-suite` measures it: run a suite with two planted
bugs, fix each, re-run, then recall the causes (5 turns).

Run `c82667`, 1 chat per arm, the hook delegating every suite run (3 subagent calls):

| Turn | Bare | Harness |
|---|---|---|
| 1 run the suite, list failures | $0.0046 | $0.0106 |
| 2 fix the first bug | $0.0041 | $0.0051 |
| 3 fix the second, re-run | $0.0038 | $0.0178 (a flaky test failed once and was re-checked) |
| 4, 5 recall | $0.0014 | $0.0016 |
| **Total** | **$0.0139** | **$0.0351** (2.5 times bare), both 5 of 5 right |

Why it costs more, from the saved chats:

- The bare agent already keeps test output small on its own: `pytest -v ... | tail -n 200`
  once (15 KB), then `pytest -q ... | tail -n 4` (340 B) for every re-run.
- Each subagent starts cold: 26,000 to 56,000 token-equivalents to set up and report (its own
  system prompt, CLAUDE.md, the run), against the 340 B it replaces.
- The main chat did not get smaller: 62k tokens of context at turn 4 against bare's 52k.

So, for a model that already trims its own output, delegating a test run is pure overhead, and
the hook now only nudges a run with nothing cutting its output down. Where a subagent should
pay is untested here: a sweep that has to read many files to reach a short answer, and a
subagent on a cheaper model than the main chat (both arms here ran `claude-haiku-5-5`).

Two bench faults that went against the harness were found and fixed on the way: Claude Code's
`dontAsk` mode refused the harness's `pytest > log` (a redirect counts as a file write), so its
suite never ran (runs `dad368`, `896893`); and a turn that waited on a background task was
graded on its last message only. The risk gate also ranked `ls .agent-spec/bin/x 2>/dev/null`
as a change to its own code, and blocked a search subagent; that is fixed too.

## How it got there

The first full measurement of the day (old version) failed the gate, and the
long-chat-with-handoff task was the main reason. Each step below is a separate run, kept in
`runs/`.

| Run | What changed | Scope | Harness against bare |
|---|---|---|---|
| `7b6a09` | old version | 8 tasks x 3 | +2.4% cost, gate FAIL |
| `20d53a` | before the handoff fix | handoff task x 3 | +23% (handoff turn $0.0227 against $0.0087) |
| `970b74` | `handoff` command added | handoff task x 3 | +8% |
| `ad8ad1` | quieter fact recording | handoff task x 3 | +4%, harness right 30/30 against 27/30 |
| `af3be8` | final version | 15 tasks x 3 | **-2.5%, gate PASS** |

The cause was found from the saved chats, not guessed. To save a chat's facts, the harness
agent read the large snapshot file, tried a shell command that the permission gate refused,
then hand-edited the file: 8 tool calls and 6,494 output tokens, against 2 calls and 1,464
for the bare agent. The fix was a single command that takes the facts and does the whole
save, so the agent never opens the file.

## What this supports, and what it does not

Supported by these runs:

- The harness costs no more than a bare agent in total over this task set, while staying at
  least as accurate (125 against 124 correct; exact McNemar p = 1, so the accuracy is equal,
  not better).
- On structural questions it is much cheaper (-25% to -54%), because the graph answers them.
- Facts saved at a handoff are recalled in a new chat (30 of 30 turns right in that task).
- The cost tests catch regressions: the gate failed until the handoff path was fixed.

Not supported, and should not be claimed:

- **Not cheaper on every chat.** The harness was dearer in 32 of the 45 paired chats (sign
  test p = 0.0066), by small amounts. The total is lower because the graph and handoff
  savings outweigh that fixed cost.
- **Not a significant saving.** The 95% interval for the total is -9.0% to +4.2%, which
  includes zero. The honest summary is "at least as cheap as bare", not "X% cheaper".
- **Not an average coding chat.** The harness tasks were picked where the harness has
  something to offer; the 7 short prompts and 3 general tasks are there to show it does not
  make ordinary chats meaningfully dearer.
- **Not Cursor.** These runs drive Claude Code (`2.1.328`) with model `claude-haiku-5-5`; the
  harness ships for Cursor. The mechanism is the same rules, digest, graph and memory, but
  the numbers were measured on Claude Code.
- **Small sample.** 3 chats per task per arm. Enough to find the handoff problem and see the
  graph effect; not a benchmark.
- **Not a subagent saving.** Subagents were never used unprompted, and when the hook made the
  model use one for test runs it cost 2.5 times bare (one chat per arm, section 4).

## Method

- **Bare arm:** a copy of the project's files only. No CLAUDE.md, no `.agent-spec/`, no hooks.
- **Harness arm:** the same copy plus CURSOR.md as CLAUDE.md, the project's `.agent-spec/`
  (graph, memory, scripts; not run state), the digest from a SessionStart hook, and the
  `agent-spec-search` and `agent-spec-verify` subagents.
- Both arms: same model, `--setting-sources project`, no MCP server, permission mode
  `dontAsk` with the same tool allowlist, a fresh workspace copy per chat. (From run `cef508`
  on, `acceptEdits`: see section 4. The gate run `af3be8` used `dontAsk`.)
- Each task is a scripted chat of 1 to 10 turns. Every turn is graded by a fixed check
  (expected strings in the answer, or a shell check on the files), never by a model.
- Cost is what Claude Code itself reports per turn, so cache reads, cache writes and output
  are each billed at their own price.
- Gate: harness total cost must not exceed bare (+0.0% allowed) and correct turns must not
  drop.

## Reproduce

From the agent-spec clone, in a terminal outside any Claude Code session:

```bash
nohup setsid bash -c 'python3 bin/agent-spec-cursor-bench.py --agent claude --compare harness --tasks evals/direct-bench.jsonl,evals/cursor-bench.jsonl,evals/harness-bench.jsonl --only http-401-403,iso-date-regex,nonetype-error,big-o,commit-message,follow-up-chat,shebang,edit-redact,fix-bug,traceback-fix,views-blast,savings-importers,long-dashboard,long-dashboard-compact,env-sweep --repeat 3 > gate.log 2>&1; echo exit=$? >> gate.log' &
```

`exit=0` in `gate.log` is a pass; `exit=4` is a cost-gate failure. The run took 29 minutes.

The final run used uncommitted changes on top of commit `b240f94`. File hashes at run time
(sha256, first 12 characters): `bin/agent-spec-cursor-bench.py` 50d9e76c03b0, `CURSOR.md`
53f7f971466e, `bin/agent-spec-memory.py` 847228a8a49c.

## Files

| Path | Contents |
|---|---|
| `runs/2026-11-21-e-full-gate-15-tasks-af3be8.md` | the final report, with paired statistics |
| `runs/2026-11-21-a` to `-d` | the earlier runs in the table above |
| `runs/2026-11-21-f-subagent-verify-c82667.md` | the subagent run in section 4 (1 chat per arm, `acceptEdits`) |
| `data/results-2026-11-21.jsonl` | one row per turn for all 7 runs of the day (784 rows), including `c965b0` (stopped early, no report) and `7f1938` (1 repeat, chats kept for diagnosis): prompt, answer, tokens, cost, tools, correct |
| `data/tasks-full-gate.jsonl` | the 15 task definitions, with the prompts and checks |
