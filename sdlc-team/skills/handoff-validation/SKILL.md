---
name: handoff-validation
description: "The non-negotiable gate between SDLC stages. Reconcile your output against the previous stage's artifact, classify every upstream item as COVERED/PARTIAL/MISSING/CONTRADICTS/OUT-OF-SCOPE, and report anything that does not reconcile instead of proceeding. Load before handing off any PRD, HLD, LLD, implementation, review, test plan, QA sign-off, or deployment plan."
---

# Handoff Validation

Every stage in this pipeline consumes the previous stage's artifact. A stage that
silently drops a requirement is worse than one that fails loudly: the loss is not
discovered until QA, or production.

**The rule: you may not hand off until you have reconciled your output against your
input, item by item, and reported the result.** Reporting a gap is success. Hiding
one is failure.

## When this applies

| You are | Reconcile against |
|---------|-------------------|
| `prd-writer` | The user's feature request (and `CLAUDE.md` constraints) |
| `hld-architect` | `01-prd.md` |
| `lld-designer` | `02-hld.md` (and the PRD for acceptance criteria) |
| `developer` | `03-lld.md` |
| `code-reviewer` | `03-lld.md` + the actual diff |
| `tester` | `01-prd.md` acceptance criteria |
| `qa-validator` | `01-prd.md` acceptance criteria + NFRs |
| `deployment-engineer` | `02-hld.md` NFRs + `07-qa-signoff.md` |

## Procedure

### 1. Load the upstream artifact — actually read it

Do not work from the orchestrator's summary of it. Read the file. If it is missing
or empty, stop and report `BLOCKED — upstream artifact not found`; do not invent
what it probably said.

### 2. Enumerate upstream items

Extract every atomic, checkable item. Use the upstream document's own IDs where it
has them (`AC-3`, `NFR-2`, `C-4`). If it has none, assign your own and say so — this
is a finding in itself, because unnumbered requirements cannot be tracked.

An item is *atomic* when it can be independently satisfied or missed. "Users can
reset their password by email within 5 minutes" is two items: the mechanism and the
latency budget.

### 3. Classify each item

| Status | Meaning |
|--------|---------|
| `COVERED` | Fully addressed. Cite the section, file, or test that addresses it. |
| `PARTIAL` | Addressed for the main path only. State precisely what is not covered. |
| `MISSING` | Not addressed at all. |
| `CONTRADICTS` | Your output conflicts with the upstream artifact. State both positions. |
| `OUT-OF-SCOPE` | Deliberately deferred. Requires a one-line reason. |

Also flag the reverse direction:

| Status | Meaning |
|--------|---------|
| `ADDED` | Present in your output but traceable to **no** upstream item — scope creep. Justify or cut it. |

`ADDED` matters as much as `MISSING`. Unrequested work is how a two-day feature
becomes a two-week one, and it arrives disguised as helpfulness.

### 4. Emit the report

Append this block to your artifact verbatim. The orchestrator and the human both
read it; it is not decorative.

```markdown
## Handoff Validation

**Upstream:** `docs/sdlc/<slug>/01-prd.md` (12 items)
**This artifact:** `docs/sdlc/<slug>/02-hld.md`

| ID | Upstream item | Status | Where addressed / why not |
|----|---------------|--------|---------------------------|
| AC-1 | Reset link expires in 15 min | COVERED | §4.2 token TTL |
| AC-2 | Rate-limited to 3/hour/account | PARTIAL | §4.5 limits per IP, not per account |
| NFR-1 | p95 < 200ms | MISSING | — |
| C-2 | Must reuse existing mailer | CONTRADICTS | HLD §5 introduces a second provider |
| — | Admin audit dashboard | ADDED | Not traceable to any PRD item |

**Tally:** 8 COVERED · 1 PARTIAL · 1 MISSING · 1 CONTRADICTS · 1 ADDED
**Verdict:** BLOCKED
**Blocking items:** NFR-1 (no latency design), C-2 (mailer conflict)
**Needed to unblock:** confirm whether the second provider is sanctioned; specify a
latency budget for the token lookup path.
```

### 5. Apply the verdict

| Condition | Verdict | What you do |
|-----------|---------|-------------|
| No `MISSING`, no `CONTRADICTS` | `CLEAR` | Hand off. |
| Only `PARTIAL` / `OUT-OF-SCOPE` with reasons | `CLEAR WITH NOTES` | Hand off; carry notes forward. |
| Any `MISSING` or `CONTRADICTS` | `BLOCKED` | **Stop. Report. Do not proceed to the next stage.** |

`BLOCKED` is a report to the human, not a failure state to work around. Return your
partial artifact along with the block — the work is not wasted, it is paused.

## What this is not

Do not resolve a `CONTRADICTS` by quietly changing the upstream artifact to match
your output. If the PRD is wrong, say the PRD is wrong and let the human decide.
Editing the spec to match the implementation destroys the audit trail that makes
this pipeline worth running.

Do not mark something `COVERED` because you intend to cover it later. Status
describes the artifact as written, right now.

## Anti-patterns

- **Summary-instead-of-table.** "Everything from the PRD is handled" is not a
  reconciliation. The table is the deliverable.
- **Vacuous coverage.** Citing a section that mentions the topic without addressing
  the requirement. "§4 discusses rate limiting" ≠ the limit is specified.
- **Silent renumbering.** Changing upstream IDs breaks traceability across stages.
- **Gap-free reports.** A clean table on a non-trivial feature usually means the
  items were written to match the output rather than extracted from the input.
