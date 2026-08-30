# Token efficiency: what is measured, and what is marketing

Back-link: [README](../README.md)

This page exists because the popular token-saving tools do not survive measurement, and
because until recently this framework had no way to check its own claims either. Nothing
here is a vendor number.

## How to measure

Claude Code writes a JSONL transcript per session under
`~/.claude/projects/<working directory with / replaced by ->/<session-uuid>.jsonl`. Every
assistant turn carries a `usage` object with four token buckets. That is ground truth.

```bash
./.agent-spec/bin/agent-spec-tokens.py session    # the four buckets, weighted
./.agent-spec/bin/agent-spec-tokens.py tools      # per tool: written in, returned
./.agent-spec/bin/agent-spec-tokens.py compare A.jsonl B.jsonl
```

`bin/agent-spec-bench.sh` still reports always-on and per-skill cost as bytes ÷ 4. That is
an estimate, labelled as one, useful for comparing two revisions of a file. Only
`--session` measures.

## Where the tokens went, across the whole corpus

One session proves nothing about the shape of the bill — it could be an artefact of that
day's task. `agent-spec-tokens.py corpus` aggregates every session on the machine.
**20 sessions, 4 projects, 6,377 assistant turns, 252,494,557 weighted tokens:**

| Bucket | Tokens | Weighted | Share |
|---|---|---|---|
| `cache_read_input_tokens` | 1,432,876,457 | 143,287,646 | **56.7%** |
| `cache_creation_input_tokens` | 60,651,843 | 75,814,804 | 30.0% |
| `output_tokens` | 6,664,178 | 33,320,890 | 13.2% |
| `input_tokens` | 71,218 | 71,218 | 0.0% |

- Output spent writing *into* tools — mostly whole file bodies: **19.3% of all output.**
- Everything tools returned: **0.51% of the bill.**
- Average context: **31,453 tokens on turn 1 → 355,548 on the last turn, 11.3x.**

That is the corpus the ordering below rests on. The single-session figures that follow are
kept because they are reproducible by anyone reading this file.

## Where the tokens went

One real session in this repository, 228 assistant turns. Weighted at the standard price
ratios — output ×5, cache write ×1.25, cache read ×0.1, relative to a fresh input token:

| Bucket | Tokens | Weighted | Share |
|---|---|---|---|
| `cache_read_input_tokens` | 34,373,756 | 3,437,376 | **56%** |
| `cache_creation_input_tokens` | 1,107,917 | 1,384,896 | 23% |
| `output_tokens` | 260,845 | 1,304,225 | 21% |
| `input_tokens` | 456 | 456 | ~0% |

Two things follow, and neither is where the tooling ecosystem points:

- **Context is re-read every turn — about 155,000 tokens per turn here.** Turn count
  multiplied by context size is the majority of the bill. Batching independent tool calls
  and ending a session at a task boundary attack the largest bucket there is.
- **28% of all output tokens were tool-call inputs**, overwhelmingly file bodies written
  into `Bash` heredocs and `Write`. A targeted edit costs a fraction of a rewrite, because
  a rewrite generates every line including the unchanged ones.

Tool results — the thing output-compression proxies exist to shrink — were **0.7%** of the
weighted total.

## What the published tools actually measured

