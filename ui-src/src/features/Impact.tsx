import { Brain, Check, Minus, Network, ShieldCheck, X } from "lucide-react";
import type { Impact as ImpactData } from "../api/traces";
import { Num, Prov } from "../components/Num";
import { Card, CardHeader, Empty } from "../components/ui/card";
import { SessionSavingsCard, type SessionSavings } from "./SkillSavings";

const fmt = (n: number | null | undefined) => (n == null ? "—" : n.toLocaleString());

const HARNESS_LABEL: Record<string, { label: string; does: string }> = {
  rules: { label: "Always-on rule", does: "Read and edit discipline: query before reading, ranged reads, targeted edits" },
  skills: { label: "Skills", does: "The invoked skill's procedure, e.g. raw-code-full's token rules" },
  subagents: { label: "Subagent definitions", does: "agent-spec-search / agent-spec-verify: sweeps run in a throwaway context" },
};

function Bar({ label, value, max, tone }: { label: string; value: number; max: number; tone: string }) {
  const pct = max > 0 ? Math.max(2, Math.round((value / max) * 100)) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs"><span className="text-muted-foreground">{label}</span><Num p="estimated">{fmt(value)} tokens</Num></div>
      <div className="h-3 rounded bg-muted"><div className={`h-3 rounded ${tone}`} style={{ width: `${pct}%` }} /></div>
    </div>
  );
}

