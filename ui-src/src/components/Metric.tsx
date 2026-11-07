import type { Provenance } from "../api/client";

const LABEL: Record<Provenance, string> = {
  measured: "Measured",
  estimated: "Estimated",
  demo_seed: "Demo seed",
};

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
        className="text-sky-400/80"
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
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs uppercase tracking-wide text-slate-500">{label}</span>
        <span
          className="rounded px-1.5 py-0.5 text-[10px] font-medium uppercase text-amber-200/90 ring-1 ring-amber-500/40"
          title={formula}
        >
          {LABEL[provenance]}
        </span>
      </div>
      <div className="mt-1 flex items-baseline justify-between gap-2">
        <div className="text-2xl font-semibold tabular-nums text-slate-100">{value}</div>
        {sparkline ? <Sparkline data={sparkline} /> : null}
      </div>
      {provenance === "estimated" && formula ? (
        <p className="mt-1 text-[11px] text-slate-500">{formula}</p>
      ) : null}
    </div>
  );
}
