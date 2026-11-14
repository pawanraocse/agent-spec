# algosec-agent-spec — Todo (sole sequenced backlog)

> **Strategy & phases:** [`docs/MASTER-PLAN.md`](docs/MASTER-PLAN.md) only.  
> **v1.1.0 shipped (2026-10-28)** → **v2.0.0** (Phase 2) → **v3.0.0** (Phase 3) → **v4.0.0** (Phase 4 — Autonomous Bots) → **v5.0.0** (Phase 5 — Marketplace)  
> Phase 1 evidence + manual checks: [`docs/PHASE1-VERIFICATION.md`](docs/PHASE1-VERIFICATION.md)  
> **Design + execution order (P2.n / P3.n labels) for every pending row:** [`docs/IMPLEMENTATION-GUIDE.md`](docs/IMPLEMENTATION-GUIDE.md) §14. Rows marked *(new)* were added there for verified gaps.

**Status:** `[ ]` open · `[~]` in progress (or built, live check owed) · `[x]` done · `[-]` deferred, merged or dropped (reason in the row)

Execute **slices in table order** (1 → 1.5 → 2 → … → 16b). **Slice 9 (O-\*)** starts only after **Slice 1** closes (**Slice 1 is closed**).  
Locked decisions live in MASTER-PLAN — not duplicated here. Close items only in this file.

---

## Phase map

| Phase | Version | Slices | Dashboard |
|-------|---------|--------|-----------|
| 0 Shipped | v1.0.3 | A-* done | CLI tokens only |
| 1 Stabilize | **v1.1.0 — done** (re-verified 2026-10-28: selftest + doctor green) | 1–4, T-054, T-040 | Trust + demo CLI + tokens + DX |
| 1→2 Carry-over | **built; live checks owed** (T-056 deferred — no git repo) | 4c: T-050–T-053, T-055, T-057–T-059 | Receipt / ROI; Phase 1 follow-ups |
| 2 Platform | v2.0.0 — **re-baselined 2026-10-31 to DEC-12/DEC-13 (skills first, minimum code).** 15 P2 rows open as of 2026-10-31 late night (D-007, D-010, D-020, S-003 now done; next D-014, then D-012, L-001, O-010, D-021, D-022); 26 rows merged/dropped. Rule: code only for DB + ingest, run-dir plumbing, hooks, backlog CLI, thin stdlib API; everything else is a skill. Live counts: `bin/agent-spec-backlog.py list`. Validation backlog: `testing_todo.md` | 5–9, T-041 | **Primary UI** — D-*, L-*, workflows in D-021 |
| 3 Enterprise | v3.0.0 | 10–11, T-042 | Mesh, registry, audit panels |
| 4 Autonomous Bots | v4.0.0 | 12–14, T-043 | Always-on agents, routines, checkpoints |
| 5 Agent Marketplace | v5.0.0 | 15–16, T-044 | Ecosystem, federation, community |

---

## Slice index (sequence)

| # | Name | IDs | Exit |
|---|------|-----|------|
| — | Foundation | A-001…A-004 | Indexing + selftest |
| 1 | Trust | T-001…T-006 (+ T-005 doctor) | **Done** — doctor, memory index <8 KB |
| 1.5 | Zero-touch | T-050…T-055 | T-050–T-055 **done** (built in **Slice 4c**, unit-tested; live Cursor check of the new hooks still owed — T-057) |
| 2 | Demo-ready CLI | T-003, T-004 | **Done** — digest freshness + onboarding nudge |
| 3 | Tokens | T-010…T-014 | **Done** — overhead <5% path (footprint measured) |
| 4 | DX | T-020…T-034 | **Done** — QUICKSTART + adoption |
| 4b | Release P1 | T-040 | **Done** — v1.1.0 (no tag: no git repo yet) |
| 5 | Dashboard data | D-001…D-006 | SQLite + transcript |
| 6 | **Dashboard UI** (v1 thin) | D-010..D-022 done; v1 static page shipped | localhost showcase, stdlib + one static page |
| 6b | **Control plane v2** (DEC-14) | CP-000..CP-050 in `dashboard_overhaul.md` §12 | React SPA, Agent Console, five spaces, guided tour |
| 6c | **AI-first realignment** (DEC-15) | AF-001…AF-008 | Hook event spine, AI session review, Console frozen, grading out of Python |
| 6d | **v3 request-trace control plane** (DEC-16, proposed) | DV-000…DV-062 | Live request tracing, AI coach, measured learning, extensible panels |
| 6e | **Measured context budget** | CB-001…CB-005 | **Done** — reset break-even from Cursor's own counters, stop-hook nudge, warm-resume digest |
| 7 | Flywheel + security | L-*, S-* | Trends + quarantine in UI |
| 8 | RCA + 3 workflow skills | B-001…B-010 | `agent-spec-wf-*` skills + AUTO-3807 eval |
| 9 | Orchestration (skill-driven) | O-001…O-020 | `agent-spec-hub-runner` skill + `agent-spec-run.py` plumbing; live run of `agent-spec-wf-example` |
| 9b | Release P2 | T-041 | Tag v2.0.0 |
| 10 | Mesh + registry | P3-001…P3-010 | Multi-repo |
| 11 | Audit + cross-org | P3-011…P3-018 | Compliance demo |
| 11b | Release P3 | T-042 | Tag v3.0.0 |
| 12 | Always-on execution | P4-001…P4-004 | Daemon runner + cloud sandbox |
| 13 | Routine synthesis + checkpoints | P4-005…P4-010 | Auto-recipe + warm resume |
| 14 | Risk-tier gating + handoffs | P4-011…P4-016 | Blast-radius `preToolUse` + typed schemas |
| 14b | Release P4 | T-043 | Tag v4.0.0 |
| 15 | Bot marketplace + integrations | P5-001…P5-008 | Template catalog + 3P connectors |
| 16 | Federation + ecosystem | P5-009…P5-014 | Cross-org agents + community routines |
| 16b | Release P5 | T-044 | Tag v5.0.0 |

---

# Phase 1 — Stabilize (v1.1.0) — COMPLETE

> **Review 2026-10-28:** Exit gate met (selftest [1]–[12] green, doctor `--strict` green, v1.1.0 + CHANGELOG). Not "100% of original ideal": git tag waived; Slice 1.5 deferred (now Slice 4c); manual checks B18–B21 (live Cursor hook payload, hard cap, Windows) unverified — tracked in Slice 4c follow-ups below.
> Scope decision (2026-10-28): Slices 1–4 + T-054 + T-040. Remaining Slice 1.5 items stay `[ ]` below and are the first candidates after Phase 1. Windows (T-033) = documented Git Bash/WSL + path conversion in `install.ps1`; native PowerShell port not built. Open follow-ups are in `.agent-spec/TECH-DEBT-REGISTER.md` (DEBT-002…007).

## Slice 1 — Trust

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[x]` | T-001 | **Memory dedupe & conflict lint** | `agent-spec-memory.py` flags duplicate keys and opposing constraints; zero false negatives on test fixtures | 2d |
| `[x]` | T-002 | **Shrink memory tree (<8 KB)** | Index holds one-line entries; bodies in separate files; `audit` passes at <8 KB | 1d |
| `[x]` | T-006 | **TECH-DEBT-REGISTER** | Template placeholders replaced with real debt entries (e.g. `manage-git-hooks.py` docstring gap) | 0.5d |
| `[x]` | T-005 | **`agent-spec-doctor`** | Skills, hooks, digest JSON, graph age, memory bytes, register path vs `pwd`; prints fix commands | 3d |

---

## Slice 1.5 — Zero-touch (hooks + receipt; UI = verify)

> MASTER-PLAN: hackathon (gate + graph + receipt) and adoption (doctor + ROI + shared facts lite).

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[x]` | T-050 | **`agent-spec-receipt.py`** | One JSON per session: tokens, graph query count, `STATE.json` gates, facts injected, whole-file read flags | 1.5d |
| `[x]` | T-051 | **Session-end hook** | On chat end/stop: write receipt + append `.agent-spec/metrics/daily.jsonl`; fail-open | 1d |
| `[x]` | T-052 | **Always-on auto-harness** | `.mdc`: code-change → 6-gate implement without user invoking skill; graph-before-big-read | 0.5d |
| `[x]` | T-053 | **Shared facts lite** | `install.sh --register` merges team facts (submodule or `TEAM_FACTS_REPO`); org constraints in digest | 1.5d |
| `[x]` | T-054 | **Doctor in register + digest** | Register runs doctor; digest one-line OK or fix command (feeds T-005) | 1d |
| `[x]` | T-055 | **Receipt / ROI viewer** | Local static or minimal server: list receipts + 7d rollup; export CSV (D-014 lite) | 1.5d |

