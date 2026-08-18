---
name: code-review
description: "Review a diff against the LLD and the repo's own conventions: correctness, SOLID violations, security issues, missing tests. Produces severity-ranked findings with concrete failure scenarios. Load when reviewing code, a PR, or an implementation handoff."
---

# Code Review

Review the **diff**, against the **design**, in the context of **this repo's conventions**.
A finding must be something that would actually go wrong, stated concretely enough to act
on. Taste dressed as a defect wastes the author's time and erodes trust in every other
finding you raise.

## Required inputs

```bash
git diff --stat main...HEAD
git diff main...HEAD
```

Plus `03-lld.md` and the repo conventions from `coding-assistant`. Read the surrounding
code, not only the changed lines — most real defects are interaction defects, invisible
inside the diff.

## Severity

| Level | Meaning | Examples |
|-------|---------|----------|
| **Critical** | Data loss, security hole, or breaks production | Injection, secret in source, unbounded delete, auth bypass |
| **High** | Wrong behavior on a realistic input | Off-by-one, unhandled null, race, wrong error code |
| **Medium** | Correct now, fragile later | Missing test on a branch, SOLID violation, swallowed error |
| **Low** | Style and clarity | Naming, dead code, redundant comment |

Rank findings by severity. Ten Low findings above one Critical means the Critical gets
skimmed past.

## What to check

### Correctness
- Boundaries: empty, single-element, maximum, zero, negative.
- Null/undefined on every value crossing a boundary.
- Off-by-one in slicing and pagination.
- `async` correctness: unawaited promises, unhandled rejections, sequential awaits in loops.
- Errors: caught at a level that can act, not swallowed to quiet a linter.

### Security
- Input validated at the trust boundary, not deep inside.
- Parameterized queries — always. Never string-built SQL.
- Output encoded for its sink (HTML, shell, SQL, log).
- No secrets in source, tests, or fixtures.
- Authorization checked on every path, not only the UI-reachable one.
- Nothing sensitive in logs: tokens, passwords, PII, full card numbers.
- Dependencies: new ones justified, and not obviously abandoned.

### Design and SOLID
- **S**: does this unit have one reason to change?
- **O**: does adding a case mean editing a `switch` in five files?
- **L**: does an override violate the base contract?
- **I**: are callers forced to depend on methods they never use?
- **D**: is business logic coupled to a concrete I/O implementation?

Flag over-abstraction just as readily. A strategy pattern with one strategy is a defect.

### Tests
- Every new branch has a test.
- Tests assert behavior, not implementation detail.
- Unhappy paths covered, not only the happy one.
- No test that passes when the feature is removed.

### Conventions
- Matches the repo's naming, layout, error style, and test placement.
- No new utility duplicating an existing one.
- No unrelated reformatting hiding the real change.

## Output format

```markdown
## Review: <feature>
**Diff:** 12 files, +430/-85 · **Against:** 03-lld.md
**Verdict:** REQUEST CHANGES

### Critical
**1. SQL injection in the token lookup** — `src/auth/token.ts:42`
Query is built by string concatenation from `req.query.token`.
*Failure:* `?token=' OR '1'='1` returns another user's valid token.
*Fix:* parameterize the query.

### High
**2. Expired tokens are accepted** — `src/auth/reset.ts:88`
`consume()` checks `consumed_at` but never `expires_at`, contradicting LLD §4.
*Failure:* a 30-day-old link still resets the password. Violates AC-3.

### Medium
...

### Design-conformance
| LLD element | Implemented | Note |
|-------------|-------------|------|
| `TokenStore.consume` | Partial | Missing expiry check (finding 2) |
```

Every finding needs a **location**, a **concrete failure scenario**, and where it is not
obvious, a **fix direction**. "This could be cleaner" is not a finding.

## Verdicts

| Verdict | When |
|---------|------|
| `APPROVE` | No Critical or High; Medium/Low noted as non-blocking |
| `APPROVE WITH NITS` | As above, with fixes the author can take or leave |
| `REQUEST CHANGES` | Any Critical or High, or a contradiction with the LLD |

## Self-check before handoff

Load `handoff-validation`. Your upstream is `03-lld.md` plus the diff.

- Every LLD interface is implemented, or its absence is a finding.
- Every LLD error-taxonomy entry is handled.
- Code present in the diff but in no LLD element is flagged `ADDED`.
- Every finding cites a real file and line you actually read.

**You do not fix what you find.** Findings go back to the developer. A reviewer who
edits the code under review has destroyed the independence that made the review worth
running.

## Anti-patterns

- **Rubber-stamping.** "LGTM" on 400 lines you did not read.
- **Style-only reviews.** Twelve naming nits, zero correctness checks.
- **Speculative findings.** "This might be slow" with no path and no measurement.
- **Rewrite-by-review.** Redesigning to your preference when the LLD was approved.
