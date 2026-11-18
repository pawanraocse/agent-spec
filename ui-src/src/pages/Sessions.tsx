import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { useEffect, useState, useMemo } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { apiGet } from "../api/client";
import { SessionSavingsCard, type SessionSavings } from "../features/SkillSavings";
import { SessionCompare, type CompareResult } from "../features/SessionCompare";
import { Play } from "lucide-react";

type SessionRow = {
  session_id: string;
  runs: number;
  tokens: number;
  workspace?: string;
  grade?: string;
  started?: string;
};


export { ConversationList as Sessions } from "../features/ConversationList";

export function SessionDetail() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<{
    session_id?: string;
    story?: { request_id: string; prompt: string; steps?: { name: string; kind: string }[]; tokens_input?: number; tokens_output?: number }[];
    session_savings?: SessionSavings | null;
  } | null>(null);

  const [tab, setTab] = useState<"timeline" | "savings" | "compare">("timeline");
  const [compareTarget, setCompareTarget] = useState("");
  const [allSessions, setAllSessions] = useState<SessionRow[]>([]);
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);

  useEffect(() => {
    if (id) {
      apiGet(`/api/sessions/${encodeURIComponent(id)}`)
        .then((res) => setData(res as any))
        .catch(console.error);
    }
    apiGet<{ sessions: SessionRow[] }>("/api/sessions")
      .then((res) => setAllSessions(res.sessions || []))
      .catch(() => {});
  }, [id]);

  // The largest single request's input is the most context the model held at once.
  const peakContext = useMemo(() => Math.max(0, ...(data?.story || []).map((r) => r.tokens_input || 0)), [data]);
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
            <Link to="/chats" className="text-xs text-muted-foreground hover:text-foreground">
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

      {/* Context Gauge (§4.2 / CP-024): only when the chat recorded token counts; 0 would read as "healthy" */}
      {peakContext > 0 && (
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
            A request passed the compact threshold; the S-004 compact nudge applies.
          </p>
        ) : (
          <p className="text-[11px] text-muted-foreground">
            Largest request stayed under the compact threshold.
          </p>
        )}
      </Card>
      )}

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
          Savings
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

      {/* Tab: Savings — the same per-chat model the request page and the chat list use */}
      {tab === "savings" && (
        data?.session_savings && !data.session_savings.error && data.session_savings.kept_out
          ? <div className="grid gap-4 lg:grid-cols-2"><SessionSavingsCard s={data.session_savings} /></div>
          : <Card className="p-5 text-xs text-muted-foreground">
              No savings recorded for this chat. Savings come from hook-recorded tool calls (graph queries, ranged reads,
              subagents, targeted edits); chats read only from Cursor's own history carry no tool sizes.
            </Card>
      )}

      {/* Tab: A/B Compare */}
      {tab === "compare" && (
        <Card className="space-y-4 p-5 text-xs">
          <div>
            <h3 className="text-sm font-semibold text-foreground">A/B Session Comparison</h3>
            <p className="text-muted-foreground">
              Pick another session to compare tokens, outcome signals, review quality and injected context
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

          {compareResult && <SessionCompare result={compareResult} />}
        </Card>
      )}
    </div>
  );
}