---

## Slice 2 — Demo blockers (harness CLI)

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[x]` | T-003 | **Digest: graph freshness signal** | Digest shows `fresh` · `incremental (Nms)` · `stale (lock held)` | 1d |
| `[x]` | T-004 | **sessionStart onboard nudge** | If `.agent-spec/.onboarding-needed` exists, digest appends "run `/agent-spec-onboard` now" | 0.5d |

---

## Slice 3 — Token efficiency

## P1 — Token Efficiency

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[x]` | T-010 | **Default tool discipline (no 3.8 KB skill)** | 5–8 bullet rules in always-on `.mdc`; or sessionStart hint when tool-share high | 1d |
| `[x]` | T-011 | **preToolUse optional hard cap** | Env flag blocks rangeless Read >N KB (default off; nudge stays default) | 0.5d |
| `[x]` | T-012 | **Post-harness measurement habit** | Documented `agent-spec-tokens.py compare` workflow; optional CI `audit --scan` | 0.5d |
| `[x]` | T-013 | **Coexistence rule** | Doc/lint: do not stack `algosec-lean` Always Apply + `agent-spec.mdc` | 0.5d |
| `[x]` | T-014 | **Trim router skill** | `agent-spec` SKILL.md <3 KB; points to `agent-spec-gate.py status` | 1d |

---

## Slice 4 — Developer experience

## P1 — Developer Experience

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[x]` | T-020 | **Router + SDLC discoverability** | QUICKSTART "Day 1" path: doctor → onboard → raw-code; SDLC only for features | 1d |
| `[x]` | T-021 | **Graph stale edge cases** | Hooks-off / 3s timeout / huge repos: digest + doctor state manual rebuild path | 0.5d |
| `[x]` | T-022 | **VERSION pin in check-install** | Compare registered harness VERSION vs clone; warn on drift | 0.5d |
| `[x]` | T-030 | **`install.sh --register-here`** | Registers `git rev-parse --show-toplevel` or `pwd` automatically | 0.5d |
| `[x]` | T-031 | **Re-register campaign** | Doctor + docs warn when workspace predates `post-rewrite` hooks | 0.5d |
| `[x]` | T-032 | **Optional `team.yaml`** | `.agent-spec/team.yaml` for team defaults (Java version, SDLC track); digest reads it | 1d |
| `[x]` | T-033 | **Windows full parity** | Register + git hooks: WSL paths documented or PowerShell port | 2d |
| `[x]` | T-034 | **Adoption checklist** | README/Confluence: install, register, hooks, doctor, onboard, compact boundary | 0.5d |

---

## Slice 4b — Phase 1 release

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[x]` | T-040 | **Release v1.1.0** | Selftest + doctor green; overhead <5%; CHANGELOG; ~~git tag~~ (waived: workspace has no git repo) | 0.5d |

---

# Phase 2 — Platform (v2.0.0) · Dashboard = showcase

## Slice 4c — Phase 1 carry-over (do before Slice 5)

> T-050–T-053, T-055 are the Slice 1.5 rows above (now `[x]`). **T-056 deferred** (no git repo in workspace, 2026-10-29); T-057 and T-058 are built but need a live Cursor session and a Windows host. Follow-ups from Phase 1 review:

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[-]` | T-056 | **Create git repo + tag v1.1.0** *(deferred)* | Waived until workspace uses git; was T-040 criterion | — |
| `[x]` | T-057 | **Live hook verification (DEBT-005)** — run live 2026-11-13 (PHASE1-VERIFICATION F). Cursor strips a Read's offset/limit and reports StrReplace as a whole-file Write before `preToolUse`, so `RANGE_KEYS` was not the fault and no hook-side match can fix it. Decision: follow Cursor's harness. Under Cursor the Read and Write nudges and the hard cap are skipped, and the spine judges each Read afterwards from `tool_output.content_length`. Evidence: docs/evidence/T-057.md | Run PHASE1-VERIFICATION B18–B20 in Cursor; fix `RANGE_KEYS`; confirm digest hook within Cursor timeout (worst case ~5 s) | 0.5d |
| `[~]` | T-058 | **Windows run (DEBT-006)** — run sheet written (PHASE1-VERIFICATION E); needs a Windows host | PHASE1-VERIFICATION B21 on real Windows Git Bash/WSL | 0.5d |
| `[x]` | T-059 | **Dangling doc refs (DEBT-002)** | `agent-spec-lint-refs.py` reports 0 dangling (was 36); enforced by selftest [12] | 1d |

> [`docs/DASHBOARD.md`](docs/DASHBOARD.md) · [`docs/platform-design/reference/ADMIN-UI.md`](docs/platform-design/reference/ADMIN-UI.md)

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

## Slice 6 — Dashboard UI (showcase)

### Metrics & Proof

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[x]` | D-010 | **Savings calculator + session compare** | One page: naive whole-file vs `graphify context`, delta tokens and $ with editable weights; pick two transcripts -> `agent-spec-tokens.py compare`. Absorbs D-011, D-023 | 1.5d |
| `[-]` | D-011 | **Session compare UI** *(merged into D-010)* | Merged into D-010 | - |
| `[x]` | D-012 | **Home KPIs + trends** | Runs/tokens today; saved vs baseline (7d); index freshness; learning trend line. Absorbs L-004 | 1d |
| `[-]` | D-013 | **Per-tool cost panel** *(merged into D-021)* | Tools tab inside the D-021 run detail | - |
| `[x]` | D-014 | **Export proof pack (CLI)** | `agent-spec-platform.py export` writes CSV/JSON metrics; no source or prompts | 0.5d |

