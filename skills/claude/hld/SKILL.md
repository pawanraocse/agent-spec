---
name: "hld"
description: "Generate High Level Design and Architecture — service boundaries, data model, API contracts, NFRs. Gated on an approved PRD/TECH-SPEC. Output to .agent-spec/sdlc/04-HLD.md"
---

# HLD Skill

## Gate

```bash
test -f .agent-spec/sdlc/03-PRD.md && echo present || echo MISSING
```

`MISSING` → stop. Say that `/prd` has to run first, and why this gate cannot
substitute for it. **Never synthesise the upstream document to unblock yourself** — a
design built on an invented predecessor is worse than no design, because it looks
approved.


Adopt the **@ARCHITECT** persona.

**Precondition:** the upstream product/requirements documents are approved and their open
decisions are answered. If any are still open, **ask before writing** — an HLD built on an
unresolved pricing or stack decision is waste.

## Required inputs (read first)

1. `.agent-spec/sdlc/03-PRD.md` — the approved product requirements
2. `.agent-spec/sdlc/02-TECH-SPEC.md` — the locked stack and NFRs
3. Any gap review or reuse ledger the project keeps — every `GAP-nn` must stay traceable
4. `./.agent-spec/bin/graphify-cli.py stats` — a bird's-eye view of what already exists

## Mandatory sections

Adapt the names to the project; do not drop a row without saying why.

| § | Content |
|---|---|
| 1 | Context + service topology, as a **Mermaid diagram** |
| 2 | Service boundaries — why each split, deploy cadence, failure domains |
| 3 | Data model — ERD, tenancy strategy, row-level access policy design |
| 4 | API contracts — REST/RPC surface, webhooks, inbound provider callbacks |
| 5 | The highest-risk subsystem — its loop, latency budget, provider abstraction, state machine |
| 6 | Safety / correctness architecture — the gate that stops a bad output reaching a user |
| 7 | Metering and cost — the rows that price a capability, consume call sites, invoice derivation |
| 8 | External integrations — vendor choice, lifecycle, consent/limits |
| 9 | Core domain engine — the model, locking, the behaviour that earns the money |
| 10 | Reuse lift — module-by-module, migration squash plan, rename surface |
| 11 | NFRs — latency, availability, RPO/RTO, scale envelope |
| 12 | Environments + infrastructure plan |
| 13 | Open questions |

## Discipline

- **Every design choice states its `GAP-nn` or a reason.** An HLD that silently
  reintroduces a corrected spec error is a failed HLD.
- **No new metered capability without a cost row and a cost figure.**
- **No user-facing AI path without its safety design.**
- **Name the verifying artifact for each subsystem** (test, eval suite, gate). "It works"
  is not a verification strategy.
- **Prefer the reused component. Justify every net-new one.**

## Before you report done — mandatory

Run the **[`self-review`](../self-review/SKILL.md) loop on the artifact you just wrote.**
Two passes, apply the fixes yourself, then report once. Do not hand over a draft and wait
to be asked for a review.

Additionally, for an HLD specifically:

- **Coverage check against upstream, mechanically.** List every MVP capability the
  approved product doc promises and confirm each has a design home. The commonest HLD
  defect is an omitted pillar, not a wrong one.
- **Re-verify every `GAP-nn`** you cited actually says what you claimed.
- **Recompute every budget and every figure.** A stated SLO sitting above a table that
  sums past it is the defect this catches.

## Output

`.agent-spec/sdlc/04-HLD.md`, self-reviewed. Then **stop** — the LLD is a separate,
separately-approved step.

## Next gate

`/lld` — classes, schemas and contracts, one file per service.

State this and stop. Do not run the next gate yourself — each one is a separate approval,
and chaining two on one "yes" is how a requirement gets dropped without anyone noticing.
