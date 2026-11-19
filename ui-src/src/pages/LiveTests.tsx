import { Fragment, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ChevronRight, CircleSlash, Copy, FlaskConical, Loader2, Play, XCircle } from "lucide-react";
import { apiGet, apiPost } from "../api/client";
import { Badge } from "../components/ui/badge";
import { Card, CardHeader, Empty } from "../components/ui/card";
import { Num } from "../components/Num";
import { cn, copyText, relTime } from "../lib/utils";

type Status = "PASS" | "FAIL" | "SKIP";
type Case = {
  id: string; tier: "smoke" | "live" | "full"; area: string; owed: string; title: string; criterion: string;
  model: string | null; status: Status; seconds: number; note?: string; error?: string; metrics?: Record<string, unknown>;
};
type Summary = Record<Status, number>;
type Report = {
  run_id: string; started: string; finished: string; models: string[]; full: boolean; summary: Summary;
  host: { platform: string; python: string; wsl: boolean }; ollama: { url: string | null; models: string[] }; cases: Case[];
};
type Run = { run_id: string; started: string; finished: string; models: string[]; full: boolean; summary: Summary };
type Overview = {
  latest: Report | null; history: Run[]; available: boolean; tiers: string[]; command: string;
  running: { pid: number; started: string; tier: string; all_models: boolean; progress: string[] } | null;
};

const TIERS = [
  { id: "quick", label: "Quick", hint: "No model: install, doctor, digest, dashboard, failure mode (~10 s)" },
  { id: "live", label: "Live", hint: "Adds every Ollama case: hooks, Impact facts, guard, redaction, Console, Ask (~2 min)" },
  { id: "full", label: "Full", hint: "Adds the demo dry run and the skill benchmark (~10 min)" },
] as const;

const AREA_LABEL: Record<string, string> = {
  backend: "Model backend", install: "Install", context: "Context", dashboard: "Dashboard", agent: "Agent + hooks",
  guard: "Guards", console: "Agent Console", ask: "Ask", failure: "Failure modes", demo: "Demo", bench: "Benchmark",
};

const OWED: Record<string, string> = {
  "H-005": "Injected facts on the Impact tab",
  "H-042": "Install matrix",
  "H-045": "Fresh-user test",
  "H-050": "Head-to-head benchmark",
  "H-053": "Timed dry runs",
};

const TONE: Record<Status, { text: string; bg: string; ring: string; Icon: typeof CheckCircle2 }> = {
  PASS: { text: "text-success", bg: "bg-success", ring: "ring-success/30", Icon: CheckCircle2 },
  FAIL: { text: "text-danger", bg: "bg-danger", ring: "ring-danger/30", Icon: XCircle },
  SKIP: { text: "text-muted-foreground", bg: "bg-muted-foreground", ring: "ring-border", Icon: CircleSlash },
};

function worst(cases: Case[]): Status {
  if (cases.some((c) => c.status === "FAIL")) return "FAIL";
  if (cases.some((c) => c.status === "PASS")) return "PASS";
  return "SKIP";
}