### UI Surfaces

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[x]` | D-020 | **Local API + static UI (stdlib)** | `http.server` on 127.0.0.1, read-only JSON from SQLite, one static `ui/index.html`; no framework, no build, no third-party import; Host check + launch token (S-003) | 2d |
| `[x]` | D-021 | **Runs list + detail** | Timeline (sessionStart -> skills -> subagents -> tools -> gate), token waterfall; tabs for per-tool cost and subagent health. Absorbs D-013, D-028 | 2d |
| `[x]` | D-022 | **Gaps / bugs panel** | SQL-rule flags: whole-file read without graphify, test fail, token spike, missing gate, S-002 blocks | 1d |
| `[-]` | D-023 | **Playground** *(merged into D-010)* | Merged into D-010 | - |
| `[-]` | D-024 | **Ask (hybrid)** *(covered by skills)* | Covered by `agent-spec-query-graph` + `agent-spec-search` subagent; no code | - |
| `[-]` | D-025 | **Graph explorer** *(covered by CLI + skill)* | Covered by `agent-spec-blast-radius` + `agent-spec-query-graph` | - |
| `[-]` | D-026 | **Memory browser** *(covered by CLI)* | Covered by `agent-spec-memory.py` list/search | - |
| `[-]` | D-027 | **Workspace manifest** *(deferred to Phase 3)* | Multi-root support belongs with the Phase 3 mesh | - |
| `[-]` | D-028 | **Subagent Health Navigator** *(merged into D-021)* | Subagents tab inside the D-021 run detail | - |
| `[x]` | D-020.1 | **SSE event stream** *(DEC-14)* | Agent Console and run step streams; built under Slice 6b CP-012/CP-013/CP-021 | 1d |
| `[x]` | D-029 | **Guarded control endpoints** *(DEC-14)* | POST for agent jobs, workflow start, cancel per dashboard_overhaul.md §6.3; not v1 `control.json` | 1d |

---

## Slice 6b — Control plane v2 (DEC-14)

> Tracker for `dashboard_overhaul.md` §12. Critical path: CP-000 → CP-001 → CP-010 → CP-012 → CP-013 → CP-014 → CP-040.

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[x]` | CP-000 | **Record DEC-14; supersede guard memory fact; Slice 6b in `todo-plan.md`** | DEC-14 row in the guide; DEC-13 tables point to it; memory fact superseded | 0.5d |
| `[~]` | CP-001 | **Spike: Cursor CLI contract** | Done 2026-11-06: R1, R2 resolved (§6.4); `ask-reconnect-loop.ndjson` recorded. Left: resume an IDE composer id (R3); R4 partly answered 2026-11-13: hooks fire headless (postToolUse, postToolUseFailure, afterFileEdit) and Task subagents run, but subagentStart/Stop, beforeSubmitPrompt, afterAgentResponse and stop do not fire in --print mode; Jira MCP headless still open; a clean run off-proxy with a `result` event, a tool-call run, and an Agent propose-then-apply run (R8) | 0.5d |
| `[x]` | CP-002 | **UI build pipeline** | `ui-src/` builds to `ui/dist/`; budget check fails over 400 KB gzip; `install.sh` copies no `ui-src` or `node_modules` | 1d |
| `[x]` | CP-003 | **SPA fallback, CSP, token meta** | Non-API GET serves `index.html` after token check; traversal test still green; new CSP on every response | 0.5d |
| `[x]` | CP-004 | **Provenance `<Metric>` + honesty test** | Test fails if any KPI renders without a badge | 0.5d |
| `[x]` | CP-005 | **Demo seed command** | `seed` adds rows with `source='demo_seed'`; remove deletes only those; KPIs badge them | 1d |
| `[x]` | CP-006 | **App shell + Home** | Sidebar, Cmd-K, themes, 4 KPIs, 5 tiles, recent activity on empty DB | 1.5d |
| `[x]` | CP-010 | **`agent_exec.py` job runner** | Cap 2 (429), 15 min timeout, `killpg` leaves no orphans, stderr drained, chunks redacted | 1.5d |
| `[x]` | CP-011 | **Fake CLI shim** | Replays CP-001 recordings; used by every Console test | 0.5d |
| `[x]` | CP-012 | **POST routing + guards** | §6.3 order tested case by case; read handlers stay `readonly=True`; job writer uses WAL | 1d |
| `[x]` | CP-013 | **Agent routes: new, resume, cancel, stream** | Work against the shim; CLI-missing returns `cli_missing` and spawns nothing | 1d |
| `[x]` | CP-014 | **Console UI** | Streaming, chips, meter, Stop, modes (Agent needs confirm), persona, workspace | 2d |
| `[x]` | CP-020 | **Sessions explorer + detail + compare** | Search and filters; grade and tips; A/B deltas from `savings.compare` | 1.5d |
| `[-]` | CP-021 | **Run events route + live step graph** (superseded by DV-011 + DV-031 (runs as workflow spans in the orchestration graph)) | `/api/runs/<id>/events`; states ok, self-healed, failed, waiting; parallel branches | 2d |
| `[x]` | CP-022 | **Inspector drawer + subagent health tab** | Step input/output/tokens/latency; failure rate and median bytes per type | 1d |
| `[x]` | CP-023 | **Workflow launch cards** | Five cards with input validation and dry-run; copy-command fallback + API launch | 0.5d |
| `[x]` | CP-030 | **Knowledge read routes** | `/api/graph`, `/api/graph/blast`, `/api/memory`, `/api/experiences` with tests | 1d |
| `[-]` | CP-031 | **Graph view** (superseded by DV-058) | 2D force graph, lazy chunk; click shows blast halo and callers; search jumps to node | 1.5d |
| `[x]` | CP-032 | **Memory, flywheel, skills and personas views** | Facts by type with injections; experience tiers; "Use in Console" inserts the command | 1d |
| `[x]` | CP-033 | **Governance routes** | `/api/gates`, `/api/health/doctor` (cached), `/api/pricing` with tests | 0.5d |
| `[x]` | CP-034 | **Governance views** | SDLC rail + REQ trace, implement audit, guard log, health, proof pack, backlog, debt | 2d |
| `[x]` | CP-035 | **`pricing.json`** | Placeholder presets; "set pricing" shown at zero rates; `as_of` age warning | 0.5d |
| `[-]` | CP-040 | **Guided tour** (superseded by DV-060) | Five steps with live numbers following demo.md script | 1.5d |
| `[x]` | CP-041 | **Budget and accessibility pass** | Under 400 KB gzip (105.4 kB achieved); WCAG AA in both themes; prefers-reduced-motion | 0.5d |
| `[x]` | CP-042 | **Retire v1 UI + docs** | Parity checklist signed (Gaps, Savings, trend, freshness, every v1 view); old UI files deleted on confirmation; `DASHBOARD.md` and `demo.md` updated | 0.5d |
| `[x]` | CP-007 | **KPI sparklines + status bar** | 7-day sparkline per KPI from `insights.home`; status bar shows graph age, hook dots, doctor dot, job count | 1d |
| `[-]` | CP-015 | **Agent-mode diff cards** (cut by DEC-15) | Each edit tool call renders a diff card with approve/reject actions | 1d |
| `[x]` | CP-024 | **Savings tab + context gauge** | v1 D-010 calculator ported with weights; gauge shows peak context vs threshold | 1d |
| `[-]` | CP-025 | **Token flow Sankey** (cut by DEC-15; the fabricated Token Flow tab was removed) | Token flow distribution across digest, graph, tools, and model outputs | 1d |
| `[x]` | CP-036 | **Gaps tab ("caught by the harness")** | All v1 D-022 rules shown, each linking to its session; Home count matches | 0.5d |
| `[x]` | CP-037 | **Team-fact filter + health lines** | Memory filter on `scope`; health shows snapshot size, rotation due, team import date | 0.5d |
| `[-]` | CP-043 | **Cross-cutting UX** (cut, DEC-15; reopen only for a named demo need) | Virtualized lists over 200 rows, skeletons, job-done toast, opt-in notification, shareable URLs, print stylesheet, `?` shortcut sheet | 1.5d |
| `[x]` | CP-050 | **Log S-004 context nudges** | Pre-tool-use logs threshold nudges to quarantine.jsonl with tests | 0.5d |

---

## Slice 6c — AI-first realignment (DEC-15)

