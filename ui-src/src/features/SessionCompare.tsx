import type { Provenance } from "../api/client";
import { Num } from "../components/Num";

type Tokens = { input: number; output: number; cache_read: number; cache_write: number; total: number };
export type CompareSide = {
  session_id: string;
  provenance?: Provenance;
  requests?: number;
  tool_calls?: number;
  tool_failures?: number;
  files_edited?: number;
  requests_with_edits?: number;
  verified_requests?: number;
  guard_blocks?: number;
  subagents?: number;
  compactions?: number;
  rework_files?: number;
  tokens?: Tokens | null;
  skills?: string[];
  quality?: { provenance: Provenance; overall: number | null; dimensions: Record<string, number | null> } | null;
  context?: { provenance: Provenance; digest_bytes: number | null; facts_injected: number; facts: string[] } | null;
};
export type CompareResult = { a: CompareSide; b: CompareSide; delta: Record<string, number> | null; text: string | null };

const SIGNALS: [keyof CompareSide, string][] = [
  ["requests", "Requests"],
  ["tool_calls", "Tool calls"],
  ["tool_failures", "Tool failures"],
  ["files_edited", "Files edited"],
  ["verified_requests", "Requests verified after last edit"],
  ["rework_files", "Files reworked later"],
  ["guard_blocks", "Guard blocks"],
  ["subagents", "Subagents"],
  ["compactions", "Compactions"],
];

function Cell({ v, p }: { v: number | null | undefined; p: Provenance }) {
  if (v == null) return <span className="text-muted-foreground">—</span>;
  return <Num p={p}>{v.toLocaleString()}</Num>;
}

/** PI-010: two conversations side by side. A dash means the data does not show it, not zero. */
export function SessionCompare({ result }: { result: CompareResult }) {
  const { a, b, delta } = result;
  const pa = a.provenance ?? "estimated";
  const pb = b.provenance ?? "estimated";
  const pd: Provenance = pa === "measured" && pb === "measured" ? "measured" : "estimated";
  const dims = Array.from(new Set([...Object.keys(a.quality?.dimensions ?? {}), ...Object.keys(b.quality?.dimensions ?? {})])).sort();
  const row = (label: string, va: React.ReactNode, vb: React.ReactNode, vd?: React.ReactNode) => (
    <tr key={label} className="border-t border-border">
      <td className="py-1 pr-2 text-muted-foreground">{label}</td>
      <td className="pr-2">{va}</td>
      <td className="pr-2">{vb}</td>
      <td>{vd ?? <span className="text-muted-foreground">—</span>}</td>
    </tr>
  );
  return (
    <div className="space-y-3 border-t border-border pt-3" data-testid="session-compare">
      <table className="w-full text-left">
        <thead className="text-muted-foreground">
          <tr>
            <th className="py-1">&nbsp;</th>
            <th className="font-mono">{a.session_id.slice(0, 12)}</th>
            <th className="font-mono">{b.session_id.slice(0, 12)}</th>
            <th>A − B</th>
          </tr>
        </thead>
        <tbody>
          <tr><td colSpan={4} className="pt-2 font-semibold">Tokens</td></tr>
          {row("Total", <Cell v={a.tokens?.total} p={pa} />, <Cell v={b.tokens?.total} p={pb} />,
            delta?.tokens_total != null ? <Cell v={delta.tokens_total} p={pd} /> : undefined)}
          {row("Cache read", <Cell v={a.tokens?.cache_read} p={pa} />, <Cell v={b.tokens?.cache_read} p={pb} />)}
          <tr><td colSpan={4} className="pt-2 font-semibold">Signals</td></tr>
          {SIGNALS.map(([k, label]) =>
            row(label, <Cell v={a[k] as number | undefined} p={pa} />, <Cell v={b[k] as number | undefined} p={pb} />,
              delta && delta[k as string] != null ? <Cell v={delta[k as string]} p={pd} /> : undefined),
          )}
          <tr><td colSpan={4} className="pt-2 font-semibold">Quality (session review)</td></tr>
          {row("Overall", <Cell v={a.quality?.overall} p="ai_judged" />, <Cell v={b.quality?.overall} p="ai_judged" />)}
          {dims.map((d) => row(d, <Cell v={a.quality?.dimensions[d]} p="ai_judged" />, <Cell v={b.quality?.dimensions[d]} p="ai_judged" />))}
          {!a.quality && !b.quality && row("Not reviewed", "—", "—")}
          <tr><td colSpan={4} className="pt-2 font-semibold">Context</td></tr>
          {row("Digest bytes", <Cell v={a.context?.digest_bytes} p="measured" />, <Cell v={b.context?.digest_bytes} p="measured" />)}
          {row("Facts injected", <Cell v={a.context?.facts_injected} p="measured" />, <Cell v={b.context?.facts_injected} p="measured" />)}
          {row("Skills", (a.skills ?? []).join(", ") || "—", (b.skills ?? []).join(", ") || "—")}
        </tbody>
      </table>
      {result.text && (
        <details>
          <summary className="cursor-pointer text-muted-foreground">Transcript token comparison</summary>
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap" data-figure-exempt>{result.text}</pre>
        </details>
      )}
    </div>
  );
}
