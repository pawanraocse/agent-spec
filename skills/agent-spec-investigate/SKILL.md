---
name: "agent-spec-investigate"
description: >-
  Diagnose before editing — name the cause with evidence, write no fix. Use for "why is X happening" and failed first attempts.
---

# investigate

The most expensive loop in agent work is edit → test → edit → test with no theory. Each
pass costs a full build and a context refill, and converges on nothing. This skill spends
reads instead of edits until one mechanism explains the evidence.

## Rule

**No production code changes until a single credible mechanism explains every symptom.**
Not a plausible one. One that accounts for what was observed, including the parts that
look irrelevant.

## Steps

1. **Separate symptom from cause.** Write down what was *observed* — exact error string,
   exact input, exact conditions — and keep it separate from what you think it means.
   Quote errors verbatim; a paraphrased stack trace has lost the evidence.

2. **Bound the blast radius before reading.**
   `./.agent-spec/bin/graphify-cli.py query --file <suspect>` gives the files that can
   reach it. Read those. Reading outside that set is almost always wasted.

3. **Trace one real case end to end.** Follow a single input from entry point through each
   layer to the output. Seam bugs are invisible when files are read in isolation: each one
   is individually correct and the handoff between them is wrong.

4. **Rank hypotheses by cheap falsification.** Not by likelihood — by how little it costs
   to rule out. A hypothesis you can kill with one grep goes first, even if you think it
   unlikely. Write the ranked list down before testing any of it.

5. **Falsify, do not confirm.** Look for the observation that would prove your favourite
   theory wrong. Confirmation is how a wrong theory survives to become a wrong fix.

6. **Stop at the cause.** The moment one mechanism explains the evidence, exploration ends.
   Also stop when you can name the exact blocker preventing diagnosis — a missing log, an
   unreproducible condition, an unavailable environment. That is a finished investigation
   too.

## Report

Five lines or fewer:

- **Cause** — the mechanism, at `file:line`.
- **Evidence** — what proves it, quoted.
- **Why it looked like something else** — if a first theory was wrong, say so; that is
  what stops the next person repeating it.
- **Ruled out** — the hypotheses killed, one line each.
- **Fix scope** — which layer owns it, and whether it is a one-line change or a design
  problem. Do not write the fix.

## Hard stops

- Never change product code here. Diagnostic logging is allowed and must be removed before
  the report.
- Never report a cause you have not evidenced. `[NEEDS CLARIFICATION]` and a named blocker
  is a correct outcome; a guess dressed as a finding is not.
- Never widen into a refactor, cleanup or unrelated bug found on the way — log those with
  `/agent-spec-debt`.

## Then

Hand the named cause to `/agent-spec-implement`, which owns the fix and its regression test.

## Delegate the wide reads

A broad "where does this live" sweep is the single largest token cost in this skill, and
none of what it reads is worth keeping. Send it to a subagent: its file reads stay in its
own context and only the answer comes back.

- Locating candidates across many files, directories or naming conventions → subagent.
- Reading the two or three files you will actually reason about → do it here.

Ask the graph before either: `./.agent-spec/bin/graphify-cli.py context --task "<task>"`
returns the file list directly, and costs a few hundred tokens.