> Tracker for `dashboard_overhaul.md` §13 and MASTER-PLAN §AI-first principle. Order: AF-001 → AF-002 → AF-003 → AF-006; AF-004, AF-005, AF-007, AF-008 are independent. Each code row names its allowed-code reason (security / exact / latency / plumbing).
> **Scope cuts (DEC-15):** CP-015 diff cards, CP-025 Sankey, CP-043 cross-cutting UX are `[-]`; CP-023 launch is copy-command only; Console CP-010..014 frozen by AF-005.

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[x]` | AF-001 | **Hook event spine** *(plumbing)* | Step 1, live-Cursor spike: record real payloads for `postToolUse`, `postToolUseFailure`, `subagentStart`, `subagentStop`, `preCompact`, `afterFileEdit` into `tests/fixtures/hooks/`; note which carry token usage. Step 2: one fail-open script `hooks/cursor-event.py` registered via `merge-hooks-json.py` appends redacted rows to `.agent-spec/metrics/events.jsonl` (also S-004 nudges, replaces CP-050); unit test per event; selftest section added | 1d |
| `[x]` | AF-002 | **Ingest reads `events.jsonl` first** *(plumbing)* | `ingest.py` builds requests/steps/subagent_runs from events; transcript and `composerHeaders` reader runs only for sessions with no events; no new code in `cursor_sessions.py`; existing API tests green | 1d |
| `[x]` | AF-003 | **`agent-spec-session-review` skill + `agent-spec-reviewer` subagent** *(AI)* | Rubric lives in `SKILL.md` (token economy, delegation, input discipline, gates, security evidence). Reads `events.jsonl` + receipt, writes `.agent-spec/metrics/reviews/<session>.json` `{grade, summary, pros[], improvements[], evidence[], model, rubric_version}`; every claim cites an event id. Runs on demand and in a daily Cursor Automation (never per turn). Dashboard shows *AI-judged* badge and "Not reviewed" when absent; `evaluate_session` removed after parity (confirm first) | 1.5d |
| `[x]` | AF-004 | **Hook-driven snapshot and compact** *(hook)* | `stop` (or `preCompact`) hook, once per session above the S-004 threshold, returns a `followup_message` to run `/agent-spec-snapshot`; `loop_limit` set; "Session End: remind developer" line removed from `CURSOR.md` at the next planned rules release; test covers one-shot behaviour | 0.5d |
| `[x]` | AF-005 | **Freeze Console; add prompt composer** *(UI, no new backend)* | `agent_exec.py` routes return 404 unless `AGENT_SPEC_CONSOLE=1`; Console UI hidden by default; composer builds persona/workflow/input into a slash command and copies it; no files deleted; tests updated | 0.5d |
| `[x]` | AF-006 | **Split gaps: facts vs judgement** *(exact)* | `insights.gaps` keeps `step_failed`, `run_failed`, `secret_path_blocked`; `whole_file_no_graph`, `token_spike`, `missing_gate` move to reviewer findings; Home "caught" count = facts + findings with evidence | 0.5d |
| `[x]` | AF-007 | **Logic audit** | One-page verdict per file (keep / shrink / replace with skill) for `agent-spec-tokens.py`, `agent-spec-memory.py` (dedup, conflict lint: let the model judge at `/agent-spec-remember`, CLI keeps storage), `agent-spec-receipt.py`, `savings.py`, `cursor_sessions.build_pipeline_stages`; follow-up rows added here | 0.5d |
| `[x]` | AF-008 | **AI-first code-task gate** | `agent-spec-prompt-audit` / selftest check: every new todo row that adds `bin/` or `hooks/` code states an allowed-code reason; one line added to `/agent-spec-implement` declaration. Always-on rule text changes ship only at a planned rules release (prefix stability) | 0.5d |

## Slice 6d — v3 request-trace control plane (DEC-16, proposed 2026-11-13)

> Design: `dashboard_overhaul.md` §14. Phases in order A → H; within a phase, rows are independent unless `Depends` says otherwise. Every row needs `docs/evidence/<ID>.md` before `[x]` (§14.9). Code rows name their allowed-code reason. Critical path: DV-001 → DV-002 → DV-010 → DV-012 → DV-030 → DV-031 → DV-060.

### Phase A — Truth (before any new UI)

| Status | ID | Task | Acceptance criteria | Effort | Depends |
|---|---|---|---|---|---|
| `[x]` | DV-000 | **Record DEC-16** | DEC-16 in `docs/MASTER-PLAN.md` decisions; §14 linked from `docs/DASHBOARD.md` | 0.25d | — |
| `[x]` | DV-001 | **Event spine on the documented contract** *(plumbing)* | `cursor-event.py` reads `hook_event_name`, `conversation_id`, `generation_id`, `model`, `cursor_version`, `workspace_roots`, `transcript_path` and the per-event fields in §14.3; prompt and response text redacted and truncated; writes under `workspace_roots[0]`, not `cwd`; `merge-hooks-json.py` registers it for `beforeSubmitPrompt`, `postToolUse`, `postToolUseFailure`, `subagentStart`, `subagentStop`, `afterFileEdit`, `afterAgentResponse`, `preCompact`, `stop`; fail-open kept; unit test per event | 1d | — |
| `[x]` | DV-002 | **Live payload recording** *(spike, no code; closes T-057, AF-001 step 1)* (Recorder built (`AGENT_SPEC_HOOK_RECORD=1` saves one payload per event); fixtures replaced with documented-contract payloads (tests/fixtures/hooks/README.md). 2026-11-13: recording is automatic. `agent-spec-platform.py hooks` reads Cursor's own hook log, which keeps every payload even when a hook cannot start, and the dashboard backfills it every 60 s. Root cause of the missing live data: Cursor opens this repo over `\\wsl.localhost`, so every hook fails with `spawn powershell ENOENT`. Fixed by opening the folder through Remote-WSL; hooks now exit 0. Recorded live: beforeSubmitPrompt, preToolUse, postToolUse, afterAgentResponse (with measured input/output/cache token counts, now kept by the spine), stop, sessionStart and sessionEnd. postToolUseFailure and afterFileEdit then recorded through the Cursor CLI (cursor-agent 2026.11.11, --model auto). subagentStart and subagentStop then recorded live from the IDE (2026-11-13 19:16). Exception: preCompact fires only when Cursor compacts a long chat; it is parsed from the documented contract, the dashboard lists it as missing, and the 60 s backfill picks up the first real one without a code change) | One real payload per event in DV-001 recorded from Cursor into `tests/fixtures/hooks/`, replacing the synthetic files; note whether any token field exists and how a skill invocation is observable | 0.5d | DV-001 |
| `[x]` | DV-003 | **Cursor store path resolver** *(plumbing)* | `cursor_sessions.py` finds `state.vscdb` on macOS, Windows (`%APPDATA%\Cursor`), WSL (`/mnt/c/Users/*/AppData/Roaming/Cursor`) and Linux (`~/.config/Cursor`); override via env var; test per OS layout | 0.5d | — |
| `[x]` | DV-004 | **Tracker and docs truth** (CP rows corrected, README version and skill count fixed, selftest suite loop fixed; CURSOR.md cut from 5607 B to 4307 B on 2026-11-13 by pointing at the agent contracts in `.cursor/agents/` instead of restating them) | CP-015, CP-025 → `[-]`; CP-021, CP-031, CP-040 → `[ ]` with a pointer to DV-031/DV-041/DV-060; README version and skill count from files; `CURSOR.md` under 4600 B at the next rules release; selftest green | 0.5d | — |
| `[x]` | DV-005 | **No fixed figures; page-level honesty test** (Fabricated Token Flow tab removed; tour figures removed; honesty test covers Live, Coach, Learning and every tab of the v2 Project pages; Overview's fixed `1,841 B` and `5 workflows` removed) | Tour and `Sessions.tsx` read every number from the API; a Vitest test renders each page with fixture data and fails on any numeric text outside a `<Metric>` with provenance | 0.5d | — |

### Phase B — Trace model and API

| Status | ID | Task | Acceptance criteria | Effort | Depends |
|---|---|---|---|---|---|
| `[x]` | DV-010 | **Trace and span tables** *(plumbing)* | Schema migration: `traces` (`generation_id`), `spans` (OTel-shaped: `trace_id`, `span_id`, `parent_span_id`, `kind`, `start`, `end`, `status`, `attributes` JSON); ingest builds them from `events.jsonl`; subagent spans parented via `parent_conversation_id`; durations from paired events or `duration_ms` | 1.5d | DV-002 |
| `[x]` | DV-011 | **Workflow runs as traces** *(plumbing)* | Hub-runner run steps become spans under the triggering `generation_id`; existing run tests green | 0.5d | DV-010 |
| `[x]` | DV-012 | **Request API** *(plumbing)* | `/api/requests` (filters: session, status, skill, date; paginated) and `/api/requests/<id>` (span tree, responses, review) with tests; read-only connection | 1d | DV-010 |
| `[x]` | DV-013 | **Live stream** *(latency)* | `GET /api/live` SSE tails `events.jsonl` from an offset; loopback + token guards; test for reconnect from offset; UI polling fallback | 1d | DV-010 |

### Phase C — UI foundation

| Status | ID | Task | Acceptance criteria | Effort | Depends |
|---|---|---|---|---|---|
| `[x]` | DV-020 | **shadcn/ui, TanStack Query/Table, motion** (Radix + cva primitives in the shadcn pattern, TanStack Query, motion; initial bundle 150.4 KB gzip. TanStack Table dropped as unused. v2 pages ported onto the primitives and theme tokens 2026-11-13) | Components copied into `ui-src/src/components/ui/`; existing pages compile on them; bundle under 400 KB gzip | 1d | — |
| `[x]` | DV-021 | **Four-space shell** | Live, Coach, Learning, Project; Console removed from nav (route kept behind the flag); settings drawer; light/dark; Cmd-K over requests and skills | 1d | DV-020 |

### Phase D — Live and request detail (centrepiece)

| Status | ID | Task | Acceptance criteria | Effort | Depends |
|---|---|---|---|---|---|
| `[x]` | DV-030 | **Request feed** | Live list updating over DV-013; filters; status, duration, skills, subagent count per row | 1d | DV-012, DV-013, DV-021 |
| `[x]` | DV-031 | **Orchestration graph** | React Flow + dagre; node per span kind with custom components; nodes animate in while running; edge labels show handed-over bytes; lazy chunk | 2d | DV-030 |
| `[x]` | DV-032 | **Waterfall + inspector** | Shared time axis; click any span → drawer with input, output, duration, subagent task/summary/files, transcript link | 1d | DV-031 |
| `[x]` | DV-033 | **Responses tab** | Every `afterAgentResponse` for the request in order, redacted | 0.5d | DV-012 |
| `[x]` | DV-034 | **Replay mode** | A recorded trace plays at real speed, badged *Recorded* | 0.5d | DV-031 |

### Phase E — Coach (AI feedback)

| Status | ID | Task | Acceptance criteria | Effort | Depends |
|---|---|---|---|---|---|
| `[x]` | DV-040 | **Review skill reads traces** *(AI)* | `agent-spec-session-review` rubric consumes spans; every finding cites a `span_id`; writes `reviews/<conversation_id>.json` with `model`, `rubric_version`, `evidence[]` | 1d | DV-010 |
| `[x]` | DV-041 | **Coach view** | Measured lag panel (p50/p95 per span kind, failure rate, guard blocks, compactions); AI top-3 issues with trend; hover highlights spans; "copy fix prompt" | 1.5d | DV-040, DV-031 |

### Phase F — Learning

| Status | ID | Task | Acceptance criteria | Effort | Depends |
|---|---|---|---|---|---|
| `[x]` | DV-050 | **Recurrence metric** *(exact)* | For each fact/experience: matching findings in N sessions before vs after creation; API + test with fixed fixtures | 1d | DV-040 |
| `[x]` | DV-051 | **Learning view** (absorbs P3-017) | Recurrence chart; facts over time; promotions; injections per session; flat results shown as flat | 1d | DV-050 |

### Phase G — Extensibility

| Status | ID | Task | Acceptance criteria | Effort | Depends |
|---|---|---|---|---|---|
| `[x]` | DV-055 | **Skill `dashboard:` frontmatter** (Catalog reads `dashboard:` (three skills annotated) and shows the icon; the orchestration graph shows category and icon, checks declared `emits` against the request, and adds planned nodes for declared `steps` that did not run) | Catalog and graph use `category`, `icon`, `emits`, `steps`; skills without it get defaults; three existing skills annotated | 0.5d | DV-021 |
| `[x]` | DV-056 | **Generic panels** *(plumbing)* | `metrics/panels/<skill>/*.json` in `kpi`/`table`/`timeline` shapes with required `provenance` render in Project › Panels; schema validated; one example skill writes one | 1d | DV-021 |
| `[x]` | DV-057 | **Typed handoff display** (pulls P4-013 forward; schemas for search, verify and reviewer in `agents/handoffs/`, validated by `bin/aspec_platform/handoffs.py`; P4-013 keeps the RCA/implement shapes) | Subagent spans show typed input/output when a schema exists | 1d | DV-032 |
| `[x]` | DV-058 | **Knowledge graph view** (redoes CP-031) | `react-force-graph-2d`, lazy; click shows blast halo and callers; search jumps to node | 1d | DV-021 |
| `[x]` | DV-059 | **"Show your skill in five minutes" doc** | Section in `docs/DASHBOARD.md` that a new skill author follows end to end | 0.25d | DV-055, DV-056 |

### Phase H — Demo

| Status | ID | Task | Acceptance criteria | Effort | Depends |
|---|---|---|---|---|---|
| `[x]` | DV-060 | **Demo script + recorded trace** (demo.md rewritten to §14.8 with no fixed figures; Replay works on any stored trace. Recorded live IDE trace with two subagents and a stop event is stored; see docs/evidence/DV-060.md) | `demo.md` rewritten to §14.8; recorded trace for Replay; numbers in the script read from this repo | 0.5d | DV-034, DV-041, DV-051 |
| `[x]` | DV-061 | **Playwright smoke** | Live → request → inspector → Coach → Learning runs green against fixture data | 1d | DV-060 |
| `[x]` | DV-062 | **Accessibility and budget pass** | WCAG AA both themes; reduced motion; initial bundle under 400 KB gzip | 0.5d | DV-061 |

Total ≈ 24.5 days. Minimum demo cut (≈ 17 d): Phase A, DV-010, DV-012, DV-013, DV-020, DV-021, DV-030–DV-034, DV-040, DV-041, DV-060.

## Slice 6e — Measured context budget (2026-11-13)

> Evidence: [`docs/evidence/CB-001.md`](docs/evidence/CB-001.md) (one file for the five rows). Chosen from data, not a backlog row: cache reads are 69.5% of the weighted bill across 413 local sessions, and context grows 4.7x per session.

| Status | ID | Task | Acceptance criteria | Effort |
|---|---|---|---|---|
| `[x]` | CB-001 | **Context budget arithmetic** *(exact)* | `bin/aspec_platform/context_budget.py` + `cursor_sessions.context_usage()`: Cursor's `contextTokensUsed` and `promptTokenBreakdown`, subagents excluded from the floor; break-even with the `agent-spec-tokens.py` weights; `/api/context`, `context` on `/api/conversations` rows and `/api/requests/<id>`; `tests/test_context_budget.py` | 0.5d |
| `[x]` | CB-002 | **Stop-hook reset nudge** *(hook; exact)* | One `followup_message` per chat naming `/agent-spec-compact` with the measured numbers, only on a `reset` verdict; loaded by path (DEC-03); `AGENT_SPEC_CONTEXT_NUDGE=0` opt-out; tests | 0.25d |
| `[x]` | CB-003 | **Context UI** | Request › Context tab, header chip, Coach › Context budget, Sessions row chip; every figure through `<Num>`; honesty test covers both views; checked live | 0.5d |
| `[x]` | CB-004 | **Warm-resume digest** *(hook; pulls the digest half of P4-009 forward)* | Digest reads the newest dated snapshot section (title, load, open), capped at 600 B; test | 0.25d |
| `[x]` | CB-005 | **AF-004 nudge fix** | Snapshot nudge marker written only when it fires; `tokens` dict no longer compared to an int; regression test | 0.1d |

## Slice 6f — Harness automation (2026-11-14)

> Evidence: [`docs/evidence/HA-001.md`](docs/evidence/HA-001.md) (one file for the six rows). Audit of scripts that a person or the model had to remember to run: each row moves one into a hook. Every row is *plumbing* (DEC-15): no judgement moves into code.

| Status | ID | Task | Acceptance criteria | Effort |
|---|---|---|---|---|
| `[x]` | HA-001 | **Snapshot follow-up runs the skill** *(plumbing)* | The long-chat `stop` follow-up is the slash command `/agent-spec-snapshot` itself, not a sentence asking for it; still one per chat; test asserts the exact message | 0.1d |
| `[x]` | HA-002 | **Mid-session graph refresh** *(plumbing)* | `afterFileEdit` and a `Shell` `postToolUse` write `.agent-spec/.graph-dirty`; the next `stop`/`sessionEnd` removes it and starts `graphify-build.py --quiet` detached (the builder's own lock handles overlap); no marker, no build; tests | 0.25d |
| `[x]` | HA-003 | **Snapshot rotation on session end** *(plumbing)* | `sessionEnd` runs `agent-spec-memory.py rotate` (no-op under its threshold), bounded by a 3 s timeout, fail-open; `stop` does not; test | 0.1d |
| `[-]` | HA-004 | **Auto-advance SDLC gates from `stop`** | Dropped: `agent-spec-sdlc` makes every gate a separate human approval ("One gate per invocation. Do not chain."), and a `followup_message` is submitted without one. The session-start digest already shows the pipeline state | — |
| `[x]` | HA-005 | **One-command project readiness** *(plumbing)* | `bin/agent-spec-ensure.py`, run from the clone through the root marker: registers the project when it is unregistered, its hooks are not merged, its rules file is missing or older than the package VERSION; builds a missing graph; reports `next: /agent-spec-onboard` from the installer's flag. `--check` and `AGENT_SPEC_AUTO_REGISTER=0` change nothing; refuses `$HOME` and `/`. `agent-spec-raw-code-full` §0, the router and `CURSOR.md` call it instead of prose; tests | 0.5d |
| `[x]` | HA-006 | **Automations panel** *(plumbing)* | Hooks and HA-005 append one row per run to `.agent-spec/metrics/automation.jsonl` (not `events.jsonl`, which the trace builder turns into conversations) and skip any id in `.agent-spec/automation.json` `disabled`. `GET/POST /api/automations` (POST behind the token, origin and content-type guards). Project › Automations: measured run counts, last status, run log, one switch per automation; an environment opt-out locks its switch; honesty test | 1d |

## Slice 7 — Flywheel + security (dashboard surfaces)

## P2 — Continuous Self-Learning Flywheel

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[x]` | L-001 | **Experience store** | `agent-spec-receipt.py` (session-end hook) appends one line to `.agent-spec/experience.jsonl`: task, tokens, gates passed, retries, corrections, injected facts; hub-runner `finish` adds workflow runs. Absorbs O-008 | 1d |
| `[x]` | L-002 | **`agent-spec-learn` skill** | One skill, three modes: distill (accepted corrections -> facts via `agent-spec-memory.py`), recall (top 3 past experiences for the task), propose (>= 3 reuses -> `skill-proposals/`, publish needs human approval). No Python. Absorbs L-003, L-006 | 1.5d |
| `[-]` | L-003 | **Pre-run experience retrieval** *(merged into L-002)* | `recall` mode of the learn skill; digest unchanged | - |
| `[-]` | L-004 | **Learning trend telemetry** *(merged into D-012)* | Trend line on the Home page | - |
| `[x]` | L-005 | **Fact schema v2** *(new)* | Optional `confidence`, `expires`, `provenance`, `version`, `supersedes`, `status`; backward compatible; digest skips non-active | 1d |
| `[-]` | L-006 | **Skill proposals** *(merged into L-002)* | `propose` mode of the learn skill | - |

---

## P2 — Enterprise Security & CLI Tooling

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[x]` | S-001 | **Blast-Radius CLI Wrapper** | `agent-spec-blast-radius --file <path>` colored terminal output over `graphify-cli` | 0.5d |
| `[x]` | S-002 | **Secrets & Sensitive Path Quarantine** | `preToolUse` hard-blocks `.env*`, credentials; events visible in D-022 | 0.5d |
| `[x]` | S-003 | **Dashboard auth + ingest redaction** | Host-header check + per-launch token in the stdlib server; `redact.py` corpus stays green | 0.5d |
| `[x]` | S-004 | **Context threshold proactive nudge** *(new)* | `cursor-pre-tool-use.py` tracks session token footprint; nudges to run `/agent-spec-compact` when session >80k tokens | 0.5d |
| `[x]` | S-005 | **MCP schema bloat audit in doctor** *(new)* | `agent-spec-doctor.py` measures token footprint of registered MCP tool schemas; warns if always-on definitions exceed budget | 0.5d |

---

## Slice 8 — JIRA RCA & three workflows (runs in dashboard)

> Beat 666 BugBot on AUTO-3807 via orchestration + Graphify + eval — not a forked 97 KB skill.

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[-]` | B-001 | **666 tool adapters** *(dropped)* | Deterministic tools are `ai: false` steps (a shell command in the step prompt); no wrapper code | - |
| `[-]` | B-002 | **Graphify in RCA** *(merged into B-006)* | A graph step in the RCA workflow skill | - |
| `[x]` | B-003 | **AUTO-3807 golden eval (skill)** | `agent-spec-wf-eval` skill: golden-ticket CSV, runs the RCA workflow per row, AI-judge step scores strict/directional % vs BugBot baseline; pass/fail gate. Absorbs O-013 | 2d |
| `[x]` | B-004 | **Governed examples seed** | `reviewed-examples/` + Jira label convention; data only, referenced by the RCA skill | 0.5d |
| `[-]` | B-005 | **Log Analyzer compose** *(merged into B-006)* | A log-parse step in the RCA workflow skill | - |
| `[x]` | B-006 | **`agent-spec-wf-rca` workflow skill** | `/agent-spec-wf-rca <KEY>`: Jira via MCP fetch step -> graph context + blast radius -> log parse -> root cause with `path:line` citations; run visible in D-021. Absorbs B-001, B-002, B-005, B-007 | 2d |
| `[x]` | B-006.1 | **Deterministic MCP output filter** *(new)* | Fetch steps in `agent-spec-wf-rca` (and Jira/MCP fetchers) pre-filter API responses to essential keys (`key`, `summary`, `symptom`, `components`) via CLI/Python before LLM context injection, avoiding 50–100 KB payload dumps | 0.5d |
| `[-]` | B-007 | **RCA entry skill/CLI** *(merged into B-006)* | The workflow skill is the entry point | - |
| `[x]` | B-008 | **`agent-spec-wf-pr-review` workflow skill** | Diff -> review -> validation steps; reuses the `review-pr` and `agent-spec-review` skills | 1.5d |
| `[x]` | B-009 | **Workflow #3 (skill)** | Pick at Slice 8 kickoff; ships as `agent-spec-wf-<name>` | 1.5d |
| `[-]` | B-010 | **Headless CI smoke** *(deferred to Phase 3)* | Cursor CLI in CI only if a need appears (DEC-12) | - |

---

## Slice 9 — Orchestration engine (gated: after Slice 1)

> Extended O-021..O-054 (AgentCore, gateway MCP): `docs/platform-design/AGENT-HUB-PLAN.md` Phase 3.

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[x]` | O-001 | **Workflow schema validator** | `agent-spec-run.py validate` checks the `steps` block of a `agent-spec-wf-*` skill (DEC-12) | 1d |
| `[x]` | O-002 | **Run envelope + run dir** | `AgentResult` under `.agent-spec/runs/<id>/` | 1d |
| `[x]` | O-002.1 | **Checkpoint + resume** *(new)* | `checkpoint.json` + step idempotency keys; `resume` never re-runs finished steps | 1d |
| `[x]` | O-003 | **Deterministic steps** | `ai: false` steps run a shell command from the step prompt; non-zero exit fails the step. In the hub-runner skill, no runner code. Live run owed | 1d |
| `[x]` | O-004 | **AI steps (Cursor Task)** | `ai: true` steps run as Task subagents (`agent:`). In the hub-runner skill. Live run owed | 1d |
| `[-]` | O-005 | **Intent router** *(covered by Cursor)* | Cursor skill routing on descriptions + the `agent-spec` router skill | - |
| `[x]` | O-005.1 | **Strategy + model + budget policy** *(new)* | Tier escalation on retry, `--budget-usd`, parallel vs serial by `writes` overlap; all in the hub-runner skill. Live run owed | 0.5d |
| `[x]` | O-006 | **Human gates** | `gate: human` -> chat approval + gate events. In the hub-runner skill. Live run owed | 0.5d |
| `[x]` | O-007 | **Parallel fan-out** | Parallel Task calls for independent ready steps with disjoint `writes`. In the hub-runner skill. Live run owed | 0.5d |
| `[-]` | O-008 | **Experience write** *(merged into L-001)* | hub-runner `finish` feeds the experience store | - |
| `[-]` | O-009 | **Local registry stub** *(dropped)* | `skills/agent-spec-wf-*` is the registry | - |
| `[x]` | O-010 | **Dashboard run ingest** | Ingestor reads `.agent-spec/runs/*/events.jsonl` into the D-002 tables | 1d |
| `[-]` | O-011 | **Contracts (Pydantic)** *(dropped, DEC-12)* | Stdlib-only; step output shapes live in the skill prompts | - |
| `[-]` | O-012 | **Observability hooks** *(dropped)* | run_id is the trace id; Langfuse stays in Phase 3 (P3-016) | - |
| `[-]` | O-013 | **Eval gate in workflow** *(merged into B-003)* | The eval skill returns pass/fail | - |
| `[x]` | O-014 | **Fetch steps (MCP)** | AI steps call Cursor MCP tools (Jira, Bitbucket) named in the step prompt; step-end records the output. Convention in the hub-runner skill. Live run owed | 0.5d |
| `[x]` | O-015 | **Workflow catalog** | RCA + PR + #3 listed in `skills/README.md`; `agent-spec-lint-refs.py` clean | 0.5d |
| `[x]` | O-016 | **Sub-agent skill binding** | `skill:` step key (validated by `agent-spec-run.py`) passed to the Task prompt. Live run owed | 0.5d |
| `[x]` | O-017 | **Partial failure status** | success / partial / failed in D-021 | 0.5d |
| `[x]` | O-018 | **Retry policy** | Per-step retries, `retry` events, model escalation on the 2nd retry. In the hub-runner skill. Live run owed | 0.5d |
| `[x]` | O-018.1 | **Error & traceback sanitization cap** *(new)* | In `agent-spec-run.py` (`step-end`), cap and sanitize step `--error` and stderr payloads to ≤1,000 chars (head/tail, strip giant stack traces/HTML) so failed steps do not poison context | 0.5d |
| `[x]` | O-019 | **Workflow versioning** | Version pin stored per run | 0.5d |
| `[x]` | O-020 | **Orchestration smoke** | Run `agent-spec-wf-example` end to end in Cursor, attach the run id as evidence; selftest runs `validate` on every `agent-spec-wf-*` | 0.5d |

---

## Slice 9b — Phase 2 release

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[x]` | T-041 | **Release v2.0.0** | Dashboard live; 3 workflow skills; learning trend (MASTER-PLAN P2 exit) | 0.5d |

