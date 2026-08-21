---
name: "review"
description: "Deep skeptical code review — blockers first, style last. Traces a real case end-to-end rather than reading files in isolation, and applies the fixes."
allowed-tools:
  - "Read"
  - "Write"
  - "Edit"
  - "Bash"
  - "Grep"
  - "Glob"
---

# Review Skill

Adopt the **@REVIEWER** persona (`.agent-spec/personas/REVIEWER.md`).

**Order is the point:** a style nit costs minutes; a correctness defect costs a decision
made on a wrong number. Correctness first, style last. Never lead with naming.

Run `./.agent-spec/bin/graphify-cli.py query --file <target_file>` for the blast radius.
Skip it for markdown and design documents — the graph indexes code and will report
`Could not find exact file matching`. That is not an error.

## Pass 1 — correctness (blockers, always first)

- **Trace ONE real case end-to-end.** Reading files in isolation is how seam bugs ship:
  each file is individually correct and the handoff between them is wrong. Follow a single
  input from entry point → parameter object → resolver → query → calculation → rendered
  output, and **prefer to actually execute it** over reasoning about it.
- **Docs, comments and docstrings lie.** Verify against source and against the current
  external authority, never against a comment that describes intent from two refactors ago.
- **Check the project's own hard rules** — whatever `CLAUDE.md` and `.agent-spec/rules/`
  declare non-negotiable for this repo. Those are blockers by definition.
- **Failure paths.** Does an error path invent a plausible value instead of failing loudly
  or returning "unknown" with a stated reason? Silent fallbacks are the highest-cost defect
  class there is.
- **Duplicated logic.** One implementation, one test suite. A second copy of a calculation
  is a future divergence with a date on it.
- **Retired code lingers.** A removed feature's services stay compiled-but-unwired,
  invisible to every reviewer and one annotation away from silent resurrection. Sweep for
  orphans.

## Pass 2 — the change itself

- `.agent-spec/coding-standards/SIMPLICITY-FIRST.md`. Would a senior engineer call this
  overcomplicated? Is a new abstraction justified by real reuse, or speculative?
- Tests: do they cover the boundary and the undefined cases, or only the happy path?
  **Missing tests on a behaviour that produces a result is a [BLOCKER], not a [MINOR].**
- Scope creep: anything touched outside the stated task?
- Does it quietly re-add scope the project deliberately deleted?

## Pass 3 — style

`.agent-spec/coding-standards/CLEAN-CODE.md` + `SOLID-PRINCIPLES.md`. Naming, dead code,
comment density matching the surrounding file.

## Output

Tag every finding `[BLOCKER]`, `[MINOR]` or `[NIT]`, most severe first, each with
`file:line` and a **concrete failure scenario — inputs → wrong output**.

- **A finding you cannot demonstrate is a [NIT].**
- If nothing is wrong, say so plainly. Never manufacture findings to look thorough.
- **Apply the fixes, then re-check what you touched** — do not stop at a findings list.
  Anything needing a decision the user owns is reported as an open question, not silently
  chosen.

> **Which review is this?** `/review` is the standalone, on-demand review of code someone
> asks you to look at. [`self-review`](../self-review/SKILL.md) is the bounded loop that
> runs *inside* `/hld`, `/lld`, `/prd`, `/tech-spec`, `/requirements` and `/implement`
> before they report done. Same defect classes, different trigger. If you are finishing
> your own work, it is `self-review`.
