import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Copy, RotateCcw } from "lucide-react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { apiGet } from "../api/client";
import { Num, Prov, Stat } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardHeader, Empty } from "../components/ui/card";
import { useContextOverview, type ContextOverview } from "../api/traces";
import { CONTEXT_CATEGORIES, CompositionBar } from "../features/ContextMeter";
import { kindMeta } from "../features/kinds";
import { copyText, fmtBytes, fmtMs, fmtTokens } from "../lib/utils";

type LagRow = { key: string; count: number; failure_rate: number; p50_ms: number | null; p95_ms: number | null; total_ms: number; provenance: "measured" | "estimated" };
type Lag = {
  requests: number; by_kind: LagRow[]; by_tool: LagRow[]; guard_blocks: number; compactions: number; whole_file_reads: number;
  subagent_bytes_in: number; subagent_bytes_out: number; sources: string[];
  slowest: { span_id: string; trace_id: string; kind: string; name: string; duration_ms: number; source: string }[];
};
type Issue = { category: string; title: string; count: number; sessions: number; severity: string; trend: { week: string; count: number }[]; examples: { session_id: string; trace_id?: string; span_id?: string; title: string; detail: string }[]; fix_prompt: string };
type Issues = { reviewed_sessions: number; issues: Issue[]; all_categories: number; grades: { session_id: string; grade: string; reviewed_at: string; model: string }[] };

const REVIEW_ALL = "Use the agent-spec-reviewer subagent to review each of my last 5 Cursor conversations (bin/agent-spec-platform.py trace --list 20) with the agent-spec-session-review skill.";