---

# Phase 3 — Enterprise (v3.0.0)

## Slice 10 — Knowledge mesh & registry

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[~]` | P3-001 | **Multi-repo Graphify** (2026-11-13: `bin/graphify-mesh.py` add/remove/build/stats, `graphify-build.py --out` and `unresolved_imports`, exact-FQN cross-repo edges; 3-repo fixture connects in `tests/test_graph_mesh.py`. On 10 local repos: 16,113 nodes, 0 import-level cross-repo edges, because none imports another, so real connectivity needs P3-002 http/message matching. Evidence: docs/evidence/P3-001.md) | ≥3 repos in connected graph | 3d |
| `[x]` | P3-002 | **Cross-repo blast radius** (step 1 of 3 done 2026-11-13: graph 5.2 `routes` with verbs and joined class prefixes for JAX-RS, Spring, Micronaut, NestJS, servlets and web.xml, plus MicroProfile REST-client targets. On local repos: project-x 0 -> 347 endpoints, zoom 0 -> 173, no endpoint lost on a Spring repo. Step 2 done the same day: graph 5.3 `http_calls` {verb, target, path, via}; Feign and MicroProfile client interfaces are now calls, not served routes (project-x 372 -> 341 routes, 31 moved); URL literals count only in files that make HTTP calls (project-x calls 278 -> 103, zoom 306 -> 34). Step 3 done the same day: `graphify-mesh.py build` adds cross-repo `http` edges (service identity, then route path, then gateway suffix; path-only matches are `http_ambiguous`) and `message` edges by topic, and `graphify-mesh.py query --file` prints a file's cross-repo blast radius; 15 mesh tests pass. On the 10 local repos there are 0 cross-repo edges, because none calls another. Follow-up: Next.js file-system API routes. Evidence: docs/evidence/P3-002.md) | Query spans repo boundaries in CLI + D-025 | 2d |
| `[ ]` | P3-003 | **Index aggregator (MCP)** | Schema per AGENT-HUB-PLAN Central Index | 1d |
| `[ ]` | P3-004 | **Agent registry** | Catalog: agent, version, capabilities | 2d |
| `[ ]` | P3-005 | **Registry in doctor** | Drift vs catalog | 0.5d |
| `[ ]` | P3-006 | **Dashboard multi-repo home** | Per-repo rows on D-012 | 1d |
| `[ ]` | P3-007 | **Self-service repo onboard** | CLI/UI add repo to mesh | 2d |
| `[ ]` | P3-008 | **IDE expansion doc** | Gemini CLI / VS Code path | 1d |
| `[ ]` | P3-009 | **Gateway audiences** | cursor / bot / harness in registry | 1d |
| `[ ]` | P3-010 | **AgentCore port checklist** | One workflow → agentcore-agents | 2d |

## Slice 11 — Audit & cross-org learning

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[ ]` | P3-011 | **Session audit export** | Session, agent, outcome, gates — immutable | 2d |
| `[ ]` | P3-012 | **Approval trails** | Experience promote / external post gated | 2d |
| `[ ]` | P3-013 | **Policy gates design** | Enterprise Cedar/policy hook | 2d |
| `[ ]` | P3-014 | **Cross-repo experience** | Repo A fix retrievable in repo B | 3d |
| `[ ]` | P3-015 | **Org cost dashboard** | Aggregate tokens without raw source upload | 2d |
| `[ ]` | P3-016 | **Langfuse optional stack** | docker-compose per ADMIN-UI.md | 2d |
| `[ ]` | P3-017 | **Experience browser** | Promote/deprecate trusted experiences | 2d |
| `[ ]` | P3-018 | **Compliance demo path** | Audit + registry + mesh leadership walkthrough | 1d |

