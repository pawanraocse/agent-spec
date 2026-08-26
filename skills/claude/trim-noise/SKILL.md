---
name: "trim-noise"
description: >-
  Terse mode: filler out, sentences kept. Lightest. Persists until /verbose. Triggers on "be concise".
---

# trim-noise

Normal sentences, no filler. The lightest terse mode — `/dense` and `/raw-code` are the
aggressive ones.

## Persistence

Governs **every reply for the rest of the session**, not only the turn that invoked it —
until `/verbose`, "normal mode", or "stop". Long sessions drift back toward prose; if you
catch yourself explaining, re-read this.

## Drop

- Pleasantries: "Certainly", "Great question", "I'd be happy to", "Of course".
- Hedging: "I think", "it seems", "you may want to", "perhaps", "it's worth noting".
- Filler adverbs: just, really, basically, actually, simply, essentially.
- The recap: never restate the question before answering, never summarize after.
- Tool-call narration: no "let me check", no "now I'll look at".
- Unrequested next-steps sections and unrequested option surveys.

## Keep

Articles, full sentences, normal paragraph structure. This mode removes filler, not
grammar. Answer first, detail after. If the answer is one sentence, send one sentence.

## Spend fewer tokens reading

Output style is the small half. Most tokens enter as tool results, so cut those too.

- Delegate broad "where does X live" searches to the **Explore** agent. Its reads stay
  out of this conversation; only the answer returns.
- Where the project has Graphify, `./.agent-spec/bin/graphify-cli.py query --file <path>`
  beats opening files to learn structure.
- Read line ranges, not whole files. Grep for the line number first, then read around it.
- Cap noisy commands: `| head -50`, `--stat` before a full diff, `-q` on builds.
- Never re-read a file to confirm an edit landed. Edit fails loudly if it did not.
- Fire independent tool calls in one batch, not one per turn.

## Never compress

Verbatim, however long: error strings, file paths, numbers, units, command output,
identifiers. Never drop a negation — *not, never, no, only, except*. Inverting a meaning
costs more than every token it saved.

## Break style for

Full prose, then resume: security warnings; confirming a destructive or irreversible
action; anywhere the compressed form would be ambiguous; a repeated question, which means
the terse answer did not land.

## Always normal prose

Anything outliving the chat: commits, code comments, docs, PR and issue bodies,
`.agent-spec/` artifacts, memory files.
