# algosec-agent-spec — Todo (sole sequenced backlog)

> **Strategy & phases:** [`docs/MASTER-PLAN.md`](docs/MASTER-PLAN.md) only.  
> **v1.1.0 shipped (2026-10-28)** → **v2.0.0** (Phase 2) → **v3.0.0** (Phase 3) → **v4.0.0** (Phase 4 — Autonomous Bots) → **v5.0.0** (Phase 5 — Marketplace)  
> Phase 1 evidence + manual checks: [`docs/PHASE1-VERIFICATION.md`](docs/PHASE1-VERIFICATION.md)  
> **Design + execution order (P2.n / P3.n labels) for every pending row:** [`docs/IMPLEMENTATION-GUIDE.md`](docs/IMPLEMENTATION-GUIDE.md) §14. Rows marked *(new)* were added there for verified gaps.

**Status:** `[ ]` open · `[~]` in progress (or built, live check owed) · `[x]` done · `[-]` deferred, merged or dropped (reason in the row)

Execute **slices in table order** (1 → 1.5 → 2 → … → 16b). **Slice 9 (O-\*)** starts only after **Slice 1** closes (**Slice 1 is closed**).  
Locked decisions live in MASTER-PLAN — not duplicated here. Close items only in this file.

---

## Slice 1 — Trust

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[x]` | T-001 | **Memory dedupe & conflict lint** | `agent-spec-memory.py` flags duplicate keys and opposing constraints; zero false negatives on test fixtures | 2d |
| `[x]` | T-002 | **Shrink memory tree (<8 KB)** | Index holds one-line entries; bodies in separate files; `audit` passes at <8 KB | 1d |
| `[x]` | T-006 | **TECH-DEBT-REGISTER** | Template placeholders replaced with real debt entries (e.g. `manage-git-hooks.py` docstring gap) | 0.5d |
| `[x]` | T-005 | **`agent-spec-doctor`** | Skills, hooks, digest JSON, graph age, memory bytes, register path vs `pwd`; prints fix commands | 3d |

---

## Slice 5 — Dashboard data

## P2 — Dashboard MVP

> Local-only. Data: transcripts + `agent-spec-tokens.py` + `graphify-cli` + memory + pipeline STATE.
> Store: SQLite.

### Data & Ingest

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[x]` | D-001 | **`schema.sql` + SQLite** | Tables: `requests`, `steps`, `subagent_runs`, `memory_facts`, `graph_stats`, `gate_events`; path configurable | 1d |
| `[x]` | D-002 | **Transcript ingestor** | Imports Cursor transcripts → one `request` per user prompt, ordered `steps` | 2d |
| `[x]` | D-003 | **Subagent correlation** | Parent/child `request_id` linkage; 7d full retention, summary forever | 1d |
| `[x]` | D-004 | **Pipeline / gate ingest** | `.agent-spec` pipeline `STATE.json` → `gate_events` for timeline + gate audit (demo §4) | 1d |
| `[x]` | D-005 | **Memory mirror** | Imports `agent-spec-memory.py` facts into `memory_facts`; shows byte cost per session | 1d |
| `[x]` | D-006 | **Graph stats snapshot** | After `graphify-build`: files/edges/cycles/SHA/age persisted for dashboard chips | 0.5d |
| `[x]` | D-004.1 | **Backlog ingest + CLI** *(new)* | `agent-spec-backlog.py` list/find/set; `[x]` refused without `--evidence`; rows → `tasks` table | 1d |
| `[x]` | D-007 | **Graph symbols + callers** *(new)* | Symbol nodes + `calls` edges in `graphify-build.py`; `graphify-cli.py` gets `symbols`, `callers`; build <= 1.5x baseline. Deterministic only; co-change dropped (DEC-13). Evidence 2026-10-31: `tests/test_graph_symbols.py` 12/12, selftest green; this repo 764 symbols / 1101 calls; full rebuild 0.36s vs 0.25s (1.4x). Symbols and `calls` are top-level graph arrays so file-level consumers are unaffected | 1.5d |
| `[-]` | D-008 | **FTS5 hybrid index** *(dropped, DEC-13)* | Cursor codebase search + `agent-spec-search` subagent + the graph cover retrieval. Revisit in Phase 3 only if the eval shows a recall gap | - |

