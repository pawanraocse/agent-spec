import { V2_ROUTES } from "./fixtures-v2";

// Fixture API payloads for the page-level honesty test (DV-005) and the Playwright smoke (DV-061).
export const requestList = {
  total: 1, limit: 100, offset: 0,
  facets: { sources: ["hook"], skills: ["agent-spec-investigate"], statuses: ["completed"], workspaces: [] },
  requests: [{
    trace_id: "gen-1", session_id: "conv-1", source: "hook", prompt: "/agent-spec-investigate why does login fail",
    model: "claude-sonnet-4-5", cursor_version: "2.1.0", start: "2026-11-13T10:00:00.000Z", end: "2026-11-13T10:00:06.100Z",
    duration_ms: 6100, status: "completed", span_count: 5, tool_count: 2, subagent_count: 1, error_count: 1,
    guard_count: 1, edit_count: 0, skills: ["agent-spec-investigate"], provenance: "measured",
  }],
};

const span = (id: string, kind: string, name: string, parent: string | null, start: number, dur: number, status = "ok", attributes: Record<string, unknown> = {}) => ({
  span_id: id, trace_id: "gen-1", parent_span_id: parent, kind, name, status, seq: 0, attributes,
  start: new Date(Date.parse("2026-11-13T10:00:00.000Z") + start).toISOString(),
  end: new Date(Date.parse("2026-11-13T10:00:00.000Z") + start + dur).toISOString(), duration_ms: dur,
});

export const requestDetail = {
  trace: requestList.requests[0],
  spans: [
    span("gen-1#root", "prompt", "/agent-spec-investigate why does login fail", null, 0, 6100, "completed"),
    span("gen-1#skill:agent-spec-investigate", "skill", "agent-spec-investigate", "gen-1#root", 0, 6100),
    span("e2", "tool", "Read", "gen-1#skill:agent-spec-investigate", 1000, 200, "ok", { target: "file_path=/p/a.py", bytes_in: 20, bytes_out: 900, ranged: false }),
    span("e3", "subagent", "agent-spec-search", "gen-1#skill:agent-spec-investigate", 1500, 2500, "completed", { task: "find callers", summary: "3 callers", bytes_in: 12, bytes_out: 9, tool_call_count: 1 }),
    span("g1", "guard", "whole-file-read", "gen-1#skill:agent-spec-investigate", 4200, 0, "blocked", { target: "big.py" }),
    span("e8", "response", "response", "gen-1#root", 5200, 800, "ok", { text: "The session is undefined after expiry.", text_chars: 38 }),
  ],
  responses: [{ span_id: "e8", ts: "2026-11-13T10:00:06.000Z", text: "The session is undefined after expiry.", text_chars: 38 }],
  review: null,
  session_requests: ["gen-1"],
  context: undefined as unknown,
};

export const lag = {
  requests: 1, guard_blocks: 1, compactions: 0, whole_file_reads: 1, subagent_bytes_in: 12, subagent_bytes_out: 9, sources: ["hook"],
  by_kind: [{ key: "subagent", count: 1, failure_rate: 0, p50_ms: 2500, p95_ms: 2500, total_ms: 2500, provenance: "measured" }],
  by_tool: [{ key: "tool:Read", count: 1, failure_rate: 0, p50_ms: 200, p95_ms: 200, total_ms: 200, provenance: "measured" }],
  slowest: [{ span_id: "e3", trace_id: "gen-1", kind: "subagent", name: "agent-spec-search", duration_ms: 2500, source: "hook" }],
};

export const issues = {
  reviewed_sessions: 4, all_categories: 2, provenance: "ai_judged", grades: [],
  issues: [{
    category: "whole_file_read", title: "Whole-file read of a large module", count: 3, sessions: 2, severity: "high",
    trend: [{ week: "2026-W44", count: 2 }, { week: "2026-W45", count: 1 }],
    examples: [{ session_id: "conv-1", trace_id: "gen-1", span_id: "e2", title: "Read a.py without a range", detail: "" }],
    fix_prompt: "/agent-spec-query-graph before reading files over 20 KB",
  }],
};

export const learning = {
  window: 10, unlinked: 1, facts_total: 2, reviewed_sessions: 4,
  recurrence: [{ id: "f1", kind: "fact", subject: "input discipline", created: "2026-10-05", addresses: ["whole_file_read"],
    before_sessions: 2, after_sessions: 2, before_findings: 3, after_findings: 0, before_rate: 1.5, after_rate: 0, verdict: "fewer" }],
  facts_by_month: [{ month: "2026-10", count: 2 }], experience_tiers: { trusted: 1 }, injections: [],
};

