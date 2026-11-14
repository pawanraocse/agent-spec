import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, FileCode2, Power } from "lucide-react";
import { apiGet, apiPost } from "../api/client";
import { Num, Stat } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Card, CardHeader, Empty } from "../components/ui/card";
import { cn, relTime } from "../lib/utils";

type Run = { ts: string; name: string; status: string; reason?: string; duration_ms?: number; session?: string; source?: string };
type Automation = {
  id: string; title: string; trigger: string; kind: "script" | "skill"; replaces: string; env: string | null;
  enabled: boolean; switched_off: boolean; env_off: boolean; runs: number; succeeded: number; failed: number;
  duration_ms_total: number | null; last: Run | null;
};
export type AutomationsData = {
  automations: Automation[]; recent: Run[]; config: string; log: string;
  totals: { runs: number; succeeded: number; failed: number; last_24h: number; enabled: number; count: number };
};

const TONE: Record<string, "success" | "danger" | "primary" | "neutral"> = {
  ok: "success", installed: "success", built: "success", started: "primary", sent: "primary", failed: "danger",
};

function Switch({ on, disabled, label, onChange }: { on: boolean; disabled?: boolean; label: string; onChange: (v: boolean) => void }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} disabled={disabled} onClick={() => onChange(!on)}
      className={cn("relative h-5 w-9 shrink-0 rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        on ? "bg-primary" : "bg-muted ring-1 ring-border")}>
      <span className={cn("absolute top-0.5 h-4 w-4 rounded-full bg-background shadow transition-transform", on ? "translate-x-4" : "translate-x-0.5")} />
    </button>
  );
}

/** HA-006: every step the harness now runs on its own, what it replaced, how often it ran and
 *  whether it worked, with a switch for each. Counts are measured from automation.jsonl. */
export function Automations() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["automations"], queryFn: () => apiGet<AutomationsData>("/api/automations"), refetchInterval: 15000 });
  const toggle = useMutation({
    mutationFn: (v: { id: string; enabled: boolean }) => apiPost<AutomationsData & { error?: string }>("/api/automations", v),
    onSuccess: (data) => { if (!data.error) qc.setQueryData(["automations"], data); },
  });
  const d = q.data;
  if (!d) return <p className="p-6 text-xs text-muted-foreground">{q.isError ? "Could not load automations." : "Loading…"}</p>;
  const t = d.totals;
  return (
    <div className="space-y-5 p-6">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Steps run for you" value={t.succeeded} p="measured" hint={<>of <Num p="measured">{t.runs}</Num> runs logged</>} />
        <Stat label="Past day" value={t.last_24h} p="measured" hint="automation runs" />
        <Stat label="Failed" value={t.failed} p="measured" hint={t.failed ? "see the run log below" : "none"} />
        <Stat label="Switched on" value={`${t.enabled} / ${t.count}`} p="measured" hint={<span className="font-mono">{d.config}</span>} />
      </div>

      <Card>
        <CardHeader title="Automations" subtitle="Steps someone used to have to remember. Each switch is read by the hook on its next run." />
        <ul className="divide-y divide-border">
          {d.automations.map((a) => (
            <li key={a.id} className="flex items-start gap-3 px-4 py-3">
              {a.kind === "skill" ? <Bot size={16} className="mt-0.5 shrink-0 text-k-skill" aria-hidden /> : <FileCode2 size={16} className="mt-0.5 shrink-0 text-muted-foreground" aria-hidden />}
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{a.title}</span>
                  <Badge tone={a.kind === "skill" ? "accent" : "neutral"}>{a.kind === "skill" ? "runs a skill" : "script"}</Badge>
                  {a.last ? <Badge tone={TONE[a.last.status] ?? "neutral"}>{a.last.status}</Badge> : null}
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">When: {a.trigger}. Replaces {a.replaces}.</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  <Num p="measured">{a.runs}</Num> runs · <Num p="measured">{a.succeeded}</Num> ok · <Num p="measured">{a.failed}</Num> failed
                  {a.duration_ms_total != null ? <> · <Num p="measured">{a.duration_ms_total}</Num> ms total</> : null}
                  {a.last ? <> · last <time dateTime={a.last.ts}>{relTime(a.last.ts)}</time></> : null}
                </p>
                {a.env_off ? <p className="mt-1 text-xs text-warning">Off by the environment: <code>{a.env}=0</code> wins over this switch.</p> : null}
              </div>
              <Switch on={a.enabled} disabled={a.env_off || toggle.isPending} label={`${a.title}: ${a.enabled ? "on" : "off"}`}
                onChange={(enabled) => toggle.mutate({ id: a.id, enabled })} />
            </li>
          ))}
        </ul>
        {toggle.data?.error ? <p className="border-t border-border px-4 py-2 text-xs text-danger">{toggle.data.error}</p> : null}
      </Card>

      <Card>
        <CardHeader title="Run log" subtitle={<>Newest first, from <code>{d.log}</code>.</>} right={<Power size={14} className="text-muted-foreground" aria-hidden />} />
        {d.recent.length === 0 ? (
          <Empty title="Nothing has run yet" hint="Rows appear after the next chat turn ends, or when a skill's preflight registers this project." />
        ) : (
          <table className="w-full text-xs">
            <thead className="text-left text-muted-foreground">
              <tr><th className="px-4 py-2 font-medium">When</th><th className="py-2 font-medium">Automation</th><th className="py-2 font-medium">Status</th><th className="py-2 font-medium">Why</th><th className="px-4 py-2 text-right font-medium">Took</th></tr>
            </thead>
            <tbody className="divide-y divide-border">
              {d.recent.map((r, i) => (
                <tr key={`${r.ts}-${r.name}-${i}`}>
                  <td className="whitespace-nowrap px-4 py-1.5"><time dateTime={r.ts}>{relTime(r.ts)}</time></td>
                  <td className="py-1.5 font-mono">{r.name}</td>
                  <td className="py-1.5"><Badge tone={TONE[r.status] ?? "neutral"}>{r.status}</Badge></td>
                  <td className="max-w-md truncate py-1.5 text-muted-foreground" data-figure-exempt title={r.reason}>{r.reason || "—"}</td>
                  <td className="px-4 py-1.5 text-right">{r.duration_ms != null ? <><Num p="measured">{r.duration_ms}</Num> ms</> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
