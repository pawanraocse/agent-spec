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

## Four spaces

| Space | Question | Built from |
|---|---|---|
| **Live** (home) | What is my agent doing, and what did it do? | Request feed; orchestration graph (React Flow), waterfall, span inspector, responses, review, replay |
| **Coach** | Where is it slow or wasteful? | p50/p95 per span kind and per tool, slowest spans (measured); top-3 issues with weekly trend and copyable fix prompts (AI-judged) |
| **Learning** | Is it getting better? | Per fact: findings per session in the N reviewed sessions before vs after it was recorded |
| **Project** | What does the harness know? | Skill catalog, knowledge graph with blast radius, skill panels, session history, runs, memory, health |

Ctrl/⌘-K searches requests and skills. Settings holds the theme (dark, light, system).

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
   `.agent-spec/metrics/panels/<skill-name>/<panel>.json`. Project › Panels renders every
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

*Algosec Cursor AI · Control Plane v3 (DEC-16)*
