---
name: lld-design
description: "Turn an HLD into implementable detail: interfaces, data models, API contracts, error taxonomy, state transitions, and concurrency rules. Load when producing or reviewing an LLD, or before implementing anything non-trivial."
---

# Low Level Design

The LLD is the last document before code. It should be detailed enough that two
developers implementing it independently produce compatible work.

The test: **could someone build this without asking you a question?** Every unanswered
question becomes an ad-hoc decision made under time pressure.

## Required inputs

`02-hld.md` and `01-prd.md` (for acceptance criteria), plus the real code — actual
signatures of anything you integrate with. Guessing an existing function's shape is the
most common way an LLD becomes unbuildable.

```bash
grep -rn "class\|interface\|def \|func \|export " <relevant-dirs> | head -40
```

## Structure

```markdown
# LLD: <feature name>
**Upstream:** 02-hld.md · **Date:** <date>

## 1. Interfaces
Exact signatures, with types, for each new or modified unit.

## 2. Data models
Schemas, constraints, indexes, migrations — forward and back.

## 3. API contracts
Method, path, request, response, status codes, per endpoint.

## 4. Error taxonomy
Every error: when raised, how surfaced, what the caller does.

## 5. State transitions
Legal states and transitions; what happens on an illegal one.

## 6. Concurrency and idempotency
Races, locks, retries, at-least-once handling.

## 7. Configuration
New settings, defaults, and which are secrets.

## 8. Test seams
Where the boundaries are and how each is faked.

## 9. Traceability
| PRD AC | LLD element |
```

## Interfaces: exact, not approximate

```typescript
// Good — a developer can implement against this
interface TokenStore {
  /** @throws {DuplicateTokenError} if the token already exists */
  create(userId: UserId, ttl: Duration): Promise<Token>;
  /** Returns null when absent or expired — does not throw */
  consume(raw: string): Promise<Token | null>;
}

// Useless
interface TokenStore { create(...): any; consume(...): any }
```

State the null/empty behavior, what throws, and whether calls are idempotent. Most
integration bugs live in exactly these unstated details.

## Data models: constraints, not just columns

```sql
CREATE TABLE password_reset_token (
  id          uuid PRIMARY KEY,
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash  bytea NOT NULL,           -- never store the raw token
  expires_at  timestamptz NOT NULL,
  consumed_at timestamptz,
  CONSTRAINT one_active_per_user
    EXCLUDE (user_id WITH =) WHERE (consumed_at IS NULL)
);
CREATE INDEX ON password_reset_token (expires_at) WHERE consumed_at IS NULL;
```

Specify the rollback for every migration. A migration you cannot reverse is an outage
you cannot undo. Adding a `NOT NULL` column to a populated table needs an explicit
backfill plan — state it.

## Error taxonomy

| Error | Raised when | HTTP | Client action | Logged |
|-------|-------------|------|---------------|--------|
| `TokenExpired` | `expires_at < now()` | 410 | Offer re-request | info |
| `TokenAlreadyUsed` | `consumed_at` set | 410 | Offer re-request | warn |
| `RateLimited` | > 3/hour/account | 429 | Back off, show retry-after | warn |

Never surface an internal error verbatim to a client. Never log a raw token, password,
or PII — say so here, so it does not become a review finding later.

## Concurrency

Name the races the HLD implied. Two simultaneous reset requests; a token consumed twice;
a retry after a timeout where the first call actually succeeded. For each: what
guarantees correctness — a unique constraint, a transaction boundary, an idempotency key.

## Test seams

For every dependency: what it is, how it is faked, and what the fake must do. If a unit
cannot be tested without real network or a real clock, redesign the seam now.

## Self-check before handoff

Load `handoff-validation`. Your upstream is `02-hld.md`, plus `01-prd.md` for criteria.

- Every HLD component has interfaces here, or is explicitly out of scope.
- Every HLD data-flow step has a method that performs it.
- Every PRD `AC-n` appears in the traceability table.
- Every error path in the PRD's unhappy cases is in the taxonomy.
- Every migration has a rollback.
- No interface returns an unspecified `any`/`interface{}`/`dict`.
- Every signature you integrate with was **read from source**, not assumed.

## Anti-patterns

- **Pseudo-code as design.** Prose narrating an algorithm instead of stating contracts.
- **Optimistic typing.** `any` deferred to implementation.
- **Missing null semantics.** Absent, empty, and error conflated.
- **Untestable seams.** Direct `new` of a network client inside business logic.
- **Irreversible migrations.** No down path.
