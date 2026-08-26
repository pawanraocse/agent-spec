---
name: "self-review"
description: >-
  Bounded review-and-repair loop run INSIDE any artifact-producing skill before it reports done. Also standalone on a file.
---

# Self-Review

**An artifact is not finished when it is written. It is finished when it has survived
being read again.** Across the projects this skill came from, the second pass has not yet
once come back empty — a representative run:

```
docs/ pre-commit review     7 defects in work described as complete
sdlc/04-HLD.md pass 1      12 defects · 5 blocker-class
sdlc/04-HLD.md pass 2      13 defects · 4 blocker-class · 2 caused by pass 1's own fixes
```

This runs **inside** the producing skill. Do not hand the user a draft and wait to be
told to review it — that is the loop this exists to remove.

---

## The loop, and its bound

```
write → PASS 1 → apply → PASS 2 → apply → report
                                    │
                          blocker found in pass 2?
                                    │ yes
                              → PASS 3 → apply → report
```

**Two passes always. A third only if pass 2 found a blocker-class defect.** Then stop and
report — including anything still unresolved. This is a bounded loop, not a
polish-until-perfect loop; the third pass has diminishing returns and the fourth is
procrastination wearing a checklist.

**Pass 2 is not optional, and it is not a formality.** On one HLD it found four
blocker-class defects, two of which *pass 1 created* — a fix in one section that left
three other sections referring to the old state. Fixing a thing and not its references is
the ordinary way a document rots.

---

## What to look for

Derived from defects actually found in practice, in yield order. Run every class; do not
stop at the first hit. The `>` examples are real findings, kept because a named defect is
easier to recognise than an abstract category.

### A · Internal contradiction — highest yield
Two parts of the same artifact disagree. Read them **against each other**, not each on
its own.
> A document scoped a client application out in §2.4 while three other sections still
> drew it as live. A partial unique index in §9.3 made the overbooking hook §9.6 claimed
> to "accommodate" impossible.

### B · Stale reference after an edit
Every edit invalidates something elsewhere. After each fix, grep for what pointed at the
old state: section numbers, figures, cross-references, diagrams, status lines.
> A `§9.9` that never existed. A "see OQ-9" left pointing at a question that had been
> closed. A "the budget is 750ms" left behind after the budget became two budgets.

### C · Unit and arithmetic error
Recompute every number. Check that a column's unit matches its values.
> `₹1,999/month` sitting in a `₹/minute` row — the exact unit confusion the document had
> been written to prevent, re-committed inside it. A latency table summing to 940ms under
> an asserted 800ms ceiling. A dashboard double-counting recovery.

### D · A claim the artifact itself refutes
Assertions of adequacy — "the schema accommodates this", "fail-closed", "tracked per
build". Verify each against what the artifact actually specifies.
> "Fail-closed" claimed in prose above DDL that would raise rather than return empty.

### E · Missing scope — check upstream, mechanically
List what the upstream approved documents promise, then confirm each appears. This is
mechanical and high-yield; do not do it from memory.
> An MVP pillar the upstream design doc called its strongest single idea was absent from
> the entire first draft, along with two entities the same doc required.

### F · Assertion with no verifying artifact
Every subsystem names the test, gate or oracle that proves it. "It works" is not a
verification strategy.

### G · Unverified claim stated as fact
Statutory, pricing and vendor claims are `[CONFIDENCE: HIGH]` only if verified **this
session**. Otherwise say so and open a question. Never guess a number that a reader would
act on.
> A statutory retention period was unverified, so it was recorded as unknown rather than
> filled with a plausible figure.

### H · Simplicity
Against `.agent-spec/coding-standards/SIMPLICITY-FIRST.md`: speculative abstraction,
unasked-for features, complexity with no present justification, cost assumed free.

---

## Applying

Apply fixes yourself — do not hand the user a findings list and stop. Two limits:

1. **A finding that needs a decision the user owns becomes a numbered open question in
   the artifact**, not a silent choice. Say plainly that it is your reading, not theirs.
2. **A finding you cannot verify becomes an open question**, not a guess.

After applying, re-run **class B** over everything you touched. That is where the
self-inflicted defects live.

---

## Reporting

Report once, at the end, in one block:

```
PASS n — <file> · <before> → <after> lines · N findings, all fixed

[BLOCKER] §x.y  what was wrong · why it matters · what it is now
[MINOR]   §x.y  ...
[NIT]     §x.y  ...

Still open: OQ-n (needs your call — this is my reading, not your decision)
```

Rules:
- **Flag defects you introduced as yours.** They are the strongest evidence the loop is
  working, and hiding them removes the reason to keep running it.
- Rank by severity, not by section order.
- If a pass genuinely finds nothing, say so — but treat it as unusual and state what you
  checked against.
- Never report "reviewed and correct" without naming what you checked it against.

---

## Standalone use

`/self-review <file>` runs the same loop against an existing artifact. Same classes, same
bound, same reporting.
