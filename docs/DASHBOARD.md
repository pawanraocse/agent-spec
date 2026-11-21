# Control Plane Dashboard — request-trace observability (v3)

> **Status:** v3 request-trace control plane (DEC-16), Slice 6d in [`todo-plan.md`](../todo-plan.md).
> **Design:** [`dashboard_overhaul.md`](../dashboard_overhaul.md) §14 (v3); §12–§13 are history.
> **Strategy:** [`MASTER-PLAN.md`](MASTER-PLAN.md) — DEC-15 AI-first, DEC-16 request traces.

The dashboard shows what every Cursor agent session did, step by step, and lets an agent
judge it. A developer types a prompt; the dashboard draws the request as a trace — prompt,
skill, subagents, tool calls, guard decisions, file edits, responses — with measured
durations and the bytes handed between steps. A review skill grades the session and the
Learning view measures whether recorded facts make those mistakes rarer.

## Start

```bash
python3 bin/agent-spec-platform.py ingest            # persists traces, memory, runs, graph stats
python3 bin/agent-spec-platform.py serve             # http://127.0.0.1:8765/?token=...
python3 bin/agent-spec-platform.py trace --list 20   # the same traces in the terminal
```

Live requests need the workspace registered (`./install.sh --register "$(pwd)"`), which
puts `hooks/cursor-event.py` on every traced Cursor hook. They appear without an ingest:
the server tails `.agent-spec/metrics/events.jsonl` and pushes new rows over SSE.

## Today: the landing page

`/` (`GET /api/today`, `bin/aspec_platform/mission.py`) answers "what needs me, and what did the
harness do?" on one screen:

| Section | Source | What you do there |
|---|---|---|
| **Needs you** | risk, proposals, index health, live tests, hook coverage, doctor, reviews, memory, snapshot, SDLC gates | Ranked *waiting on you* → *needs a fix* → *make it smarter*. Each row carries its fix: an exact action runs on the server (Rebuild graph, Refresh mesh); anything that needs judgement is a **skill** — Copy for Cursor, or Run in Console when the skill is read-only (`/agent-spec-investigate`). |
| **What the harness did for you** | `skill_savings`, memory, automations | Tokens kept out and re-sends avoided (estimated, per lever), facts injected, guard blocks, subagent sweeps, autopilot runs. |
| **Pulse** | request traces | 14 days of requests, Cursor vs Console, with tool calls and errors. |
| **Autopilot** | `metrics/automation.jsonl` | What the hooks ran on their own; repeats fold into one row with a count. |
| **Latest requests**, **Skills at work** | request traces | Jump to a trace; one-click prompts that open the Console prefilled (`/console?prompt=…`, never auto-sent). |

The page judges nothing itself (DEC-15): unreviewed chats become `/agent-spec-session-review <id>`,
a failing live test becomes `/agent-spec-investigate …`, unproven hooks become
`/agent-spec-hook-probe`, unlinked facts become `/agent-spec-learn`. Every source is read in its
own guard, so an unreadable log shows as a warning line, not a blank page.

## Local mode: no Cursor plan needed

```bash
python3 bin/agent-spec-live.py            # Ollama check, embeddings, index, RAG eval, dashboard
python3 bin/agent-spec-live.py --bench    # also runs the harness-vs-bare A/B benchmark first
```

