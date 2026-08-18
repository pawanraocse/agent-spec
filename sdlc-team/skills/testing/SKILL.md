---
name: testing
description: "Build a test plan mapped 1:1 to the PRD's acceptance criteria, then write unit, integration, and e2e tests using the repo's existing framework and conventions. Load when writing tests, planning coverage, or verifying that acceptance criteria are actually exercised."
---

# Testing

Tests exist to catch regressions and to prove the acceptance criteria hold. Coverage
percentage measures neither. **Every `AC-n` in the PRD must map to a named test** — that
mapping, not a number, is this stage's deliverable.

## Required inputs

`01-prd.md` (the criteria), the implementation, and the repo's test setup. Detect the
framework before writing anything — see `coding-assistant`.

```bash
ls -1 vitest.config.* jest.config.* pytest.ini playwright.config.* 2>/dev/null
find . -name '*.test.*' -o -name 'test_*.py' -o -name '*_test.go' | grep -v node_modules | head
grep -E '"(test|test:unit|test:e2e)"' package.json 2>/dev/null
```

Match the existing framework, file naming, location, and assertion style. Introducing a
second test framework is a defect, however much you prefer it.

## The pyramid, applied

| Level | Covers | Speed | Use for |
|-------|--------|-------|---------|
| **Unit** | One unit, dependencies faked | ms | Logic, branches, boundaries, errors |
| **Integration** | Real seams — DB, HTTP, queue | ~s | Contracts, wiring, migrations |
| **E2E** | Full user journey | ~min | The PRD's primary journeys only |

Most tests should be unit tests. E2E belongs to the handful of journeys that must never
break — they are slow, flaky, and expensive to maintain, so spend them deliberately.

## Test plan

Write this to `06-test-plan.md` **before** writing tests. It is what QA validates against.

```markdown
## Coverage of acceptance criteria
| AC | Criterion | Level | Test | Status |
|----|-----------|-------|------|--------|
| AC-1 | Link expires in 15 min | unit | `token.test.ts › rejects expired` | PASS |
| AC-2 | 3 requests/hour/account | integration | `ratelimit.test.ts › blocks 4th` | PASS |
| AC-3 | Reset completes e2e | e2e | `reset.spec.ts › full journey` | FAIL |

**Unmapped criteria:** AC-5 (no test — needs a mail sandbox)
**Tests mapping to no criterion:** `legacy-token.test.ts` (pre-existing)
```

## Writing good tests

**Name the behavior, not the function.** `rejects a token past its expiry` beats
`test consume 2`. When it fails at 3am, the name is the whole diagnosis.

**Arrange–act–assert, visibly separated.** One logical assertion per test; a test
asserting six things reports only its first failure.

**Test behavior, not implementation.** Asserting that an internal method was called
means every refactor breaks the suite while the behavior is fine.

**Control time and randomness.** Fake timers, injected clocks, seeded RNG. Never
`sleep` to wait for something — that is the definition of a flaky test.

**Fake at the boundary you own.** Fake your own `TokenStore`, not a deep internal of
the HTTP library. Deep mocks break on every dependency upgrade.

**Cover the unhappy paths.** Invalid input, expired state, concurrent action, dependency
down, permission denied. This is where the defects are — the happy path is what was
manually clicked through during development.

## Running them

Run the suite and report **actual results**, including failures, with real output.

```bash
<the repo's test command>
```

A failing test is information. Reporting a suite as green when it is not, or quietly
skipping a failing case, corrupts every downstream decision. If you cannot run the
suite, say that explicitly rather than implying it passed.

Never weaken an assertion to make a test pass. If the test is right, the code is wrong.

## Self-check before handoff

Load `handoff-validation`. Your upstream is `01-prd.md`.

- Every `AC-n` appears in the mapping table with a named test, or is listed unmapped
  with a reason.
- Every NFR with a number has a test, or is flagged as unverifiable here.
- Every test result reported is one you actually observed.
- No pre-existing test was weakened or skipped to get green.

Report unmapped criteria explicitly. A test plan covering 9 of 12 criteria is useful;
one claiming 12 of 12 while covering 9 is worse than none.

## Anti-patterns

- **Coverage theater.** Tests that execute lines without asserting on them.
- **Assertion-free tests.** Calling the function and checking it did not throw.
- **Snapshot everything.** Snapshots that get blindly re-recorded on failure.
- **Shared mutable state.** Tests that pass alone and fail in suite, or depend on order.
- **Sleep-based waiting.** Guaranteed flake under CI load.
