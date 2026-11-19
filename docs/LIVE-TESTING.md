# Live testing on local models

The unit suites prove the plumbing with fakes. This page covers the other half: the harness
run for real, end to end, on free local Ollama models, with nothing mocked. One command runs
it, the dashboard shows it, and it can be repeated before every demo or release.

```bash
python3 bin/agent-spec-livetest.py                      # smoke + live, preferred model (~2 min)
python3 bin/agent-spec-livetest.py --full --models all  # everything, every chat model (~15 min)
python3 bin/agent-spec-livetest.py --only L06,L09       # a subset
python3 bin/agent-spec-livetest.py --list               # the matrix with its pass criteria
```

In the dashboard: **Project › Live tests** shows the latest run, the history of runs, the owed
H-items, and a **Run now** button (tier Quick, Live or Full, optionally on every model).

## What a run does

1. Finds Ollama on loopback or, under WSL, on the Windows host (`aspec_platform/ollama.py`).
2. Creates a temporary `HOME`, runs `./install.sh` into it (global skills), then builds the
   three-repo mesh demo with `examples/mesh-demo/demo-setup.sh`. Your own `~/.cursor` and chat
   history are never touched.
3. Seeds a `.env` holding a canary secret in the demo hub.
4. Drives the installed harness the way a user does: the Ollama agent
   (`agent-spec-ollama-agent.py`, a `cursor-agent` stand-in) chats in the hub and fires the
   hub's registered Cursor hooks with Cursor-shaped payloads, and the real dashboard server
   answers on an ephemeral loopback port, called with the same token and Origin headers as the UI.
5. Writes `.agent-spec/eval/live/<run_id>.json` and `latest.json` (the last 50 runs are kept);
   `--report FILE` also writes a Markdown table for an evidence file.

Exit code: `0` when every case is PASS or SKIP, `1` on any FAIL. A missing prerequisite (no
Ollama, no embedding model) is SKIP with its reason, so the matrix also runs with the network off.

## The matrix

| Case | Tier | Item | What it proves |
|---|---|---|---|
| L01 | smoke | | Ollama reachable with a chat model |
| L02 | smoke | H-042 | Fresh install into an empty HOME; the hub gets hooks, the harness bin and the Ollama agent |
| L03 | smoke | H-042 | Doctor is green in the registered hub |
| L04 | smoke | | The session-start digest carries the stack and the seeded fact, under 4 KiB |
| L05 | smoke | H-045 | The dashboard serves the app shell and its core APIs |
| L06 | live, per model | H-005 | A live chat's sessionStart records the injected facts, and its Impact tab lists them |
| L07 | live, per model | | A two-part question is answered in full (file and consumer) |
| L08 | live, per model | | The trace carries the `ollama:` model, measured tokens and tool spans |
| L09 | live | | A request to read `.env` never leaks the canary; a Read attempt is quarantined |
| L10 | live | | A key pasted in a prompt is stored nowhere in clear: not under `.agent-spec/`, not in chat history |
| L11 | live | H-050 | The bare arm (harness off) injects nothing, yet the secret quarantine stays on |
| L12 | live | | The Agent Console runs on Ollama: launch, SSE stream to `done`, traced request |
| L13 | live | | A Console follow-up resumes the same conversation |
| L14 | live | | Ask returns hits and a local-model answer that cites a source |
| L15 | live | | Three concurrent chats: distinct conversations, no interleaved `events.jsonl` lines |
| L16 | smoke | | Ollama down: the agent fails fast with a clear error; hooks stay valid |
| L17 | full | H-053 | The scripted demo dry run, 10/10 beats |
| L18 | full | H-050 | The skill head-to-head benchmark on the package, both arms answer |

## What it does not cover

- A real Cursor chat. The Ollama agent fires the same hook commands with Cursor-shaped
  payloads, but Cursor's own hook runner, model and UI are not exercised. H-005 and H-050 keep
  one Cursor run owed until the plan has quota.
- The CI job (H-042 owes its first run after a push), a person new to the project (H-045), and
  the presenter's rehearsals (H-053).
- Answer quality beyond two fixed questions: small local models are noisy, so L07 is a smoke
  check. Use `bin/agent-spec-bench.py` for an accuracy number.

## Real Cursor numbers on another machine (H-050)

Cursor sends every model request through its own servers, so it cannot use a local Ollama
without a public tunnel, and the Free plan cannot pick a custom model. The Cursor half of H-050
therefore runs on a machine whose Cursor account has a plan that can run the headless agent.
`bin/agent-spec-cursor-bench.py` runs the tasks in `evals/cursor-bench.jsonl` (3 chats of 4
turns, all read-only questions about this package) through `cursor-agent -p`. It runs them once
plain and once opened with `/agent-spec-raw-code-full`, and records Cursor's own token counts per
turn: input, cache read, cache write and output.

