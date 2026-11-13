import { useQuery } from "@tanstack/react-query";
import { Copy } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { apiGet } from "../api/client";
import { Num, Prov, Stat } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardHeader, Empty } from "../components/ui/card";
import { copyText } from "../lib/utils";

type Rec = {
  id: string; kind: string; subject: string; created: string; addresses: string[];
  before_sessions: number; after_sessions: number; before_findings: number; after_findings: number;
  before_rate: number | null; after_rate: number | null; verdict: string;
};
type LearningData = {
  recurrence: Rec[]; window: number; unlinked: number; facts_total: number; reviewed_sessions: number;
  facts_by_month: { month: string; count: number }[]; experience_tiers: Record<string, number>;
  injections: { request_id: string; started: string; facts: number }[];
};

const LINK_PROMPT = "For each memory fact in .agent-spec/memory/facts/ that exists to prevent a mistake, decide which agent-spec-session-review finding category it addresses and re-record it with /agent-spec-remember --addresses <category> (supersede, do not hand-edit).";
const TIP = { background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", fontSize: 11 };

/** Learning space (§14.7, DV-051): does a fact make its mistake rarer? Flat is shown as flat. */
export function Learning() {
  const q = useQuery({ queryKey: ["learning"], queryFn: () => apiGet<LearningData>("/api/learning") });
  const d = q.data;
  const chart = (d?.recurrence ?? []).map((r) => ({ name: r.subject.slice(0, 24) || r.id, before: r.before_rate ?? 0, after: r.after_rate ?? 0 }));
  return (
    <div className="mx-auto max-w-6xl space-y-5 p-6">
      <div>
        <h1 className="text-lg font-semibold">Learning</h1>
        <p className="text-xs text-muted-foreground">Is the harness actually getting better? For every fact linked to a finding class: findings per session in the <span data-figure-exempt>{d?.window ?? 10}</span> reviewed sessions before it was recorded against the <span data-figure-exempt>{d?.window ?? 10}</span> after.</p>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Memory facts" value={d?.facts_total ?? "—"} p="measured" />
        <Stat label="Linked to a finding" value={d ? d.recurrence.length : "—"} p="measured" hint="facts with addresses:" />
        <Stat label="Reviewed sessions" value={d?.reviewed_sessions ?? "—"} p="measured" />
        <Stat label="Facts improving" value={d ? d.recurrence.filter((r) => r.verdict === "fewer").length : "—"} p="measured" hint="rate after < rate before" />
      </div>
      <Card>
        <CardHeader title={<span className="flex items-center gap-2">Recurrence before vs after <Prov p="measured" /></span>} subtitle="Findings are AI-judged; the counting is exact" />
        {!d || d.recurrence.length === 0 ? (
          <Empty
            title={d && d.facts_total ? "No fact is linked to a finding class yet" : "No facts yet"}
            hint={<>A fact joins this chart when it names the review category it prevents (<code>addresses:</code>). The model chooses the category; the dashboard only counts. <Num p="measured">{d?.unlinked ?? 0}</Num> facts are unlinked.</>}
            action={<Button size="sm" variant="outline" onClick={() => copyText(LINK_PROMPT)}><Copy size={12} />Copy linking prompt</Button>}
          />
        ) : (
          <div className="p-4">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chart} margin={{ left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
                  <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} allowDecimals />
                  <Tooltip contentStyle={TIP} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="before" name="findings / session before" fill="hsl(var(--muted-foreground))" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="after" name="after" fill="hsl(var(--success))" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <table className="mt-3 w-full text-xs">
              <thead className="text-[10px] uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border"><th className="py-1.5 text-left">Fact</th><th className="text-left">Addresses</th><th className="text-right">Before</th><th className="text-right">After</th><th className="text-right">Verdict</th></tr>
              </thead>
              <tbody>
                {d.recurrence.map((r) => (
                  <tr key={r.id} className="border-b border-border/50">
                    <td className="py-1.5">{r.subject}<time className="ml-2 text-muted-foreground">{r.created}</time></td>
                    <td>{r.addresses.map((a) => <Badge key={a} className="mr-1 normal-case">{a}</Badge>)}</td>
                    <td className="text-right"><Num p="measured">{r.before_findings}</Num> / <Num p="measured">{r.before_sessions}</Num></td>
                    <td className="text-right"><Num p="measured">{r.after_findings}</Num> / <Num p="measured">{r.after_sessions}</Num></td>
                    <td className="text-right"><Badge tone={r.verdict === "fewer" ? "success" : r.verdict === "more" ? "danger" : "neutral"}>{r.verdict}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <div className="grid gap-5 lg:grid-cols-3">
        <Card>
          <CardHeader title={<span className="flex items-center gap-2">Facts recorded per month <Prov p="measured" /></span>} />
          <div className="h-48 p-3">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={d?.facts_by_month ?? []} margin={{ left: -20 }}>
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
                <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} allowDecimals={false} />
                <Tooltip contentStyle={TIP} />
                <Bar dataKey="count" fill="hsl(var(--primary))" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <CardHeader title={<span className="flex items-center gap-2">Facts injected per request <Prov p="measured" /></span>} subtitle="How many remembered facts reached each recent request (digest)" />
          {d && d.injections.length ? (
            <div className="h-48 p-3">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={d.injections} margin={{ left: -20 }}>
                  <XAxis dataKey="started" tick={false} />
                  <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} allowDecimals={false} />
                  <Tooltip contentStyle={TIP} />
                  <Bar dataKey="facts" fill="hsl(var(--accent))" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <Empty title="No injections recorded" hint="Receipts record which facts the digest injected; they appear after sessions end with the harness installed." />}
        </Card>
        <Card>
          <CardHeader title={<span className="flex items-center gap-2">Experiences by tier <Prov p="measured" /></span>} subtitle="candidate → trusted promotions" />
          {d && Object.keys(d.experience_tiers).length ? (
            <ul className="space-y-2 p-4 text-xs">
              {Object.entries(d.experience_tiers).map(([tier, n]) => (
                <li key={tier} className="flex items-center justify-between"><Badge tone={tier === "trusted" ? "success" : tier === "deprecated" ? "danger" : "neutral"}>{tier}</Badge><Num p="measured">{n}</Num></li>
              ))}
            </ul>
          ) : <Empty title="No experiences recorded" hint="Experiences are distilled from successful workflow runs (agent-spec-learn)." />}
        </Card>
      </div>
    </div>
  );
}
