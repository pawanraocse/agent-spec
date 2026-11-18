import { Link } from "react-router-dom";
import { Zap } from "lucide-react";
import { Num, Prov } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Card, CardHeader } from "../components/ui/card";
import { cn } from "../lib/utils";

export type Lever = "graph" | "ranged_reads" | "subagents" | "writes";
type Cost = { tokens: number; resend: number };
export type SessionSavings = {
  kept_out: number; resend_avoided: number; later_calls: number; by_lever: Record<Lever, number>;
  skill_cost: Cost; net_kept_out: number; net_resend_avoided: number;
  raw_code: { active: boolean; since_request: number | null; requests_on: number; requests: number; kept_out_while_on: number };
  error?: string;
};
export type SavingsOverview = {
  kept_out: number; resend_avoided: number; skill_cost: Cost; net_kept_out: number; net_resend_avoided: number; by_lever: Record<Lever, number>; labels: Record<Lever, string>;
  chats: number; chats_with_raw_code: number;
  skill_chats?: { chats: number; kept_out: number; resend_avoided: number; cost_resend: number; net: number };
  compare: { raw_code: { requests: number; per_request: number | null }; plain: { requests: number; per_request: number | null };
             lift: number | null; min_requests: number };
  top: { session_id: string; prompt: string; requests: number; kept_out: number; resend_avoided: number; raw_code: boolean; latest_trace_id: string }[];
};