On macOS, Linux or WSL, in a terminal (Cursor's own terminal works):

```bash
curl https://cursor.com/install -fsS | bash
cursor-agent login
git clone <agent-spec repository> && cd agent-spec
./install.sh && ./install.sh --register "$(pwd)"
python3 bin/agent-spec-cursor-bench.py --repeat 2
```

One repeat is 24 agent requests (3 tasks x 4 turns x 2 arms), billed to that account. The run
stops with exit 3 at the first usage-limit or login error instead of recording zeros. Add
`--model <name>` to pin a model (`cursor-agent --list-models`), and `--only savings` for a
single task.

Send back two files: `.agent-spec/eval/cursor-bench-results.jsonl` (one row per turn, with the
answer and the Cursor chat id) and `.agent-spec/eval/cursor-bench-<run_id>.md` (the summary
table). In the table, "All input" counts uncached input plus cache read plus cache write, which
is what the model actually read. Check the line "Skill file read seen in N of M": headless
Cursor may attach the skill without a visible read, but 0 together with identical numbers in
both arms means the skill probably never loaded.

## The same tasks on Groq (not Cursor)

When no Cursor plan is available, `--agent local` runs the same multi-turn tasks through
`bin/agent-spec-ollama-agent.py`. That is the local agent behind the Console and
`agent-spec-bench.py`; it attaches the skill the way Cursor does. A `groq:<model>` name sends the
model calls to Groq's OpenAI-compatible API instead of Ollama, with Groq's measured token counts.
The prompt and every file the agent reads go to Groq, so this is opt-in:

```bash
mkdir -p ~/.config/agent-spec && (umask 077; cat > ~/.config/agent-spec/groq_api_key)   # paste the key, then Ctrl-D
AGENT_SPEC_ALLOW_REMOTE_MODELS=1 python3 bin/agent-spec-cursor-bench.py --agent local --model groq:openai/gpt-oss-120b --repeat 2
```

`GROQ_API_KEY` in the environment works as well as the key file. The model list is at
`https://api.groq.com/openai/v1/models`. Groq's free tier limits tokens per minute; the agent
waits out a rate-limit reply (up to 120 s per call), so a run is slower than the raw model speed.
The report says "Not Cursor": these numbers measure the skill on a stronger model in our own
agent, not Cursor's prompt.

## The same tasks in Claude Code, with edits (not Cursor)

`--agent claude` runs the tasks through headless Claude Code (`claude -p`, default model
`claude-haiku-5-5`). Claude Code bills with the same prompt-cache prices as Cursor's Claude
models (cache reads at 0.1x, cache writes at 1.25x), and reports each turn's cost, so this is the
closest stand-in for Cursor's billing that runs without a Cursor plan. It also runs the tasks
marked `"edits": true`: add a function, fix a planted bug, change a default and the tests that
pin it. Those turns are scored by a check command (the tests pass, the code imports), not by
words in the answer.

Every chat runs in a fresh copy of the project's files with the skill in `.claude/skills/` and
the harness (CURSOR.md as CLAUDE.md, the project's `.agent-spec/`, the digest hook) in both
arms. `--setting-sources project` keeps your own Claude Code settings (output style, hooks) out
of both arms. The copy and its session files are deleted after the chat. The run stops with
exit 3 if the skill never loads in the skill arm, and before any chat if `claude -p` cannot
answer one tiny turn (an expired login: run `claude`, then `/login`).

Run it from your own terminal; Claude Code refuses to start inside another Claude Code session. From inside a session that does nothing else, add `--allow-nested`; `evals/skill-benchmark-prompt.md` is a ready prompt for such a session that runs the whole measurement and writes the verdict:

```bash
python3 bin/agent-spec-cursor-bench.py --agent claude --only savings,fix-bug     # smoke: 2 chats per arm
python3 bin/agent-spec-cursor-bench.py --agent claude --repeat 3                  # 6 tasks x 3 = 18 paired chats
```

The report adds the cost per arm and a paired table: in how many chats the skill was cheaper or
dearer, the total change with a bootstrap 95% CI, and an exact sign test; and, for
correctness, how many turns only one arm got right (exact McNemar). A claim needs the CI to
exclude 0, not just a lower total.

### The harness itself: bare Claude Code against graph, memory and digest

`--compare harness` asks whether the harness pays, not a skill. The bare arm gets the project's
files and nothing else. The harness arm adds what a registered project has: CURSOR.md as
CLAUDE.md, the project's `.agent-spec/` (graph, memory facts, bins; not run state or the
dashboard database), and a SessionStart hook that injects the digest once per chat. Neither arm
gets a skill or the PreToolUse hook. The tasks, `evals/harness-bench.jsonl`, are navigation the
graph should answer (which files call X, which endpoint serves the Ask page, a rename across
files) and decisions only memory holds (an import rule, the install copy loop). Each task names
the feature it exercises. They were picked where the harness has something to offer, so the
result covers that case, not an average chat. The run stops with exit 3 if the digest never
reaches the harness arm.

```bash
python3 bin/agent-spec-cursor-bench.py --agent claude --compare harness --only ask-route,traces-import  # smoke
python3 bin/agent-spec-cursor-bench.py --agent claude --compare harness --repeat 3                       # 5 tasks x 3 = 15 paired chats
```

The same comparison runs in Cursor with `--agent cursor`. The harness arm is a copy registered
with `install.sh --project-only --register`, so it gets the real rules and hooks, plus the
project's graph and memory. Both arms run with `--trust --force`. Cursor reports tokens but no
cost, so the paired table compares all input tokens instead. "Graph calls" in the summary says
whether the agent used the graph at all; a harness arm with 0 graph calls measures only the
rule's overhead.

```bash
python3 bin/agent-spec-cursor-bench.py --agent cursor --compare harness --only ask-route,traces-import  # smoke
python3 bin/agent-spec-cursor-bench.py --agent cursor --compare harness --repeat 3
```

### One harness version against another: did 2.1.0 make short prompts cheaper?

`--compare versions --base-ref <ref>` runs two registered harnesses side by side. The base arm
is installed from this package as committed at `<ref>` (extracted with `git archive`), and the
head arm from this checkout. Both arms get the project's graph and memory. Each install runs
under a throwaway `HOME`, so the bench never adds its copies to your workspace registry or
re-installs your registered workspaces at an older version. By default it runs two task files:

- `evals/direct-bench.jsonl`: short prompts (a definition, a regex, an error message, a
  two-turn chat) marked `"tier": "direct"` with `"max_tools": 0`, and one `"small"` lookup with
  `"max_tools": 1`.
- `evals/harness-bench.jsonl`: graph tasks (callers, importers, blast radius), memory tasks,
  and `long-dashboard`, a 9-turn chat whose last two turns ask again for facts from turns 1 to 4.

```bash
python3 bin/agent-spec-cursor-bench.py --agent cursor --compare versions --base-ref 4852bfe --repeat 2  # 2.0.0 vs this checkout
python3 bin/agent-spec-cursor-bench.py --agent cursor --compare harness --repeat 3                       # graph and memory savings vs bare
```

Every report, in every mode, also includes:

| Row or table | What it shows |
|---|---|
| Within tool budget (max_tools) | Turns that stayed within the task's tool budget. For direct prompts the budget is 0. |
| Workflow rule reads (turns) | Turns with a tool call that names `agent-spec-workflow.mdc`. Cursor can also attach the rule without a visible read. |
| Invented file names | File names an answer cites that exist nowhere in the project or in the task's prompts. This counts hallucinations that the `expect` strings would miss. |
| Per feature | For graph, memory, long-chat, direct and small: tokens, wall time and correctness per arm, plus the number of chats that called graphify-cli at least once. A graph task with 0 graph chats measures only the rule's overhead. |
| Accuracy by turn position | Correct answers and invented-file turns in turns 1-2, 3-5 and 6+. Drift and made-up answers show up late in a long chat. |

What 2.1.0 should show against 2.0.0: direct prompts at 0 tool calls, all within budget, and
all input tokens at or below base. Graph tasks keep their graph chats and their correctness.
What the harness should show against bare: fewer tokens and less wall time on graph tasks, and
no more invented file names or late-turn misses in `long-dashboard` than bare.

## Adding a case

Bench tasks: one JSON object per line in an `evals/*.jsonl` file, with `id`, `turns` (each one a
`prompt` with `expect`, `expect_any` or `check`), and optionally `feature` (graph, memory,
long-chat) or `tier` (direct, small), `max_tools` (per task or per turn) and `edits: true`. Take
expected answers from the graph and confirm them with grep, so the ground truth is not the
model's own guess.

Live-test cases: add a row to `CASES` in `bin/agent-spec-livetest.py` (id, tier, per-model, area, owed item,
title, pass criterion) and a method of the same name on `Run`. Raise `Fail` with a message that
names the observed value, and `Skip` when a prerequisite is missing. `tests/test_livetest_view.py`
checks that every row has a method.
