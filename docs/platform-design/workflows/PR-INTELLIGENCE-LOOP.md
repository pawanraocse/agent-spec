# Workflow: PR Intelligence Loop

**Status:** Planned golden path (hackathon + first production agent)  
**Runtime:** `agentcore-agents` orchestrator · `useGateway=true`  
**Clients:** Cursor (`cursor` audience), service bot (`bot` audience)

## Goal

One end-to-end governed flow: Jira context + Bitbucket PR → structured review artifact with file citations, blockers, confidence tags — without invented APIs or unscoped tool access.

## Flow

```
Input: Jira key OR PR URL (one or more repos)
        │
        ▼
[0] Orchestrator: resolve repo_context
    - Jira → extract linked repos, branches, PR IDs
    - For each repo: gateway-bitbucket-get-pr (branch + diff)
    - Call graphify-query.blast_radius(repos=[A,B,...], branch per repo)
        │
        ▼
[1] Context agent / step — load ticket (Gateway Jira MCP)
        │
        ▼
[2] Fetch PR diff + metadata per repo+branch (Gateway Bitbucket MCP)
    ⚑  If PR spans multiple repos: fetch each in sequence
    ⚑  Branch per repo comes from repo_context (not always main)
        │
        ▼
[3] Cross-repo blast radius (Central Index MCP: graphify-query)
    - Returns: impacted files across all repos in repo_context
    - Flags: files changed in >1 repo simultaneously (interface risk)
        │
        ▼
[4] Retrieve experiences (experience store, repo namespace)
    - Match signals from diff/ticket to past experiences
    - Pre-load: known patterns for these repos (any agent that ran before)
        │
        ▼
[5] @REVIEWER logic — blockers first, file:line citations
    - Uses repo_context + blast radius + retrieved experiences
    - Emits AgentResult envelope (§11 of AGENT-HUB-PLAN.md)
        │
        ▼
[6] Optional: Sonar hotspots (Gateway / MCP)
        │
        ▼
[7] Orchestrator: merge AgentResult(s)
    - Deduplicate blockers, aggregate citations, rank by confidence
    - Write experience_candidates → experience store
        │
        ▼
Output: review_report.md → PR comment OR Confluence OR debt register
        │
        ▼
[8] Snapshot / audit log for next session
```

## Agent shape

**Orchestrator** (deterministic steps, exit-code gating) — matches platform `pr-review` pattern.

| Setting | Value |
|---------|-------|
| `shape` | orchestrator |
| `useGateway` | `true` |
| `audiences` | `cursor`, `bot` |
| Timeout awareness | MCP tool ~29s — chunk large diffs; one repo+branch fetch per step |

### Input schema

```yaml
input:
  jira_key: string?          # e.g. ENG-1234
  pr_urls: string[]?         # one or more Bitbucket PR URLs
  repo_context:              # optional override; orchestrator builds this if omitted
    - repo: string           # e.g. algosec/api-gateway
      branch: string         # e.g. feature/ENG-1234-auth or main
      pr_id: string?
```

## What to build where

| Piece | Location |
|-------|----------|
| Agent logic prototype | `prototype/java-pr-review-agent/` |
| Production agent | `agentcore-agents/agent-hub-pr-review/` (name TBD) |
| Persona rules | `.agent-spec/personas/REVIEWER.md` |
| Skill for Cursor dev | `.agents/skills/review-pr/` (if present) |
| Eval scenarios | `.agent-spec/sdlc/eval/` (to create) |

## Demo script (10–15 min)

1. Show Jira ticket with acceptance criteria.
2. Trigger agent (Cursor MCP or bot invoke).
3. Show Gateway + Cedar (same tools visible to `cursor`).
4. Show review output: Summary → Blockers → file:line → Action required.
5. Show one metric: time, blocker count, or eval pass rate.

## Success criteria

- [ ] No invented class or API names — all citations from diff or read tools
- [ ] Blockers separated from nits
- [ ] `[CONFIDENCE: …]` on non-trivial claims
- [ ] Runs on **deployed** dev agent, not laptop-only script
- [ ] Output persisted (PR comment or Confluence)

## Open items

- DevOps Jira ticket for new agent folder + dev deploy
- Pick target repo/PR for stable demo data
- 10 golden eval PRs for regression

## See also

- [AGENTCORE-HOSTING.md](../reference/AGENTCORE-HOSTING.md)
- `.agent-spec/sdlc/AGENT-HUB-PLAN.md`
