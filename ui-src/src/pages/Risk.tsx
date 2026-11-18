import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ShieldAlert, X } from "lucide-react";
import { apiGet, apiPost } from "../api/client";
import { Num, Stat } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Card, CardHeader, Empty } from "../components/ui/card";
import { relTime } from "../lib/utils";

type Pending = {
  key: string; tool: string; target: string; file?: string; tier: number; reasons: string[];
  fan_in?: number; cross_repo_callers?: number; session?: string | null; first_blocked: string; attempts: number;
};
type Event = { ts: string; event: string; key?: string; tier?: number; tool?: string; target?: string; by?: string; session?: string | null; reasons?: string[]; error?: string };
export type RiskData = {
  enabled: boolean; config: { enforce: string; tier2_fan_in: number; tier3_fan_in: number; approval_ttl_s: number } | null;
  pending: Pending[]; counts: Record<"blocked" | "warned" | "approved" | "denied" | "used" | "error", number>;
  tiers: { "2": number; "3": number }; sessions: { session: string; tier2: number; tier3: number }[];
  recent: Event[]; log: string;
};

const TONE: Record<string, "success" | "danger" | "warning" | "primary" | "neutral"> = {
  blocked: "danger", warned: "warning", approved: "success", used: "primary", denied: "neutral", error: "danger",
};

/** H-030 / P4-016: a tier-3 change the preToolUse gate blocked waits here with its blast radius.
 *  Approve lets the agent's next identical call through once; every decision is in risk.jsonl. */
export function Risk() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["risk"], queryFn: () => apiGet<RiskData>("/api/risk"), refetchInterval: 5000 });
  const decide = useMutation({
    mutationFn: (v: { key: string; decision: "approve" | "deny" }) => apiPost<{ ok?: boolean; error?: string; risk?: RiskData }>("/api/risk", v),
    onSuccess: (data) => { if (data.risk) qc.setQueryData(["risk"], data.risk); },
  });
  const d = q.data;
  if (!d) return <p className="p-6 text-xs text-muted-foreground">{q.isError ? "Could not load the risk panel." : "Loading…"}</p>;
  if (!d.enabled) return <Empty title="Risk gate not installed" hint="Re-run ./install.sh --register for this project to add agent-spec-risk.py." />;
  const c = d.counts;
  const ttlMin = Math.round((d.config?.approval_ttl_s ?? 1800) / 60);
  return (
    <div className="space-y-5 p-6">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Waiting for you" value={d.pending.length} p="measured" hint={<span data-figure-exempt>tier-3 actions blocked</span>} />
        <Stat label="Blocked" value={c.blocked} p="measured" hint={<><Num p="measured">{c.approved}</Num> approved · <Num p="measured">{c.denied}</Num> denied</>} />
        <Stat label="Warned" value={c.warned} p="measured" hint={<span data-figure-exempt>tier 2: allowed, recorded</span>} />
        <Stat label="Gate mode" value={d.config?.enforce ?? "—"} p="measured"
          hint={d.config ? <><span data-figure-exempt>tier 2 at</span> <Num p="measured">{d.config.tier2_fan_in}</Num><span data-figure-exempt>, tier 3 at</span> <Num p="measured">{d.config.tier3_fan_in}</Num> dependents</> : undefined} />
      </div>

      <Card>
        <CardHeader title="Waiting for approval"
          subtitle={<>An approval lets the same change through once, within <Num p="measured">{ttlMin}</Num> minutes. Thresholds: <code>.agent-spec/risk.json</code>.</>}
          right={<ShieldAlert size={14} className="text-muted-foreground" aria-hidden />} />
        {d.pending.length === 0 ? (
          <Empty title="Nothing is waiting" hint="When the agent tries a change many files depend on, it stops here until you decide." />
        ) : (
          <ul className="divide-y divide-border">
            {d.pending.map((p) => (
              <li key={p.key} className="flex flex-wrap items-start gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="danger"><span data-figure-exempt>tier {p.tier}</span></Badge>
                    <span className="font-mono text-sm">{p.file || p.target}</span>
                    <span className="text-xs text-muted-foreground">{p.tool}</span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground" data-figure-exempt>{p.reasons.join(" · ")}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    blocked <time dateTime={p.first_blocked}>{relTime(p.first_blocked)}</time> · <Num p="measured">{p.attempts}</Num> attempt(s)
                    {p.fan_in != null ? <> · <Num p="measured">{p.fan_in}</Num> direct dependents</> : null}
                    {p.cross_repo_callers ? <> · <Num p="measured">{p.cross_repo_callers}</Num> cross-repo callers</> : null}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button type="button" disabled={decide.isPending} onClick={() => decide.mutate({ key: p.key, decision: "approve" })}
                    className="inline-flex items-center gap-1 rounded-md bg-primary px-2 py-1 text-xs text-primary-foreground disabled:opacity-50">
                    <Check size={12} aria-hidden /> Approve once
                  </button>
                  <button type="button" disabled={decide.isPending} onClick={() => decide.mutate({ key: p.key, decision: "deny" })}
                    className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50">
                    <X size={12} aria-hidden /> Deny
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
        {decide.data?.error ? <p className="border-t border-border px-4 py-2 text-xs text-danger">{decide.data.error}</p> : null}
      </Card>

      {d.sessions.length ? (
        <Card>
          <CardHeader title="Risky chats" subtitle={<span data-figure-exempt>Tier-2 warnings and tier-3 blocks per conversation, most tier-3 first.</span>} />
          <table className="w-full text-xs">
            <thead className="text-left text-muted-foreground">
              <tr><th className="px-4 py-2 font-medium">Conversation</th><th className="py-2 text-right font-medium">Warned</th><th className="px-4 py-2 text-right font-medium">Blocked</th></tr>
            </thead>
            <tbody className="divide-y divide-border">
              {d.sessions.map((s) => (
                <tr key={s.session}>
                  <td className="px-4 py-1.5 font-mono">{s.session}</td>
                  <td className="py-1.5 text-right"><Num p="measured">{s.tier2}</Num></td>
                  <td className="px-4 py-1.5 text-right"><Num p="measured">{s.tier3}</Num></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Decision trail" subtitle={<>Newest first, from <code>{d.log}</code>: who decided what, and when it was used.</>} />
        {d.recent.length === 0 ? (
          <Empty title="No risk events yet" hint="Rows appear when the gate warns on or blocks a change." />
        ) : (
          <table className="w-full text-xs">
            <thead className="text-left text-muted-foreground">
              <tr><th className="px-4 py-2 font-medium">When</th><th className="py-2 font-medium">Event</th><th className="py-2 font-medium">Tier</th><th className="py-2 font-medium">Target</th><th className="px-4 py-2 font-medium">By</th></tr>
            </thead>
            <tbody className="divide-y divide-border">
              {d.recent.map((e, i) => (
                <tr key={`${e.ts}-${i}`}>
                  <td className="whitespace-nowrap px-4 py-1.5"><time dateTime={e.ts}>{relTime(e.ts)}</time></td>
                  <td className="py-1.5"><Badge tone={TONE[e.event] ?? "neutral"}>{e.event}</Badge></td>
                  <td className="py-1.5">{e.tier != null ? <Num p="measured">{e.tier}</Num> : "—"}</td>
                  <td className="max-w-md truncate py-1.5 font-mono" title={e.error || e.target}>{e.error || e.target || "—"}</td>
                  <td className="px-4 py-1.5 text-muted-foreground">{e.by || (e.event === "used" ? "agent retry" : "gate")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
