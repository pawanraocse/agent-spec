## 2026-11-14 — Slice 6d/6e status check, high-effort code review, all 10 findings fixed

### Done (uncommitted, on top of earlier uncommitted work on main)
- **Status check.** Slice 6d (DV-000 to DV-062) and Slice 6e (CB-001 to CB-005) are all `[x]`, with an evidence file per row (CB rows share `docs/evidence/CB-001.md`). Before the review: pytest 383, vitest 18, build in budget, Playwright 7, all green. No code review of the uncommitted diff existed (no `06-REVIEW.md`, nothing under `.agent-spec/reviews/`).
- **Review (`/code-review` high) of the uncommitted diff found 10 issues; all fixed:**
  1. `hook_logs.backfill` re-appended every row the live hook had already written: the hook stamps `ts` in ms, Cursor's log in whole seconds, so the dedupe key never matched. The live `events.jsonl` had 10 of 27 postToolUse groups doubled. Now `_row_key()` compares `ts[:19]` plus every field except `id`, `ts`, `source`, `file_bytes`, `file_chars`, `ranged`.
  2. The same function collapsed distinct same-second calls (`key_in` was event, generation, epoch). The key now includes the full input JSON.
  3. `cursor_sessions._snapshot` copied Cursor's whole chat DB into `/tmp/agent-spec-cursor-snapshot` world-readable (0755/0644). Now `~/.cache/agent-spec/cursor-snapshot` (or `$XDG_CACHE_HOME`), dir 0700, file 0600; the legacy `/tmp` dir is removed on first use.
  4. Concurrent `_snapshot` callers raced. Now a module lock, a unique temp copy with the WAL folded in (`journal_mode=DELETE`), then `os.replace`.
  5. The stop hook re-read (on WSL, copied ~27 MB of) Cursor's store on every stop. Now at most one check per chat per `AGENT_SPEC_CONTEXT_CHECK_S` (default 300 s), stamped in `.agent-spec/metrics/context-checked/<id>`.
  6. Under Cursor the hard cap is skipped by design (T-057); the debug log now records `allow-unobservable-over-cap`, and check B19 in `docs/PHASE1-VERIFICATION.md` was corrected (it still told testers to expect a denial in Cursor).
  7. `list_conversations` now filters and pages before computing `session_context`; `_billed_by_session` takes a `sessions` filter (also used by `request_detail`).
  8. Configured figures (0.1/1.25 weights, 5-call threshold, and carry/reset/saving/break-even derived from them) are now `estimated`, not `measured`, in `ContextMeter.tsx` and `Coach.tsx`; `budget()` returns `reset_threshold_calls` and `weighted_provenance: "estimated"`.
  9. `cursor-event._read_extent` compares `content_length` (characters) with the file's characters (decoded up to 4 MB), not bytes.
  10. The stop hook rejects a `conversation_id` not matching `^[\w.:-]{1,160}$` before using it in a file name.
- Tests added: `test_hook_logs` (live row not duplicated, same-second calls kept), `test_cursor_event` (multibyte whole read), `test_session_end` (throttle, unsafe id), `test_traces` snapshot (0700 dir, 0600 file, no `-wal`/`.tmp` left), `test_pre_tool_use` (`allow-unobservable-over-cap`). After fixes: pytest 386, tsc clean, vitest 18, build `initial 153831 / 409600 bytes`, Playwright 7.

### Corrections to my own earlier work this session
- My first status answer said Slice 6d/6e was implemented and green; it was, but "with review" was not true until this review ran. The ten findings above were all in the earlier uncommitted work, including CB-002 and DV-002/DV-060 code that had been marked `[x]`.

### Open
- Duplicate rows already in `.agent-spec/metrics/events.jsonl` remain (the fix only stops new ones); counts for affected chats stay inflated until they are removed.
- Installed copies in this clone are stale: `.cursor/hooks/agent-spec-cursor-session-end.py` and `agent-spec-cursor-pre-tool-use.py` differ from `hooks/`. Run `./install.sh` (also refreshes other registered workspaces).
- Nothing committed; `npm run build` also rewrote `bin/aspec_platform/ui/dist/`. Earlier opens still stand: the context nudge has not fired in a real Cursor chat; T-058, CP-001, P3-001.

### Load next session
`bin/aspec_platform/hook_logs.py` (`_row_key`, `backfill`), `bin/aspec_platform/cursor_sessions.py` (`_cache_dir`, `_snapshot`), `hooks/cursor-session-end.py` (`context_nudge`), `bin/aspec_platform/traces.py` (`list_conversations`).

## 2026-11-14 (later) — Slice 6f: harness automation, one-command project readiness, Automations panel

