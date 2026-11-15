# AI Experience Intelligence Platform: review, gaps and target architecture

> Decision record: **DEC-17** in [`MASTER-PLAN.md`](MASTER-PLAN.md). Sequenced work:
> **Slice 6g** in [`todo-plan.md`](../todo-plan.md) (PI-001…PI-012). Evidence for the built
> rows: [`docs/evidence/PI-001.md`](evidence/PI-001.md).
>
> Written 2026-11-14 after a full review of the repository against the product brief "an
> AI-first experience intelligence platform for Cursor: observe, understand, evaluate, learn and
> improve the AI-assisted development lifecycle."

## 1. What the product already is

The brief describes, almost line for line, the product this repository has been building since
DEC-14. The review traced each flow end to end rather than reading the docs.

```
Cursor hooks ──► hooks/cursor-event.py ──► .agent-spec/metrics/events.jsonl (append-only, redacted)
  sessionStart ─► digest (memory, graph, last session, doctor)            │
  preToolUse   ─► guard (secret paths, whole-file reads)                   │
  stop/sessionEnd ─► receipt, snapshot follow-up, graph refresh, rotate    │
                                                                           ▼
Cursor local store (state.vscdb) ─► cursor_sessions.py ─► ingest.py ─► platform.db (SQLite, WAL, migrations)
Hub-runner run dirs, memory facts, graph, gates ─────────────────┘        │
                                                                           ▼
                         traces.py (OTel-shaped traces/spans) ─► serve.py (loopback, token, CSP)
                                                                           ▼
                         React SPA: Live · Coach · Learning · Ask · Project
AI judgement: agent-spec-session-review skill ─► metrics/reviews/<conversation>.json (AI-judged)
```

| Brief area | State before this slice | Evidence |
|---|---|---|
| Session analysis: prompt, response, tools, files, skills, subagents, timeline | **Works.** One trace per request from documented hook fields; subagents parented; skills detected from slash commands and SKILL.md reads | `traces.build_from_events`, Live view, `tests/test_traces.py` |
| Execution transparency, observed vs inferred | **Works.** Orchestration graph, waterfall, inspector, replay; `source=hook` is Measured, `cursor_store` is Estimated, planned-but-not-run skill steps drawn as planned | DV-031…DV-034, DV-055 |
| Token and cost analytics | **Works, measured where Cursor reports it.** `afterAgentResponse` token counts; context budget from Cursor's own `contextTokensUsed`; pricing table | CB-001…CB-005, `/api/pricing` |
| Response quality | **Partial.** The review rubric judged *process* (whole-file reads, retries, delegation) but not *outcome* (relevance, completeness, correctness, rework). No measured outcome facts existed for it to cite | `skills/agent-spec-session-review` rubric 2.0.0 |
| Self-learning | **Works as designed.** Reviews → recurring category → proposed fact (human approves) → Learning view measures recurrence before vs after the fact. Skill proposals via `agent-spec-learn` need approval | DV-050/051, L-001/L-002 |
| Persistent storage | **Works.** SQLite with ordered migrations; append-only JSONL is the source of truth and the DB is derived and rebuildable (DEC-04) | `db.py`, `schema*.sql` |
| Project intelligence / RAG from the dashboard | **Missing.** D-008 (FTS5 hybrid index) was dropped under DEC-13 because Cursor's codebase search covers *the agent's* code retrieval. Nothing covered the developer asking the dashboard about past sessions, decisions and reviews, which Cursor's search does not index | `todo-plan.md` D-008; empty `fts_docs` table |
| Automation first | **Mostly.** Hooks run digest, guard, receipt, snapshot, graph refresh and rotation. The dashboard's own data refreshed in the background. | HA-001…HA-006 |

What should **not** change: the AI-first ladder (DEC-15) — rubrics and grades in skills, code
only for security, exact computation, latency or plumbing; provenance on every number; the
local-only server. The brief's "do not fabricate telemetry" and "combine measurable signals with
AI evaluation" are already the project's rules; this slice applies them to the two gaps.

## 2. Gap analysis, ranked by developer value

| # | Gap | Impact | Decision |
|---|---|---|---|
| 1 | No way to ask the project, or its AI history, a question from the dashboard | The brief's §7 in full; the most common question after a session ("what did Cursor change, and why?") had no answer surface | **Built** (PI-001…PI-005) |
| 2 | Quality judged on process only; no measured outcome facts | A request can be efficient and wrong. Reviews could not cite verification, rework or missing-path errors because nothing computed them | **Built** (PI-006, PI-007) |
| 3 | No semantic retrieval | Keyword search misses paraphrase | **Built as an optional provider** — local Ollama embeddings, fused by RRF; keyword mode is labelled as such. No pip dependency (constitution rule 2.1) |
| 4 | Agent cannot use project history | Cursor's agent had no tool to ask "have we done this before?" across sessions | **Built** (`agent-spec-ask` skill over the same index) |
| 5 | Session comparison, skill effectiveness ranking | Useful once quality dimensions accumulate | Planned (PI-010, PI-011): needs a few weeks of rubric-2.1.0 reviews first, otherwise the ranking is noise |
| 6 | Retention policy for `events.jsonl` | Grows without bound | Planned (PI-012) |
| 7 | Rule/skill improvement proposals with diff + approval in the UI | The learn skill proposes; the dashboard does not show proposals | Planned (PI-009); proposals stay files in git, approval stays human |

Rejected after review:

- **A Python quality score.** DEC-15 and constitution rule 3 ban scoring rubrics in code; the
  score comes from the review skill, with the measured signals as its evidence.
