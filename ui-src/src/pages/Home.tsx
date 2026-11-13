import { Num } from "../components/Num";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { Metric } from "../components/Metric";
import {
  Compass,
  FileCode,
  GitBranch,
  ShieldAlert,
  Brain,
  Cpu,
  ChevronRight,
  X,
  Play,
} from "lucide-react";

type HomeData = {
  seeded?: boolean;
  demo_seed_count?: number;
  today?: { runs?: number; tokens?: number };
  last_7d?: { runs?: number; tokens?: number };
  graph?: { files?: number; edges?: number; symbols?: number; age_s?: number };
  saved_vs_baseline?: {
    estimate?: boolean;
    saved_tokens?: number;
    saved_usd?: number;
    naive_tokens?: number;
    graph_tokens?: number;
  };
  learning?: { day: string; experiences: number; successes: number; avg_tokens: number }[];
};

type RunItem = {
  request_id: string;
  status: string;
  tokens_total: number;
  workflow_id?: string;
  started?: string;
};

type SessionItem = {
  session_id: string;
  workspace?: string;
  grade?: string;
  turns?: number;
};

export function Home() {
  const navigate = useNavigate();
  const [home, setHome] = useState<HomeData | null>(null);
  const [gaps, setGaps] = useState<{ gaps: { rule: string; request_id: string }[] } | null>(null);
  const [recentRuns, setRecentRuns] = useState<RunItem[]>([]);
  const [factsCount, setFactsCount] = useState<number>(0);
  const [gatesCount, setGatesCount] = useState<number>(9);
  const [tourStep, setTourStep] = useState<number | null>(null);

  useEffect(() => {
    apiGet<HomeData>("/api/home").then(setHome).catch(console.error);
    apiGet<{ gaps: { rule: string; request_id: string }[] }>("/api/gaps?limit=100")
      .then(setGaps)
      .catch(console.error);
    apiGet<{ runs: RunItem[] }>("/api/runs?limit=5")
      .then((d) => setRecentRuns(d.runs || []))
      .catch(() => {});
    apiGet<{ facts: unknown[] }>("/api/memory")
      .then((d) => setFactsCount(d.facts?.length || 0))
      .catch(() => {});
    apiGet<{ gates: unknown[] }>("/api/gates")
      .then((d) => setGatesCount(d.gates?.length || 9))
      .catch(() => {});
  }, []);

  const prov = home?.seeded ? ("demo_seed" as const) : ("measured" as const);

  // Sparkline data extracted from 14-day learning / experiences
  const learningSpark = (home?.learning || []).map((l) => l.experiences);
  const tokensSpark = (home?.learning || []).map((l) => l.avg_tokens);
  const successSpark = (home?.learning || []).map((l) => l.successes);

  // Guided tour 5-step definitions (§4.1 / CP-040)
  const TOUR_STEPS = [
    {
      title: "1. Session Digest",
      badge: "Guide",
      subtitle: "What the agent knows at start",
      desc: "Agent-Spec automatically injects project guidelines, active constraints, and graph status. The digest is kept compact so the agent starts with exact context without spending the token budget; its live size is under Project › Health.",
      actionText: "Inspect Knowledge & Memory",
      action: () => navigate("/knowledge"),
    },
    {
      title: "2. Graphify Knowledge Graph",
      badge: "Guide",
      subtitle: "Blast radius & symbol dependencies",
      desc: "Instead of naive whole-file dumping, Graphify queries only symbol declarations, callers, and import dependencies. Blast radius traces all transitive dependents in sub-second time.",
      actionText: "View Interactive Graph",
      action: () => navigate("/knowledge"),
    },
    {
      title: "3. Input Discipline & Guards",
      badge: "Guide",
      subtitle: "Pre-tool-use quarantine & context threshold nudges",
      desc: "The preToolUse hook protects against unbounded whole-file reads and sensitive data leaks. When a session exceeds 80k tokens, an S-004 nudge prompts compaction to maintain needle-in-haystack reasoning accuracy.",
      actionText: "Review Guard Log in Governance",
      action: () => navigate("/governance?tab=guards"),
    },
    {
      title: "4. SDLC Rails & 6-Gate Pipeline",
      badge: "Guide",
      subtitle: "Deterministic governance & REQ traceability",
      desc: "Changes pass through the 6-gate implement pipeline (Declaration, Failing Test, Minimal Diff, Verification) alongside the 9-gate SDLC rail with immutable receipts and requirements traces.",
      actionText: "Explore SDLC Rails",
      action: () => navigate("/governance?tab=sdlc"),
    },
    {
      title: "5. Bounded Memory & Agent Console",
      badge: "Guide",
      subtitle: "Self-learning flywheel & live execution",
      desc: "Facts migrate from candidates to trusted rules. Drive your agent from the Agent Console in read-only Ask mode or confirmed Agent mode with live streaming.",
      actionText: "Launch Agent Console",
      action: () => navigate("/console"),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Control Plane v2</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time observability, governance rails, and agent orchestration
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 shadow-sm transition-colors"
            onClick={() => setTourStep(0)}
          >
            <Compass size={14} />
            Guided demo tour
          </button>
          <button
            type="button"
            className="rounded-md bg-slate-800 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700"
            onClick={() => apiPost("/api/seed", { action: "seed" }).then(() => window.location.reload())}
          >
            Load demo seed
          </button>
          {home?.seeded ? (
            <button
              type="button"
              className="rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
              onClick={() => apiPost("/api/seed", { action: "remove" }).then(() => window.location.reload())}
            >
              Remove demo data
            </button>
          ) : null}
        </div>
      </header>

      {/* 4 KPIs with 7-day sparklines (§4.1 / CP-007) */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Metric
          label="Runs today"
          value={home?.today?.runs ?? "0"}
          provenance={prov}
          sparkline={learningSpark}
        />
        <Metric
          label="Tokens today"
          value={home?.today?.tokens ? home.today.tokens.toLocaleString() : "0"}
          provenance={prov}
          sparkline={tokensSpark}
        />
        <Metric
          label="Tokens kept out of context (7d)"
          value={
            home?.saved_vs_baseline?.saved_tokens
              ? home.saved_vs_baseline.saved_tokens.toLocaleString()
              : "0"
          }
          provenance="estimated"
          formula="naive whole-file reads minus graphified AST context"
          sparkline={tokensSpark}
        />
        <Metric
          label="Memory facts active"
          value={factsCount}
          provenance={prov}
          sparkline={successSpark}
        />
      </div>

      {/* "Caught by the harness" banner (§4.1 / CP-036) */}
      <div className="flex items-center justify-between rounded-lg border border-slate-800/80 bg-slate-900/40 px-4 py-2.5 text-xs text-slate-300">
        <div className="flex items-center gap-2">
          <ShieldAlert size={15} className="text-amber-400" />
          <span>
            Caught by the harness:{" "}
            <strong className="text-slate-100 font-semibold"><Num p="measured">{gaps?.gaps?.length ?? 0}</Num></strong>{" "}
            potential rule gap(s) or nudges detected.
          </span>
        </div>
        <Link
          to="/governance?tab=gaps"
          className="font-medium text-sky-400 hover:text-sky-300 flex items-center gap-1"
        >
          View Gaps audit <ChevronRight size={13} />
        </Link>
      </div>

      {/* "How it works" 5-Tile Strip (§4.1) */}
      <div>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
          How it works
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Link
            to="/knowledge"
            className="group rounded-xl border border-slate-800 bg-slate-900/50 p-3.5 transition-all hover:border-slate-700 hover:bg-slate-900"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 group-hover:text-slate-200" data-figure-exempt>
                1. Digest
              </span>
              <FileCode size={14} className="text-slate-500" />
            </div>
            <div className="mt-2 text-lg font-semibold text-slate-200">sessionStart</div>
            <p className="mt-1 text-[11px] text-slate-500">injected start context</p>
          </Link>

          <Link
            to="/knowledge"
            className="group rounded-xl border border-slate-800 bg-slate-900/50 p-3.5 transition-all hover:border-slate-700 hover:bg-slate-900"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 group-hover:text-slate-200" data-figure-exempt>
                2. Graphify
              </span>
              <GitBranch size={14} className="text-slate-500" />
            </div>
            <div className="mt-2 text-lg font-semibold text-slate-200">
              <Num p="measured">{home?.graph?.files ?? "—"}</Num> files
            </div>
            <p className="mt-1 text-[11px] text-slate-500">AST symbols & blast radius</p>
          </Link>

          <Link
            to="/governance?tab=guards"
            className="group rounded-xl border border-slate-800 bg-slate-900/50 p-3.5 transition-all hover:border-slate-700 hover:bg-slate-900"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 group-hover:text-slate-200" data-figure-exempt>
                3. Guard
              </span>
              <ShieldAlert size={14} className="text-slate-500" />
            </div>
            <div className="mt-2 font-mono text-lg font-semibold text-slate-200">S-002 / S-004</div>
            <p className="mt-1 text-[11px] text-slate-500">preToolUse & context nudges</p>
          </Link>

          <Link
            to="/knowledge"
            className="group rounded-xl border border-slate-800 bg-slate-900/50 p-3.5 transition-all hover:border-slate-700 hover:bg-slate-900"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 group-hover:text-slate-200" data-figure-exempt>
                4. Memory
              </span>
              <Brain size={14} className="text-slate-500" />
            </div>
            <div className="mt-2 text-lg font-semibold text-slate-200"><Num p="measured">{factsCount}</Num> facts</div>
            <p className="mt-1 text-[11px] text-slate-500">bounded memory flywheel</p>
          </Link>

          <Link
            to="/runs"
            className="group rounded-xl border border-slate-800 bg-slate-900/50 p-3.5 transition-all hover:border-slate-700 hover:bg-slate-900"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 group-hover:text-slate-200" data-figure-exempt>
                5. Subagents
              </span>
              <Cpu size={14} className="text-slate-500" />
            </div>
            <div className="mt-2 font-mono text-lg font-semibold text-slate-200">agent-spec-wf-*</div>
            <p className="mt-1 text-[11px] text-slate-500">isolated task execution</p>
          </Link>
        </div>
      </div>

      {/* Recent Activity: last 5 runs (§4.1) */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Recent activity
          </h2>
          <Link to="/runs" className="text-xs text-sky-400 hover:underline">
            View all runs
          </Link>
        </div>
        <div className="divide-y divide-slate-800/80 rounded-lg border border-slate-800 bg-slate-900/30 text-xs">
          {recentRuns.length ? (
            recentRuns.map((r) => (
              <div key={r.request_id} className="flex items-center justify-between p-3">
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-block h-2 w-2 rounded-full ${
                      r.status === "completed" || r.status === "success"
                        ? "bg-emerald-400"
                        : "bg-rose-400"
                    }`}
                  />
                  <Link to={`/runs/${r.request_id}`} className="font-mono text-sky-400 hover:underline">
                    {r.request_id}
                  </Link>
                  <span className="text-slate-400">
                    {r.workflow_id ? `· ${r.workflow_id}` : ""}
                  </span>
                </div>
                <div className="text-slate-500 tabular-nums">
                  {r.tokens_total ? <><Num p={prov}>{r.tokens_total.toLocaleString()}</Num> tokens</> : null}
                  {r.started ? <> · <time dateTime={r.started}>{r.started.slice(11, 16)} UTC</time></> : null}
                </div>
              </div>
            ))
          ) : (
            <div className="p-4 text-center text-slate-500">No recent runs recorded.</div>
          )}
        </div>
      </div>

      {/* Guided Tour Modal (§4.1 / CP-040) */}
      {tourStep !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <span className="rounded bg-indigo-500/20 px-2 py-0.5 text-xs font-medium text-indigo-300">
                Demo Tour · Step {tourStep + 1} of {TOUR_STEPS.length}
              </span>
              <button
                type="button"
                className="text-slate-400 hover:text-white"
                onClick={() => setTourStep(null)}
              >
                <X size={18} />
              </button>
            </div>

            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-semibold text-slate-100">
                  {TOUR_STEPS[tourStep].title}
                </h3>
                <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] uppercase font-bold text-amber-300">
                  {TOUR_STEPS[tourStep].badge}
                </span>
              </div>
              <p className="text-xs text-indigo-300 font-medium mt-0.5">
                {TOUR_STEPS[tourStep].subtitle}
              </p>
            </div>

            <p className="text-sm leading-relaxed text-slate-300">
              {TOUR_STEPS[tourStep].desc}
            </p>

            <div className="flex items-center justify-between pt-2 border-t border-slate-800">
              <button
                type="button"
                className="text-xs text-slate-400 hover:text-slate-200"
                onClick={() => {
                  TOUR_STEPS[tourStep].action();
                  setTourStep(null);
                }}
              >
                {TOUR_STEPS[tourStep].actionText} →
              </button>
              <div className="flex gap-2">
                {tourStep > 0 && (
                  <button
                    type="button"
                    className="rounded bg-slate-800 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700"
                    onClick={() => setTourStep((s) => (s !== null ? s - 1 : 0))}
                  >
                    Previous
                  </button>
                )}
                {tourStep < TOUR_STEPS.length - 1 ? (
                  <button
                    type="button"
                    className="rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
                    onClick={() => setTourStep((s) => (s !== null ? s + 1 : 0))}
                  >
                    Next step
                  </button>
                ) : (
                  <button
                    type="button"
                    className="rounded bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-500"
                    onClick={() => {
                      TOUR_STEPS[tourStep].action();
                      setTourStep(null);
                    }}
                  >
                    Finish tour
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