const LEVER_LABEL: Record<Lever, string> = {
  graph: "Graph queries instead of file reads",
  ranged_reads: "Ranged reads instead of whole files",
  subagents: "Sweeps kept in subagents",
  writes: "Targeted edits instead of rewrites",
};
const LEVERS: Lever[] = ["graph", "ranged_reads", "subagents", "writes"];
const n = (v: number | null | undefined) => (v == null ? "—" : v.toLocaleString());
export const compact = (v: number) => (v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(1)}k` : String(v));

/** One bar per lever on a shared zero baseline; label and value as text, hover for the exact count. */
function Levers({ by, labels }: { by: Record<Lever, number>; labels?: Record<Lever, string> }) {
  const max = Math.max(1, ...LEVERS.map((l) => by[l] || 0));
  return (
    <div className="space-y-1.5">
      {LEVERS.map((l) => (
        <div key={l} className="flex items-center gap-2 text-xs" title={`${(labels ?? LEVER_LABEL)[l]}: ${n(by[l])} tokens`}>
          <span className="w-56 shrink-0 truncate text-muted-foreground">{(labels ?? LEVER_LABEL)[l]}</span>
          <div className="h-2.5 flex-1 rounded-sm bg-muted/40">
            <div className="h-2.5 rounded-r-[4px] bg-primary" style={{ width: `${by[l] ? Math.max(1.5, (by[l] / max) * 100) : 0}%` }} />
          </div>
          <Num p="estimated" className="w-16 shrink-0 text-right">{n(by[l])}</Num>
        </div>
      ))}
    </div>
  );
}

/** Small badge for a chat row: tokens kept out, lightning when raw-code mode was on. */
export function SavingsChip({ kept, resend, raw }: { kept: number; resend: number; raw: boolean }) {
  if (!kept) return null;
  return (
    <span title={`~${n(kept)} tokens kept out of the context, ~${n(resend)} not re-sent on later calls (estimated)${raw ? " · raw-code mode on" : ""}`}
          className={cn("inline-flex items-center gap-0.5 rounded px-1 font-medium", raw ? "bg-success/10 text-success" : "text-success")}>
      {raw ? <Zap size={10} /> : null}<Num p="estimated">−{compact(kept)}</Num>
    </span>
  );
}

/** The skill's own price, netted: its body is loaded once and re-sent on every later call too. */
function Net({ net, cost }: { net: number; cost: Cost }) {
  return (
    <div className="rounded border border-border p-2 text-xs" title="The skill body enters the context when invoked and is re-sent like everything else">
      <div className="flex justify-between"><span className="text-muted-foreground">skill's own cost</span><Num p="estimated">−{n(cost.tokens + cost.resend)}</Num></div>
      <div className={cn("flex justify-between font-semibold", net >= 0 ? "text-success" : "text-warning")}>
        <span>{net >= 0 ? "net saved" : "not yet paid back: net"}</span><Num p="estimated">{net >= 0 ? "" : "−"}{n(Math.abs(net))}</Num>
      </div>
    </div>
  );
}

/** Impact tab, top: what the raw-code rules saved across this whole chat so far. */
export function SessionSavingsCard({ s }: { s?: SessionSavings | null }) {
  if (!s || s.error || !s.kept_out) return null;
  const rc = s.raw_code;
  return (
    <Card className="lg:col-span-2 border-success/40">
      <CardHeader
        title={<span className="flex items-center gap-2"><Zap className="h-4 w-4 text-success" />This chat so far <Prov p="estimated" /></span>}
        subtitle={rc.active
          ? <>raw-code mode on since request #{rc.since_request} ({rc.requests_on} of {rc.requests} requests)</>
          : <>raw-code mode was not invoked in this chat; savings come from the always-on rules and hooks</>}
        right={rc.active ? <Badge tone="success">/agent-spec-raw-code</Badge> : null}
      />
      <div className="grid gap-4 px-4 pb-4 md:grid-cols-[220px_1fr]">
        <div className="space-y-2">
          <div><div className="text-2xl font-semibold"><Num p="estimated">{n(s.kept_out)}</Num></div><div className="text-xs text-muted-foreground">tokens kept out of the context</div></div>
          <div><div className="text-lg font-semibold text-success"><Num p="estimated">{n(s.resend_avoided)}</Num></div>
            <div className="text-xs text-muted-foreground">not re-sent across the later model calls in this chat</div></div>
          {s.skill_cost.tokens > 0 && <Net net={s.net_resend_avoided} cost={s.skill_cost} />}
        </div>
        <Levers by={s.by_lever} />
      </div>
    </Card>
  );
}

/** Showcase hero: the board-level total and the raw-code vs plain comparison. */
export function SavingsHero({ o }: { o?: SavingsOverview | null }) {
  if (!o) return null;
  const c = o.compare;
  const sk = o.skill_chats;
  const enough = c.lift !== null;
  return (
    <Card className="border-success/40">
      <CardHeader
        title={<span className="flex items-center gap-1.5"><Zap size={14} className="text-success" />Tokens kept out of the context</span>}
        subtitle={<>Across {n(o.chats)} chats. Context is re-read on every model call, so each token kept out is saved again on every later call in that chat.</>}
        right={<Prov p="estimated" />}
      />
      <div className="grid gap-5 p-4 lg:grid-cols-[260px_1fr_280px]">
        <div className="space-y-3">
          <div><div className="text-3xl font-semibold"><Num p="estimated">{compact(o.kept_out)}</Num></div><div className="text-xs text-muted-foreground">tokens kept out of chat contexts</div></div>
          <div><div className="text-2xl font-semibold text-success"><Num p="estimated">{compact(o.resend_avoided)}</Num></div><div className="text-xs text-muted-foreground">re-sends avoided on later calls</div></div>
        </div>
        <Levers by={o.by_lever} labels={o.labels} />
        <div className="space-y-3">
        {sk && sk.chats > 0 && (
          <div className="space-y-1.5 rounded border border-border p-3 text-xs" title="The skill body enters the context when invoked and is re-sent on every later call, like everything else">
            <div className="font-medium">Did <code>/agent-spec-raw-code</code> pay for itself?</div>
            <div className="flex justify-between"><span className="text-muted-foreground">saved in its {n(sk.chats)} chats</span><Num p="estimated">{n(sk.resend_avoided)}</Num></div>
            <div className="flex justify-between"><span className="text-muted-foreground">its own size, re-sent</span><Num p="estimated">−{n(sk.cost_resend)}</Num></div>
            <div className={cn("flex justify-between font-semibold", sk.net >= 0 ? "text-success" : "text-warning")}>
              <span>{sk.net >= 0 ? "net saved" : "not yet: net"}</span><Num p="estimated">{sk.net >= 0 ? "" : "−"}{n(Math.abs(sk.net))}</Num>
            </div>
          </div>
        )}
        <div className="space-y-2 rounded border border-border p-3 text-xs">
          <div className="font-medium">Per Cursor request that used tools</div>
          <div className="flex justify-between"><span className="text-muted-foreground">raw-code on ({n(c.raw_code.requests)})</span><Num p="estimated">{n(c.raw_code.per_request)}</Num></div>
          <div className="flex justify-between"><span className="text-muted-foreground">plain ({n(c.plain.requests)})</span><Num p="estimated">{n(c.plain.per_request)}</Num></div>
          {enough
            ? <div className="pt-1 text-sm font-semibold text-success">{c.lift}× more kept out with raw-code</div>
            : <div className="pt-1 text-muted-foreground">Ratio shown once each side has {c.min_requests}+ requests: run a few chats with <code>/agent-spec-raw-code-full</code>.</div>}
        </div>
        </div>
      </div>
      {o.top.length > 0 && (
        <div className="border-t border-border px-4 py-3">
          <p className="mb-2 text-[11px] uppercase tracking-wide text-muted-foreground">Chats that saved the most</p>
          <ul className="space-y-1 text-xs">
            {o.top.slice(0, 6).map((r) => (
              <li key={r.session_id} className="flex items-center gap-2">
                <SavingsChip kept={r.kept_out} resend={r.resend_avoided} raw={r.raw_code} />
                <Link to={`/requests/${r.latest_trace_id}`} className="truncate hover:text-primary hover:underline">{r.prompt || r.session_id}</Link>
                <span className="ml-auto shrink-0 text-muted-foreground">{r.requests} req · {compact(r.resend_avoided)} re-sends</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
