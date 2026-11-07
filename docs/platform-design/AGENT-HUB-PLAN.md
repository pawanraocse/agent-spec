# Agent Hub — Architecture Plan

> Status: **LOCKED** — ratified 2026-09-11 (supersedes 2026-09-09 APPROVED DIRECTION)
> Source of truth for architecture, build order, and integration boundaries.
> Epic alignment: **DEVOPS-11338** (AgentCore AI Tools Platform)
> Related Confluence:
> - [DEVOPS-11338 AI Tools Platform Self-Service Architecture](https://algo-confluence.algosec.com/display/DEVOPS/DEVOPS-11338+AI+Tools+Platform+Self-Service+Architecture)
> - [How to build MCP tools and agents](https://algo-confluence.algosec.com/display/DEVOPS/How+to+build+MCP+tools+and+agents)

---

## 0. Executive summary (locked)

| Question | Locked answer |
|----------|---------------|
| What is the product? | **Python orchestration framework** — RCA/PR/triage are agents on it, not the product |
| Skills vs Python? | **Hybrid C** — Python orchestrates; `SKILL.md` optional for sub-agent prompts only (§13) |
| vs 666_BugBot? | **Compose, don't compete** — BugBot = legacy point tool; Hub = agent factory + flywheel + validation |
| Solo dev path? | Cursor → thin launcher → `framework run …` locally (P1) — same orchestrator code as company deploy |
| Company-wide path? | Port framework to AgentCore Lambda; every Cursor → shared MCP Gateway (`cursor` audience) (P3) |
| Build order? | **P1** framework + Langfuse + acceptance `pytest` → **P2** RCA then PR agents → **P3** AgentCore |
| Phase gates | No real agents until P1 acceptance passes; no AgentCore until P2 agents proven locally |
| Hackathon target? | P1 framework demo (mock workflow + Langfuse + experience flywheel) — not AgentCore deploy |

**Still open (not architecture):** two real demo repos for index acceptance (§10); Langfuse `docker-compose` in repo.

---

## 1. What Agent Hub is

**Agent Hub** is Algosec's **governed agentic AI framework** — a Python orchestration platform for **more accurate, efficient, and measurable** agentic work. It provides orchestration, memory, adaptive learning, observability, and contracts. **RCA is one use case**, not the product. PR review, digest, triage, and future workflows are additional agents on the same framework.

**Algosec-Hermes:** Hermes-shaped at the pattern level (gateway, memory, MCP, schedule) but **enterprise-grade** — shared, governed, measurable. The moat is **framework + multi-agent orchestration + learning flywheel**, not better prompts or another Cursor skill.

### What we are NOT building

| Not this | Why |
|----------|-----|
| A third RCA stack | **ailoganalyzer** already parses logs (Stage 2 / 2.5). **666_BugBot** already triages JIRA in Cursor. We **compose** them via adapters — see §14. |
| A skills-only product | Competes with BugBot on the wrong axis; cannot do headless triggers, enforced contracts, or Langfuse spans per sub-agent. |
| A PR-review skill race | Commoditized; BugBot and others already ship review flows. |

| Layer | Location | Role |
|-------|----------|------|
| **Framework** | `algosec-agent-hub/framework/` | Orchestrator, experience, index, observability, contracts — **build first** |
| **Agents** | `algosec-agent-hub/agents/<name>/` | Thin workflow definitions plugged into framework API — **after framework is stable** |
| Deployed runtime | `agentcore-agents/<agent>/` | Company-wide Lambda (Phase 3) |
| MCP tools | `agentcore-mcp-tools/` + Gateway | Shared Bitbucket, Jira, Confluence, … |
| Platform rails | `agentcore-mcp-gateway` (DevOps) | Gateway, Cedar, Entra, SSM contract, SDK |
| IDE client | Cursor (and OpenWebUI, Teams, bots) | **Dev trigger** in Phase 1; MCP → Gateway in Phase 3 |

**agent-spec** is a **separate repository** (per-repo governance kit). Do not conflate with Agent Hub.

### Framework vs agents (build order)

| Layer | What | When |
|-------|------|------|
| **Framework** | Orchestrator kernel + Langfuse + experience + index + token saving + contracts | **Phase 1** — the product |
| **Agents** | RCA, PR review, … — workflow YAML + sub-agent handlers | **Phase 2** — only after framework acceptance passes |
| **AgentCore deploy** | Port framework + agents to company platform | **Phase 3** |

The framework must make it **trivial** to:
- Register a new top-level agent (workflow definition)
- Register sub-agents within an agent
- Orchestrate **parallel** and **sequential** sub-agent runs
- Merge `AgentResult` envelopes
- Read/write experience store and query index
- Emit Langfuse spans per run and per sub-agent

Agents are thin workflow definitions (step graph, sub-agent handlers, golden evals) — not separate runtimes. See **§13** for the locked split: **Python framework orchestrates**; skills are optional **authoring format** for sub-agent instructions, not the runtime.

**Build sequence:** framework (+ Langfuse) → framework acceptance test → first agent (RCA) → more agents → AgentCore deploy.

### Framework capabilities (Phase 1 deliverables)

| Capability | Module | Role |
|------------|--------|------|
| **Orchestrator** | `framework/orchestrator/` | Workflow runner: sequential + parallel steps, sub-agent fan-out, `AgentResult` merge |
| **Agent registry** | `framework/orchestrator/registry.py` | Register top-level agents + sub-agents; load `workflow.yaml` |
| **Adaptive learning** | `framework/experience/` | Store, retrieve by `trigger_signals`, repo namespace — see `reference/ADAPTIVE-LEARNING.md` |
| **Token saving** | `framework/context/` | Context budget, digest, lazy index load, experience pre-load, chunked tool calls |
| **Index create & reuse** | `framework/index/` | Graphify build, multi-repo manifest, blast radius / co-change — see §10 |
| **Langfuse** | `framework/observability/` | Trace per run, span per sub-agent, token/latency metrics — see `reference/ADMIN-UI.md` |
| **Graphify memory** | `framework/index/` | Structural memory: imports, blast radius, module map, cross-repo edges |
| **Trigger adapters** | `framework/triggers/` | Pluggable interface (CI, Jira, Zendesk, …) — agents supply implementations in Phase 2 |
| **Contracts** | `contracts/` | `AgentResult`, `repo_context`, `experience-candidate`, `workflow-definition` schemas |

### Framework public API (target)

```python
# Register agent workflow (Phase 2 — after framework stable)
framework.register_agent("rca", workflow_path="algosec-agent-hub/agents/rca-investigation/workflow.yaml")

# Register sub-agent handler
framework.register_sub_agent("logs", handler=logs_agent.run)

# Run — framework handles orchestration, Langfuse, experience, merge
result = framework.run("rca", trigger=payload)

# Within an agent — fan out sub-agents
results = framework.dispatch_parallel(["logs", "repo"], context=ctx)
merged = framework.merge_agent_results(results)
```

**Phase 1 runtime:** Python framework in this repo. **Cursor Agent mode** invokes framework code (`framework/orchestrator/cli.py`) — Cursor is the **dev trigger**, not the orchestrator.

### Relationship to agent-spec

- No runtime dependency on the agent-spec repo.
- If a pattern from agent-spec is useful (gates, snapshot, graph query), **copy and adapt** into this repo.
- Document copies in `reference/PROJECT-BOUNDARIES.md`.
- Legacy folder name `.agent-spec/` in this repo is local content only — not a live link to the other project.

---

## 2. Hosting model (answers “common platform vs Cursor-only”)

### Phase 1 (local framework)

- Framework runs locally in `algosec-agent-hub`.
- Cursor Agent mode triggers framework CLI — not the orchestrator itself.
- MCP: local Atlassian MCP + `graphify-cli.py` for dev velocity.
- Langfuse: self-hosted Docker on internal network.

### Company-shared (AWS AgentCore) — Phase 3

- One MCP Gateway per environment (dev / stage / prod) — **already live**.
- Agents deployed once; all teams invoke the same Lambdas (`bot` M2M or scheduled).
- Tools registered once; Cedar controls visibility per audience.

### Per product repository (not centralized)

- Graphify index + `PROJECT-INDEX.md` + `CONSTITUTION.md` for **that codebase**.
- Run via CI on merge — not manually per developer.

### Per developer session (Cursor)

- `SESSION-SNAPSHOT.md` for IDE continuity.
- Phase 1: Cursor triggers local framework.
- Phase 3: MCP client → **shared Gateway** (`cursor` audience).
- Cursor is **not** the platform runtime.

---

## 3. Execution flow

> **Superseded diagrams below** describe the original Python-orchestrator design.
> **Current P1/P2 path:** `cursor agent` → `hub-runner.md` → `workflow.yaml` + `scripts/`.
> See §13, `adr/ADR-001-cursor-cli-orchestrator.md`, and `.agent-spec/sdlc/HLD.md`.

### Phase 3 target (AgentCore)

```
Cursor / Teams / OpenWebUI / service bot
        │
        ▼
  Shared MCP Gateway (Entra JWT or M2M)
        │
        ▼
  Cedar policy (default-deny, audience from tool.config.yaml)
        │
        ├──► MCP tool Lambdas (agentcore-mcp-tools)
        │
        └──► Agent Lambdas (agentcore-agents)
                 orchestrator: Lambda + Code Interpreter + Gateway MCP
                 harness: managed AgentCore Harness (model-driven)
```

### Phase 1 (local) — current (ADR-001)

```
cursor agent "mock --trigger {...}"   (dev trigger / headless CI)
        │
        ▼
  hub-runner.md  (Cursor skill — workflow loop)
        │
        ├──► agents/{name}/workflow.yaml
        ├──► scripts/*.py              (validate, store, load, emit)
        ├──► framework/                (contracts, experience, observability)
        └──► Cursor Claude             (ai: true steps only)
```

**Golden paths (Phase 2 agents):**
1. `RCA Intelligence Loop` — investigation orchestrator + Logs / Repo / Reasoning / Validation sub-agents.
2. `PR Intelligence Loop` — review orchestrator + Diff / Review / Validation sub-agents.

See §12 for reference architectures.

---

## 4. Runtime stack (phased)

> **ADR-001 update:** P1/P2 orchestrator = `hub-runner.md` (Cursor CLI), not `framework/orchestrator/`.

| Phase | What | Orchestrator | Goal |
|-------|------|--------------|------|
| **Phase 1** | Framework utilities + Langfuse + mock workflow | `hub-runner.md` (Cursor CLI) | Mock workflow proves parallel/sequential + flywheel + Langfuse |
| **Phase 2** | Real agents | Same hub-runner + workflow.yaml | RCA → PR review → more; plug into agent-registry |
| **Phase 3** | AgentCore deploy | `agentcore-agents` Lambda | Port proven workflow.yaml + scripts; Bedrock for `ai: true` |

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Reasoning model** | **Claude 3.7 / 3.5 Sonnet on AWS Bedrock** | Frontier reasoning. Bedrock API only — Claude Code CLI is **not** approved. |
| **Fallback model** | Bedrock Llama 3.3 70B or Azure GPT-4o | Cost-sensitive tasks (log parsing, formatting). |
| **Observability** | **Langfuse self-hosted (Docker, MIT)** | Traces, tokens, latency, eval pass rate. Data stays in company network. |
| **Orchestration runtime** | **`hub-runner.md` + workflow.yaml** (P1/P2); Lambda runner (P3) | LangGraph deferred; YAML step graph is the workflow engine |

> **Design principle:** Build a solid framework first. Agents plug in when orchestration is proven. Win on **multi-agent workflows + governed memory**, not commoditized review skills.

Ship path (Phase 3): `framework/` + `agents/<name>/` → `agentcore-agents/agent-template/` → pytest → Jenkins → DevOps deploy.

### Agent shapes (platform contract — Phase 3)

| Shape | Use when | Examples |
|-------|----------|----------|
| **orchestrator** | Deterministic steps, parallel sub-agent dispatch, exit-code gating | `rca-investigation`, `pr-review`, `bugbot` |
| **harness** | Event-driven, conversational reasoning | `digest-agent`, `bugbot_triage` |

---

## 5. Comparison to Hermes Agent ([hermes-ai.net](https://hermes-ai.net/) / Nous Research)

Hermes is a **personal, self-hosted** agent: one gateway process, learning loop, autonomous skill growth, 15+ chat channels, MCP client, cron.

| Capability | Hermes Agent | Agent Hub |
|------------|--------------|-----------|
| Gateway | Single local/self-hosted gateway | Shared AWS MCP Gateway (Phase 3) |
| Orchestration | Personal agent loop | **Framework orchestrator** + sub-agents |
| Memory | Agent-curated memory, FTS5 recall | Graphify structural + experience store + AgentCore Memory (P3) |
| Self-improvement | **Autonomous** skill growth | **Governed** eval → experience store → human-approved skills |
| MCP | Client to any MCP server | Company Gateway tools + Cedar (P3) |
| Best for | Personal agent that learns you | **Company agents** with audit, shared tools, compliance |

**Verdict:** Agent Hub should **not clone Hermes**. It should be Hermes-shaped but **enterprise-grade** — framework-first, governed learning, measurable via Langfuse.

### Competitive landscape: 666_BugBot (BrandFactory)

Reference: [666_BugBot Agent Setup and Invocation](https://algo-confluence.algosec.com/display/ALSaaS/666_BugBot+Agent+Setup+and+Invocation) · repo: `algosec-tools/brandfactory`

| Dimension | 666_BugBot (today) | Agent Hub (full deploy) |
|-----------|-------------------|-------------------------|
| Product | JIRA-ticket RCA in Cursor | **Framework** — RCA, PR, future agents |
| Orchestration | Cursor + `SKILL.md` | Python framework + `workflow.yaml` |
| Triggers | Manual Cursor chat | CI webhook, Jira, Support, Customer (Phase 2+) |
| Log analysis | Ticket text; optional Log Analyzer handoff | **Compose** Log Analyzer output — don't re-parse |
| Learning | `runs/<KEY>/` artifacts, no retrieval | Experience store — run 2 cheaper |
| Accuracy guard | High/Medium/Low confidence; manual paste | **Validation Agent** + enforced `AgentResult` |
| Observability | None standard | Langfuse span per sub-agent |
| Index | `repo_profiles.py` + clone repos | Graphify + `repo_context` at fixVersion/branch |

**Positioning:** BugBot = point tool for JIRA triage in Cursor. Agent Hub = **agent factory** that makes all workflows more accurate, efficient, and measurable. BugBot logic can become an agent **on** the framework (or call through adapters), not a competitor to rebuild.

**Accuracy after full deploy:** Ahead on CI failures, recurring bugs, cross-repo, and validated root causes — **only if** we integrate Log Analyzer (`BugbotHandoffContract`) and ship experience + validation. Not ahead by default on "another triage skill."

---

## 6. Known issues and mitigations

| Issue | Risk | Mitigation |
|-------|------|------------|
| DevOps deploys all envs today | Slow iteration | Phase 1 is local; track DEVOPS-11343 self-deploy to dev |
| Lambda ~29s tool timeout | Long workflows may fail | Chunk work; harness shape; MCP Tasks (future) |
| Two memory models | Confusion (graph vs experience) | graph = code structure; experience = past fixes; Gateway = live ticket/PR |
| Cursor direct MCP vs Gateway | Dev/prod drift | P1 = local MCP ok; P3 prod path = Gateway only |
| Framework not built yet | Agents reinvent orchestration | **Phase 1 gate:** framework acceptance before any real agent |
| No central cross-repo index | Multi-repo PR/RCA blind spots | Central Index — §10 |
| No sub-agent handoff format | Inconsistent outputs | `AgentResult` envelope — §11 |
| Commoditized PR review skills | No differentiation | PR review is **agent workflow on framework**, not a skills race |
| Duplicate Log Analyzer RCA | Wasted effort; worse log accuracy | RCA Logs sub-agent **consumes** Log Analyzer / `BugbotHandoffContract` — §14 |
| BugBot team overlap | Two "RCA" narratives | Position: framework platform; BugBot = legacy skill client until migrated |

---

## 7. Hackathon deliverable (Phase 1 — framework)

1. **Framework running locally** with mock multi-sub-agent workflow (parallel + sequential + merge).
2. **Langfuse live** — span tree per run: orchestrator → sub-agents → merge.
3. **Experience flywheel** — run mock workflow twice; 2nd run retrieves stored experience (tokens↓).
4. **Index module** — graphify query on 2 real demo repos.
5. **Contracts** — all steps validate against `AgentResult` / `repo_context` schemas.
6. **Framework acceptance test** — `pytest` suite proving orchestration API.

**Stretch (Phase 2, not required for hackathon win):** First real agent (RCA Investigation) on stable framework.

**Live demo script (5 minutes):**

| Step | Action | What judges see |
|------|--------|-----------------|
| 1 | Run framework mock workflow from Cursor | Orchestrator starts |
| 2 | Open Langfuse dashboard | Trace: Running → Complete; span per sub-agent |
| 3 | Click into trace | Tokens, duration, sub-agent outputs |
| 4 | Show experience store | Candidate written from run 1 |
| 5 | Re-run same workflow | Run 2: fewer tokens, experience pre-loaded — flywheel visible |
| 6 | Explain Phase 2 | "Adding RCA = register agent + 4 sub-agent handlers" |

---

## 8. Phased rollout

Platform references:
- [How to build MCP tools and agents](https://algo-confluence.algosec.com/display/DEVOPS/How+to+build+MCP+tools+and+agents)
- [DEVOPS-11338 AI Tools Platform Self-Service Architecture](https://algo-confluence.algosec.com/display/DEVOPS/DEVOPS-11338+AI+Tools+Platform+Self-Service+Architecture)

### Phase 1 — Framework (local Python + Langfuse)

**Goal:** Solid orchestration framework with all platform features. **No real agents yet** — mock sub-agents prove the API.

| Path | Module |
|------|--------|
| `framework/orchestrator/` | Workflow runner, registry, parallel/sequential dispatch, `AgentResult` merge |
| `framework/experience/` | Adaptive learning store + retrieval |
| `framework/index/` | Graphify wrapper, multi-repo manifest, blast-radius queries |
| `framework/context/` | Token budget, digest, lazy load |
| `framework/observability/` | Langfuse client — trace + spans |
| `framework/triggers/` | Pluggable trigger adapter interface |
| `contracts/` | `agent-result.yaml`, `repo-context.yaml`, `experience-candidate.yaml`, `workflow-definition.yaml` |
| `eval/golden/framework/` | Framework acceptance scenarios |
| `tests/` | `pytest` — mock workflow proving orchestration |

**Phase 1 acceptance criteria:**
- [ ] Langfuse Docker up; test trace from framework
- [ ] Mock workflow: 3 fake sub-agents, parallel + sequential + merge
- [ ] Experience write on run 1 → retrieve on run 2
- [ ] Index query on 2 demo repos via `framework/index/`
- [ ] Context budget enforced in `framework/context/`
- [ ] All outputs validate against `contracts/`
- [ ] Full acceptance in one `pytest` suite

**Phase 1 actions (order):**

1. Deploy Langfuse via `docker-compose up` on internal server.
2. Write `contracts/` YAML schemas from §11 + `workflow-definition.yaml`.
3. Scaffold `framework/orchestrator/` — registry, runner, merge.
4. Scaffold `framework/observability/` — Langfuse integration.
5. Scaffold `framework/experience/` — store + retrieve.
6. Scaffold `framework/index/` — graphify wrapper.
7. Scaffold `framework/context/` — token budget.
8. Scaffold `framework/triggers/` — adapter interface + mock trigger.
9. Build mock sub-agents + acceptance `pytest` suite.
10. Index 2 real demo repos (see §10 ACTION REQUIRED).

### Phase 2 — Agents (after framework acceptance)

Plug real agents into proven framework API. **RCA first** (differentiated); PR review second (not a skills race).

| Agent | Path | Sub-agents |
|-------|------|------------|
| RCA Investigation | `algosec-agent-hub/agents/rca-investigation/` | Logs, Repo, Reasoning, Validation |
| PR Review | `algosec-agent-hub/agents/pr-review/` | Diff, Review, Validation |
| (future) | `agents/<name>/` | Per workflow |

Each agent provides:
- `workflow.yaml` — step graph (parallel/sequential)
- Sub-agent handler modules
- `eval/golden/<agent>/` — golden scenarios
- Trigger adapter implementation (optional)

**Phase 2 actions:**

1. `algosec-agent-hub/agents/rca-investigation/` — full RCA workflow (see §12).
2. Run RCA on real trigger (CI or Support ticket).
3. Verify Langfuse trace + experience flywheel on 2nd run.
4. `algosec-agent-hub/agents/pr-review/` — same framework pattern.
5. `CONTRIBUTING.md` + `templates/agent/` for other teams.

### Phase 3 — AgentCore deploy

Port framework + agents to company platform. Logic unchanged; transport changes.

| Component | Port target |
|-----------|-------------|
| Framework orchestrator | `agentcore-agents/<orchestrator>/` or shared layer |
| Each agent | `agentcore-agents/<agent>/` |
| Index | `framework/index/` → `agentcore-mcp-tools/graphify-query/` |
| Experience | `framework/experience/` → platform-backed store |
| Observability | Langfuse (same instance) |
| MCP | Local adapters → Gateway SDK (`useGateway=true`, audiences: `cursor`, `bot`) |

**Phase 3 actions:**

1. Port framework to `agentcore-agents` (from `agent-template/`).
2. Port RCA + PR agents.
3. Deploy index + experience as Gateway MCP tools.
4. Deploy to dev; Cursor calls via shared Gateway.

### Capabilities by phase

| Capability | Phase 1 (framework) | Phase 2 (agents) | Phase 3 (AgentCore) |
|------------|---------------------|------------------|---------------------|
| Orchestration | `framework/orchestrator/` | + real agent workflows | Lambda deploy |
| Adaptive learning | `framework/experience/` | RCA/PR write candidates | Platform store |
| Token saving | `framework/context/` | Per-agent budgets | Same |
| Repo index | `framework/index/` | Repo Agent uses index | Gateway MCP |
| Langfuse | `framework/observability/` | Per-agent spans | Same |
| RCA agent | mock only | `algosec-agent-hub/agents/rca-investigation/` | Deployed |
| PR agent | mock only | `algosec-agent-hub/agents/pr-review/` | Deployed |

---

## 9. Decision log

| Decision | Rationale |
|----------|-----------|
| **Framework before agents** | Orchestration API is the moat; agents are thin plugins |
| **Langfuse in Phase 1** | Observability must be live before any agent work |
| **Agents over skills** | Differentiate on multi-agent workflows, not review prompts |
| **RCA before PR review** | RCA is differentiated; PR review skills are commoditized |
| **Cursor triggers framework** | Cursor Agent mode invokes framework CLI — not the orchestrator |
| Host agents on AgentCore (P3) | Company standard; Gateway live |
| Do not build standalone Gateway | Duplicates DEVOPS-11338 |
| **Central Index** | Per-repo indexes alone blind agents to cross-repo blast radius |
| **Cross-agent experience sharing** | Repo namespace, not agent type — shared flywheel |
| **`repo_context` input schema** | PRs and bugs span services and branches |
| Governed self-improvement | Enterprise trust beats unchecked Hermes-style growth |
| **LangGraph deferred** | Revisit after Phase 1 — custom Python orchestrator first |
| **Claude Sonnet on Bedrock** | Approved API; Claude Code CLI not approved |
| **Fine-tuning deferred (Phase 4+)** | Experience + RAG + eval first; fine-tune only after eval plateau |
| **Python framework orchestrates** | Skills-as-orchestrator cannot enforce contracts, Langfuse spans, headless triggers, or AgentCore port — see §13 |
| **Hub is the complete ecosystem** | Hub writes its own skills and agents. External systems (e.g., Log Analyzer) are called as direct API/logic — no handoff contracts, no skill wrappers. BugBot is a reference point, not an integration target. |
| **RCA is a use case, not the product** | Framework is the product; accuracy/efficiency apply to all agents |
| **Solo → company same orchestrator** | P1 local CLI and P3 Gateway MCP invoke the same workflow logic — only transport changes |
| **Plan ratified 2026-09-11** | Skills-vs-Python, BugBot positioning, phased MCP path confirmed in review session |

---

## 10. Central Multi-Repo Index

> See full design: `reference/MULTI-REPO-INDEX.md`

### Problem

Per-repo Graphify indexes live in each product repo's `.agent-spec/graph/`. When a PR or bug spans multiple repos, a single-repo index is blind to cross-repo blast radius.

### Solution: Index Aggregator Service

```
Each product repo CI job
  └─ graphify-build.py  →  knowledge-graph.json
                              │
                              ▼
                     [Index Aggregator MCP tool]   ← Phase 3 Gateway tool
                       (merges, deduplicates, stores)
                              │
                        S3 prefix: agentcore-indexes/<org>/<repo>/<sha>/
                              │
                     [graphify-query MCP tool]     ← agents call this
                        query: blast_radius(file, repos=[A,B])
```

**Phase 1:** `framework/index/` wraps local `graphify-cli.py` + multi-repo manifest on disk.

### Research: PostgreSQL as Graph Memory Store (open — not locked)

Local JSON files are the Phase 1 default (zero infra). PostgreSQL is worth exploring as the index and experience backend once the framework is proven.

| Option | What it gives | When to consider |
|--------|--------------|-----------------|
| **JSON files** (Phase 1 default) | Zero infra, instant start | Phase 1 — always |
| **PostgreSQL + JSONB** | Queryable structured store, SQL joins across experience + index | Phase 2 — when JSON files feel limiting |
| **PostgreSQL + `pgvector`** | Semantic similarity search on experience candidates (embed trigger signals) | Phase 2/3 — when keyword matching is not enough |
| **Apache AGE (graph extension)** | Native graph traversal for blast-radius queries (nodes = files, edges = imports) | Phase 3 research — if Graphify JSON queries become a bottleneck |

**Decision deferred.** Phase 1 uses files. Re-evaluate after the experience store has real data and query patterns are understood.

### Multi-repo + Branch Navigation

```yaml
repo_context:
  - repo: algosec/api-gateway
    branch: feature/JIRA-1234-auth-refactor
  - repo: algosec/auth-service
    branch: main
  - repo: algosec/common-lib
    branch: main
```

> **Resolved:** Demo repos will be **created and built within this project scope** — synthetic cross-service repos (`hub-demo-service-a`, `hub-demo-service-b`) with real import dependencies. No external Bitbucket dependency required for Phase 1 acceptance.

The orchestrator resolves `repo_context` **before** sub-agents are spawned:
1. Fetch PR/branch metadata per repo.
2. Call index module for cross-repo blast radius.
3. Pass resolved context + blast-radius summary to sub-agents.

### Central Index MCP Tool (Phase 3 target schema)

| Tool | Input | Output |
|------|-------|--------|
| `index.query_blast_radius` | `file`, `repos[]`, `branch?` | Files that depend on `file` across repos |
| `index.query_co_change` | `file`, `repos[]`, `since?` | Files frequently changed together |
| `index.list_repos` | — | Repos with indexed graph + last SHA |
| `index.get_module_map` | `repo`, `branch?` | Module → file map |

---

## 11. Sub-Agent Contract: `AgentResult` + `repo_context`

### `repo_context` Input (every sub-agent)

```yaml
repo_context:
  - repo: string
    branch: string
    pr_id: string?
    relevant_files: []
```

### `AgentResult` Output Envelope (every sub-agent)

```yaml
agent: string
task_id: string
status: success | partial | failed
confidence: HIGH | MEDIUM | LOW | UNKNOWN
repos_inspected:
  - repo: string
    branch: string
    files_read: []
summary: string
blockers: []
suggestions: []
experience_candidates:
  - trigger_signals: string[]
    resolution: string
    source_run_id: string
    confidence: HIGH | MEDIUM
    repo: string
citations:
  - file: string
    line: int
    repo: string
    branch: string
tokens_used: int
duration_seconds: float
```

### Orchestrator responsibility

1. Build `repo_context` from trigger input.
2. Retrieve experiences matching `trigger_signals` (adaptive pre-load).
3. Fan out to sub-agents (parallel or sequential per `workflow.yaml`).
4. Merge `AgentResult` envelopes: deduplicate blockers, aggregate citations.
5. Write `experience_candidates` to experience store.
6. Emit Langfuse trace with span per sub-agent.
7. Route tailored output per channel (CI / Support / Customer).

### Cross-Agent Experience Sharing (flywheel)

Experience is scoped by **repo namespace**, not agent type. Any agent working in that repo benefits from what any other agent learned there.

```
RCA run  → experience_candidates → experience store (repo + signal)
PR run   → retrieve from same namespace → pre-loaded context
Run 2    → tokens↓, time↓, higher confidence
```

---

## 12. Reference agent architectures (Phase 2)

These are **target designs** — implemented after framework acceptance (Phase 2), not Phase 1.

### RCA Investigation (first real agent)

```
[ Triggers ]
CI Webhook (Jenkins/Bitbucket) │ Support Ticket (Zendesk/Jira) │ Customer Issue (Salesforce/Slack)
                                      │
                                      ▼
                        Investigation Orchestrator
                       (Normalizes error & environment)
                                      │
               ┌──────────────────────┴──────────────────────┐
               ▼                                             ▼
          Logs Agent                                    Repo Agent
  (Jenkins artifacts / Customer                     (Central Index: matches
   log bundle / CloudWatch / Splunk)                 code to customer version/branch)
               └──────────────────────┬──────────────────────┘
                                      ▼
                            Reasoning Agent
                 (Correlates trace + code + past fixes)
                                      │
                                      ▼
                            Validation Agent
                (Verifies fix applicability & regression risk)
                                      │
               ┌──────────────────────┴──────────────────────┐
               ▼                                             ▼
       Tailored Output                              Experience Store
 - CI: PR blocker / Bitbucket comment           - Saves error signature + fix
 - Support: Internal draft reply + Jira         - Shared across all services
 - Customer: Root cause summary & patch advisory
```

| Sub-agent | Role |
|-----------|------|
| Investigation Orchestrator | Normalize trigger; build `repo_context`; dispatch |
| Logs Agent | Fetch + parse logs from source-specific adapter |
| Repo Agent | Index query — code at version/branch, blast radius |
| Reasoning Agent | Correlate trace + code + retrieved experiences |
| Validation Agent | Verify fix; regression risk; tailored output per channel |

### PR Review (second agent — not a skills race)

```
Input: Jira + PR URL(s)
  → Orchestrator: repo_context + blast radius (Repo Agent pattern)
  → Diff Agent: fetch + chunk diffs
  → Review Agent: blockers, citations (@REVIEWER persona)
  → Validation Agent: confidence gate
  → Output: review_report.md / PR comment
  → Experience Store: recurring patterns
```

Differentiation: **multi-repo index + experience flywheel + governed sub-agent contracts** — not prompt tuning on review instructions.

**RCA integration (not a third stack):**

| Evidence source | Existing system | How Logs sub-agent uses it |
|-----------------|-----------------|---------------------------|
| Parsed logs, stack frames, verdict | `ailoganalyzer` | Direct API/logic call — consume its structured output, no re-parsing raw logs |
| Structural code context | Graphify / central index | `framework/index/` — blast radius at branch/tag |

**There is no handoff contract.** Log Analyzer is pure logic/API. The Logs sub-agent calls it the same way it calls any tool. Agent Hub is the complete ecosystem — it writes its own skills and agents; it does not wrap or depend on BugBot's structure.

---

### 13. Orchestration Architecture (updated — ADR-001)

> **ADR-001 supersedes the original §13.** See `adr/ADR-001-cursor-cli-orchestrator.md`.

### Decision: **Cursor CLI orchestrates. Python owns contracts, storage, observability.**

Three facts changed §13 during Phase 1 design:
1. Cursor CLI ships headless — `cursor agent "..."` runs from Jenkins. CI blocker gone.
2. Cursor's agent loop beats single boto3 calls — iterative tool use, better results.
3. Python runner for `ai: true` steps requires Bedrock anyway — no complexity saved.

| Responsibility | Owner |
|---|---|
| Workflow execution (parallel / sequential) | `hub-runner.md` Cursor skill |
| AI reasoning (`ai: true` steps) | Cursor Claude (P1/P2) → Bedrock (P3) |
| `AgentResult` validation | `scripts/validate.py` — always enforced |
| Experience retrieve + write | `framework/experience.py` |
| Langfuse spans | `scripts/emit_langfuse.py` |
| Headless CI | `cursor agent "..."` from Jenkins |
| P3 AgentCore port | Swap `ai: true` → `boto3.invoke_model`. Scripts unchanged. |
| Sub-agent instructions | `agents/{name}/SKILL.md` (loaded for `ai: true` steps) |

### Rejected paths

| Path | Verdict |
|------|---------|
| Skills-first, no YAML | **Rejected** — BugBot pattern, no enforcement |
| Pure Python + Bedrock in P1 (original §13) | **Superseded by ADR-001** |
| LangGraph | **Rejected** — YAML workflow.yaml solves the same problem |

---

## 14. Relationship to existing systems

Agent Hub is the **complete ecosystem**. It writes its own skills and agents. External systems are called as **direct API or logic calls** — not via handoff contracts or skill wrappers.

| System | Relationship | What Hub does |
|--------|--------------|---------------|
| **Log Analyzer** (`ailoganalyzer`) | Pure logic / API — not a skill | Logs sub-agent calls its API directly to get structured log output (stack frames, verdict). Hub never re-parses raw logs. |
| **666_BugBot** (`algosec-tools/brandfactory`) | Reference only — not an integration target | BugBot is a point tool in BugBot's lane. Hub's RCA agent is a new implementation on the framework. Study BugBot's JIRA structure for domain knowledge only. |
| **AgentCore** (`agentcore-agents`) | Phase 3 port target | Framework + agents deploy here. Logic unchanged; transport changes. |

**Integration principle:** Hub calls external logic APIs where they already do the job well (e.g., Log Analyzer's log parsing). Hub does **not** adapt, wrap, or depend on BugBot's skill structure. Hub is the new platform.

---

## 15. Plan ratification

| Field | Value |
|-------|-------|
| **Status** | LOCKED |
| **Ratified** | 2026-09-11 |
| **Supersedes** | 2026-09-09 APPROVED DIRECTION (same content; formal lock + §0 summary) |
| **Authority** | `.agent-spec/sdlc/AGENT-HUB-PLAN.md` is the single architecture source of truth |

### Locked — do not relitigate without ADR

1. ~~Python `framework/` orchestrates~~ → **ADR-001:** `hub-runner.md` (Cursor CLI) orchestrates; Python owns contracts, experience, observability only. See `adr/ADR-001-cursor-cli-orchestrator.md`.
2. YAML (`workflow.yaml`) defines the step graph — readable, AI-generatable, same P1→P3.
3. Build order: P1 hub-runner + framework utilities + mock workflow → P2 real agents → P3 AgentCore Lambda.
4. Log Analyzer = direct API call from `scripts/fetch_logs.py` — no wrapper, no handoff contract.
5. ~~Cursor is a client/trigger — never the orchestrator~~ → **ADR-001:** Cursor CLI IS the orchestrator in P1/P2. Bedrock replaces it for P3 Lambda `ai: true` steps only.
6. Solo dev and company-wide share one workflow.yaml + scripts design; P3 swaps AI runtime only.

### Open — implementation inputs only

| Item | Owner | Blocks |
|------|-------|--------|
| Two cross-service demo repos | **Resolved** — created in project scope (`hub-demo-service-a/b`) | ~~§10 index acceptance~~ |
| Langfuse `docker-compose` in repo | P1 implementer | TODO Step 2 |
| `framework/`, `scripts/` scaffold | P1 implementer | Phase 1 start |

### Phase gate checklist (hard stops)

```
P1 DONE  = acceptance tests green + Langfuse trace visible + experience flywheel run-2 retrieves run-1
P2 START = P1 DONE only
P3 START = P2 RCA golden eval passes locally
```

### Next implementation action (P1 Step 1)

Deploy Langfuse (`docker-compose`) → write `framework/contracts.py` + `experience.py` + `observability.py` → write `scripts/` tools → write `.cursor/rules/hub-runner.md` → run mock workflow end-to-end.

