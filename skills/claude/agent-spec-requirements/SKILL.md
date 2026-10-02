---
name: "agent-spec-requirements"
description: >-
  SDLC gate 0: structure raw needs into 01-REQUIREMENTS.md. Assigns the REQ- identifiers gate 8 traces.
---

# Requirements Skill

## Gate

```bash
test -f .agent-spec/sdlc/00-INTENT.md && echo present || echo "none — use what the user typed"
```

If `/agent-spec-intent` ran, `00-INTENT.md` holds the originator's own framing — read it
and structure from it. If not, work from what the user said; a missing intent file is
fine. Everything downstream depends on this being honest about what is *not* known.

**Give every requirement an identifier** — `REQ-001`, `NFR-001`, `US-001`. Gate 8
traces those identifiers through every downstream artifact; without them nothing can
prove a requirement survived, and a dropped one is invisible.

1. Adopt the @WRITER persona.
2. Read `00-INTENT.md` if present, otherwise the user's raw input.
3. Structure it according to `.agent-spec/sdlc/01-REQUIREMENTS.md`.
4. Use `[NEEDS CLARIFICATION]` tags for missing information.
5. Ask the user questions to fill the gaps — one at a time, in plain language, and stop
   for the answer. A batch of five gets skimmed and half-answered.
6. **Before reporting done: run the [`self-review`](../agent-spec-self-review/SKILL.md) loop** on what
   you wrote — two passes, apply the fixes yourself, report once. Do not hand over a draft
   and wait to be asked for a review.

## What a good requirement looks like

Every requirement needs three things: **an identifier, a precise statement, and
measurable acceptance criteria.** Vague requirements produce vague tests — gate 8 will
fail to trace them, and a dropped requirement is invisible.

```
REQ-001: The system shall authenticate users via OAuth 2.0 before granting access to any endpoint.
  Acceptance: Given a valid Bearer token → 200. Given an expired token → 401.
              Given no token → 401. Given a malformed token → 400.

NFR-001: API p95 response time must be ≤ 200 ms under 1,000 concurrent users on the production tier.
  Acceptance: Load test at 1,000 RPS for 5 minutes; p95 from test tool output ≤ 200 ms.
  [NEEDS CLARIFICATION]: Which load testing tool does the team use?

US-001: As a returning user, I want my session to persist for 7 days so I don't re-authenticate daily.
  Acceptance: After login, session cookie expires in 168 h. After 168 h, next request redirects to /login.
```

**Beyond the happy path, capture:**
- **Non-goals** — what this feature explicitly does *not* do (prevents scope creep at HLD)
- **Constraints** — deadline, stack lock, compliance, budget; anything fixed before design starts
- **Known unknowns** — `[NEEDS CLARIFICATION: <one question>]`; do not guess or leave a gap silent

## Next gate

`/agent-spec-tech-spec` — feasibility and NFRs, once open `[NEEDS CLARIFICATION]` tags are answered.

State this and stop. Do not run the next gate yourself — each one is a separate approval,
and chaining two on one "yes" is how a requirement gets dropped without anyone noticing.

Record this gate before you stop:

```bash
./.agent-spec/bin/agent-spec-gate.py set 0
```
