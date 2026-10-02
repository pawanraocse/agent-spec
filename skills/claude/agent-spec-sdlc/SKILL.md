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

## Which gates to run

Not every change needs all nine. Map the change to one of four tracks using two signals:
**scope** (how many files/services change) and **algorithm** (how novel is the logic).

| | **Low algorithm** (CRUD, config, message edit) | **High algorithm** (novel data structure, state machine, crypto, schema migration) |
|---|---|---|
| **Narrow scope** (1–3 files, one service) | **Fast-track** → gates 5–8 | **Algorithm track** → gate 1, then 5–8 |
| **Wide scope** (cross-service, schema, new API) | **Design track** → gates 0–4, then 5–8 | **Full pipeline** → all 9 gates |

**Fast-track** — CSS fix, config value, error message, one-line rename:
Say "fast-track mode, gates 0–4 skipped" and go directly to `/agent-spec-implement`.
Do not record gates you did not run.

**Algorithm track** — complex function rewrite, non-trivial state machine, but confined
to one file or one service:
Run gate 1 only (`/agent-spec-tech-spec`, to surface NFR conflicts early). Skip gates 2–4.
Run gates 5–8. If `02-TECH-SPEC.md` sets `Algorithm: high`, the task qualifies for the
Complexity Override in `/agent-spec-raw-code-full` — say so before coding starts.

**Design track** — new endpoint, new DB table, cross-service change with no
algorithmic novelty:
Gates 0–4 for design artifacts, then gates 5–8.

**Full pipeline** — scope is wide *and* the algorithm is novel:
All 9 gates. Do not abbreviate.

If `02-TECH-SPEC.md` has a `## Complexity` section, read it — that is the evidence-based
input for this decision. If not, state your assumption out loud and proceed.

## The pipeline

Pre-pipeline: `/agent-spec-intent` → `00-INTENT.md` (for handoffs; not a gate).

Gates 0–8: `requirements` → `tech-spec` → `prd` → `hld` → `lld` → `implement` → `review` → `testing` → `validation`. Artifacts: `01-REQUIREMENTS.md` through `08-VALIDATION.md`, all in `.agent-spec/sdlc/`.

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
