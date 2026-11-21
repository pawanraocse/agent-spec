## 2026-11-20/21 — Harness cost on Claude Code: bench billing fixed, cost gate, levers under test

**Goal.** Prove with live runs that the token levers save money: graph search, the search
subagent, and snapshot plus a new chat. The user's constraint: the harness must never cost more
than bare.

**What broke, and the correction.** My first diagnosis was wrong. I blamed the always-on
prefix, but CURSOR.md plus the digest is only about 1.2k tokens per call. The real faults were
in the bench, not the harness:
- `claude -p --resume` reports `total_cost_usd` and `modelUsage` as the session's running total,
  while `usage` is per turn. The bench summed the running totals, so long chats were overbilled.
- The claude.ai MCP connectors ignore `--setting-sources project`. They reconnected on resumed
  turns and wrote about 16k tokens of cache at random turns in either arm. `--strict-mcp-config`
  removes them.

Each chat's cost, recomputed as its last turn's running total:

| Run | Bare | Harness | Change |
|---|---|---|---|
| 4e5bb7 | $0.3301 | $0.4285 | +29.8% |
| 3a9968 | $0.2744 | $0.2541 | −7.4% |
| a3a5fd | $0.1018 | $0.1267 | +24.5% |

All three runs predate the fixes.

**Built, committed and pushed to main.**
- `9dd9333`: each turn is billed its own cost, MCP is isolated, `new_chat` turns start a fresh
  session in the same copy, and there is a `long-dashboard-compact` task.
- `2417a73`: a cost gate. `--max-cost-change PCT` defaults to 0, so the run exits 4 when the
  harness costs more than bare or gets fewer answers right. The verdict line goes into the report.

**Built, not committed.**
- `CURSOR.md` was trimmed from 2522 B to 1747 B. I removed the install note and the onboarding
  steps, because the digest already prints ONBOARDING NEEDED.
- The bench harness arm now installs `agent-spec-search` and `agent-spec-verify` into
  `.claude/agents/`, and `Agent` is an allowed tool. A new "Subagent calls" metric counts their use.
- Two new tasks: `traceback-fix` plants a bug in `savings.py` that only a `test_insights.py`
  traceback reveals, and `env-sweep` is a sweep across files suited to a subagent.
- `add_harness` takes CURSOR.md from the package, never from the project. A user project with its
  own CURSOR.md had been benched as if that file were our rule.
- In `install.sh`, the marker check on an existing AGENTS.md was `grep -q "agent-spec\|agent-spec"`.
  This was left over from the vendor-name drop in 7101331, and any mention of agent-spec skipped
  the pointer. It is now `grep -qF ".cursor/rules/agent-spec.mdc"`.
- The 21 bench tests pass.

**Answered.** install.sh does not write a CURSOR.md into a user's project. It writes the content
into `.cursor/rules/agent-spec.mdc` and overwrites that file. AGENTS.md is copied in only if it is
missing; otherwise a pointer is appended. hooks.json is merged.

**Open.**
- The clean Claude bench (8 tasks × 3 runs, about $2) was still running at snapshot time, so the
  question "does it save now" has no answer yet. Next: read the newest
  `.agent-spec/eval/cursor-bench-*.md` for the gate verdict, long-dashboard against
  long-dashboard-compact, and graph and subagent calls in traceback-fix and env-sweep. If the gate
  fails (exit 4), fix what the run shows.
- Commit and push the uncommitted changes, after asking the user.
- Memory holds 89 facts against a cap of 40, and INDEX.md is over 8000 B. Pruning deletes facts,
  so it needs the user's confirmation.
- `/agent-spec-raw-code-full` was measured 5% dearer before. Its SKILL.md is re-read every turn.
  It needs its own A/B after the harness passes.
- Not explained: 3 invented file names in the harness long chats of run 4e5bb7, and +56% wall
  time in run 3a9968.
- The Ollama 7B model never calls graphify, so local runs cannot test the graph lever.

Files to load: `bin/agent-spec-cursor-bench.py`, `evals/harness-bench.jsonl`,
`evals/cursor-bench.jsonl`, `CURSOR.md`, the newest `.agent-spec/eval/cursor-bench-*.md`.

## 2026-11-21 — End-to-end review: graph ranking, memory search, warm resume, recall

### Done
- Graph `context` now scores symbol names, stems, 4-letter prefixes and IDF, and puts tests after
  their subject. On commit history, hit@4 went from 20% to 56% and recall@12 from 27% to 53%.
  Reproduce with `python3 evals/graph_context_eval.py`.
- `agent-spec-memory.py search` ranks free-text questions (it was a substring match that found 0
  facts) and takes `--limit`.
- The digest's warm resume parses `### Open`, `**Open.**` and `Files to load:` shapes, and the
  snapshot skill prescribes the shape. The digest no longer forbids SESSION-SNAPSHOT.md; it
  points earlier-chat questions at memory search and then the newest section.
- Recall drops path tokens and needs two shared words. RAG search keeps at most two chunks per
  file and drops question filler (MRR 0.450 to 0.457).
- Small fixes: the receipt fact counter, the `ingest --what` hint, `sessionStart` back in
  CURSOR.md (the selftest checks it), stale `.algosec-*` names in facts, and the `views-blast`
  grader.
- Report: `docs/evidence/REVIEW-2026-11-21.md`. Nothing is committed yet.

### Corrections
- I first assumed the RAG index only refreshed while the dashboard runs. `search` and `ask`
  already refresh incrementally (0.35 s), so nothing needed to change there.

### Open
- The Claude bench run 20261121T083158-7b6a09 was still running. At about 1.5 of 3 repeats the
  harness was +3.8%. It started before this session's ranking changes, so re-run it after
  committing to measure them.
- Memory holds 91 facts against a cap of 40. An age prune would delete load-bearing decisions,
  so prune by relevance, and only with the user's approval.
- The installed skills in ~/.cursor/skills predate the vendor-name drop (`.algosec-*` markers).
  Re-run `./install.sh` when the user agrees.

### Load next session
`docs/evidence/REVIEW-2026-11-21.md`, `bin/graphify-cli.py`, `bin/agent-spec-digest.py`, `evals/graph_context_eval.py`

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