function LagTable({ rows, title }: { rows: LagRow[]; title: string }) {
  return (
    <table className="w-full text-xs">
      <thead className="text-[10px] uppercase tracking-wide text-muted-foreground">
        <tr className="border-b border-border">
          <th className="px-4 py-2 text-left font-medium">{title}</th>
          <th className="px-2 py-2 text-right font-medium">Count</th>
          <th className="px-2 py-2 text-right font-medium">p50</th>
          <th className="px-2 py-2 text-right font-medium">p95</th>
          <th className="px-2 py-2 text-right font-medium">Total</th>
          <th className="px-4 py-2 text-right font-medium">Fail rate</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const [kind, name] = r.key.includes(":") ? r.key.split(/:(.*)/s) : [r.key, ""];
          const meta = kindMeta(kind);
          return (
            <tr key={r.key} className="border-b border-border/50">
              <td className="px-4 py-1.5"><span className="inline-flex items-center gap-1.5"><meta.icon size={12} className={meta.color} />{name || meta.label}</span></td>
              <td className="px-2 text-right"><Num p="measured">{r.count}</Num></td>
              <td className="px-2 text-right"><Num p={r.provenance}>{fmtMs(r.p50_ms)}</Num></td>
              <td className="px-2 text-right font-medium"><Num p={r.provenance}>{fmtMs(r.p95_ms)}</Num></td>
              <td className="px-2 text-right text-muted-foreground"><Num p={r.provenance}>{fmtMs(r.total_ms)}</Num></td>
              <td className="px-4 text-right"><Num p="measured" className={r.failure_rate > 0.1 ? "text-danger" : ""}>{Math.round(r.failure_rate * 100)}%</Num></td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/** Context budget: what each chat re-sends per model call, from Cursor's own counters. */
function ContextBudgetCard({ data }: { data: ContextOverview | undefined }) {
  return (
    <Card>
      <CardHeader
        title={<span className="flex items-center gap-2"><RotateCcw size={14} className="text-primary" />Context budget <Prov p="measured" /></span>}
        subtitle="Every model call re-sends the whole chat. Ranked by what each chat sends now; the line marks a fresh chat."
        right={<Button size="sm" variant="outline" onClick={() => copyText("/agent-spec-compact")} title="Writes the state to disk; continue in a new chat"><Copy size={12} />Copy /agent-spec-compact</Button>}
      />
      {!data ? <p className="p-4 text-xs text-muted-foreground">Loading…</p> : data.chats === 0 ? (
        <Empty title="No context readings yet" hint="Cursor writes each chat's context size to its local store as the chat runs. Nothing is shown until it has." />
      ) : (
        <div className="space-y-4 p-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-border bg-background px-3 py-2">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Chats past break-even</p>
              <p className={data.by_verdict.reset ? "text-xl font-semibold text-danger" : "text-xl font-semibold"}><Num p="measured">{data.by_verdict.reset}</Num><span className="text-sm text-muted-foreground"> / <Num p="measured">{data.chats}</Num></span></p>
              <p className="text-[10px] text-muted-foreground">a new chat pays back in under <Num p="estimated">{data.breakeven_calls}</Num> calls</p>
            </div>
            <div className="rounded-lg border border-border bg-background px-3 py-2">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Carried above a fresh chat</p>
              <p className="text-xl font-semibold"><Num p="measured">{fmtTokens(data.carried_tokens)}</Num></p>
              <p className="text-[10px] text-muted-foreground">tokens per call, summed over chats · fresh chat <Num p="measured">{fmtTokens(data.floor)}</Num></p>
            </div>
            <div className="rounded-lg border border-border bg-background px-3 py-2">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Saved per call by resetting</p>
              <p className="text-xl font-semibold text-success"><Num p="estimated">{fmtTokens(data.reset_saving_per_call)}</Num></p>
              <p className="text-[10px] text-muted-foreground">weighted tokens, chats past break-even only</p>
            </div>
          </div>
          <ul className="space-y-2">
            {data.top.map((r) => {
              const b = r.budget!;
              const name = r.name || r.session_id.slice(0, 8);
              return (
                <li key={r.session_id} className="grid grid-cols-[minmax(0,14rem)_1fr_auto] items-center gap-3 text-xs">
                  {r.latest_trace_id ? (
                    <Link to={`/requests/${encodeURIComponent(r.latest_trace_id)}`} className="truncate text-primary hover:underline" title={r.session_id}>{name}</Link>
                  ) : <span className="truncate" title={r.session_id}>{name}</span>}
                  <CompositionBar b={b} height={8} />
                  <span className="flex items-center gap-2 whitespace-nowrap">
                    <Num p="measured" className="w-14 text-right font-medium">{fmtTokens(b.used)}</Num>
                    <Num p="measured" className="w-10 text-right text-muted-foreground">{b.growth}×</Num>
                    {b.verdict === "reset" ? <Badge tone="danger">reset · <Num p="estimated">{b.breakeven_calls}</Num></Badge> : <Badge tone={b.verdict === "fresh" ? "success" : "neutral"}>{b.verdict}</Badge>}
                    {b.nudged ? <Badge tone="warning" title="The stop hook already suggested /agent-spec-compact in this chat">nudged</Badge> : null}
                  </span>
                </li>
              );
            })}
          </ul>
          <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-muted-foreground">
            {CONTEXT_CATEGORIES.map((c) => (
              <li key={c.id} className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm" style={{ background: c.color, opacity: c.fixed ? 0.75 : 1 }} />{c.label}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

/** Coach space (§14.7, DV-041): measured lag + AI-judged top issues with trend and fix prompts. */
export function Coach() {
  const lag = useQuery({ queryKey: ["lag"], queryFn: () => apiGet<Lag>("/api/coach/lag") });
  const issues = useQuery({ queryKey: ["issues"], queryFn: () => apiGet<Issues>("/api/coach/issues") });
  const context = useContextOverview();
  const l = lag.data;
  const prov = l && l.sources.some((s) => s === "cursor_store") ? "estimated" : "measured";
  return (
    <div className="mx-auto max-w-6xl space-y-5 p-6">
      <div>
        <h1 className="text-lg font-semibold">Coach</h1>
        <p className="text-xs text-muted-foreground">Where is the agent slow or wasteful, and what should change? Latency is measured from spans; issues are judged by the review skill and only counted here.</p>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Requests" value={l?.requests ?? "—"} p="measured" />
        <Stat label="Guard blocks" value={l?.guard_blocks ?? "—"} p="measured" />
        <Stat label="Whole-file reads" value={l?.whole_file_reads ?? "—"} p="measured" hint="Read spans with ranged=false (hook data only)" />
        <Stat label="Compactions" value={l?.compactions ?? "—"} p="measured" />
        <Stat label="Handed to subagents" value={l ? fmtBytes(l.subagent_bytes_in) : "—"} p="measured" hint={l ? <>returned <Num p="measured">{fmtBytes(l.subagent_bytes_out)}</Num></> : undefined} />
      </div>

      <ContextBudgetCard data={context.data} />

      <Card>
        <CardHeader
          title={<span className="flex items-center gap-2">Top issues <Prov p="ai_judged" /></span>}
          subtitle={issues.data ? <>From <Num p="measured">{issues.data.reviewed_sessions}</Num> reviewed conversations · <Num p="measured">{issues.data.all_categories}</Num> issue classes</> : "Loading…"}
          right={<Button size="sm" variant="outline" onClick={() => copyText(REVIEW_ALL)}><Copy size={12} />Copy review prompt</Button>}
        />
        {issues.data && issues.data.issues.length === 0 ? (
          <Empty title="No reviews yet" hint="Nothing is invented here. Ask the agent to review recent conversations; findings land in .agent-spec/metrics/reviews/ and are grouped into the top three issues with their weekly trend." />
        ) : (
          <div className="grid gap-3 p-4 md:grid-cols-3">
            {(issues.data?.issues ?? []).map((i, n) => (
              <div key={i.category} className="flex flex-col rounded-lg border border-border bg-background p-3">
                <div className="flex items-center gap-2">
                  <span data-figure-exempt className="flex h-5 w-5 items-center justify-center rounded-full bg-accent/15 text-[10px] font-bold text-accent">{n + 1}</span>
                  <span className="truncate text-sm font-medium">{i.title || i.category}</span>
                </div>
                <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                  <Badge tone={i.severity === "high" ? "danger" : "warning"}>{i.severity}</Badge>
                  <span><Num p="ai_judged">{i.count}</Num> findings · <Num p="measured">{i.sessions}</Num> sessions</span>
                </div>
                <div className="mt-2 h-14">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={i.trend}>
                      <XAxis dataKey="week" hide />
                      <Tooltip cursor={false} contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", fontSize: 11 }} />
                      <Bar dataKey="count" fill="hsl(var(--accent))" radius={[2, 2, 0, 0]} isAnimationActive={false} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <ul className="mt-2 space-y-1 text-[11px]">
                  {i.examples.slice(0, 2).map((e, k) => (
                    <li key={k} className="truncate">
                      {e.trace_id ? <Link className="text-primary hover:underline" to={`/requests/${encodeURIComponent(e.trace_id)}`}>{e.title}</Link> : e.title}
                    </li>
                  ))}
                </ul>
                {i.fix_prompt ? (
                  <Button size="sm" variant="subtle" className="mt-auto self-start" onClick={() => copyText(i.fix_prompt)}><Copy size={11} />Copy fix prompt</Button>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title={<span className="flex items-center gap-2">Latency by span kind <Prov p={prov} /></span>} subtitle="p50 / p95 over every request shown in Live" />
          {l ? <LagTable rows={l.by_kind} title="Kind" /> : <p className="p-4 text-xs text-muted-foreground">Loading…</p>}
        </Card>
        <Card>
          <CardHeader title="Slowest spans" subtitle="Click to open the request at that span" />
          <ul className="divide-y divide-border/60 text-xs">
            {(l?.slowest ?? []).map((s) => {
              const meta = kindMeta(s.kind);
              return (
                <li key={s.span_id}>
                  <Link to={`/requests/${encodeURIComponent(s.trace_id)}`} className="flex items-center gap-2 px-4 py-1.5 hover:bg-muted/50">
                    <meta.icon size={12} className={meta.color} />
                    <span className="truncate">{s.name}</span>
                    <span className="ml-auto font-medium"><Num p={s.source === "cursor_store" ? "estimated" : "measured"}>{fmtMs(s.duration_ms)}</Num></span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </Card>
      </div>
      <Card>
        <CardHeader title="Tools ranked by p95" subtitle="Where a narrower call would buy the most time" />
        {l ? <LagTable rows={l.by_tool} title="Tool" /> : null}
      </Card>
    </div>
  );
}
