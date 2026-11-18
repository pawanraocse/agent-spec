import type { Provenance } from "../api/client";
import { Prov } from "./Num";


function Sparkline({ data }: { data: number[] }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * 70;
      const y = 18 - ((v - min) / range) * 14;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg className="h-5 w-18 overflow-visible" viewBox="0 0 70 20">
      <polyline
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
        className="text-primary"
      />
    </svg>
  );
}

export function Metric({
  label,
  value,
  provenance,
  formula,
  sparkline,
}: {
  label: string;
  value: string | number;
  provenance: Provenance;
  formula?: string;
  sparkline?: number[];
}) {
  // Same tile and provenance badge as <Stat>, so a figure looks the same on every page.
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] uppercase tracking-wide text-muted-foreground" data-figure-exempt>{label}</span>
        <span title={formula}><Prov p={provenance} /></span>
      </div>
      <div className="mt-1 flex items-baseline justify-between gap-2">
        <div className="text-xl font-semibold tabular-nums" data-provenance={provenance}>{value}</div>
        {sparkline ? <Sparkline data={sparkline} /> : null}
      </div>
      {provenance === "estimated" && formula ? (
        <p className="mt-0.5 text-[11px] text-muted-foreground">{formula}</p>
      ) : null}
    </div>
  );
}
