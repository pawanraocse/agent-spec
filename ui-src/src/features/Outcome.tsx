import { CheckCircle2, CircleDashed, Copy, XCircle } from "lucide-react";
import type { Quality, Signals, Span } from "../api/traces";
import { Num, Prov } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardHeader, Empty } from "../components/ui/card";
import { copyText, fmtTokens } from "../lib/utils";

const DIMENSIONS: [string, string][] = [
  ["relevance", "Relevance"], ["intent", "Intent adherence"], ["completeness", "Completeness"],
  ["correctness", "Correctness"], ["verification", "Verification"], ["unnecessary_changes", "Focused changes"],
  ["hallucination_risk", "Grounded (no hallucination)"], ["rework", "No rework needed"],
];

function SpanLinks({ ids, spans, onPick }: { ids: string[]; spans: Span[]; onPick: (s: Span) => void }) {
  if (!ids.length) return null;
  return (
    <span className="ml-1 inline-flex flex-wrap gap-1">
      {ids.slice(0, 6).map((id) => {
        const s = spans.find((x) => x.span_id === id);
        return s ? (
          <button key={id} type="button" className="font-mono text-[10px] text-primary hover:underline" onClick={() => onPick(s)}>{id}</button>
        ) : <span key={id} className="font-mono text-[10px] text-muted-foreground">{id}</span>;
      })}
    </span>
  );
}

function Fact({ label, ok, children }: { label: string; ok: boolean | null; children: React.ReactNode }) {
  const Icon = ok === null ? CircleDashed : ok ? CheckCircle2 : XCircle;
  const tone = ok === null ? "text-muted-foreground" : ok ? "text-success" : "text-danger";
  return (
    <li className="flex items-start gap-2 px-4 py-2 text-xs">
      <Icon size={14} className={`mt-0.5 shrink-0 ${tone}`} aria-hidden />
      <span className="w-44 shrink-0 text-muted-foreground">{label}</span>
      <span className="min-w-0 flex-1">{children}</span>
    </li>
  );
}

/** PI-006: what the request produced. Left: measured facts from spans (exact, no score).
 *  Right: the session-review skill's AI-judged quality dimensions, each with its evidence. */