- **Chat in the dashboard.** Cursor is the console (DEC-14/15). The dashboard retrieves and
  cites; Cursor answers through `/agent-spec-ask`. A local model can answer in the dashboard only
  when the developer configures one, and the answer is labelled AI-generated with its model.
- **A vector database or embedding library dependency.** Vectors are float32 blobs in SQLite
  and similarity is a brute-force dot product, linear in chunk count (this repository: about
  3,100 chunks). That keeps the stdlib-only rule; a project large enough to make it slow is the
  trigger to revisit, and it has not been measured at that scale.
- **Indexing other workspaces' chats.** Cursor's store holds every workspace. Only this
  project's requests are indexed (project isolation).

## 3. Target architecture

### 3.1 Modules (new in bold)

| Module | Responsibility | Allowed-code reason |
|---|---|---|
| `hooks/cursor-event.py` | Observe: one redacted row per Cursor event | plumbing, security |
| `traces.py` | Understand: events → traces/spans | exact |
| **`signals.py`** | Evaluate (facts): per-request outcome signals with span ids | exact |
| `agent-spec-session-review` skill | Evaluate (judgement): process findings + **outcome quality** (rubric 2.1.0) | — (AI) |
| `observe.py` | Learn: recurrence before vs after a fact; coach issues | exact |
| **`retrieval.py`** | Index + retrieve: chunks, BM25, optional vectors, RRF, citations | plumbing, exact |
| **`agent-spec-ask` skill** | Answer from the index with citations, inside Cursor | — (AI) |
| `serve.py` | Read-only API; loopback; token; background refresh | plumbing, security |
| UI | Live, Coach, Learning, **Ask**, Project; **Outcome** tab per request | — |

### 3.2 Data model added (migration 4, `schema_v4_retrieval.sql`)

| Table | Holds |
|---|---|
| `index_sources(kind, source, stamp, sha, chunks, indexed_at)` | What was indexed and how it looked: `mtime:size` stamp for a cheap skip, content hash to avoid re-chunking a touched-but-unchanged file, and a trace's `end:status:span_count` |
| `chunks(chunk_id, kind, source, ref, title, start_line, end_line, session_id, ts, body, terms)` | Retrievable passages with citation metadata; `terms` holds split identifiers (`buildFromEvents` → `build from events`) |
| `chunks_fts` | FTS5 external-content index (porter stemmer) over title, body, terms; kept in sync by triggers |
| `chunk_vectors(chunk_id, model, dim, vec)` | Optional L2-normalised float32 embeddings per model |

`kind` ∈ `code`, `doc`, `rule`, `memory`, `request`, `review`. Like every table, the index is
derived: `ingest --rebuild` recreates it from files.

### 3.3 Retrieval flow

```
question ─► fts_query (quoted terms, identifiers split, stopwords out; user text never parsed as FTS syntax)
         ├► BM25 (title 4.0, body 1.0, terms 1.5) + metadata filters (kind, path prefix, since, session)
         ├► [AGENT_SPEC_EMBED set] cosine over chunk_vectors for the same filters
         └► reciprocal rank fusion (k = 60) ─► hits with ref = path:start-end | request <id> | review <id>
                                           ─► related files one import edge away (Graphify)
                                           ─► cursor_prompt: /agent-spec-ask + numbered sources
                                           ─► [AGENT_SPEC_LLM set] local model answer, cited [n], labelled
```

Freshness without a manual step: the dashboard's background loop runs an incremental pass every
60 s (a no-change pass over this repository takes 0.18 s), and `agent-spec-platform.py search`
/ `ask` refresh before querying, so the Cursor agent always reads a current index.

### 3.4 Privacy and safety

- Secret-shaped paths (`.env*`, keys, credentials) are never read; every chunk body passes
  through `redact.py` before it is stored.
- `.agent-spec/metrics/` and `platform/` are never indexed; only `.agent-spec/` Markdown is.
- Model endpoints must be loopback unless `AGENT_SPEC_ALLOW_REMOTE_MODELS=1`; source code does
  not leave the machine by default.
- API routes are read-only, behind the existing host, token and CSP guards.

## 4. Cursor limitations and the alternative used

| Wanted | What Cursor exposes | What the platform does |
|---|---|---|
| Which rules were applied to a request | No hook field names applied rules | Rules are indexed and searchable; the review cites rule text when it judges intent. Shown as not observable, never inferred as applied |
| Skill invocation | No skill event | Detected from a `/skill` prompt or a SKILL.md read (observed); otherwise not shown |
| Per-skill / per-subagent token cost | Tokens arrive on `afterAgentResponse` only | Attributed to the request; subagent cost is not split out and is not estimated |
| Model reasoning steps | Not exposed | Only spans that a hook observed; no synthetic "planning" node |
| Context contents | Only sizes (`contextTokensUsed`, breakdown) | Context budget view uses the sizes; contents are not reconstructed |
| Chats whose hooks never fired | Local store (unofficial format) | Ingested as `cursor_store`, durations labelled Estimated |

## 5. Configuration

| Variable | Default | Effect |
|---|---|---|
| `AGENT_SPEC_INDEX` | `1` | `0` stops the dashboard's background index pass |
| `AGENT_SPEC_EMBED` | unset | `ollama:<model>` (e.g. `ollama:nomic-embed-text`) enables hybrid retrieval |
| `AGENT_SPEC_LLM` | unset | `ollama:<model>` lets the dashboard write a cited answer |
| `AGENT_SPEC_OLLAMA_URL` | `http://127.0.0.1:11434` | Local model endpoint (loopback enforced) |
| `AGENT_SPEC_ALLOW_REMOTE_MODELS` | unset | `1` permits a non-loopback endpoint |
