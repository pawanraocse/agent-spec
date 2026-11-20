## 2026-11-19 (night) — End-to-end review; memory controls on the dashboard

**Goal.** The user asked for a full review of the project (no redundancy, keep the needed
skills, save tokens, an interactive dashboard, graph and memory across sessions, skills
orchestration), then a fix for the largest gap found: memory could only be read on the dashboard.

**Review fixes (all gates green: pytest, selftest, lint-refs, project copy, tsc, vitest, build+budget).**
- Selftest was red: router skill 3263 B over its 3072 B limit. Cut to 2999 B by removing the
  "Before handing off" section (CURSOR.md's code-change rule already says graph first) and the
  "have we done this before" phrase that overlapped the learn row. No skill removed.
- `db.migrate` race: two writers opening a fresh platform.db both applied migration 1
  (`table requests already exists`; this was the flaky `test_health_reports_schema_and_counts`).
  A first attempt (skip the step on error) was wrong: the v2 migration re-applies cleanly and
  would have reset `user_version` to 2. The fix takes `BEGIN IMMEDIATE`, re-reads the version
  under the lock and runs statements one at a time (split with `sqlite3.complete_statement`),
  because `executescript` commits any open transaction. `connect` also retries the WAL switch,
  which SQLite answers with SQLITE_BUSY without calling the busy handler. Stress: 198 failures
  in 80 four-thread races before, 0 in 240 after.
- Doctor: the memory fix hint `prune --older-than 90` removed nothing; it now computes an age
  that fits (`prune_days`, tested). The token audit no longer repeats the memory warning.
- CURSOR.md no longer lists the five graph commands; the digest carries them every session.
- livetest_view `start` takes a lock (two clicks could start two runs); cursor-bench uses
  `math.comb`.
- Live API smoke on this repo: all 45 GET routes 200 (or 400/404 without required params),
  under 2 s, no tracebacks.

**Memory controls.** New `bin/aspec_platform/memory_view.py`: GET `/api/memory` reads fact files
directly (text, status, created, supersedes) plus injection counts from the DB; POST
`/api/memory` add, edit (= `add --supersedes`), forget, prune (preview unless `apply: true`).
Every write goes through `agent-spec-memory.py`, then `ingest.run(["memory"])`, then an audit row
in `metrics/proposals.jsonl` (`proposals.audit`, made public). Team facts are read-only.
`platform_data.api_memory` removed. CLI: new `forget <id>` (moves the file to
`memory/forgotten/`); `add` collapses the subject to one line (a newline could forge frontmatter
keys), and its duplicate check skips the fact being superseded (an edit of only subject or
type was silently a no-op); INDEX.md lists active facts only. The Knowledge page was rewritten
with react-query: search, type and scope filters, show retired, index meter, add, edit,
two-click forget, prune preview then apply. Tests: `tests/test_memory_view.py` (6),
`ui-src/src/pages/Knowledge.test.tsx` (4). The remember skill and DASHBOARD.md were corrected:
the digest ranks facts by the files in play, then constraints, then age, not by age alone.

**Snapshot headings.** The four 2026-11-19 sections had `###` headings, which rotate and the
digest's "last session" line ignore, so the digest still said 2026-11-18. They were promoted to
`##` with no content change.

**Open.**
- Memory INDEX.md is 8683 B against 8000 B. Prune preview at 79 days lists 9 facts; the user
  decides (Memory page or `prune --older-than 79 --dry-run`). Nothing was deleted.
- API routes that no page calls: `/api/home`, `/api/savings`, `/api/skills`, `/api/pricing`,
  `/api/cursor/workspaces`, `/api/seed`; `/api/search` and `/api/signals` are used only by tests.
  Not removed; ask first.
- Owed in Cursor after the push: H-005 (Impact tab facts), H-042 (CI first run), H-050 (Cursor
  bench), H-045 and H-053 (a person's run, presenter rehearsals), then T-042.
- Nothing committed. `./install.sh` was re-run, so the global skills match this tree.

Files to load: `bin/aspec_platform/memory_view.py`, `ui-src/src/pages/Knowledge.tsx`,
`bin/aspec_platform/db.py`, `bin/agent-spec-memory.py`, `todo-plan.md`.

## 2026-11-19/20 (late night) — Short prompts stopped paying for code work; bench measures it

**Goal.** The user found that the harness made short prompts and plain chat dearer than no
harness. It only paid off for repo search, graph queries and session save/load.

**Cause.** CURSOR.md (4342 B) and the digest (2216 B) rode in every turn. Worse, the rules
forced tool calls before any answer: the raw-code preflight (`agent-spec-ensure.py`), the
digest run, onboarding, a graph query and a Pre-Change Declaration. Each tool call re-sends the
whole context, so a one-line question could cost several full round trips.

**Built, committed on main (not pushed; main is 2 ahead of origin/main).**
- `dae48a1` — rule split, VERSION 2.1.0. `CURSOR.md` → `.cursor/rules/agent-spec.mdc` is now
  the always-on core (2564 B). It holds the Direct / Small / Code work tiers, session start and
  hard stops; a Direct reply makes zero tool calls. `CURSOR-WORKFLOW.md` →
  `.cursor/rules/agent-spec-workflow.mdc` (`alwaysApply: false`, Agent Requested) holds
  personas, confidence tags, coding rules, implement gates, subagents and tool discipline.
  The core tells the model to Read the workflow file with its first tool call if Cursor has not
  attached it. The digest's guidance shrank to 1988 B and is scoped to code. The raw-code,
  raw-code-full and router skills now run their preflight only with the first code-work tool
  call and only when no digest is in context. install, uninstall, check-install, ensure (adds
  the gap "no workflow rule") and doctor handle the second file. The token audit no longer
  counts an `alwaysApply: false` rule as always-on. The selftest budget for CURSOR.md is now
  3200 B, down from 4600 B. The commit also carried the pending live-test work from earlier
  sessions.
- `771d9ce` — bench. `evals/direct-bench.jsonl` has six direct prompts (`max_tools` 0) and one
  small lookup (`max_tools` 1). `--compare versions --base-ref REF` installs the base arm from
  `git archive REF` and the head arm from this checkout. `harness-bench.jsonl` gained three
  graph tasks (answers taken from the graph and confirmed with grep) and `long-dashboard`, a
  nine-turn chat that recalls early facts at the end. Every report adds workflow-rule reads,
  invented file names (cited names that exist nowhere in the project), a per-feature table
  (tokens, time, correctness, chats that used the graph) and accuracy by turn position. Docs
  are in `docs/LIVE-TESTING.md`.

**What broke, and the correction.** `install.sh --register` appends the workspace to
`~/.cursor/skills/.agent-spec-projects` and then re-installs every workspace listed
there. Every past `--compare harness` run had left a `/tmp/...aspec-claude-bench-tpl-*` entry
in the user's registry (11 of them). While debugging the versions mode, a manual install from
`4852bfe` downgraded all registered workspaces to 2.0.0. They were restored at once with the
current `install.sh`, and the three existing workspaces were confirmed back on 2.1.0. My
earlier `install.sh --register "$PWD"` in this session had also refreshed `content-creation-ai`
to 2.1.0 without my noticing. The bench now runs its installs under a throwaway HOME, and a
test asserts the user's registry and workspaces are untouched. On the user's request, the
11 stale bench lines were removed from the registry; a backup was kept in this session's
scratchpad.

**Also fixed in passing.** The bench's Cursor harness note never printed, because the
skill-note branch matched first. `register_harness` no longer copies the project's
`.agent-spec/bin` over the installed bins, so each arm runs its own version's digest.

**Open / owed (live Cursor, not done).**
- Push main, then on the Cursor machine run
  `python3 bin/agent-spec-cursor-bench.py --agent cursor --compare versions --base-ref 4852bfe --repeat 2`
  and `--compare harness --repeat 3`. Pass criteria: direct prompts at 0 tool calls, all within
  budget, all-input tokens at or below base; graph tasks keep graph chats and correctness; the
  harness shows no more invented files or late-turn misses than bare in long-dashboard.
- Main risk: Cursor may not attach the Agent Requested workflow rule for code tasks. Proposed,
  not built: preToolUse denies the first tool call of a conversation once, with the workflow
  body in `agent_message` (reusing `nudged_already`), plus `globs` on the workflow mdc.
- Doctor still flags memory INDEX.md at 8788 B (limit 8000).

Files to load: `CURSOR.md`, `CURSOR-WORKFLOW.md`, `bin/agent-spec-cursor-bench.py`,
`hooks/cursor-pre-tool-use.py`, `evals/direct-bench.jsonl`, `docs/LIVE-TESTING.md`.

## Archived sections
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261031-184403.md`. Nothing is deleted.
- **2026-10-27T13:14:18** — agent-spec installed.
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
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261115-133220.md`. Nothing is deleted.
- **2026-11-15 — Gap review of Slice 6g; skill drift sync; headless CLI requests named, closed and hidden** — Gap review of Slice 6g. Read the diff of `serve.py`, `ingest.py`, `traces.py`, `db.py`, `retrieval.py` and the
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261118-105937.md`. Nothing is deleted.
- **2026-11-15 (later) — Impact tab for the hackathon story; memory injections recorded; review and 10 fixes** — The user ran the dashboard on a `/agent-spec-raw-code-full` request and could not explain the feature: no toke
**Update, same session:** P4-013 is closed: `step-end` checks the output schema, the example workflow
gather step returns the `agent-spec-search` shape, and there is a test. The graph fast path still
writes one history row per build. `bin/agent-spec-check-all.sh` passes all gates. Nothing is committed.
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261119-222001.md`. Nothing is deleted.
- **2026-11-18 (later) — Goal run: close every open todo-plan row, compact after each** — Done: P4-013 (step-end exits 4 on a handoff violation), P4-015 (typed steps get a pruned
- **2026-11-18 (night) — Dashboard and skills review goal; Windows install fix; fallback video** — The goal "fix all issues and gaps … review the dashboard and skills" was cleared by the user
- **2026-11-18 (later) — H-053 scripted dry run, H-005 fix** — Built `examples/mesh-demo/demo-dryrun.py`: two offline (`unshare -rn`) timed runs, 10/10 beats, ~2.9 s each.
- **2026-11-18 (end) — goal cleared, session closed** — The goal "complete all and review, compact after each" was cleared by the user with `/goal clear`
- **2026-11-19 — Live test matrix on Ollama (H-054), 4 defects fixed, Live tests page** — Built `bin/agent-spec-livetest.py`: 18 cases (L01–L18) run for real on local Ollama in a temporary
- **2026-11-19 (later) — Measuring /agent-spec-raw-code-full: Groq runs, Claude Code bench, H-050** — Question from the user: why L18 showed the skill using more input tokens, and whether it saves
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261120-055846.md`. Nothing is deleted.
- **2026-11-19 (evening) — Skill verdict, harness-vs-bare bench, graph never called** — Skill verdict. `/agent-spec-raw-code-full` does not save tokens. Every head-to-head so far
