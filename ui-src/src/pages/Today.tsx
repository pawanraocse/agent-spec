import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  AlertOctagon, ArrowRight, Bot, Check, CheckCircle2, CircleDot, Copy, GitBranch, Loader2, Network,
  Play, Shield, Sparkles, Wand2, Wrench, Zap,
} from "lucide-react";
import { apiGet, apiPost } from "../api/client";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardHeader, Empty } from "../components/ui/card";
import { Prov } from "../components/Num";
import { cn, copyText, fmtMs, fmtTokens, relTime } from "../lib/utils";

type Action =
  | { kind: "skill"; command: string; prompt: string; console: boolean }
  | { kind: "api"; label: string; path: string; body: Record<string, unknown> }
  | { kind: "link"; label: string; to: string };
type Level = "blocked" | "broken" | "improve";
type Item = { id: string; level: Level; title: string; detail: string; action: Action; link: string | null; count: number | null };
type Day = { day: string; requests: number; tools: number; errors: number; guard: number; local: number };
type Recent = { trace_id: string; session_id: string; prompt: string; status: string; start: string; duration_ms: number | null;
  skills: string[]; tools: number; errors: number; guard: number; subagents: number; model: string | null; origin: string | null };
export type TodayData = {
  project: { name: string; branch: string | null; sha: string | null; graph: string | null };
  attention: Item[];
  counts: Record<Level, number>;
  value: {
    requests: number; requests_7d: number; chats: number; kept_out: number | null; resend_avoided: number | null;
    by_lever: Record<string, number>; labels: Record<string, string>; guard_blocks: number; tool_calls: number; subagents: number;
    facts: number; facts_injected: number; automation_runs: number | null; automations_on: number | null; automations_total: number;
    autopilot: { ts: string; id: string; label: string; status: string; reason: string; ms: number | null; times: number }[];
  };
  pulse: Day[];
  recent: Recent[];
  skills: { skill: string; uses: number; last: string | null }[];
  errors: string[];
};

const LEVEL: Record<Level, { label: string; tone: "danger" | "warning" | "primary"; bar: string; icon: typeof AlertOctagon }> = {
  blocked: { label: "Waiting on you", tone: "danger", bar: "bg-danger", icon: AlertOctagon },
  broken: { label: "Needs a fix", tone: "warning", bar: "bg-warning", icon: Wrench },
  improve: { label: "Make it smarter", tone: "primary", bar: "bg-primary", icon: Sparkles },
};

