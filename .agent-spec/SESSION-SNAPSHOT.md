## 2026-11-13 (evening) — Selftest repaired, snapshot rotate fixed

### Done
- `bin/agent-spec-selftest.sh:68`: the digest `--cursor-hook` call now reads `< /dev/null`, so the selftest no longer hangs in a background shell.
- `bin/agent-spec-selftest.sh:145`: the lint-refs capture ends in `|| true`, so a non-zero lint-refs exit is reported as a FAIL instead of silently aborting the script before section [13].
- The dangling reference (`.agents/skills/agent-spec-prompt-audit/SKILL.md names hooks/pre-tool-use.py`) was not in the source: `skills/agent-spec-prompt-audit/SKILL.md:27` already names `hooks/cursor-pre-tool-use.py`. It came from `.agents/`, a gitignored, stale installed copy of the skills. `bin/agent-spec-lint-refs.py` now adds `.agents` to `SKIP_DIRS`; lint-refs reports `every path and skill name resolves`.
- Snapshot rotate (the pending chip): `bin/agent-spec-memory.py` split sections only on `# Session Snapshot`, so it saw 2 sections in an 82189 B file. New `SECTION_RE` also recognises `## <date>` and `## Session <date>`; earlier `## Archived sections` blocks are extracted and merged into a single index at the end of the file; `_summary_line` falls back to the first content line for sections without `## Session Summary`. New test `test_rotate_splits_dated_headings_and_merges_index` in `tests/test_memory.py`; 20 passed. Dry run on a copy: 29 sections found, 27 archived, 82189 B → 10777 B. `.agent-spec/bin/agent-spec-memory.py` synced from `bin/`.
- Full selftest, first complete run (section [13] executed): **74 OK, 1 FAIL** — `CURSOR.md 5607 B grew past the 4600 B always-on budget`.

### Corrections
- Earlier today the fix plan said to change the reference to `hooks/cursor-pre-tool-use.py`; the source already had that. The real defect was lint-refs scanning `.agents/`.
- A `cp` this session briefly created `.agent-spec/bin/agent-spec-lint-refs.py`; it was removed (install.sh does not ship lint-refs).

### Open
- `CURSOR.md` budget FAIL remains; planned for the next rules release (DV-004).
- DEC-16 still awaiting approval; Slice 6d Phase A (DV-001 onward) not started.
- Nothing committed. Uncommitted: `bin/agent-spec-selftest.sh`, `bin/agent-spec-lint-refs.py`, `bin/agent-spec-memory.py`, `tests/test_memory.py`, `dashboard_overhaul.md` (§14), `todo-plan.md` (Slice 6d), graph files, this snapshot.

### Next session: load these files
- `todo-plan.md` Slice 6d
- `dashboard_overhaul.md` §14
- `hooks/cursor-event.py`, `hooks/merge-hooks-json.py` (DV-001)

## 2026-11-13 (night) — v3 request-trace control plane built (Slice 6d)

### Done
- **Hook spine (DV-001):** `hooks/cursor-event.py` rewritten on Cursor's documented hook contract (`hook_event_name`, `conversation_id`, `generation_id`, `workspace_roots[0]`, per-event fields); registered for nine events; guard denies add `guard` rows. `AGENT_SPEC_HOOK_RECORD=1` saves one raw payload per event for DV-002.
- **Trace model (DV-010..013):** `schema_v3_traces.sql` (traces, spans), `bin/aspec_platform/traces.py` (pure builders for hook rows and Cursor store), `observe.py` (coach issues, recurrence, panels, catalog). Routes `/api/requests[/<id>]`, `/api/live` (SSE), `/api/coach/*`, `/api/learning`, `/api/panels`, `/api/catalog`. CLI `agent-spec-platform.py trace`.
- **Cursor store (DV-003):** per-OS resolver; this Cursor version has no `composerHeaders` — sessions live in `cursorDiskKV` `composerData:*` / `bubbleId:*`. History now shows 22 sessions / 28 requests on this WSL machine (was 0).
- **UI (DV-020..062):** four spaces Live/Coach/Learning/Project; React Flow orchestration graph, waterfall, inspector, responses, review, replay; force-graph knowledge view; Radix+cva primitives; initial bundle 149.6 KB gzip. Vitest honesty test, Playwright smoke + axe (both themes) all green.
- **AI-first:** `agent-spec-session-review` rubric 2.0.0 (span-cited findings, fixed categories, fix prompts, panel); `agent-spec-memory.py add --addresses` for the Learning recurrence. One real review written for conversation f0e15b1f (grade C, 4 findings).
- Tracker: 22 DV rows `[x]` with `docs/evidence/DV-*.md`; `[~]` DV-002, 004, 005, 020, 055, 060; DV-057 `[ ]`. CP-015/021/025/031/040 → `[-]` with pointers. DEC-16 in MASTER-PLAN; README version/skill count; DASHBOARD.md and demo.md rewritten.

