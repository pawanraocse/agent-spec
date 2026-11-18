import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../api/client";
import { Num } from "../components/Num";
import { Card, CardHeader, Empty } from "../components/ui/card";

type Row = {
  skill: string; requests: number; failed: number; reworked: number; edited: number;
  failure_rate: number | null; rework_rate: number | null; reviewed: number; quality: number | null; note: string | null;
};
export type SkillEffectData = { skills: Row[]; min_reviewed: number; min_requests: number };

const pct = (v: number | null) => (v == null ? null : `${Math.round(v * 100)}%`);

/** PI-011: per skill, requests, failure and rework rates (measured) and median review quality
 *  (AI-judged) — shown only past the sample-size floor, never as a number from two data points. */
export function SkillEffectiveness() {
  const q = useQuery({ queryKey: ["skill-effectiveness"], queryFn: () => apiGet<SkillEffectData>("/api/skill-effectiveness") });
  const d = q.data;
  if (!d) return null;
  return (
    <Card>
      <CardHeader title="Skill effectiveness"
        subtitle={<>Rates need <Num p="measured">{d.min_requests}</Num> requests; quality needs <Num p="measured">{d.min_reviewed}</Num> reviewed requests. “(no skill)” is the baseline.</>} />
      {d.skills.length === 0 ? <Empty title="No requests yet" hint="Rows appear once chats run in this project." /> : (
        <table className="w-full text-xs">
          <thead className="text-left text-muted-foreground">
            <tr>
              <th className="px-4 py-2 font-medium">Skill</th><th className="py-2 text-right font-medium">Requests</th>
              <th className="py-2 text-right font-medium">Failure rate</th><th className="py-2 text-right font-medium">Rework rate</th>
              <th className="px-4 py-2 text-right font-medium">Median quality</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {d.skills.map((r) => (
              <tr key={r.skill}>
                <td className="px-4 py-1.5 font-mono">{r.skill}</td>
                <td className="py-1.5 text-right"><Num p="measured">{r.requests}</Num></td>
                <td className="py-1.5 text-right">{r.failure_rate != null ? <Num p="measured">{pct(r.failure_rate)}</Num> : <span className="text-muted-foreground">—</span>}</td>
                <td className="py-1.5 text-right">{r.rework_rate != null ? <Num p="measured">{pct(r.rework_rate)}</Num> : <span className="text-muted-foreground">—</span>}</td>
                <td className="px-4 py-1.5 text-right">
                  {r.quality != null ? <Num p="ai_judged">{r.quality.toFixed(1)}</Num>
                    : <span className="text-muted-foreground" data-figure-exempt title={r.note ?? ""}>not enough data</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
