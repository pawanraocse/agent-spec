---
name: "agent-spec-sdlc"
description: >-
  Run a feature through the nine SDLC gates. Reads pipeline state, runs the one gate that is due, refuses to skip.
---

# sdlc

The gates were always there. What was missing was anything holding the order, so it
lived in whichever context window happened to be open. This reads the state from disk
instead.

## Where are we

```bash
./.agent-spec/bin/agent-spec-gate.py status
```

Starting something new:

```bash
./.agent-spec/bin/agent-spec-gate.py reset --feature "<short-name>"
```

## The pipeline

| Gate | Name | Skill | Produces |
|---|---|---|---|
| 0 | REQUIREMENTS | `/agent-spec-requirements` | `01-REQUIREMENTS.md` |
| 1 | TECH-SPEC | `/agent-spec-tech-spec` | `02-TECH-SPEC.md` |
| 2 | PRD | `/agent-spec-prd` | `03-PRD.md` |
| 3 | HLD | `/agent-spec-hld` | `04-HLD.md` |
| 4 | LLD | `/agent-spec-lld` | `05-LLD.md` |
| 5 | DEVELOPMENT | `/agent-spec-implement` | code + tests |
| 6 | REVIEW | `/agent-spec-review` | `06-REVIEW.md` |
| 7 | TESTING | `/agent-spec-testing` | `07-TEST-REPORT.md` |
| 8 | VALIDATION | `/agent-spec-validation` | `08-VALIDATION.md` |

All artifacts live in `.agent-spec/sdlc/`.

## How to run one gate

1. `status` — read the gate number.
2. `check <gate>` — exits 1 with the missing artifact named. **If it blocks, stop and say
   which gate has to run first.** Never write the upstream document yourself to unblock
   the current one: a design built on an invented predecessor looks approved and is not.
3. Invoke that gate's skill and let it do its own work. This skill routes; it does not
   write PRDs.
4. When the gate's artifact exists and its self-review has run:
   `./.agent-spec/bin/agent-spec-gate.py set <gate>`
5. **Report the gate as done, name the next command, and stop.**

## The one rule that matters

**One gate per invocation.** Do not chain. Every gate is a separate human approval, and
chaining two on one "yes" is how a requirement gets dropped with nobody noticing — which
is precisely what gate 8 exists to catch, after the cost has already been paid.

Exception, stated out loud when you use it: a change too small for a design pass. Say
"small-change mode, gates 0–4 skipped", go straight to `/agent-spec-implement`, and do not record a
gate you did not run.

## Requirement traceability

```bash
./.agent-spec/bin/agent-spec-gate.py trace
```

Every `REQ-`, `NFR-` or `US-` identifier from gate 0, and which downstream artifacts
mention it. A row of dots is a requirement that was silently dropped. Exits 1 when any
requirement reaches nothing — that is a pipeline failure, not a warning.

For this to work, gate 0 has to assign identifiers and every downstream gate has to
quote them. If `trace` says there are no identifiers, fix gate 0 before going further.

## Hard stops

- Never mark a gate passed whose artifact does not exist on disk.
- Never mark gate 7 passed over a failing test, or gate 8 over an unmapped requirement.
- Never edit `STATE.json` by hand. Use `set`; hand-editing is how the state starts
  lying, and everything downstream believes it.
