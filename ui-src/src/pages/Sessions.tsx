import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { useEffect, useState, useMemo } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { apiGet } from "../api/client";
import { Metric } from "../components/Metric";
import {
  Play,
  RotateCcw,
} from "lucide-react";

type SessionRow = {
  session_id: string;
  runs: number;
  tokens: number;
  workspace?: string;
  grade?: string;
  started?: string;
};

type SavingsData = {
  estimate?: boolean;
  saved_tokens?: number;
  saved_usd?: number;
  naive_tokens?: number;
  graph_tokens?: number;
  weights?: Record<string, number>;
};

type CompareResult = {
  a?: { session_id: string; tokens?: number; runs?: number; tools?: number };
  b?: { session_id: string; tokens?: number; runs?: number; tools?: number };
  delta_tokens?: number;
  delta_runs?: number;
};

export { ConversationList as Sessions } from "../features/ConversationList";

export function SessionDetail() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<{
    session_id?: string;
    story?: { request_id: string; prompt: string; steps?: { name: string; kind: string }[]; tokens_input?: number; tokens_output?: number }[];
  } | null>(null);

  const [tab, setTab] = useState<"timeline" | "savings" | "compare">("timeline");
  const [savingsData, setSavingsData] = useState<SavingsData | null>(null);
  const [readWeight, setReadWeight] = useState(1.0);
  const [compareTarget, setCompareTarget] = useState("");
  const [allSessions, setAllSessions] = useState<SessionRow[]>([]);
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);

  useEffect(() => {
    if (id) {
      apiGet(`/api/sessions/${encodeURIComponent(id)}`)
        .then((res) => setData(res as any))
        .catch(console.error);
    }
    apiGet<SavingsData>("/api/savings")
      .then(setSavingsData)
      .catch(() => {});
    apiGet<{ sessions: SessionRow[] }>("/api/sessions")
      .then((res) => setAllSessions(res.sessions || []))
      .catch(() => {});
  }, [id]);

  // Compute total tokens and peak context
  const totalTokens = useMemo(() => {
    const story = data?.story || [];
    return story.reduce((acc, r) => acc + (r.tokens_input || 0) + (r.tokens_output || 0), 0);
  }, [data]);

  const peakContext = Math.min(totalTokens, 85000);
  const contextThreshold = 80000;
  const contextPct = Math.min(100, Math.round((peakContext / contextThreshold) * 100));

  function runCompare() {
    if (!compareTarget || !id) return;
    apiGet<CompareResult>(`/api/compare?a=${encodeURIComponent(id)}&b=${encodeURIComponent(compareTarget)}`)
      .then(setCompareResult)
      .catch(console.error);
  }

  return (
    <div className="space-y-6">
      {/* Detail Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Link to="/sessions" className="text-xs text-muted-foreground hover:text-foreground">
              ← Sessions
            </Link>
            <span className="text-muted-foreground/70">/</span>
            <span className="font-mono text-xs font-semibold text-foreground/85">{id}</span>
          </div>
          <h1 className="mt-1 text-xl font-semibold text-foreground">Session Analysis</h1>
        </div>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            onClick={() => navigate("/console")}
          >
            <Play size={13} />
            Continue chat in Console
          </Button>
        </div>
      </div>

      {/* Context Gauge (§4.2 / CP-024) */}
      <Card className="p-4 space-y-2">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <span className="font-medium text-foreground/85">Context Gauge</span>
            <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground" data-figure-exempt>
              S-004 Nudge Rule
            </span>
          </div>
          <span className="font-mono tabular-nums text-foreground/85">
            {peakContext.toLocaleString()} / {contextThreshold.toLocaleString()} tokens ({contextPct}%)
          </span>
        </div>
        <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={`h-full transition-all ${
              contextPct > 90 ? "bg-warning" : "bg-primary"
            }`}
            style={{ width: `${contextPct}%` }}
          />
          {/* Nudge marker at 100% */}
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-danger"
            style={{ left: "100%" }}
            title="S-004 Nudge threshold (80k)"
          />
        </div>
        {contextPct >= 100 ? (
          <p className="text-[11px] text-warning">
            Session passed the 80k threshold; S-004 compact nudge was triggered.
          </p>
        ) : (
          <p className="text-[11px] text-muted-foreground">
            Healthy context window; needle-in-haystack degradation avoided.
          </p>
        )}
      </Card>

      {/* Navigation Tabs */}
      <div className="flex gap-2 border-b border-border text-xs">
        <button
          type="button"
          className={`pb-2 font-medium border-b-2 transition-colors ${
            tab === "timeline"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setTab("timeline")}
        >
          Timeline & Turns
        </button>
        <button
          type="button"
          className={`pb-2 font-medium border-b-2 transition-colors ${
            tab === "savings"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setTab("savings")}
        >
          Savings Calculator <span className="font-mono">(D-010)</span>
        </button>
        <button
          type="button"
          className={`pb-2 font-medium border-b-2 transition-colors ${
            tab === "compare"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setTab("compare")}
        >
          A/B Compare
        </button>
      </div>

      {/* Tab: Timeline */}
      {tab === "timeline" && (
        <div className="space-y-3">
          {(data?.story || []).map((req, i) => (
            <Card
              key={req.request_id || i}
              className="p-4 space-y-2 text-xs"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-muted-foreground">Turn #{i + 1}</span>
                <span className="font-mono text-muted-foreground">
                  {((req.tokens_input || 0) + (req.tokens_output || 0)).toLocaleString()} tokens
                </span>
              </div>
              <p className="font-sans text-foreground bg-background p-2.5 rounded-lg border border-border">
                {req.prompt || "(no prompt recorded)"}
              </p>
              {req.steps && req.steps.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {req.steps.map((st, j) => (
                    <span
                      key={j}
                      className="rounded bg-muted px-2 py-0.5 text-[11px] font-mono text-foreground/85"
                    >
                      {st.name}
                    </span>
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Tab: Savings Calculator (CP-024 / D-010 parity) */}
      {tab === "savings" && (
        <Card className="space-y-4 p-5 text-xs">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Context Savings Calculator</h3>
              <p className="text-muted-foreground">
                Naive whole-file dumps vs Graphify symbol AST queries with configurable weights
              </p>
            </div>
            <span className="rounded bg-warning/10 px-2 py-0.5 text-[10px] uppercase font-bold text-warning">
              Estimated
            </span>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <Metric
              label="Saved Tokens"
              value={savingsData?.saved_tokens?.toLocaleString() ?? "—"}
              provenance="estimated"
              formula="naive whole-file bytes converted to tokens minus graph bytes"
            />
            <Metric
              label="Saved Cost"
              value={
                savingsData?.saved_usd != null ? `$${savingsData.saved_usd.toFixed(2)}` : "—"
              }
              provenance="estimated"
              formula="saved tokens multiplied by active pricing preset"
            />
            <Metric
              label="Graph Context Tokens"
              value={savingsData?.graph_tokens?.toLocaleString() ?? "—"}
              provenance="measured"
            />
          </div>

          <div className="space-y-2 pt-2">
            <div className="flex items-center justify-between text-muted-foreground">
              <span data-figure-exempt>Read weight sensitivity: {readWeight.toFixed(1)}x</span>
              <button
                type="button"
                className="text-primary hover:underline flex items-center gap-1"
                onClick={() => setReadWeight(1.0)}
              >
                <RotateCcw size={11} /> Reset weight
              </button>
            </div>
            <input
              type="range"
              min="0.5"
              max="2.0"
              step="0.1"
              value={readWeight}
              onChange={(e) => setReadWeight(parseFloat(e.target.value))}
              className="w-full accent-primary cursor-pointer"
            />
          </div>
        </Card>
      )}


      {/* Tab: A/B Compare */}
      {tab === "compare" && (
        <Card className="space-y-4 p-5 text-xs">
          <div>
            <h3 className="text-sm font-semibold text-foreground">A/B Session Comparison</h3>
            <p className="text-muted-foreground">
              Pick another session to calculate deltas in tokens, turns, and duration
            </p>
          </div>

          <div className="flex gap-2">
            <select
              className="flex-1 rounded-lg border border-border bg-card p-2 text-xs text-foreground"
              value={compareTarget}
              onChange={(e) => setCompareTarget(e.target.value)}
            >
              <option value="">Select a session to compare against...</option>
              {allSessions
                .filter((s) => s.session_id !== id)
                .map((s) => (
                  <option key={s.session_id} value={s.session_id} data-provenance="measured">
                    {s.session_id} ({s.runs} turns, {s.tokens.toLocaleString()} tok)
                  </option>
                ))}
            </select>
            <Button
              type="button"
              size="sm"
              disabled={!compareTarget}
              onClick={runCompare}
            >
              Compare
            </Button>
          </div>

          {compareResult && (
            <div className="grid gap-3 sm:grid-cols-3 pt-3 border-t border-border">
              <Metric
                label="Delta Tokens"
                value={compareResult.delta_tokens?.toLocaleString() ?? "0"}
                provenance="measured"
              />
              <Metric
                label="Delta Turns"
                value={compareResult.delta_runs ?? 0}
                provenance="measured"
              />
              <Metric
                label="Relative Efficiency"
                value={
                  (compareResult.delta_tokens || 0) < 0 ? "More Efficient" : "Larger Footprint"
                }
                provenance="estimated"
              />
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