export const contextBudget = {
  used: 120000, floor: 18000, limit: 200000, percent: 60, growth: 6.67, carried_tokens: 102000, carry_per_call: 12000,
  reset_once: 22500, saving_per_call: 10200, breakeven_calls: 2.2, verdict: "reset", floor_source: "this chat's fixed categories",
  breakdown: { system_prompt: 500, tools: 8500, rules: 5600, skills: 3400, conversation: 102000 }, nudged: true,
  weights: { read: 0.1, write: 1.25 }, provenance: "measured",
};
export const contextInfo = {
  budget: contextBudget,
  billed: { requests: 2, input_total: 193809, output_total: 20, cache_read_share: 0.806, points: [36176, 157633], generations: ["gen-0", "gen-1"] },
};
requestDetail.context = contextInfo;
export const contextOverview = {
  floor: 18000, chats: 2, by_verdict: { reset: 1, carry: 1, fresh: 0 }, carried_tokens: 109000, reset_saving_per_call: 10200,
  breakeven_calls: 5, weights: { read: 0.1, write: 1.25 }, provenance: "measured", source: "fixture",
  top: [
    { session_id: "conv-1", name: "Login bug", workspace: "/p", latest_trace_id: "gen-1", ...contextInfo },
    { session_id: "conv-2", name: "Short chat", workspace: "/p", latest_trace_id: null,
      budget: { ...contextBudget, used: 25000, percent: 12.5, growth: 1.39, carried_tokens: 7000, carry_per_call: 2500, saving_per_call: 700,
        breakeven_calls: 32.1, verdict: "carry", breakdown: null, nudged: false, floor_source: "smallest chat on this machine" }, billed: null },
  ],
};

export const ROUTES: Record<string, unknown> = {
  "/api/context": contextOverview,
  ...V2_ROUTES,
  "/api/requests": requestList,
  "/api/requests/gen-1": requestDetail,
  "/api/conversations": {
    total: 1, limit: 500, offset: 0, facets: { workspaces: ["/p"] },
    conversations: [{
      session_id: "conv-1", name: "Login bug", first_prompt: "/agent-spec-investigate why does login fail",
      last_prompt: "/agent-spec-investigate why does login fail", workspace: "/p", sources: ["hook"], provenance: "measured",
      start: "2026-11-13T10:00:00.000Z", end: "2026-11-13T10:00:06.100Z", requests: 1, running: 0,
      skills: ["agent-spec-investigate"], models: ["claude-sonnet-4-5"], reviewed: false, has_transcript: false,
      latest_trace_id: "gen-1", tool_count: 2, subagent_count: 1, error_count: 1, guard_count: 1, edit_count: 0, duration_ms: 6100,
      context: contextInfo,
    }],
  },
  "/api/coach/lag": lag,
  "/api/coach/issues": issues,
  "/api/learning": learning,
  "/api/catalog": { self_described: 1, skills: [{ id: "agent-spec-investigate", name: "agent-spec-investigate", description: "", category: "Diagnose",
    icon: "search", emits: ["subagent", "tool", "edit"], steps: [], self_described: true, is_workflow: false, uses: 1 }] },
  "/api/automations": {
    config: ".agent-spec/automation.json", log: ".agent-spec/metrics/automation.jsonl",
    totals: { runs: 3, succeeded: 2, failed: 1, last_24h: 3, enabled: 4, count: 5 },
    automations: [
      { id: "graph-refresh", title: "Refresh the knowledge graph", trigger: "stop after an edit", kind: "script", replaces: "re-running the indexer",
        env: null, enabled: true, switched_off: false, env_off: false, runs: 2, succeeded: 1, failed: 1, duration_ms_total: null,
        last: { ts: "2026-11-14T02:00:00Z", name: "graph-refresh", status: "failed", reason: "could not start the builder" } },
      { id: "context-nudge", title: "Suggest a fresh chat", trigger: "stop past break-even", kind: "skill", replaces: "guessing when a reset pays",
        env: "AGENT_SPEC_CONTEXT_NUDGE", enabled: false, switched_off: false, env_off: true, runs: 0, succeeded: 0, failed: 0, duration_ms_total: null, last: null },
      { id: "snapshot-rotate", title: "Rotate the session snapshot", trigger: "sessionEnd", kind: "script", replaces: "rotate by hand",
        env: null, enabled: true, switched_off: false, env_off: false, runs: 1, succeeded: 1, failed: 0, duration_ms_total: 40,
        last: { ts: "2026-11-14T03:00:00Z", name: "snapshot-rotate", status: "ok", reason: "12000 B, under the 40000 B threshold", duration_ms: 40 } },
    ],
    recent: [
      { ts: "2026-11-14T03:00:00Z", name: "snapshot-rotate", status: "ok", reason: "12000 B, under the 40000 B threshold", duration_ms: 40 },
      { ts: "2026-11-14T02:00:00Z", name: "graph-refresh", status: "failed", reason: "could not start the builder" },
    ],
  },
  "/api/status_bar": { graph: { text: "2m old" }, doctor: { status: "ok" }, hooks: { a: true } },
};

export function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const path = String(input).replace(/^https?:\/\/[^/]+/, "").split("?")[0];
  const body = ROUTES[path] ?? ROUTES[decodeURIComponent(path)];
  return Promise.resolve(new Response(JSON.stringify(body ?? {}), { status: body ? 200 : 404, headers: { "Content-Type": "application/json" } }));
}
