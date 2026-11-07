# Platform Design Archive (Imported from Agent Hub)

> **Purpose:** Historical record and reference architecture for Phase 2 platform capabilities in `algosec-agent-spec`.
> All architectural designs, data flows, workflows, and decisions from `algosec-agent-hub` have been consolidated here.

---

## Document Index

| Document | Description |
| :--- | :--- |
| **[HLD-AGENT-HUB.md](./HLD-AGENT-HUB.md)** | Full High-Level Design: Component diagrams, sequence diagrams, step types (`run:`, `mcp:`, `ai: true`), and contracts. |
| **[AGENT-HUB-PLAN.md](./AGENT-HUB-PLAN.md)** | Architecture Plan: Product definition, orchestration rationale, and integration boundaries. |
| **[adr/ADR-001-cursor-cli-orchestrator.md](./adr/ADR-001-cursor-cli-orchestrator.md)** | Architectural Decision Record: Using Cursor CLI (`hub-runner`) for headless orchestration. |
| **[workflows/RCA-INTELLIGENCE-LOOP.md](./workflows/RCA-INTELLIGENCE-LOOP.md)** | RCA agent target workflow: Jira ticket → pre-check → investigation → blast-radius → resolution. |
| **[workflows/PR-INTELLIGENCE-LOOP.md](./workflows/PR-INTELLIGENCE-LOOP.md)** | PR review agent target workflow: PR trigger → code diff → graph analysis → review comment. |
| **[reference/ADAPTIVE-LEARNING.md](./reference/ADAPTIVE-LEARNING.md)** | The Experience Flywheel: SHA256 error-signature matching, candidate lifecycle, and retrieval. |
| **[reference/ADMIN-UI.md](./reference/ADMIN-UI.md)** | Admin dashboard & Langfuse telemetry specification. |
| **[reference/MULTI-REPO-INDEX.md](./reference/MULTI-REPO-INDEX.md)** | Cross-repo blast-radius analysis and multi-workspace indexing. |
| **[future/AGENTCORE-HOSTING.md](./future/AGENTCORE-HOSTING.md)** | Future AWS AgentCore hosting specs (Lambda, MCP Gateway, Cedar auth). |

---

## Planning (canonical — not this folder)

| Document | Role |
|----------|------|
| **[MASTER-PLAN.md](../MASTER-PLAN.md)** | Strategy, phases, locked decisions |
| **[todo-plan.md](../../todo-plan.md)** | Sole sequenced task backlog |