/** Pass-rate ring: the fraction of cases that ran (not skipped) and passed. */
function Ring({ s, size = 112 }: { s: Summary; size?: number }) {
  const ran = s.PASS + s.FAIL;
  const pct = ran ? s.PASS / ran : 0;
  const r = size / 2 - 8;
  const c = 2 * Math.PI * r;
  const tone = s.FAIL ? "text-danger" : ran ? "text-success" : "text-muted-foreground";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${Math.round(pct * 100)}% of cases that ran passed`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={8} className="stroke-muted" />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={8} strokeLinecap="round"
        strokeDasharray={`${c * pct} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`}
        className={cn("stroke-current transition-[stroke-dasharray] duration-700", tone)}
      />
      <text x="50%" y="47%" textAnchor="middle" dominantBaseline="middle" className="fill-foreground text-[22px] font-semibold tabular">
        {ran ? `${Math.round(pct * 100)}%` : "—"}
      </text>
      <text x="50%" y="66%" textAnchor="middle" dominantBaseline="middle" className="fill-muted-foreground text-[10px] uppercase tracking-wider">
        passing
      </text>
    </svg>
  );
}

function Chip({ status, label }: { status: Status; label?: string }) {
  const t = TONE[status];
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset", t.text, t.ring,
      status === "PASS" ? "bg-success/10" : status === "FAIL" ? "bg-danger/10" : "bg-muted")}>
      <t.Icon size={12} aria-hidden />{label ?? status}
    </span>
  );
}

/** Last runs as stacked columns: green passed, red failed, grey skipped. */
function History({ runs }: { runs: Run[] }) {
  if (runs.length < 2) return null;
  const max = Math.max(...runs.map((r) => r.summary.PASS + r.summary.FAIL + r.summary.SKIP), 1);
  return (
    <figure className="flex flex-col items-start gap-1 lg:items-end">
    <div className="flex h-14 items-end gap-1" aria-label="Recent runs">
      {runs.map((r) => {
        const tot = r.summary.PASS + r.summary.FAIL + r.summary.SKIP;
        return (
          <div key={r.run_id} title={`${r.run_id}: ${r.summary.PASS} pass, ${r.summary.FAIL} fail, ${r.summary.SKIP} skip — ${r.models.join(", ") || "no model"}`}
            className="flex w-2.5 flex-col-reverse overflow-hidden rounded-sm" style={{ height: `${Math.max(18, (tot / max) * 100)}%` }}>
            <div className="bg-success" style={{ flexGrow: r.summary.PASS }} />
            <div className="bg-danger" style={{ flexGrow: r.summary.FAIL }} />
            <div className="bg-muted-foreground/40" style={{ flexGrow: r.summary.SKIP }} />
          </div>
        );
      })}
    </div>
    <figcaption className="text-[10px] uppercase tracking-wide text-muted-foreground">Last {runs.length} runs</figcaption>
    </figure>
  );
}

function Detail({ c }: { c: Case }) {
  const text = c.status === "FAIL" ? c.error : c.note;
  const metrics = c.metrics && Object.keys(c.metrics).length ? c.metrics : null;
  return (
    <div className="space-y-2 rounded-md bg-muted/40 p-3 text-xs">
      <p className="text-muted-foreground"><span className="font-medium text-foreground">Pass when </span>{c.criterion}</p>
      {text ? <pre className={cn("whitespace-pre-wrap break-words font-mono text-[11px]", c.status === "FAIL" ? "text-danger" : "text-foreground")}>{text}</pre> : null}
      {metrics ? (
        <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 font-mono text-[11px]">
          {Object.entries(metrics).map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-muted-foreground">{k}</dt>
              <dd className="break-words">{typeof v === "string" ? v : JSON.stringify(v)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}

function Matrix({ report }: { report: Report }) {
  const models = report.models.length ? report.models : [null];
  // One row per case id; per-model cases spread over the model columns.
  const rows = useMemo(() => {
    const byId = new Map<string, Case[]>();
    report.cases.forEach((c) => byId.set(c.id, [...(byId.get(c.id) ?? []), c]));
    const groups = new Map<string, Case[][]>();
    byId.forEach((cs) => groups.set(cs[0].area, [...(groups.get(cs[0].area) ?? []), cs]));
    return [...groups.entries()];
  }, [report]);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const perModel = models.length > 1 || (models[0] !== null);
  return (
    <Card>
      <CardHeader title="Matrix" subtitle="Every case is a real run on this machine: no mocks. Click a row for its evidence." />
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
              <th className="w-8 px-3 py-2" />
              <th className="px-2 py-2">Case</th>
              <th className="px-2 py-2">Item</th>
              {perModel ? models.map((m) => <th key={m ?? "-"} className="px-2 py-2 font-mono normal-case">{m}</th>) : <th className="px-2 py-2">Result</th>}
              <th className="px-3 py-2 text-right">Time</th>
            </tr>
          </thead>
          {rows.map(([area, cases]) => (
            <tbody key={area}>
              <tr><td colSpan={4 + models.length} className="bg-muted/30 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{AREA_LABEL[area] ?? area}</td></tr>
              {cases.map((cs) => {
                const c = cs[0];
                const isOpen = open[c.id] ?? cs.some((x) => x.status === "FAIL");
                const time = cs.reduce((a, x) => a + x.seconds, 0);
                return (
                  <Fragment key={c.id}>
                    <tr className="cursor-pointer border-b border-border/60 hover:bg-muted/30" onClick={() => setOpen({ ...open, [c.id]: !isOpen })}>
                      <td className="px-3 py-2"><ChevronRight size={14} className={cn("text-muted-foreground transition-transform", isOpen && "rotate-90")} /></td>
                      <td className="px-2 py-2">
                        <span className="mr-2 font-mono text-[11px] text-muted-foreground">{c.id}</span>
                        <span className="font-medium">{c.title}</span>
                        {c.tier !== "live" ? <Badge className="ml-2">{c.tier}</Badge> : null}
                      </td>
                      <td className="px-2 py-2">{c.owed ? <Badge tone="accent">{c.owed}</Badge> : null}</td>
                      {perModel && c.model !== null ? models.map((m) => {
                        const x = cs.find((y) => y.model === m);
                        return <td key={m ?? "-"} className="px-2 py-2">{x ? <Chip status={x.status} /> : <span className="text-xs text-muted-foreground">—</span>}</td>;
                      }) : (
                        <td colSpan={perModel ? models.length : 1} className="px-2 py-2">
                          <Chip status={worst(cs)} />{perModel && models.length > 1 ? <span className="ml-2 text-[11px] text-muted-foreground">once per run</span> : null}
                        </td>
                      )}
                      <td className="px-3 py-2 text-right font-mono text-xs text-muted-foreground"><Num p="measured">{time.toFixed(1)} s</Num></td>
                    </tr>
                    {isOpen ? (
                      <tr className="border-b border-border/60">
                        <td />
                        <td colSpan={3 + models.length} className="space-y-2 px-2 pb-3">
                          {cs.map((x) => (
                            <div key={x.model ?? "-"}>
                              {x.model && cs.length > 1 ? <p className="mb-1 font-mono text-[11px] text-muted-foreground">{x.model}</p> : null}
                              <Detail c={x} />
                            </div>
                          ))}
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })}
            </tbody>
          ))}
        </table>
      </div>
    </Card>
  );
}

function OwedItems({ report }: { report: Report }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {Object.entries(OWED).map(([id, title]) => {
        const cs = report.cases.filter((c) => c.owed === id);
        const st = cs.length ? worst(cs) : null;
        return (
          <Card key={id} className={cn("p-3", st === "FAIL" && "border-danger/50")}>
            <div className="flex items-center justify-between gap-2">
              <Badge tone="accent">{id}</Badge>
              {st ? <Chip status={st} /> : <span className="text-[11px] text-muted-foreground">not in this run</span>}
            </div>
            <p className="mt-2 text-sm font-medium">{title}</p>
            <p className="mt-1 text-[11px] text-muted-foreground">{cs.length ? [...new Set(cs.map((c) => c.id))].join(" · ") : "Run the full tier to cover it"}</p>
          </Card>
        );
      })}
    </div>
  );
}

function RunControls({ data }: { data: Overview }) {
  const qc = useQueryClient();
  const [tier, setTier] = useState<string>("live");
  const [allModels, setAllModels] = useState(false);
  const [copied, setCopied] = useState(false);
  const run = useMutation({
    mutationFn: () => apiPost<{ ok: boolean; error?: string; live: Overview }>("/api/livetest", { tier, all_models: allModels }),
    onSuccess: (r) => qc.setQueryData(["livetest"], r.live),
  });
  const busy = !!data.running || run.isPending;
  const cmd = `python3 bin/agent-spec-livetest.py${tier === "full" ? " --full" : tier === "quick" ? " --only L01,L02,L03,L04,L05,L16" : ""}${allModels ? " --models all" : ""}`;
  return (
    <div className="flex flex-col items-stretch gap-2 sm:items-end">
      <div className="flex flex-wrap items-center gap-2">
        <div role="radiogroup" aria-label="Tier" className="inline-flex rounded-md border border-border p-0.5">
          {TIERS.map((t) => (
            <button key={t.id} type="button" role="radio" aria-checked={tier === t.id} title={t.hint} onClick={() => setTier(t.id)}
              className={cn("rounded px-2.5 py-1 text-xs font-medium transition-colors", tier === t.id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}>
              {t.label}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <input type="checkbox" checked={allModels} onChange={(e) => setAllModels(e.target.checked)} className="accent-[hsl(var(--primary))]" />
          every model
        </label>
        <button type="button" disabled={busy || !data.available} onClick={() => run.mutate()}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-90 disabled:opacity-50">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}{busy ? "Running…" : "Run now"}
        </button>
      </div>
      <button type="button" onClick={async () => { setCopied(await copyText(cmd)); setTimeout(() => setCopied(false), 1500); }}
        className="inline-flex items-center gap-1.5 self-start rounded border border-border px-2 py-1 font-mono text-[11px] text-muted-foreground hover:text-foreground sm:self-end" title="Copy the same run as a terminal command">
        <Copy size={11} />{copied ? "copied" : cmd}
      </button>
      {run.data && !run.data.ok ? <p className="text-xs text-warning">{run.data.error}</p> : null}
      {run.error ? <p className="text-xs text-danger">{String(run.error)}</p> : null}
    </div>
  );
}

export function LiveTests() {
  const q = useQuery({
    queryKey: ["livetest"],
    queryFn: () => apiGet<Overview>("/api/livetest"),
    refetchInterval: (query) => (query.state.data?.running ? 2000 : false),
  });
  const data = q.data;
  if (q.isLoading) return <p className="p-6 text-xs text-muted-foreground">Loading…</p>;
  if (!data) return <Empty title="Live tests unavailable" hint={String(q.error ?? "")} />;
  const r = data.latest;
  return (
    <div className="space-y-5 p-6">
      <Card className="relative overflow-hidden">
        <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_120%_at_0%_0%,hsl(var(--primary)/0.12),transparent_60%),radial-gradient(50%_120%_at_100%_100%,hsl(var(--accent)/0.10),transparent_60%)]" />
        <div className="relative flex flex-col gap-5 p-5 lg:flex-row lg:items-center">
          {r ? <Ring s={r.summary} /> : <div className="flex h-28 w-28 items-center justify-center rounded-full border-8 border-muted"><FlaskConical className="text-muted-foreground" /></div>}
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold tracking-tight">Live tests</h2>
              {r ? (["PASS", "FAIL", "SKIP"] as Status[]).map((k) => <Chip key={k} status={r.summary[k] ? k : "SKIP"} label={`${r.summary[k]} ${k.toLowerCase()}`} />) : null}
            </div>
            <p className="max-w-2xl text-xs text-muted-foreground">
              The harness end to end on local Ollama models: a fresh install in a temporary HOME, real Cursor-shaped hooks,
              the dashboard server, the guards, the Console and Ask. Results are measured, never mocked.
            </p>
            {r ? (
              <p className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                <span>Last run <span className="text-foreground">{relTime(r.finished)}</span></span>
                <span>Models <span className="font-mono text-foreground">{r.models.join(", ") || "none"}</span></span>
                <span>Ollama <span className="font-mono text-foreground">{r.ollama.url ?? "not reachable"}</span></span>
                <span>Host <span className="text-foreground">{r.host.wsl ? "WSL · " : ""}Python {r.host.python}</span></span>
              </p>
            ) : null}
          </div>
          <div className="flex flex-col gap-3 lg:items-end">
            <RunControls data={data} />
            <History runs={data.history} />
          </div>
        </div>
      </Card>

      {data.running ? (
        <Card className="border-primary/40">
          <CardHeader title={<span className="inline-flex items-center gap-2"><span className="h-2 w-2 animate-pulse rounded-full bg-primary" />Running the {data.running.tier} tier{data.running.all_models ? " on every model" : ""}</span>}
            subtitle={`Started ${relTime(data.running.started)}. Lines appear as each case finishes.`} />
          <pre className="scrollbar-thin max-h-64 overflow-auto p-4 font-mono text-[11px] leading-5">
            {data.running.progress.length ? data.running.progress.join("\n") : "Building the demo in a temporary HOME…"}
          </pre>
        </Card>
      ) : null}

      {r ? (
        <>
          <section className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Owed items</h3>
            <OwedItems report={r} />
          </section>
          <Matrix report={r} />
        </>
      ) : (
        <Card><Empty title="No live run yet" hint="Start Ollama with a chat model, then press Run now, or run the command shown above in a terminal." /></Card>
      )}
    </div>
  );
}