### Done (uncommitted, on top of earlier uncommitted work on main)
- **Audit.** Every `bin/` script, hook and skill was checked for whether a hook runs it or someone has to remember to. Already automated: digest, doctor line and graph refresh at session start; git-hook re-indexing on checkout, merge and rewrite; receipts; the context nudge. Still manual: the snapshot, a mid-session re-index, snapshot rotation, gate transitions, saving learnings, CI.
- **HA-001.** The long-chat `stop` follow-up is now exactly `/agent-spec-snapshot`, not a sentence asking for it (`hooks/cursor-session-end.py`).
- **HA-002.** `hooks/cursor-event.py` writes `.agent-spec/.graph-dirty` after `afterFileEdit` or a `Shell`/`run_terminal_cmd`/`Write`/`Delete`/`delete_file` postToolUse. The next `stop`/`sessionEnd` spends the marker and starts `graphify-build.py --quiet` detached.
- **HA-003.** `sessionEnd` runs `agent-spec-memory.py rotate` (3 s timeout, fail-open); `stop` does not.
- **HA-004 dropped.** No auto-advance of SDLC gates: `skills/agent-spec-sdlc/SKILL.md` makes every gate a separate human approval, and a follow-up message is submitted without one.
- **HA-005.** `bin/agent-spec-ensure.py`, run from the clone via `~/.cursor/skills/.algosec-agent-spec-root`. It registers the project when it is unregistered, its hooks are unmerged, its rules file is missing, or the rules file is older than `VERSION`; builds a missing graph; and prints one JSON line with `next: /agent-spec-onboard` when the installer's flag is set. `--check` / `AGENT_SPEC_AUTO_REGISTER=0` change nothing, and it refuses `$HOME` and `/`. It replaces the preflight prose in `agent-spec-raw-code-full` §0, the `agent-spec` router and `CURSOR.md`. Measured: first install 0.72 s, re-register on a stale stamp 540 ms.
- **HA-006.** Project › Automations panel. Hooks and HA-005 append rows to `.agent-spec/metrics/automation.jsonl` and skip ids listed in `.agent-spec/automation.json` `disabled`. `GET/POST /api/automations` (`bin/aspec_platform/automations.py`, `serve.py`; POST behind token, origin and content-type guards). UI: `ui-src/src/pages/Automations.tsx`, the first Project tab: measured totals, a row and switch per automation, a run log. An environment opt-out locks its switch.
- Tests: `tests/test_ensure.py` (8), `tests/test_automations.py` (5, added to `tests/platform-suites.txt`), new cases in `test_session_end.py` and `test_cursor_event.py`, a UI honesty case. Final: pytest 404, vitest 19, tsc clean, build `initial 153954 / 409600 bytes`, selftest and lint-refs green. API live-checked against `agent-spec-platform.py serve` on a scratch project.
- `./install.sh` re-run: global skills in `~/.cursor/skills` and this repo's harness (`.cursor/hooks`, rules, `.agent-spec/bin`) are current; `./check-install.sh` passes. That resolves the previous section's "installed copies are stale" open.
- Backlog: `todo-plan.md` Slice 6f, HA-001 to HA-006 (HA-004 `[-]`). Evidence: `docs/evidence/HA-001.md`. `CHANGELOG.md` updated.

### Corrections to my own earlier work this session
- I first proposed auto-advancing SDLC gates from `stop` (item #4) and a separate stop-hook dispatcher. The gate rule above ruled out #4, and with #4 gone the existing follow-up order already picks one action, so no dispatcher was built.
- HA-005 first logged its rows to `events.jsonl`. `traces.build_from_events` turns every row there into a conversation, so the rows moved to `metrics/automation.jsonl`.
- I wrote the HA rows as `[x]` before the tests ran, then reset them to `[ ]` and closed them through the backlog CLI after the tests passed.
- The panel's "Last 24 hours" label failed the honesty test (a digit outside provenance) and was renamed "Past day".

### Open
- Nothing tested in a live Cursor chat: the slash-command follow-up, the graph refresh after edits, or the panel in a browser (Playwright is not installed). The tool names `Delete`, `delete_file` and `run_terminal_cmd` have not been seen in a recorded payload.
- `install.sh` writes only `~/.cursor/skills`. The Claude Code copies in `~/.claude/skills` are older (this session's `agent-spec-raw-code-full` had no §0 preflight).
- Not built from the audit: auto `/agent-spec-learn distill` on correction signals, a `preCompact` state write, CI or a pre-push test hook, a `ui/dist` staleness check.
- Nothing committed; `npm run build` rewrote `bin/aspec_platform/ui/dist/` again. Earlier opens still stand: duplicate rows already in `events.jsonl`; the context nudge has not fired in a real chat; T-058, CP-001, P3-001.
- User priority (hackathon): orchestration, efficiency, transparency and dashboard control come before new skills.

### Load next session
`hooks/cursor-session-end.py` (`automation_enabled`, `log_automation`, `refresh_graph`, `rotate_snapshot`), `bin/agent-spec-ensure.py` (`registration_gaps`, `ensure`), `bin/aspec_platform/automations.py` (`REGISTRY`, `overview`, `set_enabled`), `ui-src/src/pages/Automations.tsx`.

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
