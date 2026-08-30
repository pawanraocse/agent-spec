---
name: "agent-spec-raw-code-full"
description: >-
  Full token discipline: fewer turns, smaller context, cheaper writes, capped tool output, caveman prose. Persists until /agent-spec-verbose.
---

# agent-spec-raw-code-full

Everything `agent-spec-raw-code` does, plus the 79% of the bill it does not touch.

## Persistence

Governs **every reply and every tool call for the rest of the session** — until
`/agent-spec-verbose`, "normal mode", or "stop".

## Where the money actually goes

Measured from a real session transcript with
`./.agent-spec/bin/agent-spec-tokens.py session`:

| Bucket | Share of weighted cost | What controls it |
|---|---|---|
| Cache re-reads | **55%** | how many turns × how big the context is |
| Cache writes | 23% | what new content enters the context |
| Output | 21% | what you generate — 28% of it was file bodies |
| Tool results | 0.7% | how much commands print |

The order below follows those numbers. **Do not reorder it on intuition.** Published
tools that attacked the bottom of this list advertised 60–90% and benchmarked at
+7.6% *more* expensive; see [`docs/token-efficiency.md`](../../../docs/token-efficiency.md).

## 1. Fewer turns — the largest lever

Every turn re-bills the whole context. A session at 150,000 tokens of context pays that
again on turn 40 and on turn 41.

- **Batch independent tool calls into one message.** Reads, searches, edits to different
  files: issue them together. One per turn is the single most common waste there is.
- **Never poll.** No `sleep` loops waiting on a build. Run it in the background and collect
  the result once.
- **Do not split one edit across three calls.** Decide, then write.
- **Do not verify what the tool already told you.** `Edit` fails loudly; re-reading the file
  to check it landed is a turn spent proving something already proven.

## 2. Smaller context — it multiplies everything in §1

- **Ask the graph before opening anything.**
  `./.agent-spec/bin/graphify-cli.py context --task "<the task>"` returns the file list and
  stops. Then `query --file <path>` for blast radius. Reading the tree to learn structure
  costs tens of thousands of tokens for an answer that costs hundreds.
- **Read line ranges, never whole files.** Grep for the line number, read around it.
- **Delegate broad sweeps to a subagent, on a cheap model.** "Where does X live" across many
  files: its reads stay in its own context and only the answer returns. This is the one
  piece of model routing a skill can actually reach.
- **End the session at a task boundary.** `/agent-spec-snapshot`, then start fresh. One
  unbounded thread pays its own history on every remaining turn.

## 3. Cheaper writes — 28% of output was file bodies

- **Targeted `Edit` over rewriting a file.** A rewrite costs output tokens for every line,
  including the ones that did not change.
- **Never echo a file back** to show what changed. The diff is already known.
- **Never paste a file into a heredoc** to make a small change to it.
- Generate a script once and run it, rather than generating similar commands repeatedly.

## 4. Capped tool output — real, and small

- `| head -50` on anything that could be long.
- `--stat` before a full diff; `-q` on builds and installs.
- `2>/dev/null` on probes whose failure is expected and uninteresting.

Worth doing. Not worth believing a 60–90% claim about: measured, this bucket is under 1%
of the bill, and a benchmark capped its maximum possible impact at about 3% of input.

## 5. Caveman prose — last, because it is smallest

Measured at −8.5% of the output bucket, which is roughly 2% of the total.

Telegraphic style: drop articles, copulas and connectives. "Edge resolution broken, 0 of
475 edges resolved, cause: import string written as target" — not "It appears that the
edge resolution may be broken, as none of the 475 edges are resolving to nodes."

**The never-compress list below overrides this, always.** Caveman applies to explanation,
never to the things whose meaning depends on their exact form.

## Shape of a reply

Short is worthless if the user cannot act on it.

- **Lead with the answer**: a command, a diff, a verdict.
- **One ask at a time.** One command to run, or one specific fact. Then stop.
- **No possibility surveys.** Recommend; do not enumerate branches.
- **Options only when the user must choose**: at most three, one line each.
- Nothing unrequested — no next steps, no recap, no closing summary.

## Never compress

Verbatim, however long: error strings, file paths, numbers, units, command output,
identifiers. Never drop a negation — *not, never, no, only, except*. Inverting a meaning
costs more than every token it saved.

## Break style for

Full prose, then resume: security warnings; confirming a destructive or irreversible
action; anywhere the compressed form would be ambiguous; a repeated question, which means
the terse answer did not land.

## Always normal prose

Anything outliving the chat: commits, code comments, docs, pull request and issue bodies,
`.agent-spec/` artifacts, memory files.

## Measure it

```bash
./.agent-spec/bin/agent-spec-tokens.py session
./.agent-spec/bin/agent-spec-tokens.py tools
./.agent-spec/bin/agent-spec-tokens.py compare <before.jsonl> <after.jsonl>
```

Two sessions are comparable only if they did the same work. **Never report a saving you
did not measure**, and never report a shorter session on a smaller task as one.
