---
name: "agent-spec-prd"
description: >-
  SDLC gate 2: user stories and MoSCoW into 03-PRD.md. Needs 02-TECH-SPEC.md.
---

# PRD Skill

## Gate

```bash
./.agent-spec/bin/agent-spec-gate.py check 2
```

`BLOCKED` → stop. Say which gate has to run first, and why this gate cannot
substitute for it. **Never synthesise the upstream document to unblock yourself** — a
design built on an invented predecessor is worse than no design, because it looks
approved.

1. Adopt the @WRITER persona.
2. Read `.agent-spec/sdlc/01-REQUIREMENTS.md` and `02-TECH-SPEC.md`.
3. Follow the iterative Discover → Document → Review cycle.
4. Apply MoSCoW prioritization to all features. Every Must Have must be achievable within
   the tech constraints from gate 1 — if it isn't, it is a Should Have.
5. Run the **Validation Checklist** (below) before reporting done.
6. Output to `.agent-spec/sdlc/03-PRD.md`.
7. **Before reporting done: run the [`self-review`](../agent-spec-self-review/SKILL.md) loop** —
   two passes, apply the fixes yourself, then give the Status Report once. Pay particular
   attention to coverage: every upstream `REQ-` identifier must appear in at least one
   user story.

## What good MoSCoW looks like

Each item needs a priority label, the `REQ-` it traces to, and one clear "done" signal.

```
[Must Have]   US-001 → REQ-001: User can log in with Google OAuth.
              Done: /login?provider=google returns a valid session; dashboard loads.

[Should Have] US-002 → REQ-002: User can switch between light and dark theme.
              Done: Theme persists across browser sessions via localStorage.

[Could Have]  US-003: User sees animated onboarding tour on first login.
              Done: Tour renders on first login; dismissed state persisted.

[Won't Have]  US-004: Multi-language support. (Deferred to v2 — NFR-003 compliance window.)
```

## Validation Checklist (run before self-review)

A PRD passes when every item below is true. Fix before handing off.

- [ ] Every `REQ-` from gate 0 appears in at least one user story.
- [ ] Every `NFR-` from gate 1 has a corresponding acceptance criterion in at least one story.
- [ ] Every Must Have is feasible within the gate 1 stack and budget.
- [ ] No story has "done" criteria that cannot be objectively tested by a QA engineer.
- [ ] The Won't Have section explicitly names what is deferred and why.
- [ ] No story creates a dependency on a service not mentioned in gate 1.
- [ ] Stories are ordered by dependency (a story that blocks others comes first).

## Next gate

`/agent-spec-hld` — service boundaries and data model.

State this and stop. Do not run the next gate yourself — each one is a separate approval,
and chaining two on one "yes" is how a requirement gets dropped without anyone noticing.

Record this gate before you stop:

```bash
./.agent-spec/bin/agent-spec-gate.py set 2
```
