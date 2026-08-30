---
name: "testing"
description: >-
  SDLC gate 7: execute the full test suite, report coverage and every failure verbatim into 07-TEST-REPORT.md. Needs 06-REVIEW.md.
---

# testing

Adopt the **@QA** persona (`.agent-spec/personas/QA-ENGINEER.md`).

## Gate

```bash
./.agent-spec/bin/agent-spec-gate.py check 7
```

`BLOCKED` → stop and say which gate has to run first.

This gate is **not** where tests get written. `/implement` gate G2 writes the failing
test before the fix. This gate runs everything, finds what nobody wrote a test for, and
reports the truth about what passed.

## Do

1. Find the real test command. Take it from `.agent-spec/PROJECT-INDEX.md`, the build
   manifest or the CI configuration — **never invent one**. If you cannot find it, say so
   and stop.
2. Run the whole suite. Not the subset touched by this change: a regression is by
   definition somewhere you were not looking.
3. Capture coverage if the project already produces it. Do not add a coverage tool as a
   side effect of this gate.
4. Identify the gaps that matter, using the design as the checklist:
   - every acceptance criterion in `03-PRD.md` — is there a test that would fail if it
     broke?
   - every error path in `05-LLD.md` — the boundary cases, the empty input, the timeout,
     the "unknown with a stated reason" case
   - the integration edges: `./.agent-spec/bin/graphify-cli.py services` names what talks
     to what. An untested cross-service call is the highest-cost gap on the list.
5. Write the missing tests for anything in step 4 that produces a result. **A behaviour
   that produces a value and has no test is a blocker, not a note.**
6. Re-run. Paste the real command and its real output.

## Write `.agent-spec/sdlc/07-TEST-REPORT.md`

```markdown
# Test Report — <feature> — <date>

## Command
`<the exact command>`

## Result
<pass/fail counts, verbatim from the runner's own summary line>

## Failures
<each one: test name, assertion, and the runner's message quoted exactly>

## Coverage
<numbers, or "not measured — the project has no coverage tooling">

## Gaps closed this gate
- <test added> — covers <REQ-id or LLD section>

## Gaps remaining
- <what is still untested, and why it was left>
```

## Hard stops

- **A failing test is reported as a failing test, with its output.** Never summarise a
  red suite as "mostly passing".
- Never mark this gate passed over a failure. `set 7` after green, never before.
- Never delete, skip or `xfail` a test to make the gate pass. If a test is genuinely
  wrong, say why, in the report, and let a human decide.
- Never quote a number you did not see the runner print.

## Next gate

`/validation` — acceptance against the original requirements.

Record and stop:

```bash
./.agent-spec/bin/agent-spec-gate.py set 7
```