## Slice 11b — Phase 3 release

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[ ]` | T-042 | **Release v3.0.0** | MASTER-PLAN P3 exit gate | 0.5d |

---

# Phase 4 — Autonomous Bots (v4.0.0) — *Inspired by Cursor Grok Bot*

> **Design influence:** Cursor's Grok Bot model — always-on cloud agents with persistent
> environments, learned routines, tiered safety boundaries, and structured bot-to-bot handoffs.

## Slice 12 — Always-on execution

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[ ]` | P4-001 | **Daemon runner architecture** | Design doc for persistent background agent process (local daemon or container) that outlives the IDE session; lifecycle: start / pause / stop / health-check | 2d |
| `[ ]` | P4-002 | **Local daemon implementation** | `agent-spec-daemon.py` — background process that picks up queued workflows from `.agent-spec/queue/`, executes via `agent-spec-run.py`, writes results to SQLite dashboard; survives terminal close | 3d |
| `[ ]` | P4-003 | **Cloud sandbox design** | Architecture for optional remote execution environment (container / VM) with secure credential vault, browser automation, and persistent file system; local-first default preserved | 2d |
| `[ ]` | P4-004 | **Cloud sandbox MVP** | Dockerfile + docker-compose for self-hosted sandbox; `agent-spec-daemon.py --cloud` flag routes execution to container; health endpoint; dashboard ingest from remote runs | 3d |

