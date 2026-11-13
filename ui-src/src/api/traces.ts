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
