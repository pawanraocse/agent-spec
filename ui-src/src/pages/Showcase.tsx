import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Cpu, ExternalLink, FlaskConical, Search, Terminal, XCircle } from "lucide-react";
import { apiGet } from "../api/client";
import { Prov, Stat } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Card, CardHeader, Empty } from "../components/ui/card";
import { cn, fmtMs, relTime } from "../lib/utils";
import { SavingsHero, type SavingsOverview } from "../features/SkillSavings";

type Score = { hit1: number; hitk: number; mrr: number; semantic_weight?: number };
type Arm = { cases: number; correct: number; tokens_in: number; tokens_out: number; tools: number; ms: number };
type ArmRow = { correct: boolean; tokens_in: number; tokens_out: number; tools: number; ms: number; request_id?: string; answer?: string };
type Showcase = {
  requests: number;
  tokens: { avoided: number; plain_cursor: number; context_in: number; reduction_pct: number | null; billed_in: number; billed_out: number;
            cache_read: number; cache_share_pct: number | null; whole_file_estimate?: { saved_tokens: number; saved_usd: number; measured: { whole_file_reads: number } } | null };
  efficiency: { tools_per_request: number | null; graph_first_pct: number | null; ranged_read_pct: number | null; graph_queries: number;
                subagents: number; guard_blocks: number; median_ms: number | null; p90_ms: number | null };
  accuracy: { completed_pct: number | null; tool_error_pct: number | null; rules_pass_pct: number | null; rules_checked: number;
              review_score_avg: number | null; reviews: number };
  rag: {
    index: { ready: boolean; mode?: string; embedder?: string | null; by_kind: Record<string, { sources: number; chunks: number }>; vectors?: Record<string, number> };
    eval: { ok: boolean; ts: string; k: number; cases: number; embedder: string | null; made_by: string[]; modes: Record<string, Score>;
            examples: { q: string; expect: string; keyword_rank: number | null }[] } | null;
    history: { ts: string; label: string; cases: number; modes: Record<string, Score> }[];
    fusion: { semantic_weight: number; tuned_at: string | null; cases: number } | null;
  };
  bench: { run_id: string; ts: string; model: string; arms: { harness?: Arm; bare?: Arm };
           cases: { case: number; prompt: string; expect: string[]; harness?: ArmRow; bare?: ArmRow }[];
           runs: { run_id: string; ts: string; arms: { harness?: Arm; bare?: Arm } }[] } | null;
  by_model: { model: string; requests: number; tokens_in: number; tokens_out: number; avoided: number; tools_per_request: number; median_ms: number | null; local: boolean }[];
  prompts: { trace_id: string; prompt: string; model: string; status: string; start: string; duration_ms: number | null; tools: number;
             tokens_in: number; tokens_out: number; avoided: number; guard: number; errors: number }[];
};