### Corrections
- This section was first spliced into the middle of the (evening) section: the insert matched `## Archived sections` inside a backticked sentence, not the heading. Moved here; no other text changed.
- Selftest section [13] silently skipped every suite after `test_api` (a suite read the loop's stdin); fixed with `</dev/null`. Those 6 suites plus the 2 new ones pass.
- Removed the Sessions "Token Flow" tab: every figure in it was hard-coded. Tour step figures removed.
- My first hook draft imported `aspec_platform.redact`; `test_platform_guard` forbids core hooks importing the extra — redaction is inline now.
- Graph node clicks were swallowed when hover rebuilt the node array; highlight now travels by context.

### Open
- DV-002: record live payloads from Cursor (`AGENT_SPEC_HOOK_RECORD=1`), then replace `tests/fixtures/hooks/*.json`; confirm how a skill invocation appears.
- Selftest still fails one check: `CURSOR.md` 5607 B > 4600 B (deferred to the next rules release).
- DV-057 typed handoffs; v2 pages not ported to primitives nor under the honesty test; 31 memory facts have no `addresses:` (Learning chart empty until linked).
- Nothing committed; working tree mixes this session with earlier uncommitted edits.

### Next session: load these files
- `todo-plan.md` Slice 6d, `dashboard_overhaul.md` §14, `docs/DASHBOARD.md`, `bin/aspec_platform/traces.py`.

## Archived sections
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261031-184403.md`. Nothing is deleted.
- **2026-10-27T13:14:18** — algosec-agent-spec installed.
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261113-140506.md`. Nothing is deleted.
- **2026-10-28T13:56** — Phase 1 (v1.1.0) built and verified: Slices 1-4, T-054, T-040. Selftest sections [1]-[12] pass; doctor --stric
- **2026-10-28 (afternoon) — Phase 1 completion review** — Re-verified Phase 1 exit gate: `bin/agent-spec-selftest.sh` all pass (unsandboxed; section [3] fails in the re
- **2026-10-28 (evening) — Onboarding made automatic** — Onboarding is now an agent-internal step; the user never runs `/agent-spec-onboard` or sees it as pending.
- **2026-10-28 (late evening) — Raw-code skills self-install the harness** — Raw-code preflight now covers install as well as onboarding: no `<ws>/.agent-spec/` → agent runs `"$(cat ~/.cu
- **2026-10-28 (night) — Slice 4c built** — T-059 36 dangling doc refs fixed by editing docs (lint was 36, not the 35 in todo-plan); `agent-spec-lint-refs
- **2026-10-29 — Phase 1 manual verification (developer machine)** — Layer A: User ran `bash bin/agent-spec-selftest.sh` — green.
- **2026-10-31** — no summary
- **2026-10-29 / 2026-10-31 — Unified implementation guide (Phase 2 + 3 design)** — `docs/IMPLEMENTATION-GUIDE.md` (v1.1.0, ~58 KB): single unified HLD + LLD + implementation plan for every pend
- **2026-10-31 (evening) — Phase 2 build started, Cursor-native pivot (DEC-12)** — D-001 `bin/aspec_platform/{schema.sql,db.py,common.py}` + `bin/agent-spec-platform.py init|status|ingest|serve
- **2026-10-31 (evening) — Phase 2 re-baselined to DEC-12 / DEC-13** — Status review: Phase 2 was 15 of 67 rows done, 52 open. The dashboard is Phase 2 (slices 5-6), not Phase 4; th
- **2026-10-31 (night) — D-007 graph symbols + callers built** — D-007 done, test first. `tests/test_graph_symbols.py` (12 tests) failed before the change and passes now. `./b
- **2026-10-31 (late night) — S-003 + D-020 dashboard server built and reviewed** — S-003 and D-020 done, tests first (red: `ImportError: cannot import name 'serve'`, then green). `tests/test_ap
- **2026-10-31 (late night) — D-010 savings calculator + session compare** — `bin/aspec_platform/savings.py` (new): `parse_weights`, `savings`, `sessions`, `compare`. Routes `/api/savings
- **2026-10-31 (late night) — Phase 2 build-out: D-012/D-014/D-021/D-022, L-001, O-010 + workflow skills** — `bin/aspec_platform/ingest.py`: new sources `runs` (O-010: `.agent-spec/runs/*/{run,result}.json` + `events.js
- **2026-11-03 — Framework solidification (skills deferred)** — User priority: agentic framework first (run plumbing, hub-runner coordination, sub-agent recording, transparen
- **2026-11-06 — O-020 live proof & Phase 2 code hardening complete** — O-020 (Orchestration smoke live run): Executed `agent-spec-wf-example` live (`01M6JD36AEKCV8Z95D5DPM1VDA`). Fu
- **2026-11-06 — Dashboard overhaul v2 plan (docs only, no code)** — Reviewed v1 `dashboard_overhaul.md` (48 KB). Found: invented figures and features ("$1,428.60 saved", "0 secur
- **2026-11-06 — Dashboard overhaul final review, coverage pass, Cursor CLI contract (docs + one fixture, no code)** — Final review of `dashboard_overhaul.md` against the repo. Verdict: approve DEC-14 with
- **2026-11-06 (evening) — Grok Bot learnings incorporated; Phase 4 & Phase 5 added to roadmap** — Analyzed Cursor Grok Bot architecture and operational models (`cursor.com/docs/grok-bot/get-started`).
- **2026-11-07 — Control plane v2 MVP (Slice 6b)** — Governance (CP-000): DEC-14 in `docs/IMPLEMENTATION-GUIDE.md`; Slice 6b in `todo-plan.md`; guard memory supers
- **2026-11-07 (evening) — Slice 6b: exec race, Runs CP-022/023, test hygiene** — `agent_exec.py` stdout race: single reader → `queue.Queue`; `iter_sse` consumes queue only (no second `proc.st
- **2026-11-07 (late evening) — Slice 6b Backlog Completion (CP-007, CP-015, CP-024, CP-025, CP-036, CP-037, CP-040, CP-041, CP-050)** — CP-050 (Log S-004 context nudges): `hooks/cursor-pre-tool-use.py` now logs context threshold nudges to `.agent
- **2026-11-07 (evening) — AI-first realignment (DEC-15), docs only** — Reviewed the v2 implementation against an "AI-first, hooks and skills first" request. No code, tests or deleti
- **2026-11-07 (late evening) — Slice 6c (AI-First Realignment AF-001..AF-008 Completed)** — AF-001 (Hook Event Spine): Created `hooks/cursor-event.py` (fail-open latency floor < 5ms). Recorded hook payl
- **2026-11-07 (night) — CP-042 Legacy v1 Retirement & Clean Up Completed** — Deleted Legacy v1 UI Files: Safely deleted `bin/aspec_platform/ui/index.html`, `dashboard.js`, and `chart.umd.
- **2026-11-07 (late night) — AI-First Autonomous SDLC, Zero-Touch Memory & Subagents** — Zero-Touch Memory Distillation Hook:
- **2026-11-13 — Onboard + index, and a source-checked review of the dashboard plan** — Rebuilt the graph with the repository's own builder (`python3 bin/graphify-build.py --rebuild`):
- **2026-11-13 (later) — Full backlog review and the v3 request-trace dashboard plan** — Reviewed every row in `todo-plan.md`: 118 `[x]`, 25 `[-]`, 3 `[~]` (T-057, T-058, CP-001),
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261113-144719.md`. Nothing is deleted.
- **2026-11-13 (end) — Selftest hang diagnosed; fixes deferred to a new session** — The selftest re-run started at 12:47 hung for over an hour. Cause: `bin/agent-spec-selftest.sh:68`
