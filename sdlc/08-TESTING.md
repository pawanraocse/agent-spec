# Stage 8: Testing

> **Skill**: `/testing`
> **Input**: `06-REVIEW.md`, `03-PRD.md`, `05-LLD.md`
> **Output**: `.agent-spec/sdlc/07-TEST-REPORT.md`

## The Goal

Run everything, and report the truth about what passed. This stage does not write the
first test — `/implement` gate G2 does that, before the fix. This stage runs the whole
suite, finds what nobody wrote a test for, and closes the gaps that matter.

## What the gate covers

- The real test command, taken from the project index, the manifest or the CI config.
  Never invented.
- The **whole** suite, not the subset this change touched: a regression is by definition
  somewhere nobody was looking.
- Every acceptance criterion in the PRD, and every error path in the LLD — the boundary,
  the empty input, the timeout, the "unknown with a stated reason" case.
- The integration edges. `graphify-cli.py services` names what talks to what; an untested
  cross-service call is the highest-cost gap on the list.

## Exit criteria

Green, with the real command and its real output pasted. A failing test is reported as a
failing test. Never delete, skip or `xfail` a test to pass the gate.

```bash
./.agent-spec/bin/agent-spec-gate.py set 7
```