`agent-spec-live.py` finds Ollama (loopback, or the Windows host's gateway address under WSL),
picks a chat model (`qwen2.5-coder:7b`, then `qwen3:4b`), pulls `nomic-embed-text` once if no
embedding model is installed, ingests and embeds the index, scores retrieval, and starts the
dashboard with the **Console** and **Ask** answering on that model. Nothing leaves the machine;
an endpoint that is neither loopback nor the WSL host needs `AGENT_SPEC_ALLOW_REMOTE_MODELS=1`.

The Console runs `bin/agent-spec-ollama-agent.py`, which takes `cursor-agent -p` arguments and
fires the project's registered Cursor hooks with Cursor-shaped payloads (sessionStart digest,
preToolUse guard, postToolUse, afterAgentResponse with Ollama's measured token counts, stop), so
its requests are traced, measured and reviewed exactly like Cursor chats. They carry
`origin: "local"` and stay visible in Live (CLI runs stay hidden). Its tools are read-only: ranged
`Read`, `Grep`, `graphify_context` and `search_project` (this dashboard's retrieval). The backend
is `cursor-agent` only when `AGENT_SPEC_CONSOLE=1` is set (or `AGENT_SPEC_AGENT_BACKEND=cursor`);
`AGENT_SPEC_CONSOLE=0` turns the Console off.

| Command | What it measures |
|---|---|
| `agent-spec-platform.py rag-embed` | Embeds every pending index chunk (`AGENT_SPEC_EMBED=ollama:nomic-embed-text`). After that, search, Ask, the Console and ingest use those vectors with no env var whenever Ollama is reachable and serves the model; `AGENT_SPEC_EMBED=none` forces keyword mode. |
| `agent-spec-platform.py rag-eval [--build] [--label L]` | hit@1, hit@k and MRR for keyword, semantic, hybrid and tuned search on `.agent-spec/eval/rag-golden.jsonl` (questions a local model writes without naming the file). Stores the semantic fusion weight with the best MRR; `search()` uses it, and a weight of 0 skips the embedding call. |
| `agent-spec-bench.py [--model M]` | The same prompts on the same model with the harness on and off (`--bare`: no digest, no guard, no graph or search tool). Correct = the answer names every expected string in `.agent-spec/eval/agent-bench.jsonl`. |

The **Impact › Summary** page (`/impact`, `GET /api/showcase`) puts these together: the A/B result per
prompt with links to both traces, the RAG accuracy table and its history across changes, tokens
avoided and billed, rule pass rate, ranged-read share, tool error rate, latency, a per-model table
and the latest prompts. Each figure is labelled measured, estimated or AI-judged.

## Tokens saved by the raw-code rules

Every chat shows what `/agent-spec-raw-code` and `/agent-spec-raw-code-full` saved, computed by
`bin/aspec_platform/skill_savings.py` from the same spans as the Impact tab (bytes ÷ 4, estimated):

| Lever | Priced as |
|---|---|
| Graph queries | one median indexed file per `graphify` query, minus its answer |
| Ranged reads | the unread rest of each file read in a range |
| Subagents | tool output that stayed in a subagent's own context |
| Targeted edits | file size minus the edit, for each Edit instead of a rewrite |

Because the context is re-read on every model call, each saving is also multiplied by the
measured number of later model calls in that chat (the main-context tool calls left in its own
request, plus later main-context tool calls and later requests): the "re-sends avoided" figure.
A subagent's own tool calls are not counted: they run in its context, which never carries the
parent's. What a subagent read counts against the main calls made after it returned. The
skill's own body is priced the same way, against only the chats that invoked it. Chats read only from Cursor's history are left out of that payback: they record no tool sizes, so only the cost side could be counted. The chat
page (**Activity › Chats › a chat › Savings**) shows the same per-chat figures. A chat is in raw-code mode from the first `/agent-spec-raw-code*`
request until `/agent-spec-verbose`. Where it shows: the **Impact** tab opens with a "This chat so
far" card, each row of **Activity › Chats** carries a −N chip (⚡ when raw-code was on), and the
**Impact › Summary** leads with the board total, per-lever bars, the chats that saved the most and a
raw-code vs plain comparison per Cursor request that used tools (the ratio appears only once each
side has 5+ requests). `GET /api/skill-savings` returns the board; `session_savings` on a request
and `savings` on a conversation carry the per-chat numbers.

## Five spaces

Each sidebar space is a row of tabs; every tab keeps its own URL, and the old URLs
(`/showcase`, `/sessions`, `/project/runs`, `/governance`, …) redirect to their new home.

| Space | Question | Tabs |
|---|---|---|
| **Impact** (home) | What does the harness change? | **Summary**: tokens kept out and re-sends avoided, whether `/agent-spec-raw-code` paid for its own size, harness A/B on a local model (with its sample size), RAG accuracy, token ledger, per-model table, latest prompts (`showcase.py`, `skill_savings.py`). **Coach**: p50/p95 per span kind, slowest spans, top issues with fix prompts. **Learning**: findings before vs after each recorded fact |
| **Activity** | What did my agent do? | **Requests**: live feed with the orchestration graph, waterfall, span inspector, outcome, review, replay; local runs say *harness on* or *harness off*. **Chats**: one row per conversation. **Workflow runs**: hub-runner runs only, by workflow and input |
| **Ask** | Why was this built? Have we done this before? | **Search the project**: cited search over code, docs, rules, memory, requests and reviews (`retrieval.py`, see [`INTELLIGENCE-PLATFORM.md`](INTELLIGENCE-PLATFORM.md)). **Run the agent**: the local Console, streamed from `/api/agent/sessions` |
| **Inbox** | What is waiting on me? | **Risky edits** blocked by the risk gate, learning-loop **Proposals**, and **Automations** with each run's recorded outcome. The sidebar badge counts what waits |
| **Project** | What does the harness know, and is it healthy? | Skills (used first; skill panels on top), knowledge graph (most-depended-on files, unlinked files hidden), memory (every fact with its text and injection count; add, edit as a new version, forget, and prune with a preview, each through `agent-spec-memory.py` and audited in `proposals.jsonl`), repos, search index, health (doctor first; the SDLC rail appears while a pipeline is in flight) |

Ctrl/⌘-K searches requests and skills, and sends any text to Ask. Settings holds the theme (dark, light, system) and loads or removes the labelled demo data.

## Impact tab

Each request opens on **Impact**, which answers "what did agent-spec change here?" against a plain
Cursor chat. It is computed by `bin/aspec_platform/impact.py` from the request's spans.

| Card | Provenance | How |
|---|---|---|
| Tokens kept out of the chat | Estimated | Tool output that stayed in a subagent's own context, plus each graph query priced as one read of the median indexed file, plus the unread part of each ranged read. Bytes ÷ 4. |
| raw-code-full rules | Measured | Graph before search, no whole-file reads in the main context, broad sweeps in subagents, tool output under 8,000 B, guard blocks. |
| Memory injected | Measured | Facts the sessionStart digest injected, from `metrics/injections.jsonl` (recorded from 2026-11-15 on). |
| What agent-spec adds | Measured | Rules, skills and subagent definitions from Cursor's own context breakdown: the fixed cost per model call. |

## Data sources and provenance

| Source | Where | Durations | Badge |
|---|---|---|---|
| Hook events | `.agent-spec/metrics/events.jsonl` from `hooks/cursor-event.py` (and guard rows from `cursor-pre-tool-use.py`) | measured: Cursor's `duration` / `duration_ms`, or paired start/stop | Measured |
| Cursor local store | `state.vscdb` under `~/Library/Application Support/Cursor`, `%APPDATA%\Cursor`, `~/.config/Cursor`, or `/mnt/c/Users/*/AppData/Roaming/Cursor` (WSL); override `AGENT_SPEC_CURSOR_USER_DIR`; off with `AGENT_SPEC_CURSOR_STORE=0` | estimated from message timestamps | Estimated, "Cursor local store (unofficial)" |
| Workflow runs | `.agent-spec/runs/<id>/` from the hub runner; joins its request when `run.json` has `generation_id` | measured | Measured |
| Reviews | `.agent-spec/metrics/reviews/<conversation_id>.json` from `/agent-spec-session-review` | — | AI-judged |

Every figure on Live, Coach and Learning renders through `<Num>` with its provenance; the
Vitest honesty test (`ui-src/src/test/honesty.test.tsx`) fails on any bare number.

## Trace model

A request is a trace keyed by Cursor's `generation_id`; the session is `conversation_id`.
Spans use OpenTelemetry field names (`trace_id`, `span_id`, `parent_span_id`, `kind`,
`start`, `end`, `attributes`). Kinds: `prompt` (root), `skill`, `subagent`, `tool`,
`guard`, `edit`, `response`, `compact`, `workflow`, `run_step`. Rows from a subagent's own
conversation nest under its span. Token counts are not in Cursor's documented hook payloads
and are not shown as measured.

| Route | Returns |
|---|---|
| `GET /api/requests?q=&source=&status=&skill=&session=&workspace=&limit=&offset=` | traces + facets |
| `GET /api/requests/<trace_id>` | trace, spans, responses, review |
| `GET /api/live` | SSE: `rows` events from `events.jsonl`, resumable with `Last-Event-ID` |
| `GET /api/coach/lag`, `/api/coach/issues` | measured latency; grouped AI findings |
| `GET /api/learning` | recurrence before/after per linked fact |
| `GET /api/catalog`, `/api/panels` | skills with `dashboard:` blocks; skill panels |

All routes are GET, loopback-only and token-checked (S-003).

## AI-first split

| Judgement (skills) | Computation (code) |
|---|---|
| `/agent-spec-session-review` reads `trace --session <id>` and writes findings, each citing a `span_id`, in a fixed category list | Trace building, durations, p50/p95, failure rates, counts |
| `/agent-spec-remember --addresses <category>`: the model decides which finding class a fact prevents | Recurrence: findings per session before vs after the fact's date |
| Fix prompts in findings; "Copy investigate prompt" in the inspector hands a span to the agent | Copying text to the clipboard |

The dashboard never grades. With no review file it shows "Not reviewed" and the prompt to
run one.

## Make your skill show up in five minutes

1. **Describe it.** Add a `dashboard:` block to the skill's frontmatter. Project › Skills
   and the catalog pick it up on reload; without the block the skill still appears with
   defaults. In Live's orchestration graph the skill's node takes its `icon` and
   `category`, shows each `emits` kind lit when a span of that kind ran under it and dim
   when none did, and a workflow gets a dashed *planned · not run* node for every `steps`
   id with no matching run step. Icons come from a fixed set in
   `ui-src/src/features/skillMeta.ts`; an unknown name keeps the span kind's icon.

   ```yaml
   dashboard:
     category: Diagnose          # catalog group
     icon: search                # lucide icon name
     emits: [subagent, tool]     # span kinds it produces
     steps: [fetch, analyse]     # workflows: step ids in order
   ```

2. **Show a number, table or timeline.** Have the skill write one JSON file to
   `.agent-spec/metrics/panels/<skill-name>/<panel>.json`. Project › Skills renders every
   valid file and lists invalid ones with the reason.

   ```json
   {"type": "kpi", "title": "Open findings", "value": 3, "unit": "findings", "hint": "since Monday", "provenance": "ai_judged"}
   {"type": "table", "title": "Slow tests", "columns": ["test", "seconds"], "rows": [["auth", 31]], "provenance": "measured"}
   {"type": "timeline", "title": "Deploys", "events": [{"ts": "2026-11-13", "label": "v2.1", "detail": "green"}], "provenance": "measured"}
   ```

   `provenance` is required: `measured`, `estimated`, `ai_judged` or `demo_seed`.
   `agent-spec-session-review` writes `last-review.json` as the worked example.

3. **Appear in Live.** Nothing to do. Its prompt (`/your-skill …`) or a read of its
   `SKILL.md` creates a skill span; its subagents, tools and edits nest under it. A
   hub-runner workflow appears as a `workflow` span with one `run_step` per step.

4. **Type a subagent's handoff (optional).** If the skill delegates to a subagent, add
   `agents/handoffs/<agent-name>.json` with `{"version", "input": <JSON Schema>, "output":
   <JSON Schema>}` and have the subagent answer with one fenced `json` block in that shape.
   The inspector then shows the subagent's task and reply as fields with a *typed* badge;
   a reply that does not parse or match is shown raw, with the first mismatches listed.
   The validator supports `type`, `required`, `properties`, `additionalProperties`,
   `items`, `enum` and `maxItems`. `install.sh` copies the schemas to
   `.cursor/agents/handoffs/`.

5. **Check it.** `bin/agent-spec-platform.py trace --list 5`, then open the request in Live.

## Develop

```bash
(cd ui-src && npm run build)      # initial bundle budget 400 KB gzip; graphs load lazily
(cd ui-src && npx vitest run)     # unit + page-level honesty test
(cd ui-src && npx playwright test) # smoke: Live -> inspector -> Coach -> Learning on fixture data
python3 tests/test_traces.py && python3 tests/test_cursor_event.py
```

## Related documents

| Document | Purpose |
|---|---|
| [`demo.md`](../demo.md) | Three-minute demo script |
| [`dashboard_overhaul.md`](../dashboard_overhaul.md) | §14 v3 design; earlier sections are history |
| [`tests/fixtures/hooks/README.md`](../tests/fixtures/hooks/README.md) | Hook payload fixtures and how to record live ones (DV-002) |
| [`LOGIC-AUDIT-DEC15.md`](LOGIC-AUDIT-DEC15.md) | Which logic stays code and which moved to skills |

---

*Control Plane v3 (DEC-16)*
