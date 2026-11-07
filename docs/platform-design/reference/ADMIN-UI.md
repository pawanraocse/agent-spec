# Agent Hub — Admin UI

**Status:** Planned  
**Purpose:** Observability, troubleshooting, and continuous improvement of all agent runs.

---

## Dashboard (Main View)

![Agent Hub Admin Dashboard](../assets/agent_hub_admin_dashboard.jpg)

---

## What it tracks (per run)

| Field | Purpose |
|-------|---------|
| `run_id` | Unique run reference |
| `trigger` | Webhook / CLI / Manual / Cursor user |
| `repos` | Which repos + branches were inspected |
| `agent` | Which agent ran (PR Reviewer, RCA, etc.) |
| `model_input` | Exact system prompt + messages sent to LLM |
| `model_output` | Raw LLM response (before parsing) |
| `agent_result` | Structured AgentResult envelope |
| `tokens_used` | For cost tracking and improvement loop |
| `duration_seconds` | For performance tracking |
| `status` | `success` / `partial` / `failed` |
| `experience_candidates` | What the agent proposed to learn |

---

## UI Screens

### 1. Dashboard
- Stat cards: Total Runs, Success Rate, Avg Tokens, Avg Duration
- Active Agent Runs table (live)
- Token Usage Trend (last 7 days — should trend down as learning kicks in)
- Eval Pass Rate donut chart

### 2. Run Detail (click any run)
- Full prompt sent to model
- Full model output
- Parsed AgentResult: blockers, citations, confidence
- Files read per repo + branch
- Experience candidates extracted
- Side-by-side diff view for before/after on repeat runs

### 3. Experience Store browser
- Filter by repo, agent, status (trusted / candidate / deprecated)
- Promote candidate → trusted (with approval)
- Deprecate a bad experience
- View which runs produced each experience

### 4. Eval
- Golden task list with pass/fail history
- Compare two runs on same task
- Regression alert if pass rate drops after a skill promote

### 5. Settings / Admin
- Register new repos for Central Index
- Configure agent audiences (cursor / bot / harness)
- Set confidence thresholds for auto-post vs flag-for-review

---

## Where it runs

| Component | Location |
|-----------|----------|
| Run records | DynamoDB (`agentcore-run-log`) |
| Experience store | DynamoDB + S3 |
| Admin UI | React app / OpenWebUI adapter |
| Auth | Entra SSO (same as rest of AgentCore) |

---

## Hackathon demo value

Show this screen during the demo:
1. Trigger a PR review live
2. Watch run appear in the table (status: Running → Complete)
3. Click run → show exact prompt, output, tokens
4. Show Experience Store: new candidate extracted
5. Show Token Trend: second run on same repo uses fewer tokens

**This makes the self-learning flywheel visible to judges.**

---

## Related docs

- [`AGENT-HUB-PLAN.md`](../../.agent-spec/sdlc/AGENT-HUB-PLAN.md)
- [`ADAPTIVE-LEARNING.md`](ADAPTIVE-LEARNING.md)
- [`MULTI-REPO-INDEX.md`](MULTI-REPO-INDEX.md)

---

## Observability: Langfuse (self-hosted)

**Decision:** Use [Langfuse](https://github.com/langfuse/langfuse) (MIT, open-source) for all LLM observability. Self-hosted on Docker — data never leaves the company network.

### What Langfuse replaces

Langfuse covers ~60% of the custom Admin UI:

| Capability | Langfuse | Custom UI |
|---|---|---|
| Traces (prompt → output per run) | ✅ | — |
| Token cost per run / agent | ✅ | — |
| Eval scores + pass rate over time | ✅ | — |
| Prompt versioning + A/B | ✅ | — |
| Golden dataset + regression | ✅ | — |
| Experience store browser | — | ✅ needed |
| Promote/deprecate experiences | — | ✅ needed |
| Central Index repo management | — | ✅ needed |

### Deployment

```yaml
# docker-compose.yml — run on internal server (Windows Server or Linux VM)
services:
  langfuse:
    image: langfuse/langfuse:latest
    ports: ["3000:3000"]
    environment:
      DATABASE_URL: postgres://langfuse:secret@postgres:5432/langfuse
      NEXTAUTH_SECRET: <generate>
      SALT: <generate>
    depends_on: [postgres]

  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: langfuse
    volumes: ["pgdata:/var/lib/postgresql/data"]

volumes:
  pgdata:
```

### Agent integration (2 lines per Lambda)

```python
from langfuse import Langfuse
lf = Langfuse(host="http://langfuse-server:3000")

trace = lf.trace(name="pr-review", input=repo_context)
span  = trace.span(name="reviewer-step", input=prompt)
span.end(output=agent_result, usage={"input": prompt_tokens, "output": completion_tokens})
trace.score(name="eval-pass", value=1.0)  # set after eval check
```

### Why self-hosted over Langfuse Cloud

- Code and prompts stay inside company network
- Full data ownership — no SaaS dependency
- Aligns with AgentCore VPC security model
- MIT license — free forever, no vendor lock-in
- Can run on same Docker host as Ollama (Windows Server)
