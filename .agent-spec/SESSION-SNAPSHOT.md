## 2026-11-18 (later) — Goal run: close every open todo-plan row, compact after each

**Done:** P4-013 (step-end exits 4 on a handoff violation), P4-015 (typed steps get a pruned
`context` and the run page shows the bytes saved), H-006 (a full install now writes
`.algosec-agent-spec-full`, and `install_is_lean` in `agent-spec-ensure.py` treats an unmarked
install as lean when all six SDLC skills are missing). check-all was green after P4-015.

**PI-010 done:** `/api/compare` is now a project route on `aspec_platform/session_compare.py`. It
returns per-session signals, tokens, review quality (`ai_judged`) and injected context, plus the
a − b delta. The UI is `features/SessionCompare.tsx`. A correction: in the old UI the zero delta
always showed, because the API never returned `delta_tokens`.

**P3-014 done:** `bin/agent-spec-recall.py` searches this project's experience store and those of
its mesh peers (mesh.json members, plus registered hubs that list this project) and cites
`<repo>:.agent-spec/experience.jsonl:<line>`. It only reads peers. `install.sh` ships it to projects,
and the learn skill's recall step calls it.

**H-044 done:** the full API pass found 4 issues, all fixed in `serve.py` (`PATH_ID`,
`WORKFLOW_NAME`, `_argv_text`, the console gate on workflow start, negative Content-Length). The
evidence is in `docs/evidence/H-044.md`.

**P3-001 closed:** on the six cloud-infra-lite modules meshed from a scratch hub, 29 of 29 import
edges were correct and none were missed. There is no HTTP edge from the Angular frontend, because
its URLs are built at runtime. The script is `examples/mesh-demo/measure_imports.py`.

**H-052 decided, H-051 built (video owed):** `examples/mesh-demo/demo-setup.sh` sets up the
offline demo through the real hooks and gate, and `demo.md` is the 5-minute story. Fixes made along
the way: store chats are scoped to the project (`ingest.store_for_project`), and recall reads
`repo_id` from mesh.json.

**H-042 advanced:** the WSL2 install cycle ran green here, and CI has an `install-windows` Git Bash
job. Still open: the first CI run (`.github/` is uncommitted) and one manual run on real Windows.

**Order for the rest of the goal:** P3-001 → H-052 → H-051 → H-042
(the CI part) → final review. H-005, H-045, H-050 and H-053 need a person, live Cursor or the demo
machine. Do not push the T-042 tag without the user's go-ahead.

**Files for next session:** `bin/agent-spec-ensure.py` (`install_is_lean`), `bin/agent-spec-run.py`
(`_step_context`, `_handoff_schema`), `ui-src/src/pages/Runs.tsx`, `tests/test_handoff_step.py`.
Nothing is committed.

## 2026-11-18 (night) — Dashboard and skills review goal; Windows install fix; fallback video

The goal "fix all issues and gaps … review the dashboard and skills" was cleared by the user
with `/goal clear`. It was not completed: the rows left open each need a person or a push
approval the user has not given.

**Committed on `main` (8 commits ahead of origin, not pushed):** bc0a8e8, 7e472bf, e6237ce,
2a7a799, f6c8877, b28f9e5, 66e81f2, 5a49a75. Earlier in the session I said "7 commits ahead";
it is 8 (bc0a8e8 was also unpushed).