const n = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v.toLocaleString());
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v}%`);
const p100 = (v: number) => `${Math.round(v * 100)}%`;

/** One metric, two arms: paired bars on a shared zero baseline, direct-labelled, hover for the exact value. */
function PairBar({ label, harness, bare, fmt, lowerIsBetter }: { label: string; harness: number; bare: number; fmt: (v: number) => string; lowerIsBetter?: boolean }) {
  const max = Math.max(harness, bare, 1);
  const better = lowerIsBetter ? harness < bare : harness > bare;
  const delta = bare ? Math.round(((harness - bare) / bare) * 100) : null;
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between text-xs">
        <span className="font-medium">{label}</span>
        {delta !== null && delta !== 0 && (
          <span className={cn("tabular", better ? "text-success" : "text-warning")}>{delta > 0 ? "+" : ""}{delta}% vs bare</span>
        )}
      </div>
      {([["harness", harness, "bg-primary"], ["bare", bare, "bg-muted-foreground/50"]] as const).map(([arm, v, tone]) => (
        <div key={arm} className="group flex items-center gap-2" title={`${arm}: ${fmt(v)}`}>
          <span className="w-14 shrink-0 text-[11px] text-muted-foreground">{arm}</span>
          <div className="h-3 flex-1 rounded-sm bg-muted/40">
            <div className={cn("h-3 rounded-r-[4px] transition-[width] group-hover:opacity-80", tone)} style={{ width: `${Math.max((v / max) * 100, 1.5)}%` }} />
          </div>
          <span className="w-20 shrink-0 text-right text-[11px] tabular">{fmt(v)}</span>
        </div>
      ))}
    </div>
  );
}

function Bench({ b }: { b: NonNullable<Showcase["bench"]> }) {
  const h = b.arms.harness, r = b.arms.bare;
  if (!h || !r) return null;
  return (
    <Card>
      <CardHeader
        title={<span className="flex items-center gap-1.5"><FlaskConical size={14} />Harness A/B on a free local model</span>}
        subtitle={<>Same {h.cases} prompts, same model (<code>{b.model}</code>), harness on vs off. Correct = the answer names the expected file. Run {relTime(b.ts)}.{h.cases < 10 ? <> <b className="text-warning">n = {h.cases}: a smoke test, not a benchmark.</b></> : null}</>}
        right={<Prov p="measured" />}
      />
      <div className="grid gap-5 p-4 md:grid-cols-2">
        <div className="space-y-4">
          <PairBar label="Correct answers" harness={h.correct} bare={r.correct} fmt={(v) => `${v} / ${h.cases}`} />
          <PairBar label="Tool calls" harness={h.tools} bare={r.tools} fmt={(v) => n(v)} lowerIsBetter />
        </div>
        <div className="space-y-4">
          <PairBar label="Prompt tokens evaluated" harness={h.tokens_in} bare={r.tokens_in} fmt={(v) => n(v)} lowerIsBetter />
          <PairBar label="Wall time" harness={h.ms} bare={r.ms} fmt={(v) => fmtMs(v)} lowerIsBetter />
        </div>
      </div>
      <div className="overflow-x-auto border-t border-border">
        <table className="w-full text-xs">
          <thead className="text-left text-muted-foreground">
            <tr><th className="px-4 py-2 font-medium">Prompt</th><th className="px-2 font-medium">Harness</th><th className="px-2 font-medium">Bare</th></tr>
          </thead>
          <tbody>
            {b.cases.map((c) => (
              <tr key={c.case} className="border-t border-border align-top">
                <td className="px-4 py-2">{c.prompt}<div className="mt-0.5 text-muted-foreground">expects: {c.expect.join(", ")}</div></td>
                {(["harness", "bare"] as const).map((arm) => {
                  const x = c[arm];
                  return (
                    <td key={arm} className="whitespace-nowrap px-2 py-2" title={x?.answer}>
                      {x ? (
                        <span className="flex items-center gap-1.5">
                          {x.correct ? <CheckCircle2 size={13} className="text-success" aria-label="correct" /> : <XCircle size={13} className="text-danger" aria-label="wrong" />}
                          <span className="tabular text-muted-foreground">{n(x.tokens_in)} tok · {x.tools} tools</span>
                          {x.request_id && <Link to={`/requests/${x.request_id}`} className="text-primary" aria-label="trace"><ExternalLink size={11} /></Link>}
                        </span>
                      ) : "—"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Rag({ rag }: { rag: Showcase["rag"] }) {
  const ev = rag.eval;
  const order = ["keyword", "semantic", "hybrid", "tuned"].filter((m) => ev?.modes[m]);
  const best = ev ? order.reduce((a, m) => (ev.modes[m].mrr > ev.modes[a].mrr ? m : a), order[0]) : null;
  const chunks = Object.values(rag.index.by_kind || {}).reduce((s, k) => s + k.chunks, 0);
  const vectors = Object.values(rag.index.vectors || {}).reduce((s, v) => Math.max(s, v), 0);
  return (
    <Card>
      <CardHeader
        title={<span className="flex items-center gap-1.5"><Search size={14} />RAG: measured retrieval accuracy</span>}
        subtitle={ev ? <>{ev.cases} golden questions written by {ev.made_by.join(", ")} without naming the file; does search return it? hit@{ev.k} = in the top {ev.k} files.</> : "No eval yet."}
        right={<Prov p="measured" />}
      />
      <div className="grid gap-4 p-4 lg:grid-cols-[1fr_260px]">
        {ev ? (
          <table className="w-full text-xs">
            <thead className="text-left text-muted-foreground">
              <tr><th className="py-1 font-medium">Mode</th><th className="font-medium">hit@1</th><th className="font-medium">hit@{ev.k}</th><th className="font-medium">MRR</th></tr>
            </thead>
            <tbody>
              {order.map((m) => (
                <tr key={m} className={cn("border-t border-border", m === best && "font-semibold")}>
                  <td className="py-1.5">
                    {m === "tuned" ? `tuned fusion (semantic ×${ev.modes[m].semantic_weight})` : m}
                    {m === best && <Badge tone="success" className="ml-2">best</Badge>}
                  </td>
                  <td className="tabular">{p100(ev.modes[m].hit1)}</td>
                  <td className="tabular">{p100(ev.modes[m].hitk)}</td>
                  <td className="tabular">{ev.modes[m].mrr.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty title="Run the RAG eval" hint={<code>agent-spec-platform.py rag-eval --build</code>} />}
        <div className="space-y-2 text-xs">
          <div className="flex justify-between"><span className="text-muted-foreground">Indexed chunks</span><span className="tabular">{n(chunks)}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Embedded</span><span className="tabular">{n(vectors)}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Embedder</span><span className="truncate pl-2 font-mono">{rag.index.embedder ?? "off (keyword)"}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Search uses</span><span>{rag.fusion?.tuned_at ? `semantic ×${rag.fusion.semantic_weight} (self-tuned)` : "plain RRF"}</span></div>
          {Object.entries(rag.index.by_kind || {}).map(([k, v]) => (
            <div key={k} className="flex justify-between text-muted-foreground"><span>· {k}</span><span className="tabular">{n(v.chunks)}</span></div>
          ))}
        </div>
      </div>
      {rag.history.length > 1 && (
        <div className="border-t border-border px-4 py-3">
          <p className="mb-2 text-[11px] uppercase tracking-wide text-muted-foreground">Accuracy over our changes (best mode MRR)</p>
          <ol className="space-y-1 text-xs">
            {rag.history.map((h, i) => {
              const top = Math.max(...Object.values(h.modes).map((s) => s.mrr));
              return (
                <li key={i} className="flex items-center gap-2" title={Object.entries(h.modes).map(([m, s]) => `${m}: MRR ${s.mrr}`).join(" · ")}>
                  <span className="w-5 text-muted-foreground">{i + 1}.</span>
                  <div className="h-2.5 w-40 rounded-sm bg-muted/40"><div className="h-2.5 rounded-r-[4px] bg-primary" style={{ width: `${top * 100}%` }} /></div>
                  <span className="w-12 tabular">{top.toFixed(3)}</span>
                  <span className="truncate text-muted-foreground">{h.label} · {h.cases} cases</span>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </Card>
  );
}

export function Showcase() {
  const q = useQuery({ queryKey: ["showcase"], queryFn: () => apiGet<Showcase>("/api/showcase"), refetchInterval: 15000 });
  const sv = useQuery({ queryKey: ["skill-savings"], queryFn: () => apiGet<SavingsOverview>("/api/skill-savings"), refetchInterval: 15000 });
  const d = q.data;
  if (q.isLoading) return <div className="p-6 text-sm text-muted-foreground">Loading…</div>;
  if (!d) return <div className="p-6"><Empty title="Showcase unavailable" hint={String(q.error ?? "")} /></div>;
  const t = d.tokens, e = d.efficiency, a = d.accuracy;
  return (
    <div className="mx-auto max-w-6xl space-y-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border pb-4">
        <div>
          <h1 className="text-xl font-semibold">What the harness changes</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {d.requests} traced requests. Every number is labelled measured, estimated or AI-judged; nothing here is a mock.
          </p>
        </div>
        <Link to="/console" className="inline-flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground hover:bg-primary/90">
          <Terminal size={13} />Try it in the Console<ArrowRight size={13} />
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
        <Stat label="Cache-read share" value={pct(t.cache_share_pct)} p="measured" hint="of billed input, re-sent at 0.1×" />
        <Stat label="Harness rules pass" value={pct(a.rules_pass_pct)} p="measured" hint={`${n(a.rules_checked)} checks`} />
        <Stat label="Ranged reads" value={pct(e.ranged_read_pct)} p="measured" hint="of file reads" />
        <Stat label="Tool error rate" value={pct(a.tool_error_pct)} p="measured" hint={`${n(e.guard_blocks)} guard blocks`} />
        <Stat label="Median request" value={fmtMs(e.median_ms)} p="measured" hint={`p90 ${fmtMs(e.p90_ms)}`} />
      </div>

      <SavingsHero o={sv.data} />

      {d.bench ? <Bench b={d.bench} /> : (
        <Card className="p-4 text-xs text-muted-foreground">No A/B run yet: <code>bin/agent-spec-bench.py</code> runs the same prompts with the harness on and off.</Card>
      )}

      <Rag rag={d.rag} />

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title={<span className="flex items-center gap-1.5"><Cpu size={14} />By model</span>} subtitle="Local Ollama runs cost $0 and never leave the machine." right={<Prov p="measured" />} />
          <table className="w-full text-xs">
            <thead className="text-left text-muted-foreground">
              <tr><th className="px-4 py-2 font-medium">Model</th><th className="font-medium">Req</th><th className="font-medium">Tools/req</th><th className="font-medium">Avoided</th><th className="pr-4 font-medium">Median</th></tr>
            </thead>
            <tbody>
              {d.by_model.map((m) => (
                <tr key={m.model} className="border-t border-border">
                  <td className="px-4 py-1.5 font-mono">{m.model}{m.local && <Badge tone="success" className="ml-2">local</Badge>}</td>
                  <td className="tabular">{m.requests}</td>
                  <td className="tabular">{m.tools_per_request}</td>
                  <td className="tabular">{n(m.avoided)}</td>
                  <td className="pr-4 tabular">{fmtMs(m.median_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card>
          <CardHeader title="Token ledger" subtitle="Billed counts come from the hooks; avoided is the impact model's estimate." />
          <div className="space-y-2 p-4 text-xs">
            {([
              ["Billed input", t.billed_in, "measured"], ["of which cache reads", t.cache_read, "measured"], ["Billed output", t.billed_out, "measured"],
              ["Context the harness let in", t.context_in, "estimated"], ["Plain-Cursor equivalent", t.plain_cursor, "estimated"],
              ["Kept out by graph, ranged reads, subagents", t.avoided, "estimated"],
            ] as const).map(([label, v, p]) => (
              <div key={label} className="flex items-center justify-between gap-2 border-b border-border/50 pb-1.5">
                <span className="text-muted-foreground">{label}</span>
                <span className="flex items-center gap-2"><span className="tabular">{n(v)}</span><Prov p={p} /></span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader title="Latest prompts" subtitle="Each row links to its full trace: tools, rules, injected memory, tokens." />
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-left text-muted-foreground">
              <tr><th className="px-4 py-2 font-medium">Prompt</th><th className="font-medium">Model</th><th className="font-medium">Tools</th><th className="font-medium">Tokens in</th><th className="font-medium">Avoided</th><th className="pr-4 font-medium">Time</th></tr>
            </thead>
            <tbody>
              {d.prompts.map((r) => (
                <tr key={r.trace_id} className="border-t border-border">
                  <td className="max-w-[420px] truncate px-4 py-1.5">
                    <Link to={`/requests/${r.trace_id}`} className="hover:text-primary hover:underline">{r.prompt || <span className="text-muted-foreground">(no prompt recorded)</span>}</Link>
                  </td>
                  <td className="whitespace-nowrap font-mono">{r.model}</td>
                  <td className="tabular">{r.tools}{r.guard ? <span className="text-warning"> · {r.guard} blocked</span> : null}</td>
                  <td className="tabular">{n(r.tokens_in)}</td>
                  <td className="tabular">{n(r.avoided)}</td>
                  <td className="whitespace-nowrap pr-4 tabular">{fmtMs(r.duration_ms)} · {relTime(r.start)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
