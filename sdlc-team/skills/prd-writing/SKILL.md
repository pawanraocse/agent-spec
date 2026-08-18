---
name: prd-writing
description: "Turn a feature idea into a PRD: problem, goals and non-goals, user stories, testable acceptance criteria, NFRs, and success metrics. Load when writing or reviewing a PRD, or when a feature request needs to be made concrete enough to design against."
---

# PRD Writing

A PRD defines **what** and **why**, never **how**. The moment you name a database or a
framework, you have taken a decision that belongs to the architect and removed it from
the table.

Its real job is to be **checkable**. Every downstream stage reconciles against this
document; a requirement that cannot be verified cannot be tested, and will not be built.

## Required inputs

The feature request, plus the repo's `CLAUDE.md` for product constraints. If the request
is one line, ask up to three clarifying questions — the highest-value ones — then proceed
with stated assumptions. Do not stall on a questionnaire, and do not silently invent
scope to fill the gaps.

## Structure

```markdown
# PRD: <feature name>
**Status:** Draft · **Date:** <date> · **Slug:** <kebab-slug>

## 1. Problem
Who is hurting, what it costs them, and how we know. Evidence beats assertion:
a support-ticket volume, a drop-off rate, a quoted complaint.

## 2. Goals
- G-1 ...   (outcome, not feature: "users recover access unaided", not "add a reset form")

## 3. Non-goals
- NG-1 ...  (the ones a reasonable reader would otherwise assume are in scope)

## 4. User stories
- US-1: As a <role>, I want <capability> so that <outcome>.

## 5. Acceptance criteria
- AC-1: Given <state>, when <action>, then <observable result>.

## 6. Non-functional requirements
- NFR-1: <latency / throughput / availability / security / compliance>, with a number.

## 7. Success metrics
- M-1: <metric>, from <baseline> to <target>, measured by <source> within <window>.

## 8. Open questions
- Q-1: <question> — blocking / non-blocking

## 9. Assumptions
- A-1: <assumption made in the absence of an answer>
```

## Acceptance criteria are the load-bearing section

Everything downstream keys off these. Write them so that two engineers would build the
same thing and one test could prove it.

| Weak | Strong |
|------|--------|
| "Reset should be fast" | AC: p95 end-to-end under 2s (NFR-1) |
| "Handle invalid tokens" | AC: Given an expired token, when submitted, then 410 and re-request offered |
| "Secure the endpoint" | AC: Given 4 requests in an hour for one account, when a 5th is made, then 429 |

Each criterion must be:
- **Given/when/then** — a state, an action, an observable result.
- **Singular** — one behavior; split compound criteria.
- **Observable** — from outside the system. "Then the cache is updated" is untestable at
  this level; "then a subsequent read returns the new value" is.
- **Numbered** — `AC-n`, permanently. Later stages cite these IDs; renumbering breaks
  traceability across every artifact.

Cover the unhappy paths explicitly: invalid input, expired state, concurrent action,
permission denied, dependency unavailable. A PRD with only happy paths hands every edge
case to the developer as an unlogged decision.

## Non-goals earn their place

Non-goals are where scope creep dies. If someone might reasonably assume it is included,
name it and exclude it: "SSO accounts are out of scope for v1 — they reset upstream."

## Success metrics vs. acceptance criteria

They are different and both required. Acceptance criteria say the feature *works*;
metrics say it *mattered*. "Reset completes successfully" is a criterion. "Password-reset
support tickets fall 60% within one quarter" is a metric.

## Self-check before handoff

Load `handoff-validation`. Your upstream is the user's request. Reconcile:

- Every explicit ask in the request maps to a goal or an acceptance criterion.
- Nothing in the PRD is traceable to no ask — or if it is, it is flagged `ADDED` and
  justified.
- Every acceptance criterion is given/when/then, singular, observable, numbered.
- Every NFR carries a number. "Scalable" is not an NFR.
- Constraints from `CLAUDE.md` are reflected, not contradicted.
- Open questions are marked blocking or non-blocking, and assumptions are written down.

Report the result. A PRD built on three unanswered blocking questions should say so
rather than presenting invented answers as requirements.

## Anti-patterns

- **Solution smuggling.** "Users need a Redis-backed token store" — that is an HLD
  decision wearing a requirement's clothes.
- **Unfalsifiable criteria.** "Intuitive", "seamless", "robust", "performant".
- **Unbounded metrics.** A target with no baseline, source, or window is decoration.
- **Silent scope inflation.** Adding an audit log nobody asked for because it seemed prudent.