## Slice 13 — Routine synthesis & environment checkpoints

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[ ]` | P4-005 | **Session recording format** | Define schema for recording a successful SDLC session: graph entry points, test commands, file patterns, gate track, tool sequence; stored as `.agent-spec/recordings/<session-id>.json` | 1d |
| `[ ]` | P4-006 | **Routine synthesizer** | `agent-spec-synthesize.py` — reads a session recording and generates a parameterized skill (markdown + step YAML) in `.agent-spec/skills/`; variables extracted from file paths, class names, test names | 3d |
| `[ ]` | P4-007 | **Routine replay & validation** | Synthesized routine can be executed via `agent-spec-hub-runner`; replay produces equivalent diff on a clean branch; selftest validates replay fidelity | 2d |
| `[ ]` | P4-008 | **Environment checkpoint schema** | Machine-readable checkpoint: `{ git_sha, graph_hash, branch, gate_track, test_results: {pass: [...], fail: [...]}, active_files, memory_hash }` — written on session end and snapshot | 1d |
| `[ ]` | P4-009 | **Warm resume from checkpoint** (digest half done in CB-004: the sessionStart digest carries the last snapshot's title, files to load and open items) | `agent-spec-resume.py` — reads `checkpoint.json`, reconstructs session state (digest, graph, memory, gate position) in < 2 seconds; new Cursor chat starts with full context | 2d |
| `[ ]` | P4-010 | **Routine scheduling** | Daemon supports cron-like scheduling for synthesized routines (e.g., nightly regression RCA, weekly dependency audit); schedule config in `.agent-spec/schedules.yaml` | 2d |

## Slice 14 — Risk-tier gating & structured handoffs

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[ ]` | P4-011 | **Blast-radius classifier** | `agent-spec-risk.py` — classifies tool actions into tiers using graph topology: Tier 0 (reads, tests) / Tier 1 (new files, non-core modules) / Tier 2 (migrations, shared APIs, core architecture) / Tier 3 (destructive ops, credential access) | 2d |
| `[ ]` | P4-012 | **Risk-tier preToolUse integration** | Enhanced `preToolUse` hook consults `agent-spec-risk.py`; Tier 0–1 auto-allow, Tier 2 log + soft warning, Tier 3 blocks until explicit user approval; configurable per project via `.agent-spec/risk-policy.yaml` | 2d |
| `[ ]` | P4-013 | **Handoff contract schema** | JSON schema for inter-agent handoffs: `SearchResult { rca, affected_files, graph_paths, confidence }`, `ImplementResult { diff, tests_added, tests_passed }`, `VerifyResult { verdict, evidence, coverage_delta }` | 1d |
| `[ ]` | P4-014 | **Typed handoff in orchestrator** | `agent-spec-hub-runner` validates step outputs against handoff schemas before passing to next step; schema violations fail the step with actionable error | 2d |
| `[ ]` | P4-015 | **Handoff context pruning** | Subagents receive only their typed input schema — zero narrative carry-over; measured context reduction vs. current pass-through | 1d |
| `[ ]` | P4-016 | **Risk + handoff dashboard panel** | D-030: Risk tier distribution (pie chart); D-031: Handoff flow visualization (Sankey / sequence); both in the localhost dashboard | 2d |

