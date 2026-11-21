## 2026-11-21 (evening) — Subagent delegation measured: test runs cost 2.5x bare

### Learned
- Delegating test runs to the agent-spec-verify subagent cost 2.5 times bare on bench task verify-suite (run 20261121T180024-c82667, 1 chat per arm, claude-haiku-5-5: $0.0351 against $0.0139, both 5 of 5 correct). The model already trims test output itself (`pytest -v | tail -n 200` once, then `pytest -q | tail -n 4`, 340 B), and each subagent starts cold at 26k to 56k token-equivalents; the main chat was not smaller (62k against 52k at turn 4). The preToolUse delegation nudge therefore fires only on a noisy run with no pipe and no redirect. Subagent value is still untested for read-heavy search sweeps and for a subagent on a cheaper model than the main chat.
- Claude Code under `--permission-mode dontAsk` refuses a shell redirect into a file (`pytest > log 2>&1`) even when `Bash(python3:*)` is allowed, because the redirect counts as a file write; `acceptEdits` allows writes inside the working directory and still refuses unlisted commands (curl). A `claude -p` turn that waits on a background task emits two `result` events: `usage` covers its own segment, `total_cost_usd` is the running total. The bench now uses acceptEdits, joins answers and sums usage.

### Done
- hooks/cursor-pre-tool-use.py: delegate-verify nudge (once per command, command position only, skips subagent calls via `parent_tool_call_id` or `agent_id`, asks for a foreground call, leaves a `delegate-verify` guard event), and Claude Code's own verdict shape (`hookSpecificOutput`) when `hook_event_name` is `PreToolUse`.
- bin/agent-spec-cursor-bench.py: harness arm gets the preToolUse hook on Bash only; permission mode acceptEdits; `echo` and `pwd` allowlisted; two-result turns graded on all answers.
- bin/agent-spec-risk.py (and the installed .agent-spec/bin copy): redirects to /dev/null, `&1`, `&2` and an interpreter in front of a harness script no longer make the protected-path check fire; `ls .agent-spec/bin/x 2>/dev/null` had blocked a search subagent, and `python3 .agent-spec/bin/agent-spec-memory.py handoff` would have been blocked too. The new test fails on the old code.
- Tests: 79 pass across test_pre_tool_use, test_cursor_bench, test_risk, test_risk_api, test_hook_logs.
- harness-test/README.md section 4 now carries the measured result; report copied to harness-test/runs/2026-11-21-f-subagent-verify-c82667.md.

### Corrections
- I first made the hook nudge redirected runs too (`pytest > log; tail log`); probe c82667 showed that doubled the turn's cost ($0.0106 against $0.0046), so it was reverted.
- `pkill -f agent-spec-cursor-bench` also killed my own shell, so the edit in the same command never ran; it was re-applied.
- Two machine restarts wiped /tmp and killed runs dad368 and the first probe; bench logs now go to .agent-spec/eval/probe.log.

### Open
- The full 15-task gate (af3be8, -2.5%) ran under dontAsk; re-run it under acceptEdits before the README claims new totals.
- timeout-sweep (search subagent) has not been run with the hook.
- Next subagent measurement to choose: a cheaper subagent model than the main chat, or a read-heavy search sweep.
- tests/test_run_dir.py::test_list_and_compact is flaky (1 of 3 full runs); a suggested task was raised for it.
- Nothing is committed (this session adds the hook, risk gate, bench, tests and README changes to the earlier uncommitted set). b240f94 is not pushed. Ask before committing; run `./install.sh --skills-only` after.
- Memory is over its cap (45 of 40 after this promote).

### Load next session
`harness-test/README.md`, `hooks/cursor-pre-tool-use.py`, `bin/agent-spec-cursor-bench.py`, `.agent-spec/eval/cursor-bench-20261121T180024-c82667.md`

## 2026-11-21 (night) — Compact test flake fixed; orchestration and prompt-lookup ideas weighed

### Learned
- The WSL2 wall clock on this machine steps backwards: 4 backward steps in 60 s, the worst 1.027657 s (measured with time.time() in a loop). Any test that compares wall-clock timestamps taken in two processes can flip; backdate the stored timestamp instead of sleeping. This was the cause of the tests/test_run_dir.py::test_list_and_compact flake: cmd_compact compares a run's `started` (not its finish time) against now - --days, and a run started a moment earlier looked like it started in the future.
- Rejected: a once-per-chat project lookup (graphify-cli.py context --budget 4 plus agent-spec-memory.py search --limit 3, about 1.5 KB) on the first code-work prompt in the raw-code skills. It was added and reverted the same session because the user does not want cost to rise and it was unmeasured; memory search returns its top 3 even when none match, and the extra tool call re-sends the whole context. Revisit only with a relevance cut-off in memory search, a skip when the prompt names a file or carries a traceback, and a `--compare skill` bench run that shows no cost increase.