[JetBrains SkillsBench](https://blog.jetbrains.com/ai/2026/07/rtk-claude-code-token-savings/),
86 of 87 tasks, 425 billed trials, Claude Code 2.1.201, claude-sonnet-5:

| Tool | Advertised | Measured |
|---|---|---|
| `rtk` | 60–90% savings | **+7.6% more expensive** at low effort (p=0.004); +0.1% at high effort (p=0.99) |
| `caveman` | −65% | **−8.5%** |

The benchmark's own explanation: `rtk`'s Bash hook could see "just under 20% of tool-result
chars", because Claude Code's built-in `Read` and `Grep` bypass Bash entirely. Even
"squeezing rtk's whole share by 70%" caps its impact at "≈3% of input tokens". And:
"cached re-reads that dominate input cost bill at a tenth of the price."

[Paul Hackenberger's stack](https://paul-hackenberger.medium.com/the-ultimate-token-saving-stack-rtk-caveman-and-tokensave-163badadd9ec)
combines `rtk`, `caveman` and `TokenSave`. Over a large corpus of sessions the three
measured 2.8%, 0.5% and 0.4% — **3.7% combined**. `TokenSave` is graph querying, which this
framework already has as Graphify.

## Context re-reads: you cannot compress them, you reset

Cache reads are 56% of the bill and the obvious reaction is to compress the context. It
does not work, for a mechanical reason: **a cache read bills at a tenth precisely because
the bytes are unchanged.** Edit them and the prefix is invalidated, so the whole thing is
re-written at cache-write price. Compression is not a discount on a re-read; it is a
re-write.

Nor can a filtering proxy help here. `rtk` and its kind rewrite command *output*. The
context is the conversation — every previous message, every tool result already accepted.
No `Bash` hook can reach it. That is why the benchmark found `rtk` capped at about 3% of
input while cache reads dominated.

So the two real moves are carry it or start again, and which one wins is arithmetic:

```bash
./.agent-spec/bin/agent-spec-tokens.py context
```

Measured on one session in this repository:

| | Tokens |
|---|---|
| Context on turn 1 | 32,786 |
| Context on turn 258 | 327,898 (10.0x) |
| Cost of carrying it | 32,790 per turn |
| Cost of a fresh session | 15,978 once, then 1,278 per turn |
| **Break-even** | **0.5 turns** |

Resetting wins, and far earlier than intuition suggests — long before the context feels
large. A *reset* also beats a *compaction*: compaction pays output price to generate a
summary and then carries it, while `/agent-spec-snapshot` writes the same state to a file
that was going to be written at session end anyway.

The other half of the answer is not to put things in the main context at all.
`agent-spec-search` and `agent-spec-verify` are subagents pinned to a cheap model: a broad
sweep or a full test run happens in a context that is discarded when it finishes, and only
the paths, or the verdict and the failures, come back. That does the job a filtering proxy
advertises, without the filtered remainder still landing in the conversation and being
re-read on every remaining turn.

## The measured result: no difference between the two modes

18 runs, 3 tasks, 3 repeats per arm, interleaved, `claude-sonnet-5`, each in a fresh clone.

| | `/agent-spec-raw-code` | `/agent-spec-raw-code-full` |
|---|---|---|
| Verified completion | 6 of 9 | 6 of 9 |
| Median cost per verified task | **$0.0811** | **$0.0852** |
| Range | $0.0634 – $0.1136 | $0.0690 – $0.1098 |
| Tasks won | 1 | 0 |
| Tasks indistinguishable | 2 | 2 |

**`raw-code-full` was 5.0% more expensive, not cheaper**, and on two of three tasks the
ranges overlap. The honest headline is *no measurable difference*.

The mechanism is visible in the buckets and is the framework's own lesson turned back on
it. `agent-spec-raw-code-full/SKILL.md` is 6,770 bytes against `raw-code`'s 2,523 — about
**1,062 extra tokens sitting in the system prompt, re-read on every turn**. On the
five-turn search task that predicts roughly 5,300 extra cache-read tokens; the measured
difference was +4,570. The caveman prose it exists to enable saved **−2 output tokens** on
that same task.

A skill body is context. A mode that spends 1,062 tokens per turn telling the agent to
spend fewer tokens has to save more than 1,062 tokens per turn, and on short tasks it does
not. The advice inside `raw-code-full` is still correct — turns and context dominate, which
is exactly *why* its own size defeats it — but it earns its keep only on long sessions,
and the suite above is made of short ones.

Task `03-fix-a-real-bug` failed in all six runs, both arms, on a verifier that counted
generated files under `.agent-spec/` as scope creep. That is a broken verifier, not a
finding about either mode; it has been scoped to source files and needs re-running.

## A skill body is context

This is the finding the benchmark produced, and it applies to every skill in the
framework, not just these two.

Once a skill is invoked its body sits in the prompt prefix and is **re-read on every
turn**, exactly like `CLAUDE.md`. The first `agent-spec-raw-code-full` was 6,770 bytes, of
which roughly 4,247 were evidence, citations and rationale — all true, all correct, and
all paid at about 1,062 tokens per turn to say. On a five-turn task that is 5,310 tokens
spent to save 2. The skill whose first line is "context is re-read every turn" was the
context.

Both modes were rewritten to hold imperatives only. Everything explaining *why* moved
here, to a file a human reads once and no prompt ever loads.

| | Before | After |
|---|---|---|
| `agent-spec-raw-code` | 2,523 B (~630 tok) | **1,573 B (~393 tok)** |
| `agent-spec-raw-code-full` | 6,770 B (~1,692 tok) | **2,928 B (~732 tok)** |
| Gap between the two modes | 4,247 B (~1,062 tok/turn) | **1,355 B (~338 tok/turn)** |

Every safety clause survived — never-compress, break-style-for, always-normal-prose — and
the self-test now asserts both bodies stay under 3,000 bytes and keep all three sections,
so the next person to add a paragraph of justification is stopped by a failing test rather
than by a benchmark six months later.

**The rule this generalises to: put imperatives in the skill, evidence in the docs.** A
line of rationale in a `SKILL.md` is charged every turn for the whole session. The same
line in `docs/` is free.

## The resulting order of leverage

1. **Fewer turns.** Batch independent calls; never poll; do not split one edit across three
   messages; do not re-read a file to confirm an edit landed.
2. **Reset at task boundaries**, and keep bulk reading out of the main context entirely —
   graph before files, line ranges not whole files, `agent-spec-search` and
   `agent-spec-verify` for anything broad or noisy.
3. **Cheaper writes.** Targeted `Edit` over rewriting; never echo a file back.
4. **Capped tool output.** `| head -50`, `--stat`, `-q`. Real, and under 1%.
5. **Prose compression.** Roughly 2% of the total. Last, because that is where the evidence
   puts it.

`/agent-spec-raw-code` covers item 5 and says so. `/agent-spec-raw-code-full` covers all
five.

## What is not reachable from a skill

Prompt caching is already on and automatic. `max_tokens`, batch API pricing, semantic
response caching and API-level model routing are real techniques that a Claude Code skill
cannot touch. The one reachable piece of model routing — running a mechanical search in a
subagent on a cheaper model — is in `/agent-spec-raw-code-full` §2.

## The rule

**Never report a saving you have not measured.** Two sessions are comparable only if they
did the same work; a shorter session on a smaller task is not an efficiency gain, and
reporting it as one is how a 60–90% claim gets made.

### Use the benchmark, not the A/B

`bin/agent-spec-ab.sh` compares one task once per arm, and that is not enough to say
anything. Three successive runs of two *identical* configurations — the skill body was
never loaded, so both arms were the same — produced deltas of −47.8%, −19.6% and −0.5%.
That spread is the noise floor. Any real difference has to be bigger than it.

```bash
bin/agent-spec-benchmark.sh --repeats 3
```

What makes it stable rather than merely automated:

| | |
|---|---|
| **A fixed task suite** | `benchmarks/tasks/*.task`, each paired with a `*.verify` script. Savings depend on task shape, so one task is one opinion. |
| **Verified completion** | The verify script is the arbiter, not the model's own report. A mode that is cheap because it half-finishes would otherwise win every time. |
| **Cost per verified task** | Never cost per run. A failed run is not a cheap run. |
| **Repeats, interleaved** | N runs per arm per task, arms alternating, so latency drift lands on both. |
| **Median and range** | Overlapping ranges are reported as overlapping. A delta smaller than the spread that produced it is not a result. |
| **n≥2 before any delta** | A median of one run is that run. |
| **Fresh clone per run** | No run sees another's edits; the working tree is never touched. |

Every verify script must fail on an unmodified tree — otherwise doing nothing scores as
success. The self-test asserts that for all of them.

`bin/agent-spec-ab.sh run "<task>"` remains for a single ad-hoc comparison. It runs: both arms via
`claude -p`, each with its own session id and its own throwaway clone at the same commit,
so the only variable is the mode. It reports the token buckets and the real dollar cost
per arm, and it refuses to count an arm that errored. Run it from a plain terminal —
Claude Code will not launch inside itself, and a nested run would not be a fresh context
anyway, which is the variable under test.

The manual `start`/`end`/`report` path — it records the transcript
boundary around each arm, refuses an arm where no new transcript appeared, and warns when
the two arms were given different tasks. **The suite has now been run: no measurable
difference, and `raw-code-full` 5.0% more expensive per verified task.** See the section
above. What each can still be said to *address* is 13.2% and roughly 99.5% of the bill
respectively — reach is not the same as saving, and this is the difference between them.
