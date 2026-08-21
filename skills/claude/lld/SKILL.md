---
name: "lld"
description: "Generate Low Level Design — classes, DB schemas, API contracts, sequence flows. One file per service. Gated on an approved 04-HLD.md. Output to .agent-spec/sdlc/05-LLD[-<service>].md"
allowed-tools:
  - "Read"
  - "Write"
  - "Bash"
---

# LLD Skill

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

Run the **[`self-review`](../self-review/SKILL.md) loop on the artifact you just wrote.**
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
