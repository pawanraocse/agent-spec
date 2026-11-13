import type { Handoff, HandoffSide } from "../api/traces";
import { Prov } from "../components/Num";
import { Badge } from "../components/ui/badge";

const isRecord = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);

function Scalar({ v }: { v: unknown }) {
  if (v === null || v === undefined) return <span className="text-muted-foreground">—</span>;
  if (typeof v === "boolean") return <span>{v ? "yes" : "no"}</span>;
  return <span className="break-words">{String(v)}</span>;
}

/** Arrays of objects become a table (union of keys), other arrays a list, objects nested rows. */
function Value({ v }: { v: unknown }) {
  if (Array.isArray(v)) {
    if (!v.length) return <span className="text-muted-foreground">none</span>;
    if (v.every(isRecord)) {
      const cols = Array.from(new Set(v.flatMap((r) => Object.keys(r))));
      return (
        <table className="w-full table-fixed border-collapse text-[11px]">
          <thead><tr>{cols.map((c) => <th key={c} className="border-b border-border/60 py-0.5 pr-2 text-left font-normal text-muted-foreground">{c}</th>)}</tr></thead>
          <tbody>
            {v.map((r, i) => (
              <tr key={i} className="align-top">{cols.map((c) => <td key={c} className="border-b border-border/30 py-0.5 pr-2"><Value v={r[c]} /></td>)}</tr>
            ))}
          </tbody>
        </table>
      );
    }
    return <ul className="space-y-0.5">{v.map((x, i) => <li key={i}><Value v={x} /></li>)}</ul>;
  }
  if (isRecord(v)) {
    return (
      <dl className="space-y-0.5">
        {Object.entries(v).map(([k, x]) => (
          <div key={k} className="grid grid-cols-[110px_1fr] gap-2">
            <dt className="text-muted-foreground">{k}</dt>
            <dd className="min-w-0"><Value v={x} /></dd>
          </div>
        ))}
      </dl>
    );
  }
  return <Scalar v={v} />;
}

function Side({ label, side }: { label: string; side: HandoffSide }) {
  return (
    <div className="mt-3">
      <div className="mb-1 flex items-center gap-2">
        <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
        {side.typed ? <Badge tone="success">typed</Badge> : <Badge tone="warning">untyped</Badge>}
      </div>
      {side.typed && side.value ? (
        // What the subagent reported, not something the dashboard measured.
        <div className="rounded-md bg-muted p-2 font-mono text-[11px]" data-provenance="ai_judged">
          <Value v={side.value} />
        </div>
      ) : (
        <p className="text-[11px] text-muted-foreground">
          Does not match the schema, shown raw below:{" "}
          <span className="font-mono">{side.errors.slice(0, 4).join("; ")}{side.errors.length > 4 ? " …" : ""}</span>
        </p>
      )}
    </div>
  );
}

/** DV-057: typed input and output of a subagent span when `agents/handoffs/<agent>.json` exists. */
export function HandoffView({ handoff }: { handoff: Handoff }) {
  return (
    <section className="mt-3 rounded-md border border-border/60 p-2" aria-label="Typed handoff">
      <div className="flex items-center gap-2 text-xs">
        <span className="font-medium">Handoff contract</span>
        <span className="font-mono text-muted-foreground">{handoff.agent}{handoff.version ? `@${handoff.version}` : ""}</span>
        <Prov p="ai_judged" className="ml-auto" />
      </div>
      {handoff.input ? <Side label="Input" side={handoff.input} /> : null}
      {handoff.output ? <Side label="Output" side={handoff.output} /> : null}
    </section>
  );
}