export function Outcome({ signals, quality, spans, onPick, reviewPrompt }: {
  signals?: Signals | null; quality?: Quality | null; spans: Span[]; onPick: (s: Span) => void; reviewPrompt: string;
}) {
  if (!signals) return <Empty title="No outcome signals" hint="Signals are computed from this request's spans; none were recorded." />;
  const p = signals.provenance;
  const v = signals.verification;
  const edited = signals.files_edited;
  const rework = signals.rework_later;
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card>
        <CardHeader title="Measured signals" subtitle="Facts counted from the spans. They are the evidence a review scores; they are not a score." right={<Prov p={p} />} />
        <ul className="divide-y divide-border">
          <Fact label="Tool failures" ok={signals.tool_failures.count === 0}>
            <Num p={p}>{signals.tool_failures.count}</Num> of <Num p={p}>{signals.tool_calls}</Num> calls
            <SpanLinks ids={signals.tool_failures.span_ids} spans={spans} onPick={onPick} />
          </Fact>
          <Fact label="Unchanged retries" ok={signals.repeated_failures.length === 0}>
            {signals.repeated_failures.length === 0 ? "none" : signals.repeated_failures.map((r) => (
              <div key={r.tool + r.target}><span className="font-mono">{r.tool}</span> {r.target.slice(0, 80)} × <Num p={p}>{r.span_ids.length}</Num></div>
            ))}
          </Fact>
          <Fact label="Missing-path errors" ok={signals.missing_path_errors.count === 0}>
            <Num p={p}>{signals.missing_path_errors.count}</Num>
            <span className="text-muted-foreground"> — a path the agent expected that does not exist</span>
            <SpanLinks ids={signals.missing_path_errors.span_ids} spans={spans} onPick={onPick} />
          </Fact>
          <Fact label="Files edited" ok={edited.churn.length === 0}>
            <Num p={p}>{edited.count}</Num> file(s)
            {edited.churn.length ? <span className="text-warning" data-figure-exempt> · edited 3+ times: {edited.churn.map((f) => f.split("/").pop()).join(", ")}</span> : null}
            {edited.files.length ? <div className="mt-0.5 truncate font-mono text-[10px] text-muted-foreground" title={edited.files.join("\n")}>{edited.files.map((f) => f.split("/").slice(-2).join("/")).join(" · ")}</div> : null}
          </Fact>
          <Fact label="Verified after last edit" ok={edited.count ? v.ran_after_last_edit : null}>
            {edited.count === 0 ? "no edits" : v.ran_after_last_edit ? "a test, build or lint command ran" : "no test, build or lint command after the last edit"}
            {v.commands.slice(0, 3).map((c) => (
              <div key={c.span_id} className="truncate font-mono text-[10px] text-muted-foreground">{c.status === "error" ? "✗ " : "✓ "}{c.command}</div>
            ))}
          </Fact>
          <Fact label="Rework in a later request" ok={rework ? rework.files.length === 0 : null}>
            {!rework ? "no later request in this chat" : rework.files.length === 0 ? "none" : (
              <>same file(s) edited again: <span className="font-mono">{rework.files.map((f) => f.split("/").pop()).join(", ")}</span></>
            )}
          </Fact>
          <Fact label="Guard blocks · compactions" ok={signals.guard_blocks === 0 && signals.compactions === 0}>
            <Num p={p}>{signals.guard_blocks}</Num> · <Num p={p}>{signals.compactions}</Num>
          </Fact>
          <Fact label="Subagents" ok={signals.subagents.failed.length === 0}>
            <Num p={p}>{signals.subagents.count}</Num> run, <Num p={p}>{signals.subagents.failed.length}</Num> failed
          </Fact>
          <Fact label="Tokens (Cursor-reported)" ok={null}>
            {signals.tokens ? (
              <>in <Num p="measured">{fmtTokens(signals.tokens.input)}</Num> · out <Num p="measured">{fmtTokens(signals.tokens.output)}</Num> · cache read <Num p="measured">{fmtTokens(signals.tokens.cache_read)}</Num></>
            ) : "not reported for this request"}
          </Fact>
        </ul>
      </Card>

      <Card>
        <CardHeader title="Outcome quality" subtitle={<span data-figure-exempt>Scored 1–5 by the session-review skill (rubric 2.1.0) from the signals and spans; blank means not assessable.</span>} right={<Prov p="ai_judged" />} />
        {!quality ? (
          <Empty title="Not scored yet" hint="Run the review in Cursor; it reads these signals and scores each dimension with evidence."
            action={<Button size="sm" onClick={() => copyText(reviewPrompt)}><Copy size={12} />{reviewPrompt}</Button>} />
        ) : (
          <div className="space-y-3 p-4 text-xs">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-accent/10 text-xl font-bold text-accent">
                <Num p="ai_judged">{quality.overall ?? "–"}</Num>
              </div>
              <p className="leading-relaxed">{quality.summary}</p>
            </div>
            <ul className="space-y-1.5">
              {DIMENSIONS.map(([key, label]) => {
                const d = quality.dimensions?.[key];
                return (
                  <li key={key} className="flex items-start gap-2">
                    <span className="w-44 shrink-0 text-muted-foreground">{label}</span>
                    <span className="flex w-24 shrink-0 gap-0.5" aria-label={`${label}: ${d?.score ?? "not assessed"}`}>
                      {[1, 2, 3, 4, 5].map((n) => (
                        <span key={n} className={`h-2 w-4 rounded-sm ${d?.score && n <= d.score ? "bg-accent" : "bg-muted"}`} />
                      ))}
                    </span>
                    <span className="min-w-0 flex-1">
                      {d?.score == null ? <Badge>not assessable</Badge> : <Num p="ai_judged">{d.score}</Num>}
                      {d?.note ? <span className="ml-1 text-muted-foreground">{d.note}</span> : null}
                      <SpanLinks ids={d?.evidence ?? []} spans={spans} onPick={onPick} />
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </Card>
    </div>
  );
}