**Built**
- Dashboard: five spaces (Impact, Activity, Ask, Inbox, Project); per-chat Savings tab
  (`views.session_savings`); honest raw-code payback (subagent-owned spans excluded, chats from
  Cursor's store with no tool sizes counted as `unmeasured`); fixture skills hidden from the
  catalog; empty-project first-run card; "Load demo data" button removed (it wrote a table no
  page reads).
- `serve.ensure_db` creates the schema before serving (fixed `no such table: steps` on a
  fresh register).
- `agent-spec-bench.py --skill NAME` compares plain vs skill arms; the Ollama agent loads a
  `/agent-spec-*` skill body. Measured on qwen2.5-coder:7b: raw-code-full cost +60–65% input
  tokens with no accuracy gain, because the local Read is already capped at 80 lines.
  `raw-code-full` SKILL.md cut to 2,541 B (only what the always-on rule does not carry).
- H-042: on real Windows Git Bash, `--register` reported a false `FAIL digest`. Cause: the
  doctor passed its own stdin to `digest --cursor-hook`, which reads stdin to EOF; under any
  open non-tty stdin that never ends, so the 15 s timeout hit. Fix: `stdin=DEVNULL` in the
  doctor's `run()`. Also `native_path()` maps Git Bash `/c/...` registry paths on Windows.
  Windows run: install, register (green, 11 s), unregister, uninstall all exit 0.
- H-051 closed: `docs/demo/fallback-demo.mp4` (97 s, 751 KB), recorded by
  `examples/mesh-demo/record-video.mjs` (terminal commands run live, dashboard clicked in
  Playwright). Recording showed the recorded chat keeps 0 tokens out; `demo.md` no longer
  claims a saving on that beat. `demo-setup.sh` now sends the blocked edit's prompt through
  `beforeSubmitPrompt`, so the chat is no longer "(untitled chat)".

**Corrections to my own earlier work**
- The skill payback box first disagreed with the chat page (a Cursor-store chat had cost
  but no sizes); fixed by excluding unmeasured chats.
- The chat cost row first showed the wrong figure; it now shows `cost.resend`.
- My first H-051 caption claimed the Impact beat showed tokens kept out; the frame showed 0.
  Corrected before committing.

**Open, each needs the user**
- H-042: the CI install jobs run only after a push. Push not approved.
- H-005 (live Cursor chat), H-050 Cursor half, H-045 (new person), H-053 (presenter
  rehearsals), T-042 (`v3.0.0` tag decision).
- Housekeeping still owed: memory is over its cap; run `agent-spec-memory.py prune`.

**Load next time:** `todo-plan.md` (open rows), `docs/evidence/H-042.md`,
`docs/evidence/H-051.md`, `demo.md`.

**Gotchas**
- Never run `pkill -f agent-spec-live.py` in a command whose own text contains that string;
  it kills its own shell. Kill by PID from `ss -ltnp`.
- Windows Python's `expanduser` reads `USERPROFILE`, not `HOME`; a sandbox must set both.

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
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261115-133220.md`. Nothing is deleted.
- **2026-11-15 — Gap review of Slice 6g; skill drift sync; headless CLI requests named, closed and hidden** — Gap review of Slice 6g. Read the diff of `serve.py`, `ingest.py`, `traces.py`, `db.py`, `retrieval.py` and the
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261118-105937.md`. Nothing is deleted.
- **2026-11-15 (later) — Impact tab for the hackathon story; memory injections recorded; review and 10 fixes** — The user ran the dashboard on a `/agent-spec-raw-code-full` request and could not explain the feature: no toke
**Update, same session:** P4-013 is closed: `step-end` checks the output schema, the example workflow
gather step returns the `agent-spec-search` shape, and there is a test. The graph fast path still
writes one history row per build. `bin/agent-spec-check-all.sh` passes all gates. Nothing is committed.
### 2026-11-18 (later) — H-053 scripted dry run, H-005 fix
- Built `examples/mesh-demo/demo-dryrun.py`: two offline (`unshare -rn`) timed runs, 10/10 beats, ~2.9 s each.
- Fixed `hooks/cursor-session-start.py`: the first chat in a freshly registered project lost its
  injections.jsonl row because `metrics/` did not exist yet (H-005).
- `demo-setup.sh` now writes onboarding files, remembers one fact and proposes a different one.
- H-005, H-053 now `[~]`: the live Cursor chat and the presenter's two rehearsals are owed.
- Still needs a person: H-045, H-050 (plain Cursor vs harness), T-042 (tag approval), H-042 CI run, H-051 video.
- check-all green, all 7 gates. Nothing committed. Memory 75 facts against a cap of 40: prune.
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261118-161329.md`. Nothing is deleted.
- **2026-11-15 (evening) — Local Ollama mode, Console restored, Showcase, RAG eval, per-chat skill savings; committed and pushed** — The user has no usable Cursor plan: every `cursor-agent` prompt returns `ActionRequiredError: You've hit your 
### 2026-11-18 (end) — goal cleared, session closed
- The goal "complete all and review, compact after each" was cleared by the user with `/goal clear`
  after the remaining rows proved to need a person; it was not completed.
- Closed this session: P4-013, P4-015, H-006, PI-010, P3-014, H-044, P3-001, H-052.
- Partly done: H-005, H-053 (scripted parts done and verified), H-042 (CI job added; it has not run on GitHub yet),
  H-051 (the video is owed).
- Not started, each needs the user: H-045 (fresh-user test), H-050 (plain Cursor vs harness),
  T-042 (`v3.0.0` tag needs approval).
- State: all check-all gates green; nothing committed, all changes are in the working tree on `main`.
  Next session: commit on a new branch (needs the user's go-ahead), push so the H-042 CI job runs.
- Housekeeping owed: memory holds 75 facts against a cap of 40; run `agent-spec-memory.py prune`.
- Files to load next time: `todo-plan.md` (open rows), `docs/evidence/H-005.md`, `docs/evidence/H-053.md`,
  `examples/mesh-demo/demo-dryrun.py`.
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261118-214550.md`. Nothing is deleted.
- **2026-11-18 — Production push: guardrails, dashboard control, RAG fixes (uncommitted)** — Done (todo-plan.md rows closed with docs/evidence/): H-001 H-002 H-003 H-004 H-010 H-011
