# Workflow: RCA Intelligence Loop (Universal Failure Investigator)

**Status:** Planned workflow (CI failures, Support escalations, Customer incidents)  
**Runtime:** `agentcore-agents` orchestrator · `useGateway=true`  
**Clients:** Cursor (`cursor` audience), Jenkins/CI webhook (`bot` audience), Jira/Zendesk integration (`bot` audience)

---

## Goal

Provide a universal, governed Root Cause Analysis (RCA) pipeline for failures across CI builds, internal support, and production customer tickets. Produces cited evidence, pinpoints root causes in code, queries past resolutions, and generates actionable, verifiable fixes without hallucinated APIs or manual source searches.

---

## Architecture

```
[ Ingestion / Triggers ]
 Jenkins/CI Failure   │   Support Escalation (Jira/Zendesk)   │   Customer Incident (Slack/Ticket)
                      │                                       │
                      └───────────────────┬───────────────────┘
                                          ▼
                         [0] Main Platform Orchestrator
                             (Validates Auth, Cedar Policy, Langfuse trace)
                                          │
                                          ▼
                      Investigation Domain Orchestrator
                       - Normalizes error signature & metadata
                       - Resolves target repo(s), commit/release tag/branch
                       - Queries Central Experience Store for known patterns
                                          │
                      ┌───────────────────┴───────────────────┐
                      ▼                                       ▼
               [1] Logs Agent                          [2] Repo Agent
             - Parses stack traces                   - Queries Central Index
             - Fetches Jenkins console /             - Resolves cross-repo deps
               customer log bundles                  - Fetches files at target
             - Isolates error frames                   branch/tag via Bitbucket MCP
                      └───────────────────┬───────────────────┘
                                          ▼
                           [3] Reasoning Agent
                             - Correlates stack traces with source code
                             - Evaluates candidate experiences from store
                             - Identifies root cause defect
                                          │
                                          ▼
                          [4] Validation Agent
                             - Verifies code path exists in cited branch
                             - Checks regression risk / breaking changes
                             - Formulates reproducible verification step
                                          │
                                          ▼
                        [5] Orchestrator Output Consolidation
                             - Emits standardized AgentResult envelope
                             - Extracts experience candidate -> Experience Store
                             - Dispatches tailored delivery
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              ▼                           ▼                           ▼
        CI Pipeline                 Support Portal             Engineering / PR
  PR/Commit blocker comment      Internal Jira RCA draft    Fix PR or bug ticket
  with file:line citations       + customer summary packet  with verification steps
```

---

## Step-by-Step Flow

| Step | Component | Action |
|---|---|---|
| **0. Normalize Context** | Investigation Orchestrator | Extracts failure signature, error logs, and environment (service, version/tag, branch). |
| **1. Retrieve Experience** | Experience Store | Checks repo namespace for previously solved instances of this signature. |
| **2. Fetch Evidence (Parallel)** | **Logs Agent** & **Repo Agent** | - **Logs Agent:** Isolates relevant stack traces and error messages.<br>- **Repo Agent:** Uses Central Index to locate code across relevant repos at the exact release tag or branch. |
| **3. Reason & Correlate** | Reasoning Agent | Matches stack frames to source files. Synthesizes why failure occurred. |
| **4. Validate** | Validation Agent | Audits reasoning against source code. Flags confidence (`HIGH`, `MEDIUM`, `LOW`). |
| **5. Store & Deliver** | Orchestrator | Appends candidate to Experience Store. Sends report to target surface (CI, Jira, Slack). |

---

## Agent Shape & Configuration

**Shape:** Orchestrator with parallel sub-agents (Deterministic pipeline with LLM reasoning nodes).

| Setting | Value |
|---|---|
| `shape` | orchestrator |
| `useGateway` | `true` |
| `audiences` | `cursor`, `bot` |
| `subagents` | `logs-agent`, `repo-agent`, `reasoning-agent`, `validation-agent` |
| Timeout Awareness | Chunk log bundle parsing; read targeted file lines via Gateway MCP |

### Input Schema

```yaml
input:
  source_type: ci | support | customer_incident
  incident_id: string          # e.g. JIRA-9876, BUILD-5432
  error_payload:
    log_text: string?          # Raw logs or stack trace snippet
    log_url: string?           # URL to Jenkins console or S3 log bundle
  repo_context:
    - repo: string             # e.g. algosec/auth-service
      branch: string?          # e.g. main, release/v24.2
      commit_sha: string?
      release_tag: string?     # e.g. v24.2.1
```

### Output Envelope (`AgentResult`)

```yaml
agent: investigation-orchestrator
task_id: JIRA-9876
status: success | partial | failed
confidence: HIGH | MEDIUM | LOW | UNKNOWN
root_cause:
  summary: "NullPointerException in TokenValidator due to missing claim in v24.2 token payload."
  primary_file: "src/main/java/com/algosec/auth/TokenValidator.java"
  primary_line: 142
  repo: "algosec/auth-service"
  branch: "release/v24.2"
evidence:
  stack_trace_snippet: "..."
  code_snippet: "..."
verification_steps:
  - "Run `mvn test -Dtest=TokenValidatorTest#testMissingClaim`"
remediation:
  suggested_fix: "Add null-check or default empty map for customClaims."
experience_candidate:
  trigger_signals: ["NullPointerException", "TokenValidator", "customClaims"]
  resolution: "Enforce null-check on optional token claims"
```

---

## Success Criteria

- [ ] Exact file, line, and repo citations for root causes (Zero hallucinated paths).
- [ ] Operates across multi-repo services using Central Index.
- [ ] Version/branch aware (investigates the exact customer release tag or PR branch).
- [ ] Compounding efficiency: identical failure signatures resolve in <30s via Experience Store.
- [ ] Full traceability via self-hosted Langfuse integration.
