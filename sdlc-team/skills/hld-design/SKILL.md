---
name: hld-design
description: "Turn a PRD into a system-level design: component decomposition, data flow, integration points, technology choices with honest trade-offs, and NFR budgets. Load when producing or reviewing an HLD, or when a feature needs an architectural shape before detailed design."
---

# High Level Design

The HLD answers **how, at the level of boxes and arrows**. It decides component
boundaries, data flow, and technology — and it records *why*, so the next person to
question a decision can find the reasoning instead of re-litigating it.

It stops short of function signatures and schemas. Those are the LLD's.

## Required inputs

`01-prd.md`, plus the actual repository. An HLD written without reading the existing
code is fiction — you cannot decide what to extend if you do not know what is there.

```bash
find . -maxdepth 3 -type d -not -path '*/node_modules/*' -not -path '*/.git/*' | head -40
cat CLAUDE.md 2>/dev/null
```

## Structure

```markdown
# HLD: <feature name>
**Upstream:** 01-prd.md · **Date:** <date>

## 1. System context
Where this sits in the existing system, and what it touches.

## 2. Components
| Component | Responsibility | New or existing | Owns |
|-----------|----------------|-----------------|------|

## 3. Data flow
A Mermaid sequence diagram for each primary user journey in the PRD.

## 4. Data ownership
What is stored, by whom, and its lifecycle. Retention and deletion.

## 5. Technology decisions
One subsection per decision, in the ADR shape below.

## 6. NFR budgets
| NFR | Target (from PRD) | Design provision | Headroom |

## 7. Failure modes
| What fails | Blast radius | Detection | Degradation |

## 8. Security model
Trust boundaries, authn/authz, secrets, data classification.

## 9. Rejected alternatives
What was considered and why it lost.
```

## Decisions carry their reasoning

Each technology decision gets this shape. Without the alternatives and consequences it
is an assertion, not a decision.

```markdown
### D-1: Token storage
**Decision:** Reuse the existing Postgres instance with a TTL index.
**Alternatives:** Redis (new dependency, better TTL semantics); JWT stateless
(no storage, but unrevocable — fails AC-4).
**Why:** AC-4 requires revocation on use. Volume (~2k/day) is far inside what Postgres
handles. A new datastore is not justified by this feature alone.
**Consequences:** A cleanup job is needed for expired rows. If reset volume grows 100×,
revisit Redis.
```

Prefer boring, already-present technology. **Every new dependency costs the team
forever;** a marginal fit for one feature is rarely worth it. When you do add one, say
what it costs, not only what it gives.

## NFR budgets must decompose

A PRD NFR of "p95 < 200ms" is useless until you spend it across the path:

| Hop | Budget |
|-----|--------|
| Ingress + auth | 20ms |
| Token lookup | 30ms |
| Business logic | 50ms |
| Mailer enqueue (async) | 0ms |
| Headroom | 100ms |

If the budget does not close, say so **now**. An NFR that cannot be met is a PRD problem,
and this is the last cheap moment to raise it.

## Diagrams

Use Mermaid `sequenceDiagram` for journeys, `flowchart` for component relationships. The
diagram must match the prose — a diagram showing a component the text never mentions is
a defect, and reviewers trust the picture.

## Self-check before handoff

Load `handoff-validation`. Your upstream is `01-prd.md`. Reconcile:

- Every `AC-n` maps to a component and a data flow that could satisfy it.
- Every `NFR-n` has a budget and a design provision, or is flagged.
- Nothing in the design traces to no PRD item without an `ADDED` justification.
- Non-goals are respected — you have not designed for excluded scope.
- Every new dependency is justified against reusing what exists.
- Failure modes cover each external integration.

## Anti-patterns

- **Resume-driven architecture.** A message queue for 2k events/day.
- **Diagram-as-design.** Boxes with no responsibilities or contracts.
- **Unbudgeted NFRs.** Restating "p95 < 200ms" without showing where the time goes.
- **Invisible coupling.** Two components sharing a table without saying who owns writes.
- **Premature microservices.** A new deployable for one endpoint.
