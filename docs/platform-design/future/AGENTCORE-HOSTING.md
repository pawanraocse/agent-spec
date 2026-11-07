# AgentCore Hosting Model

How Agent Hub agents run as a **common company platform** — not per-developer Cursor-only setups.

Epic: **DEVOPS-11338** · Platform: **AgentCore AI Tools Platform**

## Short answer

| Question | Answer |
|----------|--------|
| Where do agents run? | `agentcore-agents/<agent>/` on AWS (Lambda orchestrator or harness) |
| How do Cursor users interact? | MCP → **shared MCP Gateway** (same URL for everyone, `cursor` audience) |
| Is Cursor the platform? | **No** — IDE client only |
| One index for all code? | **No** — Graphify index per product repo via CI |
| Who deploys today? | DevOps (dev after CI; stage/prod with approvals) |

## Architecture

```
Cursor / Teams / OpenWebUI / service bot
        │
        ▼
  Shared MCP Gateway (Entra JWT or M2M)
        │
        ▼
  Cedar (default-deny, tool.config.yaml audiences)
        │
        ├──► agentcore-mcp-tools (Bitbucket, Jira, Confluence, …)
        │
        └──► agentcore-agents (orchestrator | harness)
```

## Repos (company standard)

| Repo | Owner | Content |
|------|-------|---------|
| `agentcore-mcp-gateway` | DevOps | Gateway, OAuth, Cedar, SSM, SDK |
| `agentcore-mcp-tools` | Tool teams | `tool.config.yaml` + `src/tools.py` per target |
| `agentcore-agents` | Any dev team | One folder per deployed agent |
| `agentcore-jenkins-lib` | DevOps | Shared CI pipeline |

## The contract (teams never fork Gateway)

1. **SSM** `/agentcore/platform/*` — ARNs and URLs at deploy
2. **Platform SDK** — Lambda layer, attach don't copy
3. **Managed IAM policies** — least privilege from DevOps
4. **Gateway MCP tools** — call through Gateway, not raw APIs

## Audiences (who sees which tools)

| Audience | Caller | Auth |
|----------|--------|------|
| `cursor` | Cursor IDE users | Entra JWT |
| `openwebui` | OpenWebUI | Per-user 3LO |
| `harness` | Managed harness agents | M2M |
| `bot` | Service agents (`pr-review`, …) | M2M |

Cedar hides or blocks tools not allowed for the caller. No audience = invisible to all.

## Agent Hub repo role (`algosec-agent-hub`)

This repo does **not** replace AgentCore. It holds:

- Agent templates and logic prototypes (`prototype/`)
- Personas, skills, eval scenarios
- Documentation and architecture plans
- Copy of patterns needed for hub work (no dependency on agent-spec repo)

Before production: PR agent folder to `agentcore-agents`, DevOps deploy to dev.

## Common misconceptions

| Wrong | Right |
|-------|-------|
| Every developer runs their own agent runtime | One deployed agent, many clients |
| Everyone manually runs Graphify locally | Product repos index in CI; agents pull PR/Jira via MCP |
| Build standalone Gateway like Hermes | Use company Gateway — already live |
| agent-spec = Agent Hub | Separate projects — see [PROJECT-BOUNDARIES.md](PROJECT-BOUNDARIES.md) |

## References

- [How to build MCP tools and agents](https://algo-confluence.algosec.com/display/DEVOPS/How+to+build+MCP+tools+and+agents)
- [DEVOPS-11338 Architecture](https://algo-confluence.algosec.com/display/DEVOPS/DEVOPS-11338+AI+Tools+Platform+Self-Service+Architecture)
