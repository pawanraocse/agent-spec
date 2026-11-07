# ADR-001: Cursor CLI as Orchestrator (supersedes §13 Python-framework-orchestrates)

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-09-14 |
| **Supersedes** | AGENT-HUB-PLAN.md §13 "Python framework orchestrates" |
| **Deciders** | Platform team |

---

## Context

AGENT-HUB-PLAN.md §13 locked **Python framework as the orchestrator** with `framework/orchestrator.py`
running the workflow graph and calling Bedrock for AI reasoning steps.

During Phase 1 design, three new facts emerged that were not available when §13 was written:

1. **Cursor CLI ships headless agent execution.** `cursor agent "..."` runs from any terminal,
   GitHub Actions, or Jenkins — without the Cursor GUI open. The headless-CI blocker no longer exists.

2. **Cursor's agent loop outperforms single boto3 calls.** Cursor's Claude iterates: reads files,
   runs tools, adjusts reasoning mid-run. A single `invoke_model` call cannot do this. Real-world
   evidence from the AI Log Analyzer team confirms Cursor-based skills produce better RCA results
   than equivalent boto3 prompts.

3. **Python runner for `ai: true` steps requires Bedrock anyway.** Any Python orchestrator that
   needs to run AI reasoning must call Bedrock via boto3. This reintroduces AWS key setup,
   prompt engineering overhead, and inferior single-call reasoning in Phase 1 and 2 — the exact
   phases where Cursor CLI is available and superior.

---

## Decision

Replace `framework/orchestrator.py` with **`hub-runner.md`** (a Cursor CLI skill) as the runtime
orchestrator for Phase 1 and Phase 2.

```
Triggers
  └─► cursor agent "rca --jira ASMS-123"   (P1/P2)
        └─► hub-runner.md reads workflow.yaml
              ├─► scripts/*.py  (data steps — deterministic Python)
              └─► Cursor Claude (ai:true steps — iterative reasoning)
```

Python retains ownership of:
- `framework/contracts.py` — schema enforcement (Pydantic)
- `framework/experience.py` — experience store read/write
- `framework/observability.py` — Langfuse wrapper
- `scripts/*.py` — all deterministic tools (fetch, validate, store, emit)

Python does NOT own:
- The workflow execution loop (hub-runner.md owns this)
- AI reasoning (Cursor Claude owns this in P1/P2; Bedrock in P3 Lambda)

---

## Consequences

### Positive
- No Bedrock setup in P1/P2 — Cursor's Claude is the model
- Better reasoning quality — iterative agent loop vs single prompt call
- Cursor CLI is headless — Jenkins and GitHub Actions can trigger it
- Less Python code — `framework/orchestrator.py` (~100 lines) removed from P1 scope
- YAML workflows are still fully enforced — hub-runner.md reads them

### Negative / Mitigations
- **"Hope model follows rules" risk** — mitigated by strict hub-runner.md instructions,
  calling validate.py after `ai: true` and `validate` steps only (AgentResult enforcement),
  and golden eval tests that catch deviations
- **P3 swap required** — AgentCore Lambda cannot run Cursor CLI. The `ai: true` step
  must swap to `boto3.invoke_model`. All scripts and contracts are unchanged. This is
  a single-function swap, not a rewrite.
- **Reproducibility** — Cursor agent runs are not byte-identical. Mitigated by enforced
  Pydantic contracts on every output; the structure is deterministic even if prose varies.

### What does NOT change
- `workflow.yaml` format — identical in P1 and P3
- `scripts/*.py` — identical in P1 and P3
- `framework/contracts.py`, `experience.py`, `observability.py` — identical in P1 and P3
- Agent contribution model — teams write workflow.yaml + scripts, never the runner

---

## Alternatives considered

| Alternative | Rejected because |
|---|---|
| Python orchestrator + Bedrock in P1 | Reintroduces boto3 complexity; single-call reasoning is inferior |
| Pure Cursor chat skill (no YAML) | No enforcement; no self-service; BugBot's pattern |
| LangGraph | Adds framework dependency; solves problems we don't have in P1 |

---

## References
- AGENT-HUB-PLAN.md §13 (superseded)
- HLD.md §4 (hub-runner.md specification)
- cursor.com/cli (headless agent execution)
