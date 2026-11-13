import type { Span } from "../api/traces";

export interface ViewNode {
  id: string;
  span: Span;
  /** >1 when consecutive identical siblings were folded into one node. */
  count: number;
  members: Span[];
  parent: string | null;
  depth: number;
}

const ms = (iso?: string | null) => (iso ? new Date(iso).getTime() : NaN);

/** Order children by start time and fold runs of identical (kind, name, status) siblings when
 *  the trace is large, so a 250-call request still reads as a graph. */
export function buildView(spans: Span[], foldAbove = 40): ViewNode[] {
  const byParent = new Map<string | null, Span[]>();
  const ids = new Set(spans.map((s) => s.span_id));
  for (const s of spans) {
    const p = s.parent_span_id && ids.has(s.parent_span_id) ? s.parent_span_id : null;
    if (!byParent.has(p)) byParent.set(p, []);
    byParent.get(p)!.push(s);
  }
  for (const list of byParent.values()) list.sort((a, b) => (ms(a.start) || 0) - (ms(b.start) || 0) || a.seq - b.seq);
  const fold = spans.length > foldAbove;
  const out: ViewNode[] = [];
  const walk = (parent: string | null, viewParent: string | null, depth: number) => {
    const kids = byParent.get(parent) ?? [];
    if (fold && kids.length > 10) {
      // Wide fan-out: one node per (kind, name, status) among leaf siblings, in first-seen order.
      // Time order is still exact in the waterfall; the graph shows structure.
      const groups = new Map<string, Span[]>();
      for (const s of kids) {
        const key = byParent.has(s.span_id) ? `own:${s.span_id}` : `${s.kind}|${s.name}|${s.status}`;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key)!.push(s);
      }
      for (const run of groups.values()) {
        const s = run[0];
        out.push({ id: s.span_id, span: s, count: run.length, members: run, parent: viewParent, depth });
        walk(s.span_id, s.span_id, depth + 1);
      }
      return;
    }
    let i = 0;
    while (i < kids.length) {
      const s = kids[i];
      const run = [s];
      if (fold && !byParent.has(s.span_id)) {
        while (
          i + run.length < kids.length &&
          !byParent.has(kids[i + run.length].span_id) &&
          kids[i + run.length].kind === s.kind &&
          kids[i + run.length].name === s.name &&
          kids[i + run.length].status === s.status
        ) run.push(kids[i + run.length]);
      }
      out.push({ id: s.span_id, span: s, count: run.length, members: run, parent: viewParent, depth });
      walk(s.span_id, s.span_id, depth + 1);
      i += run.length;
    }
  };
  walk(null, null, 0);
  return out;
}

export function timeBounds(spans: Span[]): [number, number] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const s of spans) {
    const a = ms(s.start);
    const b = ms(s.end) || a;
    if (!Number.isNaN(a)) lo = Math.min(lo, a);
    if (!Number.isNaN(b)) hi = Math.max(hi, b);
  }
  if (!Number.isFinite(lo)) return [0, 1];
  return [lo, Math.max(hi, lo + 1)];
}

export function bytesOf(s: Span, key: "bytes_in" | "bytes_out"): number | null {
  const v = s.attributes?.[key];
  return typeof v === "number" ? v : null;
}