/** Per-request impact: tokens kept out, rules followed, memory injected, harness cost. */
export function Impact({ impact, session, harnessOff }: { impact?: ImpactData | null; session?: SessionSavings | null; harnessOff?: boolean }) {
  if (harnessOff) {
    return <Empty title="Harness was off for this request" hint="This is the control arm of an A/B run: no digest, no graph tools, no guard. Its harness-on twin is on Impact › Summary, under the A/B card." />;
  }
  if (!impact) return <Empty title="No impact data" hint="This request has no tool spans to measure." />;
  if (impact.error) return <Empty title="Impact could not be computed" hint={impact.error} />;
  const t = impact.tokens;
  const pct = t.plain_cursor > 0 ? Math.round((t.avoided / t.plain_cursor) * 100) : 0;
  const applied = impact.rules.filter((r) => r.pass !== null);
  const passed = applied.filter((r) => r.pass).length;
  const facts = impact.memory.facts;

  return (
    <div className="grid max-w-5xl gap-4 lg:grid-cols-2">
      <SessionSavingsCard s={session} />
      <Card className="lg:col-span-2">
        <CardHeader
          title={<span className="flex items-center gap-2">Tool output in this chat vs plain Cursor <Prov p="estimated" /></span>}
          subtitle="Tool results stay in the context and are re-sent on every later model call"
        />
        <div className="space-y-3 px-4 pb-4">
          <div className="text-2xl font-semibold"><Num p="estimated">{fmt(t.avoided)}</Num> <span className="text-base font-normal text-muted-foreground">tokens kept out of the chat (<Num p="estimated">{pct}%</Num>)</span></div>
          <Bar label="Plain Cursor, same work" value={t.plain_cursor} max={t.plain_cursor} tone="bg-muted-foreground/50" />
          <Bar label="With agent-spec" value={t.context_in} max={t.plain_cursor} tone="bg-primary" />
          <div className="grid gap-2 pt-1 text-xs sm:grid-cols-3">
            <div className="rounded border p-2"><div className="text-muted-foreground">Subagent sweeps</div><Num p="estimated" className="text-sm font-medium">{fmt(t.avoided_by.subagents)}</Num><div className="text-muted-foreground"><Num p="measured">{impact.tools.in_subagents}</Num> calls ran in <Num p="measured">{impact.tools.subagents}</Num> subagent context{impact.tools.subagents === 1 ? "" : "s"}</div></div>
            <div className="rounded border p-2"><div className="text-muted-foreground">Graph queries</div><Num p="estimated" className="text-sm font-medium">{fmt(t.avoided_by.graph)}</Num><div className="text-muted-foreground"><Num p="measured">{impact.tools.graph}</Num> quer{impact.tools.graph === 1 ? "y" : "ies"} instead of reading a ~<Num p="measured">{fmt(impact.median_file_bytes)} B</Num> file</div></div>
            <div className="rounded border p-2"><div className="text-muted-foreground">Ranged reads</div><Num p="estimated" className="text-sm font-medium">{fmt(t.avoided_by.ranged_reads)}</Num><div className="text-muted-foreground"><Num p="measured">{impact.tools.read_ranged}</Num> ranged, <Num p="measured">{impact.tools.read_whole}</Num> whole-file</div></div>
          </div>
          <p className="text-xs text-muted-foreground">Bytes ÷ <Num p="estimated">{impact.bytes_per_token}</Num> = tokens. Subagent output stays in the subagent's own context; a graph query is priced as the median indexed file it replaced; a ranged read as the part of the file it skipped.</p>
        </div>
      </Card>

      <Card>
        <CardHeader title={<span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4" /> raw-code-full rules <Prov p="measured" /></span>} subtitle={<><Num p="measured">{passed}</Num> of <Num p="measured">{applied.length}</Num> held in this request{applied.length < impact.rules.length ? " (others did not apply)" : ""}</>} />
        <ul className="space-y-2 px-4 pb-4 text-sm">
          {impact.rules.map((r) => (
            <li key={r.rule} className="flex gap-2">
              {r.pass === null ? <Minus className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" /> : r.pass ? <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" /> : <X className="mt-0.5 h-4 w-4 shrink-0 text-danger" />}
              <div><div>{r.rule}</div><Num p="measured" className="block text-xs text-muted-foreground">{r.detail}</Num></div>
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <CardHeader title={<span className="flex items-center gap-2"><Brain className="h-4 w-4" /> Memory injected <Prov p="measured" /></span>}
          subtitle={impact.memory.digest_bytes ? <>Session-start digest: <Num p="measured">{fmt(impact.memory.digest_bytes)} B</Num>, <Num p="measured">{facts.length}</Num> remembered facts</> : "Facts the session-start digest put in front of the model"} />
        <div className="px-4 pb-4">
          {facts.length ? (
            <ul className="space-y-1.5 text-sm">
              {facts.slice(0, 8).map((f) => (
                <li key={f.fact_id} className="flex gap-2"><span className="shrink-0 rounded bg-muted px-1.5 text-[11px] uppercase text-muted-foreground">{f.type}</span><span data-figure-exempt>{f.subject}</span></li>
              ))}
              {facts.length > 8 ? <li className="text-xs text-muted-foreground"><Num p="measured">+{facts.length - 8}</Num> more</li> : null}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">{impact.memory.recorded ? "The digest for this chat carried no remembered facts." : "No injection recorded for this chat: it started before the sessionStart hook recorded injections, or without the harness hooks."}</p>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader title={<span className="flex items-center gap-2"><Network className="h-4 w-4" /> Harness queries</span>} subtitle="Structure answered from the graph and memory, not file reads" />
        <div className="px-4 pb-4">
          {impact.graph_queries.length ? (
            <ul className="space-y-1 font-mono text-xs">
              {impact.graph_queries.map((g, i) => (
                <li key={i} className="truncate" title={g.target}>{g.name} <span className="text-muted-foreground">→ {fmt(g.bytes)} B</span></li>
              ))}
            </ul>
          ) : <p className="text-sm text-muted-foreground">No graph or memory query in the main context.</p>}
          {impact.whole_reads.length ? (
            <div className="mt-3 text-xs"><div className="mb-1 text-muted-foreground">Whole-file reads (missed savings)</div>
              <ul className="space-y-0.5 font-mono">{impact.whole_reads.map((w, i) => <li key={i} className="truncate">{w.target} <span className="text-muted-foreground">{fmt(w.file_bytes)} B</span></li>)}</ul>
            </div>
          ) : null}
        </div>
      </Card>

      <Card>
        <CardHeader title={<span className="flex items-center gap-2">What agent-spec adds to the prompt {impact.harness.provenance ? <Prov p="measured" /> : null}</span>}
          subtitle="Compared with a plain Cursor chat (Cursor's own context breakdown)" />
        <div className="px-4 pb-4">
          {impact.harness.total ? (
            <ul className="space-y-2 text-sm">
              {Object.entries(impact.harness.tokens).map(([k, v]) => (
                <li key={k}><div className="flex justify-between"><span>{HARNESS_LABEL[k]?.label ?? k}</span><Num p="measured">{fmt(v)} tokens</Num></div>
                  <div className="text-xs text-muted-foreground">{HARNESS_LABEL[k]?.does}</div></li>
              ))}
              <li className="flex justify-between border-t pt-2 font-medium"><span>Fixed cost per model call</span><Num p="measured">{fmt(impact.harness.total)} tokens</Num></li>
              <li className="text-xs text-muted-foreground">Plus the session-start digest (stack, graph health, remembered facts, last session's open items) and the preToolUse guard (<Num p="measured">{impact.tools.guard_blocks}</Num> block{impact.tools.guard_blocks === 1 ? "" : "s"} here).</li>
            </ul>
          ) : <p className="text-sm text-muted-foreground">Cursor reported no context breakdown for this chat.</p>}
        </div>
      </Card>
    </div>
  );
}
