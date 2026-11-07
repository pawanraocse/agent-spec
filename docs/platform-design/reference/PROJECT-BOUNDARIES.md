# Project Boundaries — Agent Hub vs agent-spec

## Two separate projects

| Project | Repository | Purpose |
|---------|------------|---------|
| **Agent Hub** | `algosec-agent-hub` (this repo) | Company agentic AI framework — orchestration, agents, memory, eval, templates for **AgentCore** |
| **agent-spec** | Separate repository | Per-repo developer governance kit (gates, constitution, graphify for **product codebases**) |

Do not describe this repository as an "agent-spec distribution" or assume runtime coupling to the agent-spec repo.

## Rule: copy in, do not depend out

If Agent Hub needs an idea, file, or pattern from agent-spec:

1. **Copy** the content into this repository (under `docs/`, `.agents/skills/`, or the appropriate hub path).
2. **Adapt** naming and context for Agent Hub + AgentCore (not per-repo install).
3. **Document** what was copied and why in this file or a short note in the target doc.
4. **Do not** add git submodules, runtime imports, or "go read agent-spec" instructions for day-to-day hub work.

This repo must stand alone for hackathon demos, onboarding, and CI.

## What lives only in Agent Hub (this repo)

- Agent Hub architecture plan (`/.agent-spec/sdlc/AGENT-HUB-PLAN.md`)
- Agent templates aligned to `agentcore-agents/agent-template/`
- Golden paths and eval scenarios (e.g. PR Intelligence Loop)
- Agent registry / persona definitions for **deployed** agents
- Integration docs for DEVOPS-11338 / AgentCore MCP Gateway
- Prototypes under `prototype/` before PR to `agentcore-agents`

## What stays in agent-spec (other repo)

- Install kit dropped into **product** repositories (`bin/install.sh`, per-repo `CONSTITUTION.md`)
- Coding standards for Java/Angular product code
- Per-repo Graphify index as part of product CI

Agent Hub may **reuse concepts** (gates, snapshot, graph query) but owns its **copy** of any shared docs here.

## Legacy paths in this repository

Some directories use the name `.agent-spec/` and scripts named `agent-spec-index`. That is **legacy naming from an early import** — the content in this repo is **Agent Hub property**, maintained here, not fetched from the agent-spec repository at build time.

Future cleanup (optional): rename to `.agent-hub/` and `agent-hub-index` when churn is acceptable.

## Related documentation in this repo

- [README.md](../../README.md) — documentation index
- [AGENT-HUB-PLAN.md](../AGENT-HUB-PLAN.md)
- [AGENTCORE-HOSTING.md](AGENTCORE-HOSTING.md)

## When editing docs or talking to stakeholders

- Say **Agent Hub** for this project.
- Say **agent-spec** only when referring to the separate per-repo kit.
- Say **AgentCore** for AWS hosting (`agentcore-agents`, Gateway, MCP tools).
