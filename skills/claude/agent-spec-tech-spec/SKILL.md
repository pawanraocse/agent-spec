---
name: "agent-spec-tech-spec"
description: >-
  SDLC gate 1: feasibility, stack and NFRs into 02-TECH-SPEC.md. Needs 01-REQUIREMENTS.md.
---

# Tech-spec Skill

## Gate

```bash
./.agent-spec/bin/agent-spec-gate.py check 1
```

`BLOCKED` → stop. Say which gate has to run first, and why this gate cannot
substitute for it. **Never synthesise the upstream document to unblock yourself** — a
design built on an invented predecessor is worse than no design, because it looks
approved.

1. Adopt the @ARCHITECT persona.
2. Read `.agent-spec/sdlc/01-REQUIREMENTS.md` and `.agent-spec/PROJECT-INDEX.md`.
   **If `PROJECT-INDEX.md` names a stack under `Stack:`, that decision is locked — do not
   re-derive it.** A spec that reopens a settled stack decision is how a deleted
   architecture comes back.
3. Assess technical feasibility against each `REQ-` identifier. Flag any requirement that
   cannot be met with the current stack — do not silently drop it.
4. Define NFRs with **numbers, not adjectives**. See below.
5. **Assign a Complexity Score** and write it under `## Complexity` in the output.
   The SDLC router reads this field to select which gates to run. Use:
   ```
   ## Complexity
   Scope: narrow        # narrow | wide
   Algorithm: low       # low | high
   Track: fast-track    # fast-track | algorithm | design | full
   Rationale: <one sentence>
   ```
   Scope is **narrow** when ≤ 3 files change and no service boundary is crossed.
   Algorithm is **high** when the change requires a novel data structure, state machine,
   cryptographic primitive, or multi-site schema migration — not CRUD or config.
   Do not guess scope. If unsure, run:
   `graphify-cli.py context --task "<task>"` before filling this in.
6. Output to `.agent-spec/sdlc/02-TECH-SPEC.md` following the template.
7. **Before reporting done: run the [`self-review`](../agent-spec-self-review/SKILL.md) loop** —
   two passes, apply the fixes yourself, report once. Recompute every NFR figure; a stated
   budget that its own table exceeds is the defect this catches.

## What a good NFR looks like

An NFR without a number is not an NFR — it is an aspiration. Gate 7 cannot test
"fast" or "scalable". Every NFR must have a metric, a threshold, and a measurement method.

```
NFR-001 Performance: p95 API response ≤ 200 ms at 1,000 concurrent users.
  Measure: k6 load test for 5 min at 1,000 RPS on the staging tier.

NFR-002 Availability: 99.9% uptime over any 30-day window (≤ 43.8 min downtime/month).
  Measure: Uptime monitor alerts; monthly SLA report from observability platform.

NFR-003 Data retention: User PII purged within 30 days of account deletion.
  Measure: Automated audit script on deletion queue; manual spot-check quarterly.
  [NEEDS CLARIFICATION]: Does GDPR right-to-erasure apply (determines the 30-day window)?
```

**Feasibility traps to check explicitly:**
- Does any `REQ-` depend on a third-party API with unknown rate limits?
- Does the performance NFR require infrastructure changes not currently budgeted?
- Does any requirement conflict with an existing constraint in `PROJECT-INDEX.md`?

If yes to any: surface it here. A known conflict caught at gate 1 costs one conversation.
The same conflict caught at gate 7 costs the full pipeline.

## Next gate

`/agent-spec-prd` — user stories and MoSCoW, built on this spec.

State this and stop. Do not run the next gate yourself — each one is a separate approval,
and chaining two on one "yes" is how a requirement gets dropped without anyone noticing.

Record this gate before you stop:

```bash
./.agent-spec/bin/agent-spec-gate.py set 1
```
