---
name: "agent-spec-validation"
description: >-
  SDLC gate 8: acceptance against the original requirements, one verdict per requirement, into 08-VALIDATION.md. Needs 07-TEST-REPORT.md.
---

# validation

The last gate, and the only one that looks all the way back to gate 0. Every other gate
checks its own document against the one before it, which is exactly how a requirement
disappears: each handoff is locally consistent and the chain still drops something.

## Gate

```bash
./.agent-spec/bin/agent-spec-gate.py check 8
```

`BLOCKED` → stop and say which gate has to run first.

## Do

1. Run the mechanical trace first — it is free and it is not fooled by prose:

   ```bash
   ./.agent-spec/bin/agent-spec-gate.py trace
   ```

   Any requirement with no downstream mention is dropped. That is a **FAIL** for that
   requirement before you read a line of anything.

2. Read `01-REQUIREMENTS.md` and `03-PRD.md`. Take every requirement, acceptance
   criterion and user story.

3. For each one, give exactly one verdict, and cite the evidence:

   | Verdict | Means | Evidence required |
   |---|---|---|
   | **PASS** | implemented and a test proves it | test name from `07-TEST-REPORT.md` |
   | **FAIL** | implemented wrongly, or not at all | what is wrong, with `file:line` |
   | **NOT-TESTED** | implemented, nothing proves it | where the code is, why no test |
   | **DEFERRED** | consciously out of scope | who decided, and where that is recorded |

   **There is no fifth verdict, and no partial credit.** "Mostly working" is FAIL.
   A requirement you cannot find evidence for is NOT-TESTED, never PASS.

4. Check the non-functional requirements the same way. An NFR with no measurement is
   NOT-TESTED — the number was never taken, so nobody knows.

5. Verify the delivered system against the design, not only against the tests: does
   `04-HLD.md`'s service boundary match what
   `./.agent-spec/bin/graphify-cli.py services` reports? A design that says three
   services over a system that ships two is a finding.

## Write `.agent-spec/sdlc/08-VALIDATION.md`

```markdown
# Validation — <feature> — <date>

## Verdict
<SHIP | DO NOT SHIP>, and the one-line reason.

## Traceability
| Requirement | Verdict | Evidence |
|---|---|---|
| REQ-001 | PASS | test_login_rejects_expired_token |
| REQ-002 | FAIL | never implemented; no reference after 01-REQUIREMENTS.md |

## Design conformance
<HLD/LLD versus what was actually built, including the service map>

## Open risks
<what ships unproven, and what it would cost if it is wrong>
```

## Hard stops

- **Never write SHIP while any requirement is FAIL.** One FAIL is DO NOT SHIP; the user
  may overrule that, and their overrule goes in the document, under their name.
- Never mark a requirement PASS on the strength of reading the code. A test proves it or
  it is NOT-TESTED.
- Never quietly reclassify a dropped requirement as DEFERRED. Deferred means someone
  decided; dropped means nobody noticed. Conflating them destroys the only signal this
  gate produces.
- This gate writes no code. If it finds a defect, it reports it and the pipeline returns
  to gate 5.

## Close

```bash
./.agent-spec/bin/agent-spec-gate.py set 8
```

Then `/agent-spec-snapshot`. The pipeline is complete; the record of what shipped unproven is the
thing worth keeping.
