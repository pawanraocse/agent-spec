import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet } from "./client";

export type SpanKind = "prompt" | "skill" | "subagent" | "tool" | "guard" | "edit" | "response" | "compact" | "workflow" | "run_step";
export type Source = "hook" | "cursor_store" | "run" | "demo_seed";

export interface Trace {
  trace_id: string;
  session_id: string;
  source: Source;
  workspace?: string | null;
  prompt?: string | null;
  session_name?: string | null;
  model?: string | null;
  cursor_version?: string | null;
  start?: string | null;
  end?: string | null;
  duration_ms?: number | null;
  status: string;
  span_count: number;
  tool_count: number;
  subagent_count: number;
  error_count: number;
  guard_count: number;
  edit_count: number;
  skills: string[];
  transcript_path?: string | null;
  provenance: "measured" | "estimated";
}

export interface Span {
  span_id: string;
  trace_id: string;
  parent_span_id: string | null;
  kind: SpanKind;
  name: string;
  start?: string | null;
  end?: string | null;
  duration_ms?: number | null;
  status: string;
  seq: number;
  attributes: Record<string, unknown>;
}

/** DV-057: one side of a typed subagent handoff, checked server-side against agents/handoffs/<agent>.json. */
export interface HandoffSide {
  typed: boolean;
  value: Record<string, unknown> | null;
  errors: string[];
}

export interface Handoff {
  agent: string;
  version?: string | null;
  input: HandoffSide | null;
  output: HandoffSide | null;
}

export interface Finding {
  category: string;
  severity: string;
  title: string;
  detail?: string;
  span_id?: string;
  trace_id?: string;
  fix_prompt?: string;
}

export interface Review {
  conversation_id?: string;
  session_id?: string;
  grade?: string;
  score?: number;
  summary?: string;
  model?: string;
  rubric_version?: string;
  reviewed_at?: string;
  findings?: Finding[];
  pros?: ({ span_id?: string; text?: string } | string)[];
  improvements?: string[];
  evidence?: { span_id?: string; event_id?: string; check?: string; verdict?: string }[];
}

export interface RequestList {
  total: number;
  limit: number;
  offset: number;
  requests: Trace[];
  facets: { sources: string[]; skills: string[]; statuses: string[]; workspaces: string[] };
}

export interface RequestDetail {
  trace: Trace;
  spans: Span[];
  responses: { span_id: string; ts?: string; text?: string; text_chars?: number }[];
  review: Review | null;
  session_requests: string[];
  context?: ContextInfo | null;
}

/** Context budget (exact arithmetic over Cursor's own counters; see context_budget.py). */
export interface ContextBudget {
  used: number;
  floor: number;
  limit: number | null;
  percent: number | null;
  growth: number | null;
  carried_tokens: number;
  carry_per_call: number;
  reset_once: number;
  saving_per_call: number;
  breakeven_calls: number | null;
  reset_threshold_calls: number;
  verdict: "reset" | "carry" | "fresh";
  floor_source?: string;
  breakdown?: Record<string, number> | null;
  nudged?: boolean;
  weights: { read: number; write: number };
  provenance: "measured";
}

export interface ContextBilled {
  requests: number;
  input_total: number;
  output_total: number;
  cache_read_share: number | null;
  points: number[];
  generations?: string[];
}

export interface ContextInfo {
  budget: ContextBudget | null;
  billed: ContextBilled | null;
}

export interface ContextOverview {
  floor: number | null;
  chats: number;
  by_verdict: { reset: number; carry: number; fresh: number };
  carried_tokens: number;
  reset_saving_per_call: number;
  breakeven_calls: number;
  weights: { read: number; write: number };
  top: (ContextInfo & { session_id: string; name?: string | null; workspace?: string | null; latest_trace_id?: string | null })[];
  provenance: "measured";
  source: string;
}

export function useContextOverview() {
  return useQuery({ queryKey: ["context"], queryFn: () => apiGet<ContextOverview>("/api/context"), refetchInterval: 15000 });
}

export interface Filters {
  q?: string;
  source?: string;
  status?: string;
  skill?: string;
  session?: string;
  workspace?: string;
}

function qs(f: Filters & { limit?: number }): string {
  const p = new URLSearchParams();
  Object.entries(f).forEach(([k, v]) => {
    if (v !== undefined && v !== "" && v !== null) p.set(k, String(v));
  });
  const s = p.toString();
  return s ? `?${s}` : "";
}

export function useRequests(filters: Filters, limit = 100) {
  return useQuery({
    queryKey: ["requests", filters, limit],
    queryFn: () => apiGet<RequestList>(`/api/requests${qs({ ...filters, limit })}`),
    refetchInterval: (q) => (q.state.error ? false : 15_000),
  });
}

export interface Conversation {
  session_id: string;
  name?: string | null;
  first_prompt?: string | null;
  last_prompt?: string | null;
  workspace?: string | null;
  sources: Source[];
  provenance: "measured" | "estimated";
  start?: string | null;
  end?: string | null;
  requests: number;
  running: number;
  skills: string[];
  models: string[];
  reviewed: boolean;
  has_transcript: boolean;
  latest_trace_id: string;
  tool_count: number;
  subagent_count: number;
  error_count: number;
  guard_count: number;
  edit_count: number;
  duration_ms: number;
  context?: ContextInfo | null;
}

export interface ConversationList {
  total: number;
  conversations: Conversation[];
  facets: { workspaces: string[] };
}

/** Every Cursor chat (hooks + Cursor's local store), one row per conversation. */
export function useConversations(filters: Pick<Filters, "q" | "source" | "workspace">, limit = 500) {
  return useQuery({
    queryKey: ["conversations", filters, limit],
    queryFn: () => apiGet<ConversationList>(`/api/conversations${qs({ ...filters, limit })}`),
    refetchInterval: (q) => (q.state.error ? false : 15_000),
  });
}

export function useRequest(id: string | null) {
  return useQuery({
    queryKey: ["request", id],
    enabled: !!id,
    queryFn: () => apiGet<RequestDetail>(`/api/requests/${encodeURIComponent(id!)}`),
  });
}

export type LiveState = "connecting" | "live" | "polling" | "off";

/** DV-013: one EventSource on /api/live; on new rows refresh the feed and the open request.
 *  Falls back to polling every 2 s when the stream drops. */
export function useLive(enabled = true): { state: LiveState; lastRowAt: number | null; rows: number } {
  const qc = useQueryClient();
  const [state, setState] = useState<LiveState>(enabled ? "connecting" : "off");
  const [lastRowAt, setLast] = useState<number | null>(null);
  const [rows, setRows] = useState(0);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled || typeof EventSource === "undefined") {
      setState("off");
      return;
    }
    let poll: number | null = null;
    const refresh = () => {
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["requests"] });
        qc.invalidateQueries({ queryKey: ["request"] });
        qc.invalidateQueries({ queryKey: ["conversations"] });
      }, 250);
    };
    const es = new EventSource("/api/live");
    es.addEventListener("hello", () => {
      setState("live");
      if (poll) window.clearInterval(poll);
      poll = null;
    });
    es.addEventListener("rows", (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data);
        const n = Array.isArray(data.rows) ? data.rows.length : 0;
        if (n) {
          setRows((r) => r + n);
          setLast(Date.now());
          refresh();
        }
      } catch {
        /* ignore malformed frame */
      }
    });
    es.onerror = () => {
      setState("polling");
      if (!poll) poll = window.setInterval(refresh, 2000);
    };
    return () => {
      es.close();
      if (poll) window.clearInterval(poll);
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [enabled, qc]);

  return { state, lastRowAt, rows };
}
