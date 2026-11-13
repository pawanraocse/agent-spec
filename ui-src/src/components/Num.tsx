import type { Provenance } from "../api/client";
import { cn } from "../lib/utils";

const LABEL: Record<Provenance, string> = {
  measured: "Measured",
  estimated: "Estimated",
  demo_seed: "Demo seed",
  ai_judged: "AI-judged",
};
const TONE: Record<Provenance, string> = {
  measured: "text-success ring-success/30 bg-success/10",
  estimated: "text-warning ring-warning/30 bg-warning/10",
  demo_seed: "text-muted-foreground ring-border bg-muted",
  ai_judged: "text-accent ring-accent/30 bg-accent/10",
};

/** Every figure on a v3 page renders through <Num> so its provenance travels with it (DV-005). */
export function Num({ children, p, className, title }: { children: React.ReactNode; p: Provenance; className?: string; title?: string }) {
  return (
    <span data-provenance={p} className={cn("tabular", className)} title={title ?? LABEL[p]}>
      {children}
    </span>
  );
}

export function Prov({ p, className }: { p: Provenance; className?: string }) {
  return (
    <span className={cn("inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ring-1 ring-inset", TONE[p], className)}>
      {LABEL[p]}
    </span>
  );
}

/** KPI tile: label, value, provenance badge, optional hint. */
export function Stat({ label, value, p, hint }: { label: string; value: React.ReactNode; p: Provenance; hint?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</span>
        <Prov p={p} />
      </div>
      <div className="mt-1 text-xl font-semibold">
        <Num p={p}>{value}</Num>
      </div>
      {hint ? <p className="mt-0.5 text-[11px] text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
