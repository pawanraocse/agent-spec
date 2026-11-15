## 2026-11-15 — Gap review of Slice 6g; skill drift sync; headless CLI requests named, closed and hidden

### Done (uncommitted, on top of the uncommitted Slice 6f and 6g work)
- **Gap review of Slice 6g.** Read the diff of `serve.py`, `ingest.py`, `traces.py`, `db.py`, `retrieval.py` and the `agent-spec-ask` skill. `agent-spec-lint-refs.py`: every path and skill name resolves. `agent-spec-ask` was missing from `~/.cursor/skills`, and the installed `agent-spec` and `agent-spec-session-review` were stale.
- **HA-007 skill drift sync.** `bin/agent-spec-ensure.py` gains `skill_gaps()`: it compares each package skill directory, file by file, with `~/.cursor/skills`. When a skill is missing (the six `--lean` SDLC skills excepted) or different, it runs `install.sh --skills-only`, adding `--lean` when none of those six are installed. Output has a new `skills` key (`ok/needed/installed/failed`) and `skill_gaps`. `--check` and the `skills-sync` switch (new row in `automations.REGISTRY`) turn it into a report. It logs one `automation.jsonl` row. Ran it here: 3 skills installed, `check-install.sh` passes.
- **PI-013 indexer symlink guard.** `retrieval.index_files` skips a file whose realpath leaves the project or is a secret path.
- **DV-063 headless requests.** `cursor-agent --print` fires no `beforeSubmitPrompt` and no `stop`, so those requests showed "(prompt not captured)" and stayed RUNNING. `traces.transcript_queries()` reads the `<user_query>` blocks from the event's `transcript_path`: realpath under `~/.cursor` only, 8 MB cap, redacted, 500 chars, cached by mtime and size. `_Builder.recover_prompts()` assigns them only when a chat has exactly one query or as many queries as requests; it sets `prompt_source: transcript`. `finish(now_ms)` marks a request with no `stop` and no event for `AGENT_SPEC_TRACE_IDLE_S` (default 1800 s) as `incomplete`, `status_reason: no stop event`. `hook_traces` rebuilds its cache when a cached `running` request has gone idle.
- **DV-064 CLI runs labelled and hidden.** Hook traces get `origin`: `cli` when `cursor_version` matches `CLI_BUILD` (cursor-agent's date-stamped build, e.g. `2026.11.11-b912975`), else `ide` (the IDE reports semver such as `3.6.21`). `_match` hides `cli` unless `origin=cli|all`. Facet `cli_runs`. `origin` is accepted by `serve.py` and `list_conversations`. Coach `lag`, `observe` skill usage and `retrieval.index_traces` exclude CLI runs. UI: "Show CLI runs (n)" toggle in `RequestFeed`, a "CLI runs" source in `ConversationList`, labels in `RequestView`. Live: 34 requests by default, 46 with CLI runs.
- Tests: `tests/test_ensure.py` (+2), `tests/test_retrieval.py` (+1), `tests/test_traces.py` (+5), `tests/test_automations.py` (registry list). Final: fast platform suite 58, traces+retrieval 49, ensure 10, vitest 21, tsc clean, UI rebuilt.
- `todo-plan.md` rows HA-007, DV-063, DV-064, PI-013 `[x]`; `CHANGELOG.md` entries for all four.

### Corrections to my own earlier work this session
- DV-063 first gave the CLI probe requests the probe prompts, which made scripted runs look like the user's own chats. The user asked where those prompts came from; DV-064 then labelled and hid them.
- The transcript rule first required the query count to equal the request count. The CLI gives one query 2 or 3 generation ids, so 4 requests stayed blank. Extended: a single query names every request of its chat.
- `pkill -f 'agent-spec-platform.py serve …'` matched its own shell and killed the command. Use `pkill -f '[a]gent-spec-platform.py serve'`.
- The background selftest reported 1 failure in `test_automations`: it overlapped the `skills-sync` registry edit. The test now passes on its own; the full selftest was not re-run.

### Open
- Full `bin/agent-spec-selftest.sh` not re-run after the fixes.
- This repo's `.agent-spec/bin/aspec_platform` copy is older than `bin/` (no symlink guard): project copies refresh only on a VERSION change.
- `~/.claude/skills/agent-spec-*` are August–October copies without the preflight section; `install.sh` installs into Cursor only.
- Not run live in Cursor: `/agent-spec-ask`, and rubric 2.1.0 (still no review with a `quality` block). PI-009…PI-012 and the CP-001 live checks are still open.
- One hook request (`8fc0f5bc…`, IDE 3.30.8) has no prompt and no `transcript_path`; it stays "(prompt not captured)".
- Nothing committed. Dashboard running in the background on `127.0.0.1:8765`.

### Load next session
`bin/aspec_platform/traces.py` (`CLI_BUILD`, `transcript_queries`, `_Builder.recover_prompts`, `_Builder.finish`, `hook_traces`, `_match`), `bin/agent-spec-ensure.py` (`skill_gaps`, `ensure`), `ui-src/src/features/RequestFeed.tsx`, `todo-plan.md` Slice 6g.

## 2026-11-15 (later) — Impact tab for the hackathon story; memory injections recorded; review and 10 fixes

### Why
The user ran the dashboard on a `/agent-spec-raw-code-full` request and could not explain the feature: no tokens saved on the request page, the trace looked like "grep, not graphify", and nothing showed memory or self-learning. Investigation: `/api/savings` existed only project-wide (Project → Sessions → Savings, 74,140 tokens estimated); Cursor's hook payloads carry no file content sizes (Read `out` = 82–107 B); graphify calls were drawn as "Shell"; receipts had `facts_injected: null` and `fact_injections` had no rows, so memory use was never recorded. In that trace, 61 of the tool calls (most Grep and Read) ran inside 2 `agent-spec-search` subagents; the main context had 6 calls, the first `graphify context`.

### Done (uncommitted, on top of the uncommitted Slice 6f/6g work)
- **Impact tab** (default tab on a request page): `bin/aspec_platform/impact.py` + `ui-src/src/features/Impact.tsx`, wired into `traces.request_detail` as `impact` (wrapped in try/except so it never breaks the page). Cards: tokens kept out of the chat vs plain Cursor (estimated: subagent-internal tool output, graph query priced as one median indexed file, unread part of ranged reads; bytes ÷ 4); raw-code-full rule checks (measured; `pass: null` = not applicable, left out of the score); memory injected; what agent-spec adds to the prompt (rules/skills/subagent definitions from Cursor's own context breakdown). On the raw-code-full review trace: 17,741 of 20,181 tokens kept out, 4 of 4 rules, harness fixed cost 11,017 tokens.
- **Injected facts recorded.** `hooks/cursor-session-start.py` (copied to `.cursor/hooks/agent-spec-session-start.py`) parses the payload's `conversation_id` and appends `{ts, conversation_id, digest_bytes, facts}` to `.agent-spec/metrics/injections.jsonl`. `ingest.ingest_memory` matches lines to facts by `- [type] subject:` prefix (`match_facts`) into `fact_injections` for every trace of the conversation; `observe.learning` now joins `traces` as well as `requests`. The Impact tab reads injections.jsonl live (`impact.injection_row`), not the table.
- **Graph queries named.** `traces.tool_category()` names a Shell call to `graphify-cli.py` / `agent-spec-memory.py` "graphify <sub>" / "memory <sub>" and stores `category`, `tool_name`, `read_chars`, `file_bytes` on tool spans.
- **Read extent for ranged reads.** `hooks/cursor-event.py` records `read_chars` + `file_bytes` for explicit ranges via `_ranged_extent` (stat only, no decode).
- Docs: `docs/DASHBOARD.md` "Impact tab" section; `CHANGELOG.md` entries.

### Review (high effort) and fixes — all 10 fixed
1. `ingest.ALL` ran memory before traces → injections joined stale traces; `traces` now precedes `memory`. 2. Impact read `fact_injections`, which the server never refreshes → reads injections.jsonl live. 3. Edit spans counted as "other". 4. `SEARCH_TOOL` prefix matched `search_replace`. 5. Any `read*` tool (ReadLints) counted as a file read. 6. Unknown `ranged` treated as whole-file. 7. "Guard rails held" always passed → removed from rules. 8. "Graph before search" failed requests that never searched → n/a. 9. `agent-spec-ensure.py` skill sync forced `--lean` when no lean skill was installed → `install.sh` now writes `~/.cursor/skills/.algosec-agent-spec-lean` on `--lean` and removes it on a full install; ensure passes `--lean` only when the marker exists. 10. Ranged reads decoded the whole file in the hook → stat only.
- Tests: `tests/test_impact.py` (new, in `platform-suites.txt`), `tests/test_cursor_event.py` (+1), `tests/test_ensure.py` (+1), vitest Impact honesty test. Final: pytest 442 passed, fast platform 58, vitest 22, tsc clean, UI build within gzip budget.

### Corrections to my own earlier work this session
- First Impact build defaulted to the Impact tab unconditionally and broke the DV-055 honesty test (it expects the Orchestration graph); the default is now Impact only when `impact` is present without an error.
- Several Impact figures were plain text and failed the provenance (DV-005) check; all wrapped in `<Num>`, fact subjects marked `data-figure-exempt`.
- My first ensure regression test expected a missing-lean-skills full install to stay without them; wrong — no marker means a full install, which correctly restores them.
- Items 1–8 and 10 of the review were defects in code I wrote earlier the same session.

### Open
- Not verified live: a new Cursor chat should show its injected facts on the Impact tab. Chats before 2026-11-15 have none (Cursor transcripts do not carry the digest; no backfill).
- Existing `--lean` installs have no marker yet: the next skill sync adds the six SDLC skills back unless `./install.sh --lean` is re-run once.
- "Kept out of the chat" is re-send savings in the parent context, not lower total billing: subagents still spend tokens. Say so when presenting.
- Hackathon demo not run: same prompt in plain Cursor vs `/agent-spec-raw-code-full`, compare Impact tabs and Project → Sessions → Compare.
- Untracked `retrieval.py`, `signals.py`, `skills/agent-spec-ask/` were outside the review (it covered `git diff HEAD` only).
- Earlier opens still stand: full `bin/agent-spec-selftest.sh` not re-run; project `.agent-spec/bin/aspec_platform` copy older than `bin/`.
- Nothing committed. Dashboard running on `127.0.0.1:8765` (token rotates per launch).

### Load next session
`bin/aspec_platform/impact.py` (`for_request`, `tool_rows`, `rule_checks`, `injection_row`, `injected_facts`), `bin/aspec_platform/traces.py` (`tool_category`, `request_detail`), `bin/aspec_platform/ingest.py` (`ALL`, `match_facts`, `_ingest_injections`), `hooks/cursor-session-start.py`, `ui-src/src/features/Impact.tsx`.

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
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261113-152325.md`. Nothing is deleted.
- **2026-11-13 (evening) — Selftest repaired, snapshot rotate fixed** — `bin/agent-spec-selftest.sh:68`: the digest `--cursor-hook` call now reads `< /dev/null`, so the selftest no l
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261113-175118.md`. Nothing is deleted.
- **2026-11-13 (night) — v3 request-trace control plane built (Slice 6d)** — Hook spine (DV-001): `hooks/cursor-event.py` rewritten on Cursor's documented hook contract (`hook_event_name`
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261113-185521.md`. Nothing is deleted.
- **2026-11-13 (late night) — DV-005, DV-057, DV-055 closed and committed** — Review: of Slice 6d, only DV-002, 004, 005, 020, 055, 057 and 060 were open at session start.
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261113-194426.md`. Nothing is deleted.
- **2026-11-13 (late night, 2) — DV-020, DV-004 closed; DV-002 automated; P3-001 built; P3-002 steps 1–2** — DV-020 `[x]`: the six v2 Project pages (`Home`, `Sessions`, `Runs`, `Knowledge`, `Governance`, `Console`) move
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261113-202816.md`. Nothing is deleted.
- **2026-11-13 (late night, 3) — P3-002 step 3 built; P3-002 closed** — LLD first: added "LLD addendum — P3-002 step 3: cross-repo matching and mesh query" to `docs/IMPLEMENTATION-GU
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261113-204633.md`. Nothing is deleted.
- **2026-11-13 (night, 4) — Status audit; /agent-spec-hook-probe built and run live; two live-payload bugs fixed** — Phases 1–2: 136 `[x]`, 5 `[~]` (T-057, T-058, CP-001, DV-002, DV-060), 0 `[ ]`. Phase 3: P3-002 `[x]`, P3-001 
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261113-211607.md`. Nothing is deleted.
- **2026-11-13 (night, 5) — Dashboard v3 closed; Cursor store unreadable on WSL fixed; Sessions page lists every chat** — DV-002 and DV-060 closed (`[x]`). `subagentStart`/`subagentStop` had been recorded live from the IDE at 19:16,
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261114-063307.md`. Nothing is deleted.
- **2026-11-13 (night, 6) — T-057 closed live: preToolUse follows Cursor's harness** — T-057 ran live with `cursor-agent` 2026.11.11 (`--print --trust --model auto`, `AGENT_SPEC_HOOK_DEBUG=1`). Sli
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261114-073304.md`. Nothing is deleted.
- **2026-11-13 (night, 7) — Slice 6e: measured context budget, stop-hook reset nudge, warm-resume digest** — Feature chosen from data, not the backlog. Slices 6c/6d had no open rows; the rest is Phase 3–5. `agent-spec-t
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261114-184939.md`. Nothing is deleted.
- **2026-11-14 — Slice 6d/6e status check, high-effort code review, all 10 findings fixed** — Status check. Slice 6d (DV-000 to DV-062) and Slice 6e (CB-001 to CB-005) are all `[x]`, with an evidence file
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261115-095717.md`. Nothing is deleted.
- **2026-11-14 (later) — Slice 6f: harness automation, one-command project readiness, Automations panel** — Audit. Every `bin/` script, hook and skill was checked for whether a hook runs it or someone has to remember t
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261115-115840.md`. Nothing is deleted.
- **2026-11-14 (evening) — Slice 6g: project intelligence (local index, Ask space) and outcome quality** — Review against the "AI experience intelligence platform" brief. Traced hooks → `events.jsonl` → `ingest.py` → 