### Done
- tests/test_run_dir.py::test_list_and_compact now backdates run.json `started` to 2000-01-01 and asserts the run was compacted; bin/agent-spec-run.py is unchanged. 30/30 in a loop, full suite 617 passed three times.
- Committed everything to main as 56f69f5 at the user's explicit request (the earlier uncommitted memory promote/handoff, pre-tool-use delegation, risk-gate, bench and skill changes, plus harness-test/). The empty nohup.out was left out. Not pushed.
- Answered what the harness can claim, from harness-test/README.md, and recomputed the af3be8 totals from the raw rows (bare $0.2524 and 124/126, harness $0.2460 and 125/126).

### Decisions and reasoning
- Subagents run `model: inherit`, so delegation only pays when the output it keeps out of the main chat is large. A rough break-even (estimate, not measured): with a 30k-token subagent start, raw output must exceed about 21k tokens with 5 later turns, or about 11k with 20. The user's view is that validation in a subagent saves tokens; agreed for large or messy output, not for output the model already trims with `tail`.
- Recommended next lever, not started: a deterministic test-output filter script (failures only, full log to a file) as the default, with the verify subagent kept for large output and the hook choosing from past output sizes.
- Session-start does not improve the user's prompt: the digest is project context, beforeSubmitPrompt only logs (hooks/cursor-event.py:169), and raw-code shapes replies only. Nothing removes content already in a long chat; the only shrink is a handoff to a new chat.

### Open
- Whether Cursor's beforeSubmitPrompt can add context, and whether preToolUse/postToolUse can rewrite a command or its output, is unknown; /agent-spec-hook-probe can answer it.
- The 15-task gate (af3be8) still needs a re-run under acceptEdits before the README claims new totals.
- timeout-sweep (search subagent) is still unmeasured.
- Push of 56f69f5 and `./install.sh` so Cursor gets the committed skill text are not done.

### Load next session
`harness-test/README.md`, `hooks/cursor-pre-tool-use.py`, `hooks/cursor-event.py`, `.cursor/agents/agent-spec-verify.md`

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
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261121-084418.md`. Nothing is deleted.
- **2026-11-19 (night) — End-to-end review; memory controls on the dashboard** — Goal. The user asked for a full review of the project (no redundancy, keep the needed
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261121-092542.md`. Nothing is deleted.
- **2026-11-19/20 (late night) — Short prompts stopped paying for code work; bench measures it** — Goal. The user found that the harness made short prompts and plain chat dearer than no
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261121-094706.md`. Nothing is deleted.
- **2026-11-20/21 — Harness cost on Claude Code: bench billing fixed, cost gate, levers under test** — Goal. Prove with live runs that the token levers save money: graph search, the search
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261121-102827.md`. Nothing is deleted.
- **2026-11-21 — End-to-end review: graph ranking, memory search, warm resume, recall** — Graph `context` now scores symbol names, stems, 4-letter prefixes and IDF, and puts tests after
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261121-111044.md`. Nothing is deleted.
- **2026-11-21 (later) — Cost levers, memory consolidation, committed as b240f94** — Bench run 20261121T083158-7b6a09 (old version, Haiku 5.5, 8 tasks x 3) finished with the cost
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261121-141253.md`. Nothing is deleted.
- **2026-11-21 (late morning) — Turn-6 save cost traced to shell quoting; `promote` added** — Fact text in a double-quoted shell argument breaks the save. Claude Code in dontAsk mode refuses `agent-spec-m
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261121-182220.md`. Nothing is deleted.
- **2026-11-21 (midday) — Turn-6 handoff cost brought to parity with `handoff`** — Appending a section to a large SESSION-SNAPSHOT.md by hand is what made the harness's handoff turn dear, not m
> Moved to `.agent-spec/memory/snapshots/snapshots-through-20261121-194237.md`. Nothing is deleted.
- **2026-11-21 (afternoon) — Full cost gate passed; harness-test/ evidence folder** — Full gate run 20261121T133335-af3be8 (15 tasks x 3, Claude Code 2.1.328, claude-haiku-5-5) passed: harness $0.
