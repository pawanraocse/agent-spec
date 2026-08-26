---
name: "implement"
description: >-
  Build a change through the 6-gate pipeline: declare, test first, surgical diff, self-review, honest report.
---

# Implement Skill

## Gate

```bash
ls .agent-spec/sdlc/05-LLD*.md 2>/dev/null || echo "no LLD — small-change mode"
```

If an LLD covers this area, read it first and build what it specifies; a diff that
contradicts an approved design is a defect even when it works. If there is none, this is
small-change mode — proceed, but say so, so nobody assumes a design gate was passed.

**If the cause of the problem is not yet known, stop and run `/investigate` instead.**
Edit-test-edit without a mechanism is the most expensive loop in this framework.


## Before writing anything

1. Read the project's hard rules — `CLAUDE.md` and anything under `.agent-spec/rules/`.
   Every time. They are deliberately not restated inside this skill.
2. Read `.agent-spec/coding-standards/SIMPLICITY-FIRST.md` and the language standard under
   `.agent-spec/coding-standards/languages/`.
3. Run `./.agent-spec/bin/graphify-cli.py query --file <target_file>` for the blast radius
   **before** modifying any code.
4. Post the **Pre-Change Declaration**: file and line range, current behaviour *quoted from
   source*, intended change, risk, test command, confidence.
   **CONFIDENCE LOW or UNKNOWN → stop and ask.**

## The gates

**G1 — Placement.** Which layer or module does this belong in? If the answer is "it spans
two", the change is two changes. If the answer is "a new service" or "a new language",
**stop** — that is an architecture decision needing an ADR, not a commit.

**G2 — Tests first.** Write the failing test before the fix, including the cases that must
return "unknown" with a stated reason rather than a plausible value. A bug's RED test is
kept permanently as the regression lock.

**G3 — Build it.** Surgical: only what the task requires (Absolute Rule #9). Match the
surrounding style, naming and comment density. Do not touch adjacent code.

**G4 — Verify the boundary.** Run the tests that enforce architecture — layering, purity,
import direction. A structural break should fail here, not in production six months on.

**G5 — Verify clean.** The full local gate: tests, linter, type checker. All green, no
exceptions. Paste the command and its real output.

**G6 — Self-review, then report.** Run the
[`self-review`](../self-review/SKILL.md) loop over the diff — two passes, apply the fixes
yourself, report once. Pay particular attention to class B (stale reference after an edit):
callers, tests, imports and docs that referred to what you just changed.

Do not proceed to the next gate until the current one's checklist is complete.

## Reporting

What was built, what was skipped, what is still unverified. **A failing test is reported as
a failing test, with its output.** Never report "done" over a yellow build, and never
report tests green before they are.
