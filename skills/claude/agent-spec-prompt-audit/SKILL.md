---
name: "agent-spec-prompt-audit"
description: >-
  Audit a prompt body — SKILL.md, CLAUDE.md, AGENTS.md, a persona — for dead references, bloat and unenforceable rules. Use before shipping any text an agent re-reads every turn.
---

# agent-spec-prompt-audit

A prompt body is charged on every turn, not once. An instruction the model cannot follow
costs the same as one it can, and then spends a tool call proving itself wrong. This audits
one file at a time and reports findings as `Finding. Risk. Fix.`

Usage: `/agent-spec-prompt-audit CLAUDE.md`, or name the file in the sentence.

## Do

1. **Read the target in full.** It is a prompt; you cannot audit half of it.
2. **Resolve every reference.** For each repository path, command and `/agent-spec-<skill>`
   the file names, confirm it exists. A path under `.agent-spec/` belongs to the installed
   project, so check it against the installed tree, not this one.
3. **Measure the body.** `wc -c` the file. Report the number. Anything over 3000 B that is
   re-read every turn needs a reason, and "it is thorough" is not one.
4. **Separate imperative from evidence.** Every sentence is either an instruction the agent
   must act on or rationale explaining why. Rationale belongs in `docs/`. Quote each
   offending passage and say where it should move.
5. **Test each rule for enforceability.** A rule the model may silently ignore is a request.
   Name the ones that need `hooks/pre-tool-use.py` instead.
6. **Find duplication.** A fact stated in two files drifts. Say which copy is the source of
   truth and which should link to it.
7. **Check the frontmatter contract.** `name:` must equal the directory name, and
   `description:` must say when to reach for the skill, not what it contains.

## Report

One table, worst first: `Finding | Risk | Fix`. Then the byte count before and after any
edit you make. Apply fixes only to the audited file — never to adjacent ones.

## Hard stops

- **Never delete a safety clause to save bytes.** Hard stops, negations and refusal rules
  survive every cut.
- Never report a saving you did not measure. Byte counts are measured; behaviour is not.
- Never invent a reference to replace a dangling one. If the intended target is unclear,
  say `[UNKNOWN]` and ask.
- Never audit more than the named file. Adjacent bloat goes to `/agent-spec-debt`.
