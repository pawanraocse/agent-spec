# Central Multi-Repo Index

**Status:** Design / planned  
**Owner:** Agent Hub (this repo); deployment to `agentcore-mcp-tools/graphify-query/`  
**Depends on:** `AGENT-HUB-PLAN.md §10`, `ADAPTIVE-LEARNING.md`, `AGENTCORE-HOSTING.md`

---

## Problem

Each product repo builds its own Graphify index in CI and stores it at `.agent-spec/graph/knowledge-graph.json`. This works for single-repo questions, but **fails** for the two most common engineering workflows:

| Scenario | Why per-repo index is blind |
|----------|-----------------------------|
| **PR review spanning multiple repos** | A change in `api-gateway` breaks an interface in `auth-service`. Single-repo blast radius misses the downstream impact. |
| **Bug / RCA tracing across services** | A `NullPointerException` originates in `common-lib` and surfaces in `payment-service`. No cross-repo co-change history. |
| **Branch feature development** | Feature branch `feature/ENG-1234` exists in three repos simultaneously. Queries against `main` return stale answers. |

---

## Solution: Central Index Aggregator

```
Product repo CI (each repo, on merge or PR)
  └─ graphify-build.py  →  knowledge-graph.json
                             │
                    CI webhook / push trigger
                             │
                             ▼
              ┌──────────────────────────────┐
              │   Index Aggregator Lambda    │
              │   - Validates schema         │
              │   - Deduplicates edges       │
              │   - Writes to S3             │
              │   - Updates DynamoDB manifest│
              └──────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │  S3 prefix                  │
              │  agentcore-indexes/         │
              │    <org>/<repo>/<sha>/      │
              │      knowledge-graph.json   │
              └──────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │  DynamoDB: index-manifest   │
              │  PK: org/repo               │
              │  SK: sha                    │
              │  fields: s3_key, branch,    │
              │          indexed_at, status │
              └──────────────────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  graphify-query MCP tool     │  ← agents call this
              │  (agentcore-mcp-tools)       │
              │  audiences: cursor, bot      │
              └──────────────────────────────┘
```

---

## graphify-query MCP Tool (contract)

All tools are read-only. No writes from agents.

### `index.query_blast_radius`

Returns every file across the given repos that depends on `file` (direct + transitive, depth configurable).

**Input:**
```yaml
file: string              # e.g. src/main/java/com/algosec/auth/TokenService.java
repos:                    # list of repos to search
  - repo: string          # e.g. algosec/api-gateway
    branch: string        # e.g. feature/ENG-1234 or main
depth: int?               # default 2; max 5
```

**Output:**
```yaml
blast_radius:
  - repo: string
    branch: string
    file: string
    edge_type: import | reference | co-change
    distance: int         # hops from source file
interface_risk:           # files changed in >1 repo simultaneously (for this branch set)
  - file: string
    repos: string[]
```

---

### `index.query_co_change`

Files frequently changed in the same commit or PR as `file` (git history, across repos).

**Input:**
```yaml
file: string
repos:
  - repo: string
    branch: string
since: string?            # ISO date, default: 90 days
limit: int?               # default 10
```

**Output:**
```yaml
co_change:
  - file: string
    repo: string
    change_count: int     # times changed together
    last_changed: string  # ISO date
```

---

### `index.list_repos`

Returns all repos with an indexed graph, their last indexed SHA and branch.

**Input:** none

**Output:**
```yaml
repos:
  - repo: string
    last_sha: string
    last_branch: string
    indexed_at: string    # ISO datetime
    status: ok | stale | error
```

---

### `index.get_module_map`

Returns the module → file list for a repo, optionally for a specific branch.

**Input:**
```yaml
repo: string
branch: string?           # default: main
```

**Output:**
```yaml
modules:
  - module: string        # e.g. com.algosec.auth
    files: string[]
    entry_points: string[]
```

---

## Branch-Aware Querying

The aggregator stores one index entry per `(repo, sha)` pair. The manifest maps `(repo, branch)` → latest SHA for that branch.

When an agent passes `branch: feature/ENG-1234`, the query tool:
1. Looks up DynamoDB: `org/repo` + `branch = feature/ENG-1234` → SHA.
2. If not found, falls back to `main`/`master` and sets `confidence: MEDIUM` in response.
3. Returns results with the resolved `sha` so agents can cite it.

This lets agents switch context between branches without re-indexing manually.

---

## How Agents Use This

### PR Review spanning two repos

```yaml
# Orchestrator resolves repo_context from Jira ticket ENG-1234
repo_context:
  - repo: algosec/api-gateway
    branch: feature/ENG-1234-auth-refactor
  - repo: algosec/auth-service
    branch: feature/ENG-1234-auth-refactor

# Step 3 in PR Intelligence Loop:
call: index.query_blast_radius
input:
  file: src/main/java/com/algosec/api/AuthClient.java
  repos: [algosec/api-gateway@feature/ENG-1234, algosec/auth-service@feature/ENG-1234]

# Result surfaces:
# - auth-service/TokenValidator.java depends on AuthClient (distance 1)
# - interface_risk: AuthClient.java changed in both repos — flag as interface risk
```

### Bug trace (RCA agent)

```yaml
call: index.query_co_change
input:
  file: common-lib/src/NullSafeMapper.java
  repos: [algosec/common-lib@main, algosec/payment-service@main]
  since: "2026-07-01"

# Result shows: PaymentProcessor.java co-changes with NullSafeMapper 8x in 90 days
# → RCA agent reads PaymentProcessor.java first, not random scan
```

---

## Hosting on AgentCore

| Component | Where | Notes |
|-----------|-------|-------|
| Index Aggregator | Lambda (triggered by CI webhook) | Triggered by product repo CI on merge; writes to S3 + DynamoDB |
| S3 bucket | `agentcore-indexes-<env>` | Standard AgentCore S3 via SSM parameter |
| DynamoDB table | `agentcore-index-manifest` | PK: `org/repo`, SK: `sha`; GSI on `branch` |
| graphify-query tool | `agentcore-mcp-tools/graphify-query/` | `tool.config.yaml` audiences: `cursor`, `bot` |
| Cedar policy | Standard Gateway rules | Read-only for `cursor` + `bot`; write blocked |

---

## Phase 1 (hackathon / MVP)

Skip the full Aggregator. Use a simpler approach:
1. Each product repo pushes its `knowledge-graph.json` to a known S3 key on merge.
2. The query tool reads the relevant S3 keys, merges in-memory, and responds.
3. No DynamoDB manifest — branch lookup uses S3 key convention: `<org>/<repo>/<branch>/knowledge-graph.json`.
4. Only two repos needed for live demo.

This proves the concept in the demo without full infrastructure build.

---

## Related docs

- [`AGENT-HUB-PLAN.md §10`](../../.agent-spec/sdlc/AGENT-HUB-PLAN.md)
- [`AGENT-HUB-PLAN.md §11`](../../.agent-spec/sdlc/AGENT-HUB-PLAN.md) — `AgentResult` + `repo_context`
- [`ADAPTIVE-LEARNING.md`](ADAPTIVE-LEARNING.md) — cross-agent repo-namespaced experience store
- [`PR-INTELLIGENCE-LOOP.md`](../workflows/PR-INTELLIGENCE-LOOP.md) — uses this in step 3
- [`AGENTCORE-HOSTING.md`](AGENTCORE-HOSTING.md) — platform hosting model
