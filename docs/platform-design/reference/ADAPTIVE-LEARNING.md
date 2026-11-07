# Adaptive / Self-Improving Agents

**Status:** Planned capability (Agent Hub)  
**Terminology:** **Adaptive agent** — not unbounded “self-learning.” The base model weights do not change each run; **experience, skills, and retrieval** improve over time.

## Goal

If an agent spends time fixing a particular issue today, the **next** run should be faster, cheaper (fewer tokens), and more accurate — without rediscovering the same root cause.

Example:

> Today: `JAVA_HOME` points to Java 17 but project requires Java 21 → 5 minutes, ~20k tokens investigating.  
> Later: retrieve “Gradle unsupported Java version” experience for repo `X` → check `.java-version` / `build.gradle` → JDK 21 → retry → ~1 minute, ~4k tokens.

## Loop (governed)

```
Run → observe → extract experience → validate → store → reuse next time
```

**Do not** let the LLM rewrite its own weights or merge unchecked skills after every run. Learning lives **around** the model.

## Memory layers (Agent Hub + AgentCore)

| Layer | What | Where (target) | Scope |
|-------|------|----------------|-------|
| 1. Short-term | Current task, tool outputs, investigation state | Agent run context, Code Interpreter session | Per run |
| 2. Episodic | Past problems, errors, fixes, outcomes | AgentCore Memory + run artifacts (S3 / Confluence) | **Repo namespace** (any agent) |
| 3. Skills / procedures | Distilled reusable steps | `.agents/skills/` → eval → merge; agentskills.io format | All agents |
| 4. Structural | Imports, blast radius, co-change, multi-repo | Central Index (S3+DynamoDB) + Graphify per repo | **All repos, cross-agent** |
| 5. Reflection | What worked, failed, reusable? | Post-run eval step (automated) | Per agent run, stored in repo namespace |
| 6. Human approval | High-impact learned skills | PR + team lead before "trusted" tier | Org-wide |

> **Key design decision:** Experience (layer 2) is scoped by **repo namespace**, not by agent type.
> A PR-review agent and an RCA agent both working in `algosec/api-gateway` share the same experience store entry.
> This is the company-wide sharpness flywheel: every run by any agent makes the next run cheaper and faster — for everyone.

## Retrieval flow (next run, cross-agent)

```
New task (any agent: PR review, RCA, bug triage, …)
   ↓
Identify repos in repo_context
   ↓
Retrieve relevant experience from repo namespace
   (episodic store keyed: org/repo + signal tags)
   ↓
"Similar issue seen before by [review-agent | rca-agent]" [CONFIDENCE: MEDIUM|HIGH]
   ↓
Apply known fix (narrow tools, fewer file reads, targeted branch/file)
   ↓
Verify result (tests, conformance, eval golden task)
   ↓
Update or promote experience (governed, same repo namespace)
```

## Improvement order (do not skip)

```
context quality → memory → retrieval → skills and tools → fine-tuning (last)
```

Fine-tuning the base model is **out of scope** until retrieval and eval prove stable wins.

## Agent Hub vs Hermes-style learning

| Hermes (hermes-ai.net) | Agent Hub |
|------------------------|-----------|
| Autonomous skill create + improve during use | Extract → **eval golden task** → human-approved skill PR |
| Personal machine memory | **Shared** episodic store keyed by **repo namespace** — all agents, all teams |
| No enterprise gate | Cedar-scoped tools; promotion tiers |

We take the **learning loop pattern**; we add **governance** for company use.

## Experience record (schema sketch)

Store per agent or per repo namespace:

```yaml
id: exp-gradle-java-version-mismatch
agent: agent-hub-pr-review  # or repo-scoped
repo: algosec/some-service
trigger:
  signals: ["unsupported Java version", "Gradle", "JAVA_HOME"]
  tools_used: [gateway-bitbucket-get-file]
problem: Gradle build failed — JDK mismatch
resolution: Read .java-version and build.gradle; use JDK 21; retry
verification: ./gradlew test -q passes
outcome: success
tokens_saved_estimate: 16000  # optional metric from A/B
confidence: high
status: trusted  # candidate | trusted | deprecated
approved_by: team-lead  # required for trusted
```

## Promotion tiers

| Tier | Meaning | Auto-use on next run? |
|------|---------|----------------------|
| `candidate` | Extracted after one success | Suggest only; agent must verify |
| `trusted` | Passed eval + human approval | Retrieve and apply if match score high |
| `deprecated` | Failed eval or superseded | Never apply; keep for audit |

## Where this runs (AgentCore)

| Component | Role |
|-----------|------|
| **Orchestrator agent** (`agentcore-agents`) | Run loop + reflection step at end |
| **AgentCore Memory** | Long-term episodic facts |
| **Gateway MCP** | Narrow domain tools (not `shell.exec(any)`) |
| **Code Interpreter** | Repro scripts; capture stdout as evidence |
| **Experience store** | S3 prefix or dedicated MCP tool target (future `agentcore-mcp-tools`) |
| **Eval suite** | Golden tasks in `.agent-spec/sdlc/eval/` — regression before promote |

## Minimal v1 (build tiny first)

**Coding agent + experience store + reflection → adaptive agent**

1. One agent (PR review or RCA stub).
2. One experience store (JSON or S3; no vector DB yet).
3. Post-run reflection prompt → `candidate` experience JSON.
4. Pre-run retrieval: match triggers against new task text + error snippets.
5. Three golden scenarios; measure tokens and time before/after promote.

## Metrics (prove learning)

| Metric | Target |
|--------|--------|
| Tokens per successful fix | Down over repeated scenario |
| Time to resolution | Down on golden eval set |
| Hallucination rate | No increase after promote |
| Eval pass rate | Stable or up after skill merge |

## RCA / coding agent fit

Especially strong for:

- Repeated stack traces → repo/file associations
- Known debugging sequences (which logs, which 2 files to open)
- Co-change patterns (graph + git history via tools)
- Escalation packets when fix unknown (Afatech-style)

## Related docs

- [AGENT-HUB-PLAN.md](../AGENT-HUB-PLAN.md)
- [AGENTCORE-HOSTING.md](AGENTCORE-HOSTING.md)
- `.agent-spec/sdlc/AGENT-HUB-PLAN.md` §5 (Hermes comparison)
- [PR-INTELLIGENCE-LOOP.md](../workflows/PR-INTELLIGENCE-LOOP.md)
