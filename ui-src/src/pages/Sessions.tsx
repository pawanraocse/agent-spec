import { useEffect, useState, useMemo } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { apiGet } from "../api/client";
import { Metric } from "../components/Metric";
import {
  Search,
  Sliders,
  Sparkles,
  GitCompare,
  ArrowRight,
  TrendingDown,
  Layers,
  CheckCircle,
  AlertTriangle,
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

export function Sessions() {
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<{ sessions: SessionRow[] }>("/api/sessions")
      .then((res) => setSessions(res.sessions || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    return sessions.filter((s) => s.session_id.toLowerCase().includes(search.toLowerCase()));
  }, [sessions, search]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Sessions</h1>
          <p className="text-xs text-slate-400">
            Explorer, context threshold audits, and session efficiency
          </p>
        </div>
        <div className="relative w-64">
          <Search size={14} className="absolute left-3 top-2.5 text-slate-500" />
          <input
            className="w-full rounded-lg border border-slate-800 bg-slate-900 py-1.5 pl-9 pr-3 text-xs text-slate-200 placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
            placeholder="Search session IDs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="divide-y divide-slate-800/80 rounded-xl border border-slate-800 bg-slate-900/30 text-sm">
        {loading ? (
          <div className="p-6 text-center text-xs text-slate-500">Loading sessions...</div>
        ) : filtered.length === 0 ? (
          <div className="p-6 text-center text-xs text-slate-500">No sessions match search.</div>
        ) : (
          filtered.map((s) => (
            <div key={s.session_id} className="flex items-center justify-between p-3.5 hover:bg-slate-900/50 transition-colors">
              <div className="flex items-center gap-3">
                <span className="rounded bg-indigo-500/10 px-2 py-0.5 text-xs font-mono font-medium text-indigo-300">
                  {s.session_id.slice(0, 8)}...
                </span>
                <Link
                  to={`/sessions/${encodeURIComponent(s.session_id)}`}
                  className="font-mono text-xs text-sky-400 hover:underline"
                >
                  {s.session_id}
                </Link>
              </div>
              <div className="flex items-center gap-4 text-xs text-slate-400 tabular-nums">
                <span>{s.runs} turns</span>
                <span>·</span>
                <span>{(s.tokens || 0).toLocaleString()} tokens</span>
                <Link
                  to={`/sessions/${encodeURIComponent(s.session_id)}`}
                  className="text-slate-400 hover:text-white"
                >
                  Inspect →
                </Link>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

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
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Link to="/sessions" className="text-xs text-slate-500 hover:text-slate-300">
              ← Sessions
            </Link>
            <span className="text-slate-600">/</span>
            <span className="font-mono text-xs font-semibold text-slate-300">{id}</span>
          </div>
          <h1 className="mt-1 text-xl font-semibold text-slate-100">Session Analysis</h1>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 transition-colors"
            onClick={() => navigate("/console")}
          >
            <Play size={13} />
            Continue chat in Console
          </button>
        </div>
      </div>

      {/* Context Gauge (§4.2 / CP-024) */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 space-y-2">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <span className="font-medium text-slate-300">Context Gauge</span>
            <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
              S-004 Nudge Rule
            </span>
          </div>
          <span className="font-mono tabular-nums text-slate-300">
            {peakContext.toLocaleString()} / {contextThreshold.toLocaleString()} tokens ({contextPct}%)
          </span>
        </div>
        <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-slate-800">
          <div
            className={`h-full transition-all ${
              contextPct > 90 ? "bg-amber-400" : "bg-indigo-500"
            }`}
            style={{ width: `${contextPct}%` }}
          />
          {/* Nudge marker at 100% */}
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-rose-500"
            style={{ left: "100%" }}
            title="S-004 Nudge threshold (80k)"
          />
        </div>
        {contextPct >= 100 ? (
          <p className="text-[11px] text-amber-400">
            Session passed the 80k threshold; S-004 compact nudge was triggered.
          </p>
        ) : (
          <p className="text-[11px] text-slate-500">
            Healthy context window; needle-in-haystack degradation avoided.
          </p>
        )}
      </div>

      {/* Navigation Tabs */}
      <div className="flex gap-2 border-b border-slate-800 text-xs">
        <button
          type="button"
          className={`pb-2 font-medium border-b-2 transition-colors ${
            tab === "timeline"
              ? "border-indigo-500 text-indigo-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
          onClick={() => setTab("timeline")}
        >
          Timeline & Turns
        </button>
        <button
          type="button"
          className={`pb-2 font-medium border-b-2 transition-colors ${
            tab === "savings"
              ? "border-indigo-500 text-indigo-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
          onClick={() => setTab("savings")}
        >
          Savings Calculator (D-010)
        </button>
        <button
          type="button"
          className={`pb-2 font-medium border-b-2 transition-colors ${
            tab === "compare"
              ? "border-indigo-500 text-indigo-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
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
            <div
              key={req.request_id || i}
              className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 space-y-2 text-xs"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-slate-400">Turn #{i + 1}</span>
                <span className="font-mono text-slate-500">
                  {((req.tokens_input || 0) + (req.tokens_output || 0)).toLocaleString()} tokens
                </span>
              </div>
              <p className="font-sans text-slate-200 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800">
                {req.prompt || "(no prompt recorded)"}
              </p>
              {req.steps && req.steps.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {req.steps.map((st, j) => (
                    <span
                      key={j}
                      className="rounded bg-slate-800 px-2 py-0.5 text-[11px] font-mono text-slate-300"
                    >
                      {st.name}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Tab: Savings Calculator (CP-024 / D-010 parity) */}
      {tab === "savings" && (
        <div className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/40 p-5 text-xs">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-100">Context Savings Calculator</h3>
              <p className="text-slate-400">
                Naive whole-file dumps vs Graphify symbol AST queries with configurable weights
              </p>
            </div>
            <span className="rounded bg-amber-500/10 px-2 py-0.5 text-[10px] uppercase font-bold text-amber-300">
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
            <div className="flex items-center justify-between text-slate-400">
              <span>Read weight sensitivity: {readWeight.toFixed(1)}x</span>
              <button
                type="button"
                className="text-indigo-400 hover:underline flex items-center gap-1"
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
              className="w-full accent-indigo-500 cursor-pointer"
            />
          </div>
        </div>
      )}


      {/* Tab: A/B Compare */}
      {tab === "compare" && (
        <div className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/40 p-5 text-xs">
          <div>
            <h3 className="text-sm font-semibold text-slate-100">A/B Session Comparison</h3>
            <p className="text-slate-400">
              Pick another session to calculate deltas in tokens, turns, and duration
            </p>
          </div>

          <div className="flex gap-2">
            <select
              className="flex-1 rounded-lg border border-slate-800 bg-slate-900 p-2 text-xs text-slate-200"
              value={compareTarget}
              onChange={(e) => setCompareTarget(e.target.value)}
            >
              <option value="">Select a session to compare against...</option>
              {allSessions
                .filter((s) => s.session_id !== id)
                .map((s) => (
                  <option key={s.session_id} value={s.session_id}>
                    {s.session_id} ({s.runs} turns, {s.tokens.toLocaleString()} tok)
                  </option>
                ))}
            </select>
            <button
              type="button"
              className="rounded-lg bg-indigo-600 px-4 py-2 font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
              disabled={!compareTarget}
              onClick={runCompare}
            >
              Compare
            </button>
          </div>

          {compareResult && (
            <div className="grid gap-3 sm:grid-cols-3 pt-3 border-t border-slate-800">
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
        </div>
      )}
    </div>
  );
}