## Slice 14b — Phase 4 release

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[ ]` | T-043 | **Release v4.0.0** | MASTER-PLAN P4 exit gate: ≥ 1 headless workflow, routine synthesis proven, checkpoint resume, risk-tier gating active | 0.5d |

---

# Phase 5 — Agent Marketplace & Ecosystem (v5.0.0)

## Slice 15 — Bot marketplace & third-party integrations

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[ ]` | P5-001 | **Bot template format** | Spec for distributable agent template: metadata (name, description, author, version, tags), required skills, risk policy, graph requirements, default schedule; packaged as `.agent-spec-bot/` directory | 2d |
| `[ ]` | P5-002 | **Template catalog & install** | `agent-spec-marketplace.py list / install / uninstall` — discovers templates from local dirs and remote registries; installs into `.agent-spec/bots/`; doctor validates dependencies | 3d |
| `[ ]` | P5-003 | **Built-in bot templates** | Ship ≥ 5 templates: RCA Specialist, Security Reviewer, Dependency Auditor, Migration Assistant, Onboarding Bot; each with tests and documentation | 5d |
| `[ ]` | P5-004 | **Integration connector framework** | Plugin architecture for external service connectors (Slack, email, webhooks, monitoring); connector interface: `on_event()`, `send_result()`, `health_check()`; registry in `.agent-spec/connectors/` | 3d |
| `[ ]` | P5-005 | **Slack connector** | Bot receives Slack messages / slash commands, triggers workflows, posts results back; OAuth2 + webhook setup documented | 3d |
| `[ ]` | P5-006 | **Webhook connector** | Generic inbound webhook (GitHub, CI/CD, monitoring alerts) triggers workflow execution; outbound webhook posts results to configurable endpoints | 2d |
| `[ ]` | P5-007 | **Email connector** | Bot monitors inbox (IMAP) for trigger patterns, executes workflows, replies with results; supports templates for formatted responses | 2d |
| `[ ]` | P5-008 | **Connector dashboard panel** | D-035: Connector status, event history, error rates; integrated into localhost dashboard | 1d |

## Slice 16 — Federation & ecosystem governance

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[ ]` | P5-009 | **Federation protocol** | Spec for cross-organization agent communication: discovery, capability negotiation, trust levels, encrypted handoffs; builds on Phase 3 cross-repo + Phase 4 handoff contracts | 3d |
| `[ ]` | P5-010 | **Community routine sharing** | Publish/subscribe model for synthesized routines; `agent-spec-marketplace.py publish / subscribe`; attribution tracking; opt-in sharing with access control | 3d |
| `[ ]` | P5-011 | **Trust & sandboxing for 3P bots** | Third-party bot templates run in sandboxed mode by default (restricted file access, no credential access, read-only graph); trust promotion requires explicit review | 2d |
| `[ ]` | P5-012 | **Usage metering & billing hooks** | Track bot execution time, token usage, API calls per bot template; export to billing systems; support for commercial bot marketplace | 2d |
| `[ ]` | P5-013 | **Ecosystem health dashboard** | D-040: Org-wide view of all bots, connectors, shared routines, federation links, trust levels; leadership-ready | 2d |
| `[ ]` | P5-014 | **Federation demo** | End-to-end demonstration: bot in Org A discovers routine from Org B, negotiates handoff, executes cross-org workflow with audit trail | 2d |

## Slice 16b — Phase 5 release

| Status | ID | Task | Acceptance Criteria | Effort |
|--------|----|------|---------------------|--------|
| `[ ]` | T-044 | **Release v5.0.0** | MASTER-PLAN P5 exit gate: marketplace ≥ 10 templates, ≥ 2 third-party integrations, federation demonstrated | 0.5d |

---

## Phase 0 — Foundation (done)

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| `[x]` | A-001 | Layer 1: `post-checkout`, `post-merge`, `post-rewrite` | `hooks/manage-git-hooks.py` |
| `[x]` | A-002 | Layer 2: `ensure_fresh_graph()` on sessionStart | `bin/agent-spec-digest.py` |
| `[x]` | A-003 | flock + atomic writes | `bin/graphify-build.py` |
| `[x]` | A-004 | Test suite [10/10] | `tests/test_manage_git_hooks.py`, `bin/agent-spec-selftest.sh` |

---

## Open decisions

| Item | When to decide |
|------|----------------|
| Workflow #3 (B-009) | Slice 8 kickoff — RCA follow-on, PR, FireFlow/AFF, or support triage |
| ~~Dashboard frontend stack~~ | **Resolved 2026-10-31 (DEC-12):** stdlib `http.server` + one static page, no build step, no third-party import |
| O-021..O-054 detail | AgentCore deploy — track in `docs/platform-design/AGENT-HUB-PLAN.md` |
| Cloud sandbox: self-hosted vs managed | Slice 12 kickoff — container on dev machine vs. optional hosted service |
| Routine synthesis: full replay vs delta-only | Slice 13 kickoff — full branch replay or diff-only application |
| Federation protocol: push vs pull | Slice 16 kickoff — agents push routines to peers vs. pull from registry |

---

*Algosec Cursor AI · Update this file when closing items. Last updated: 2026-11-06 (Phase 4 + Phase 5 added — Grok Bot inspired).*