function ItemAction({ item }: { item: Item }) {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [copied, setCopied] = useState(false);
  const run = useMutation({
    mutationFn: (a: Extract<Action, { kind: "api" }>) => apiPost<{ ok?: boolean; error?: string }>(a.path, a.body),
    onSettled: () => qc.invalidateQueries({ queryKey: ["today"] }),
  });
  const a = item.action;
  if (a.kind === "link") {
    return <Button size="sm" variant="outline" onClick={() => nav(a.to)}>{a.label}<ArrowRight size={12} /></Button>;
  }
  if (a.kind === "api") {
    return (
      <div className="flex items-center gap-2">
        {run.isError ? <span className="text-[11px] text-danger">{String((run.error as Error).message).slice(0, 80)}</span> : null}
        {run.isSuccess ? <span className="text-[11px] text-success">done</span> : null}
        <Button size="sm" onClick={() => run.mutate(a)} disabled={run.isPending}>
          {run.isPending ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}{a.label}
        </Button>
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      <Button size="sm" variant="outline" title={a.prompt}
        onClick={async () => { if (await copyText(a.prompt)) { setCopied(true); setTimeout(() => setCopied(false), 1500); } }}>
        {copied ? <Check size={12} /> : <Copy size={12} />}{copied ? "Copied" : "Copy for Cursor"}
      </Button>
      {a.console ? (
        <Button size="sm" onClick={() => nav(`/console?prompt=${encodeURIComponent(a.prompt)}`)} title="Read-only skill: the dashboard's agent can run it">
          <Bot size={12} />Run in Console
        </Button>
      ) : null}
    </div>
  );
}

function AttentionRow({ item }: { item: Item }) {
  const l = LEVEL[item.level];
  return (
    <li className="group relative flex gap-3 px-4 py-3 hover:bg-muted/30">
      <span aria-hidden className={cn("absolute inset-y-2 left-0 w-0.5 rounded-full", l.bar)} />
      <l.icon size={16} className={cn("mt-0.5 shrink-0", item.level === "blocked" ? "text-danger" : item.level === "broken" ? "text-warning" : "text-primary")} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          {item.link ? <Link to={item.link} className="text-sm font-medium hover:underline">{item.title}</Link> : <span className="text-sm font-medium">{item.title}</span>}
          <Badge tone={l.tone}>{l.label}</Badge>
          {item.action.kind === "skill" ? <code className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-accent">{item.action.command}</code> : null}
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">{item.detail}</p>
      </div>
      <div className="shrink-0 self-center"><ItemAction item={item} /></div>
    </li>
  );
}

function Hero({ d }: { d: TodayData }) {
  const need = d.counts.blocked + d.counts.broken;
  const v = d.value;
  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-card">
      <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-primary/15 blur-3xl" />
      <div aria-hidden className="pointer-events-none absolute -bottom-28 left-1/3 h-64 w-64 rounded-full bg-accent/10 blur-3xl" />
      <div className="relative flex flex-wrap items-end justify-between gap-6 p-6">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5"><GitBranch size={11} />{d.project.branch ?? "no git"}{d.project.sha ? <code className="ml-1">@{d.project.sha}</code> : null}</span>
            <Link to="/project/index" className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 hover:text-foreground">
              <Network size={11} />graph {d.project.graph ?? "—"}
            </Link>
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Today in <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">{d.project.name}</span></h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            {need === 0
              ? d.counts.improve
                ? <>Nothing is blocked or broken. {d.counts.improve} suggestion{d.counts.improve === 1 ? "" : "s"} would make the agent smarter.</>
                : <>Nothing needs you. The index is current and the harness is healthy.</>
              : <><b className="text-foreground">{need} item{need === 1 ? "" : "s"}</b> need{need === 1 ? "s" : ""} you before the agent works at full strength.</>}
            {" "}This week the agent handled <b className="text-foreground">{v.requests_7d}</b> request{v.requests_7d === 1 ? "" : "s"}
            {v.kept_out ? <> and the harness kept <b className="text-foreground">~{fmtTokens(v.kept_out)}</b> tokens out of chat contexts</> : null}.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-3 text-center">
          {([["blocked", d.counts.blocked], ["broken", d.counts.broken], ["improve", d.counts.improve]] as [Level, number][]).map(([k, n]) => (
            <div key={k} className="min-w-[88px] rounded-lg border border-border bg-background/60 px-3 py-2">
              <div className={cn("text-2xl font-semibold tabular-nums", n === 0 ? "text-muted-foreground" : k === "blocked" ? "text-danger" : k === "broken" ? "text-warning" : "text-primary")}>{n}</div>
              <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{LEVEL[k].label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Value({ v }: { v: TodayData["value"] }) {
  const levers = Object.entries(v.by_lever || {}).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...levers.map(([, n]) => n));
  const tiles: [string, React.ReactNode, typeof Zap, string][] = [
    ["Facts injected", v.facts_injected, Sparkles, `${v.facts} remembered facts, read back at session start`],
    ["Guard blocks", v.guard_blocks, Shield, "Wasteful or unsafe tool calls stopped before they ran"],
    ["Subagent sweeps", v.subagents, Bot, "Broad searches whose output never entered the main chat"],
    ["Autopilot runs", v.automation_runs ?? "—", Wand2, `${v.automations_on ?? 0}/${v.automations_total} automations switched on`],
  ];
  return (
    <Card className="flex flex-col">
      <CardHeader title={<span className="flex items-center gap-2"><Zap size={14} className="text-primary" />What the harness did for you</span>}
        right={<Link to="/impact" className="whitespace-nowrap text-xs text-primary hover:underline">Impact →</Link>} />
      <div className="space-y-4 p-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="text-3xl font-semibold tabular-nums">{fmtTokens(v.kept_out)}</div>
            <div className="text-xs text-muted-foreground">tokens kept out of chat contexts</div>
          </div>
          <div className="text-right">
            <div className="text-lg font-semibold tabular-nums text-success">{fmtTokens(v.resend_avoided)}</div>
            <div className="text-[11px] text-muted-foreground">re-sends avoided</div>
          </div>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground"><Prov p="estimated" />bytes ÷ 4 for each lever; formula on the Impact page</div>
        <div className="space-y-1.5">
          {levers.map(([k, n]) => (
            <div key={k} className="grid grid-cols-[1fr_auto] items-center gap-x-3 text-xs">
              <span className="truncate text-muted-foreground">{v.labels[k] ?? k}</span>
              <span className="tabular-nums">{fmtTokens(n)}</span>
              <div className="col-span-2 h-1.5 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-gradient-to-r from-primary to-accent" style={{ width: `${(n / max) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2">
          {tiles.map(([label, value, Icon, hint]) => (
            <div key={label} title={hint} className="rounded-lg border border-border bg-background/50 px-3 py-2">
              <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-muted-foreground"><Icon size={11} />{label}</div>
              <div className="mt-0.5 text-lg font-semibold tabular-nums">{value}</div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

function Pulse({ days }: { days: Day[] }) {
  const data = days.map((d) => ({ ...d, ide: d.requests - d.local, label: d.day.slice(5) }));
  const total = days.reduce((s, d) => s + d.requests, 0);
  const errs = days.reduce((s, d) => s + d.errors, 0);
  const tools = days.reduce((s, d) => s + d.tools, 0);
  return (
    <Card>
      <CardHeader title="Pulse — last 14 days"
        subtitle={<>{total} requests · {tools} tool calls · {errs} errors <Prov p="measured" className="ml-1" /></>}
        right={<Link to="/requests" className="whitespace-nowrap text-xs text-primary hover:underline">All requests →</Link>} />
      <div className="h-48 px-2 py-3">
        {total === 0 ? <Empty title="No requests in 14 days" hint="Chats in Cursor (hooks) or the Console appear here as they happen." /> : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
              <CartesianGrid vertical={false} stroke="hsl(var(--border))" />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip cursor={{ fill: "hsl(var(--muted) / 0.4)" }}
                contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                formatter={(val: number, name: string) => [val, name === "ide" ? "Cursor" : name === "local" ? "Console / local" : name]} />
              <Bar dataKey="ide" stackId="r" fill="hsl(var(--primary))" radius={[0, 0, 0, 0]} />
              <Bar dataKey="local" stackId="r" fill="hsl(var(--accent))" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
      <div className="flex gap-4 px-4 pb-3 text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm bg-primary" />Cursor</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm bg-accent" />Console / local model</span>
      </div>
    </Card>
  );
}

function Autopilot({ v }: { v: TodayData["value"] }) {
  return (
    <Card>
      <CardHeader title={<span className="flex items-center gap-2"><Wand2 size={14} className="text-accent" />Autopilot</span>}
        subtitle="Steps the harness ran so nobody had to remember them"
        right={<Link to="/automations" className="whitespace-nowrap text-xs text-primary hover:underline">Switches →</Link>} />
      {v.autopilot.length === 0 ? <Empty title="Nothing ran yet" hint="Hooks refresh the graph, sync skills and rotate snapshots on their own." /> : (
        <ol className="space-y-0 px-4 py-3">
          {v.autopilot.map((r, i) => (
            <li key={i} className="relative flex gap-3 pb-3 last:pb-0">
              {i < v.autopilot.length - 1 ? <span aria-hidden className="absolute left-[5px] top-3 h-full w-px bg-border" /> : null}
              <CircleDot size={11} className={cn("mt-1 shrink-0", r.status === "failed" ? "text-danger" : r.status === "ok" ? "text-success" : "text-muted-foreground")} />
              <div className="min-w-0 text-xs">
                <p className="font-medium">{r.label}{r.times > 1 ? <span className="ml-1.5 text-muted-foreground">×{r.times}</span> : null}</p>
                <p className="truncate text-muted-foreground">{r.reason || r.status} · {relTime(r.ts)}{r.ms ? ` · ${fmtMs(r.ms)}` : ""}</p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

function RecentList({ rows }: { rows: Recent[] }) {
  return (
    <Card>
      <CardHeader title="Latest requests" subtitle="What the agent was asked, and how it went"
        right={<Link to="/chats" className="whitespace-nowrap text-xs text-primary hover:underline">Chats →</Link>} />
      {rows.length === 0 ? <Empty title="No requests yet" hint="Open a chat in Cursor, or ask in the Console." /> : (
        <ul className="divide-y divide-border">
          {rows.map((r) => (
            <li key={r.trace_id}>
              <Link to={`/requests/${encodeURIComponent(r.trace_id)}`} className="flex items-center gap-3 px-4 py-2.5 hover:bg-muted/30">
                <span className={cn("h-2 w-2 shrink-0 rounded-full", r.status === "completed" ? "bg-success" : r.status === "error" ? "bg-danger" : "bg-warning")} title={r.status} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm">{r.prompt}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {relTime(r.start)} · {fmtMs(r.duration_ms)} · {r.tools} tools{r.subagents ? ` · ${r.subagents} subagents` : ""}
                    {r.guard ? <span className="text-warning"> · {r.guard} guarded</span> : null}
                    {r.errors ? <span className="text-danger"> · {r.errors} errors</span> : null}
                    {r.origin === "local" ? " · Console" : ""}
                  </p>
                </div>
                {r.skills.slice(0, 2).map((s) => <Badge key={s} tone="accent" className="hidden md:inline-flex">{s.replace(/^agent-spec-/, "")}</Badge>)}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

const QUICK: { label: string; hint: string; prompt: string; icon: typeof Zap }[] = [
  { label: "Where is…", hint: "Find code graph-first", prompt: "Which file implements the session-start digest, and what does it read? Name the files.", icon: Network },
  { label: "Blast radius", hint: "What breaks if I change it", prompt: "/agent-spec-query-graph If I change bin/aspec_platform/traces.py, which files depend on it?", icon: Shield },
  { label: "Why did it fail?", hint: "Investigate, no edits", prompt: "/agent-spec-investigate Why did the most recent failed request fail? Cite the trace.", icon: AlertOctagon },
];

function Skills({ skills }: { skills: TodayData["skills"] }) {
  const nav = useNavigate();
  const max = Math.max(1, ...skills.map((s) => s.uses));
  return (
    <Card>
      <CardHeader title="Skills at work" subtitle="Requests that invoked each skill" right={<Link to="/project/skills" className="whitespace-nowrap text-xs text-primary hover:underline">Catalog →</Link>} />
      <div className="space-y-2 p-4">
        {skills.length === 0 ? <p className="text-xs text-muted-foreground">No skill invoked yet. Try <code>/agent-spec-raw-code-full</code> in Cursor.</p> : skills.map((s) => (
          <div key={s.skill} className="text-xs">
            <div className="flex justify-between"><code className="truncate">/{s.skill}</code><span className="tabular-nums text-muted-foreground">{s.uses}</span></div>
            <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-accent" style={{ width: `${(s.uses / max) * 100}%` }} /></div>
          </div>
        ))}
        <p className="pt-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Ask the agent</p>
        <div className="grid gap-1.5">
          {QUICK.map((q) => (
            <button key={q.label} type="button" onClick={() => nav(`/console?prompt=${encodeURIComponent(q.prompt)}`)}
              className="flex items-center gap-2 rounded-md border border-border px-2.5 py-1.5 text-left text-xs hover:border-primary/50 hover:bg-muted/40">
              <q.icon size={12} className="text-primary" /><span className="font-medium">{q.label}</span><span className="ml-auto truncate text-muted-foreground">{q.hint}</span>
            </button>
          ))}
        </div>
      </div>
    </Card>
  );
}

/** Landing page: what needs you (each fix is a skill or an exact action), what the harness did, the pulse. */
export function Today() {
  const q = useQuery({ queryKey: ["today"], queryFn: () => apiGet<TodayData>("/api/today"), refetchInterval: 20000 });
  if (q.isLoading) return <p className="p-6 text-xs text-muted-foreground">Loading…</p>;
  if (q.isError || !q.data) return <Empty title="Could not load Today" hint={String((q.error as Error | null)?.message ?? "")} />;
  const d = q.data;
  return (
    <div className="mx-auto max-w-[1400px] space-y-4 p-6">
      <Hero d={d} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Needs you" subtitle="Ranked: what blocks the agent, what is broken, what would make it smarter. Fixes that need judgement run as skills."
            right={d.attention.length ? <Badge tone={d.counts.blocked ? "danger" : d.counts.broken ? "warning" : "primary"}>{d.attention.length}</Badge> : null} />
          {d.attention.length === 0 ? (
            <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
              <CheckCircle2 size={28} className="text-success" />
              <p className="text-sm font-medium">All clear</p>
              <p className="max-w-md text-xs text-muted-foreground">No risky edit waiting, no proposal pending, the graph is current, every hook fired and the live tests pass.</p>
            </div>
          ) : (
            <ul className="divide-y divide-border">{d.attention.map((i) => <AttentionRow key={i.id} item={i} />)}</ul>
          )}
          {d.errors.length ? <p className="border-t border-border px-4 py-2 text-[11px] text-warning" title={d.errors.join("\n")}>{d.errors.length} source(s) could not be read; the rest is shown.</p> : null}
        </Card>
        <Value v={d.value} />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2"><Pulse days={d.pulse} /></div>
        <Autopilot v={d.value} />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2"><RecentList rows={d.recent} /></div>
        <Skills skills={d.skills} />
      </div>
    </div>
  );
}
