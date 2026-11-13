import type { Span } from "../api/traces";
import type { Skill } from "./skillMeta";

export interface ViewNode {
  id: string;
  span: Span;
  /** >1 when consecutive identical siblings were folded into one node. */
  count: number;
  members: Span[];
  parent: string | null;
  depth: number;
  /** DV-055: a step the workflow declares in its `dashboard.steps` that has no run_step span. */
  planned?: boolean;
  /** DV-055: the catalog entry for a skill or workflow node, when it has one. */
  skill?: Skill;
  /** DV-055: each kind the skill declares in `dashboard.emits`, and whether a descendant span has it. */
  emits?: { kind: string; seen: boolean }[];
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

/** DV-055: join the view with the skill catalog. Skill and workflow nodes get their catalog
 *  entry and the declared `emits` checked against the kinds found below them; a workflow's
 *  declared `steps` without a matching run_step become `planned` nodes, so the graph shows
 *  the whole plan and what of it ran. Nodes without a catalog entry are returned unchanged. */
export function planView(view: ViewNode[], catalog: Map<string, Skill>): ViewNode[] {
  if (!catalog.size) return view;
  const kids = new Map<string, ViewNode[]>();
  for (const v of view) if (v.parent) kids.set(v.parent, [...(kids.get(v.parent) ?? []), v]);
  const kindsBelow = (id: string, acc = new Set<string>()): Set<string> => {
    for (const c of kids.get(id) ?? []) {
      acc.add(c.span.kind);
      kindsBelow(c.id, acc);
    }
    return acc;
  };
  const out: ViewNode[] = [];
  for (const v of view) {
    const skill = v.span.kind === "skill" || v.span.kind === "workflow" ? catalog.get(v.span.name) : undefined;
    if (!skill) {
      out.push(v);
      continue;
    }
    const below = kindsBelow(v.id);
    out.push({ ...v, skill, emits: skill.emits.map((kind) => ({ kind, seen: below.has(kind) })) });
    if (v.span.kind !== "workflow" || !skill.steps.length) continue;
    const ran = new Set((kids.get(v.id) ?? []).filter((c) => c.span.kind === "run_step").map((c) => c.span.name));
    skill.steps.forEach((step, i) => {
      if (ran.has(step)) return;
      const id = `${v.id}#planned:${step}`;
      out.push({
        id, count: 1, members: [], parent: v.id, depth: v.depth + 1, planned: true,
        span: { span_id: id, trace_id: v.span.trace_id, parent_span_id: v.id, kind: "run_step", name: step,
                status: "planned", seq: 1000 + i, start: null, end: null, duration_ms: null, attributes: {} },
      });
    });
  }
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
