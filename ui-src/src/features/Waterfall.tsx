import { useMemo } from "react";
import type { Span } from "../api/traces";
import { cn, fmtMs } from "../lib/utils";
import { buildView, timeBounds } from "./spanTree";
import { kindMeta, statusTone } from "./kinds";

/** DV-032: one bar per span on a shared time axis; the slowest step is visible without reading. */
export function Waterfall({ spans, provenance, selected, hovered, onSelect, onHover }: {
  spans: Span[];
  provenance: "measured" | "estimated";
  selected?: string | null;
  hovered?: string | null;
  onSelect: (s: Span, members: Span[]) => void;
  onHover?: (id: string | null) => void;
}) {
  const rows = useMemo(() => buildView(spans, 120), [spans]);
  const [lo, hi] = useMemo(() => timeBounds(spans), [spans]);
  const span = hi - lo;
  const slowest = useMemo(
    () => rows.filter((r) => r.span.kind !== "prompt" && r.span.kind !== "skill").reduce<string | null>((best, r) =>
      !best || (r.span.duration_ms ?? 0) > (rows.find((x) => x.id === best)!.span.duration_ms ?? 0) ? r.id : best, null),
    [rows],
  );
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  return (
    <div className="text-xs">
      <div className="sticky top-0 z-10 grid grid-cols-[minmax(180px,30%)_1fr_72px] border-b border-border bg-background/95 py-1 text-[10px] text-muted-foreground backdrop-blur">
        <span className="px-2">Span</span>
        <div className="relative">
          {ticks.map((t) => (
            <span key={t} className="absolute -translate-x-1/2" style={{ left: `${t * 100}%` }}>
              <span data-provenance={provenance} className="tabular">{fmtMs(span * t)}</span>
            </span>
          ))}
        </div>
        <span className="pr-2 text-right">Duration</span>
      </div>
      {rows.map((r) => {
        const s = r.span;
        const meta = kindMeta(s.kind);
        const a = s.start ? new Date(s.start).getTime() : lo;
        const b = s.end ? new Date(s.end).getTime() : hi;
        const left = ((a - lo) / span) * 100;
        const width = Math.max(((b - a) / span) * 100, 0.4);
        const tone = statusTone(s.status);
        const on = selected === s.span_id || hovered === s.span_id || r.members.some((m) => m.span_id === hovered);
        return (
          <button
            key={r.id}
            type="button"
            onClick={() => onSelect(s, r.members)}
            onMouseEnter={() => onHover?.(s.span_id)}
            onMouseLeave={() => onHover?.(null)}
            className={cn("grid w-full grid-cols-[minmax(180px,30%)_1fr_72px] items-center py-[3px] text-left hover:bg-muted/60", on && "bg-primary/10")}
          >
            <span className="flex min-w-0 items-center gap-1.5 px-2" style={{ paddingLeft: 8 + r.depth * 12 }}>
              <meta.icon size={11} className={meta.color} />
              <span className="truncate">{s.kind === "prompt" ? "request" : s.name}</span>
              {r.count > 1 ? <span className="text-muted-foreground">×{r.count}</span> : null}
            </span>
            <span className="relative h-3.5">
              <span
                className={cn("absolute top-0 h-full rounded-sm", meta.bar, tone === "danger" ? "opacity-100 ring-1 ring-danger" : "opacity-80", s.status === "running" && "animate-pulse", r.id === slowest && "ring-2 ring-warning")}
                style={{ left: `${left}%`, width: `${width}%` }}
              />
            </span>
            <span className="pr-2 text-right text-muted-foreground">
              <span data-provenance={provenance} className="tabular">{fmtMs(s.duration_ms)}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
