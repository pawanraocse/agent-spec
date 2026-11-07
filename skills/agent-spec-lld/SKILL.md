---
name: "agent-spec-lld"
description: >-
  SDLC gate 4: classes, schemas, sequence flows into 05-LLD.md, one per service. Needs 04-HLD.md.
---

# LLD Skill

## Gate

```bash
./.agent-spec/bin/agent-spec-gate.py check 4
```

`BLOCKED` → stop. Say which gate has to run first, and why this gate cannot
substitute for it. **Never synthesise the upstream document to unblock yourself** — a
design built on an invented predecessor is worse than no design, because it looks
approved.


Adopt the **@ARCHITECT** persona.

**Precondition:** `.agent-spec/sdlc/04-HLD.md` exists and is approved. Do not write an LLD
against a draft HLD.

## Scope per service

If the HLD defines more than one service, **write one LLD per service, not one monolith**.
Order them: largest net-new surface first, then highest-risk, then the deltas on any
lifted base. A single file covering every service produces the monolith this scope rule
exists to avoid.

Run `./.agent-spec/bin/graphify-cli.py search <domain>` first to find the existing classes
you should be extending rather than duplicating.

## Mandatory content

| Area | Required |
|---|---|
| Classes | Package layout, key interfaces, responsibilities. SOLID — no god services. |
| Schema | DDL, indexes, constraints, row-level access policies, migration version |
| APIs | Path, method, request/response DTOs, status codes, idempotency keys |
| Sequences | The critical end-to-end flows, one diagram each |
| State machines | Every entity with a lifecycle |
| Errors | Failure modes and the user-visible behaviour for each |
| Tests | The specific test that proves each unit of behaviour |

## Non-negotiables

- **Test-first.** Every bug gets a RED failing test reproducing it before the fix, kept as
  the permanent regression lock.
- **Parameters live in the database**, never hardcoded — pricing, costs, rules, timings.
- **Name the verifying oracle** for each behaviour. A green unit test alone is necessary,
  never sufficient — say what independently proves correctness.
- **Idempotency on every webhook.** Providers retry; duplicates are the default failure
  mode, not the edge case.
- **SOLID, sanity-checked against `.agent-spec/coding-standards/SIMPLICITY-FIRST.md`** —
  unchecked, SOLID produces a Strategy pattern for a one-off calculation.

## Before you report done — mandatory

Run the **[`self-review`](../agent-spec-self-review/SKILL.md) loop on the artifact you just wrote.**
Two passes, apply the fixes yourself, then report once. Do not hand over a draft and wait
to be asked for a review.

Additionally, for an LLD specifically:

- **Every HLD decision must survive.** An LLD that quietly contradicts the approved HLD is
  a failed LLD — check section by section, not from memory.
- **Every table gets its access policy**, or an explicit entry on the exempt allowlist.
  "No policy" must always be a reviewed statement, never an omission.
- **Every DTO field, status code and idempotency key is named** — a signature you did not
  read is a signature you must not invent.
- **Every behaviour names its test.** A section with no verifying oracle is not done.

## Output

`.agent-spec/sdlc/05-LLD-<service>.md`, one per service, self-reviewed. A single
`05-LLD.md` is correct only when the HLD defines exactly one service.

## Next gate

`/agent-spec-implement` — the 6-gate coding pipeline, one LLD section at a time.

State this and stop. Do not run the next gate yourself — each one is a separate approval,
and chaining two on one "yes" is how a requirement gets dropped without anyone noticing.

Record this gate before you stop:

```bash
./.agent-spec/bin/agent-spec-gate.py set 4
```
