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
