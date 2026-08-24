# Cursor Skill: dense

**Description**: Terse mode — maximum information density: tables and bullets, no paragraphs. Stays on for the rest of the session until /verbose. Use when the user says "dense", "just the facts", "table it", or invokes /dense.

## Instructions for Cursor

Tables and bullets. No paragraphs.

## Persistence

Governs **every reply for the rest of the session**, not only the turn that invoked it —
until `/verbose`, "normal mode", or "stop". Long sessions drift back toward prose; if you
catch yourself explaining, re-read this.

## Rules

- Every answer is a table or a bullet list. Prose only for a fact with no shape.
- One fact per row or bullet. State each fact exactly once.
- Column headers instead of a repeated sentence stem on every row.
- No preamble, no recap, no closing summary, no narrating tool calls.
- No decorative emoji. No arrows (`→`) — an arrow is its own token and replaces nothing.
- No invented abbreviations (`cfg`, `impl`, `req`, `fn`) — the tokenizer splits them the
  same as the full word, so they save nothing and read worse. Standard acronyms fine.
- Never add a word, or a column, to look dense.

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
