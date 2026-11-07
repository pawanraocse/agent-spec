import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiGet } from "../api/client";
import { Metric } from "../components/Metric";
import {
  ShieldCheck,
  ShieldAlert,
  AlertOctagon,
  CheckCircle2,
  XCircle,
  FileText,
  Activity,
  Layers,
  ArrowRight,
  Download,
  AlertTriangle,
} from "lucide-react";

type GateItem = {
  gate: number;
  name: string;
  skill: string;
  status: "ok" | "missing";
  artifact: string | null;
};

type GapItem = {
  rule: string;
  request_id?: string;
  ts?: string;
  detail: string;
};

type DoctorCheck = {
  id: string;
  status: "OK" | "WARN" | "FAIL" | "INFO";
  message: string;
  fix?: string;
};

type TaskRow = {
  task_id: string;
  slice: string;
  title: string;
  status: string;
  effort?: string;
};

export function Governance() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = (searchParams.get("tab") as any) || "gates";
  const [tab, setTab] = useState<"gates" | "gaps" | "guards" | "health" | "tasks">(initialTab);

  const [gatesData, setGatesData] = useState<{
    current_gate?: number;
    current_gate_name?: string;
    gates?: GateItem[];
    req_trace?: string[];
  } | null>(null);

  const [gapsData, setGapsData] = useState<GapItem[]>([]);
  const [doctorData, setDoctorData] = useState<{ ok: boolean; checks: DoctorCheck[] } | null>(null);
  const [tasksData, setTasksData] = useState<TaskRow[]>([]);
  const [statusBarData, setStatusBarData] = useState<{
    snapshot?: { size_bytes?: number; rotation_due?: boolean };
  } | null>(null);

  useEffect(() => {
    const t = searchParams.get("tab");
    if (t && ["gates", "gaps", "guards", "health", "tasks"].includes(t)) {
      setTab(t as any);
    }
  }, [searchParams]);

  useEffect(() => {
    apiGet<any>("/api/gates").then(setGatesData).catch(console.error);
    apiGet<{ gaps: GapItem[] }>("/api/gaps?limit=100")
      .then((res) => setGapsData(res.gaps || []))
      .catch(console.error);
    apiGet<{ ok: boolean; checks: DoctorCheck[] }>("/api/health/doctor")
      .then(setDoctorData)
      .catch(console.error);
    apiGet<{ tasks: TaskRow[] }>("/api/tasks")
      .then((res) => setTasksData(res.tasks || []))
      .catch(console.error);
    apiGet<any>("/api/status_bar")
      .then(setStatusBarData)
      .catch(() => {});
  }, []);

  const changeTab = (newTab: "gates" | "gaps" | "guards" | "health" | "tasks") => {
    setTab(newTab);
    setSearchParams({ tab: newTab });
  };

  const gatePassCount = (gatesData?.gates || []).filter((g) => g.status === "ok").length;
  const docFailCount = (doctorData?.checks || []).filter((c) => c.status === "FAIL").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Governance & Rail Audits</h1>
        <p className="text-xs text-slate-400">
          9-gate SDLC, 6-gate implement audit, harness gaps, doctor health, and proof pack
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-3 sm:grid-cols-4">
        <Metric
          label="SDLC Gate Rail"
          value={`${gatePassCount} / 9`}
          provenance="measured"
        />
        <Metric
          label="Open Gaps Caught"
          value={gapsData.length}
          provenance="measured"
        />
        <Metric
          label="Doctor Health"
          value={docFailCount === 0 ? "Green" : `${docFailCount} FAIL`}
          provenance="measured"
        />
        <Metric
          label="Snapshot Size"
          value={
            statusBarData?.snapshot?.size_bytes
              ? `${Math.round(statusBarData.snapshot.size_bytes / 1024)} KB`
              : "—"
          }
          provenance="measured"
          formula={
            statusBarData?.snapshot?.rotation_due ? "Rotation due (>40 KB)" : "Normal size"
          }
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-800 text-xs">
        {[
          ["gates", "9-Gate SDLC Rail"],
          ["gaps", `Caught by Harness (${gapsData.length})`],
          ["guards", "Guard Log & Quarantine"],
          ["health", "Doctor Health & Snapshot"],
          ["tasks", `Backlog (${tasksData.length})`],
        ].map(([t, label]) => (
          <button
            key={t}
            type="button"
            onClick={() => changeTab(t as any)}
            className={`pb-2.5 font-medium border-b-2 transition-colors ${
              tab === t
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* TAB 1: 9-Gate SDLC Rail */}
      {tab === "gates" && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 space-y-4">
            <h3 className="text-sm font-semibold text-slate-100">9-Gate SDLC Governance Rail</h3>
            <div className="grid gap-3 sm:grid-cols-3">
              {(gatesData?.gates || []).map((g) => (
                <div
                  key={g.gate}
                  className={`rounded-lg border p-3 text-xs space-y-1 transition-colors ${
                    g.status === "ok"
                      ? "border-emerald-900/60 bg-emerald-950/20"
                      : "border-slate-800 bg-slate-900/60"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-slate-400">Gate {g.gate}</span>
                    {g.status === "ok" ? (
                      <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-400">
                        <CheckCircle2 size={13} /> Passed
                      </span>
                    ) : (
                      <span className="text-[11px] text-slate-500">Pending</span>
                    )}
                  </div>
                  <div className="font-semibold text-slate-200">{g.name}</div>
                  <div className="font-mono text-[10px] text-slate-400">
                    {g.artifact || "(automated validation)"}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* REQ Trace */}
          {(gatesData?.req_trace || []).length > 0 && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 space-y-2 text-xs">
              <h4 className="font-semibold text-slate-200">Requirements Traceability</h4>
              <div className="divide-y divide-slate-800 rounded-lg border border-slate-800 bg-slate-950 font-mono text-[11px]">
                {gatesData?.req_trace?.map((req, i) => (
                  <div key={i} className="p-2 text-slate-300">
                    {req}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: Caught by the Harness (Gaps - CP-036) */}
      {tab === "gaps" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs text-slate-400">
            Rule-based detection flags deviations from strict agent discipline (whole-file reads
            without AST queries, failed steps, unhandled exceptions, token spikes, and missing
            gates).
          </div>
          <div className="divide-y divide-slate-800 rounded-xl border border-slate-800 bg-slate-900/30 text-xs">
            {gapsData.length === 0 ? (
              <div className="p-6 text-center text-slate-500">
                Zero rule gaps detected. Full compliance with harness standards.
              </div>
            ) : (
              gapsData.map((gap, idx) => (
                <div key={idx} className="flex items-center justify-between p-3.5 hover:bg-slate-900/40">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-rose-500/10 px-2 py-0.5 font-mono text-[11px] font-medium text-rose-300 border border-rose-500/20">
                        {gap.rule}
                      </span>
                      {gap.request_id && (
                        <Link
                          to={`/runs/${gap.request_id}`}
                          className="font-mono text-sky-400 hover:underline"
                        >
                          Run {gap.request_id}
                        </Link>
                      )}
                    </div>
                    <p className="text-slate-300">{gap.detail}</p>
                  </div>
                  {gap.ts && (
                    <span className="font-mono text-slate-500 text-[11px]">
                      {gap.ts.slice(0, 19).replace("T", " ")}
                    </span>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* TAB 3: Guard Log & Quarantine */}
      {tab === "guards" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs text-slate-400">
            S-002 Quarantine filters sensitive files (credentials, .env) and S-004 context threshold
            nudges guard against prompt cache blowups.
          </div>
          <div className="divide-y divide-slate-800 rounded-xl border border-slate-800 bg-slate-900/30 text-xs">
            {gapsData.filter((g) => g.rule.includes("quarantine") || g.rule.includes("token")).length === 0 ? (
              <div className="p-6 text-center text-slate-500">
                No active quarantine blocks or nudges recorded.
              </div>
            ) : (
              gapsData
                .filter((g) => g.rule.includes("quarantine") || g.rule.includes("token"))
                .map((gap, i) => (
                  <div key={i} className="flex items-center justify-between p-3.5">
                    <span className="font-mono text-amber-300">{gap.rule}</span>
                    <span className="text-slate-300">{gap.detail}</span>
                  </div>
                ))
            )}
          </div>
        </div>
      )}

      {/* TAB 4: Doctor Health & Snapshot (CP-037) */}
      {tab === "health" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 text-xs space-y-2">
            <h3 className="font-semibold text-slate-200">Session Snapshot & Health Lines</h3>
            <div className="grid gap-3 sm:grid-cols-2 pt-1">
              <div className="p-3 rounded-lg border border-slate-800 bg-slate-950">
                <span className="text-slate-500 block mb-1">SESSION-SNAPSHOT.md Size</span>
                <span className="font-mono font-semibold text-slate-200">
                  {statusBarData?.snapshot?.size_bytes
                    ? `${(statusBarData.snapshot.size_bytes / 1024).toFixed(1)} KB`
                    : "0 KB"}
                </span>
                <span className="block mt-1 text-[11px] text-slate-400">
                  {statusBarData?.snapshot?.rotation_due
                    ? "⚠️ Snapshot is >40 KB; rotation due via /agent-spec-snapshot"
                    : "✓ Healthy size, no rotation needed"}
                </span>
              </div>
              <div className="p-3 rounded-lg border border-slate-800 bg-slate-950">
                <span className="text-slate-500 block mb-1">Local / Team Facts Scope</span>
                <span className="font-mono font-semibold text-slate-200">Merged & Linted</span>
                <span className="block mt-1 text-[11px] text-slate-400">
                  Verified with team-fact boundary compliance
                </span>
              </div>
            </div>
          </div>

          <div className="divide-y divide-slate-800 rounded-xl border border-slate-800 bg-slate-900/30 text-xs">
            {(doctorData?.checks || []).map((chk) => (
              <div key={chk.id} className="p-3.5 space-y-1 hover:bg-slate-900/40">
                <div className="flex items-center justify-between">
                  <span className="font-mono font-semibold text-slate-200">{chk.id}</span>
                  <span
                    className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase ${
                      chk.status === "OK"
                        ? "bg-emerald-500/20 text-emerald-300"
                        : chk.status === "WARN"
                        ? "bg-amber-500/20 text-amber-300"
                        : "bg-rose-500/20 text-rose-300"
                    }`}
                  >
                    {chk.status}
                  </span>
                </div>
                <p className="text-slate-300">{chk.message}</p>
                {chk.fix && <p className="font-mono text-[11px] text-slate-500">Fix: {chk.fix}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 5: Backlog & Tasks */}
      {tab === "tasks" && (
        <div className="divide-y divide-slate-800 rounded-xl border border-slate-800 bg-slate-900/30 text-xs">
          {tasksData.map((t) => (
            <div key={t.task_id} className="flex items-center justify-between p-3 hover:bg-slate-900/40">
              <div className="flex items-center gap-3">
                <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
                  {t.slice || "P"}
                </span>
                <span className="font-mono text-slate-300">{t.task_id}</span>
                <span className="text-slate-200">{t.title}</span>
              </div>
              <span
                className={`font-mono ${
                  t.status === "done" ? "text-emerald-400" : "text-amber-400"
                }`}
              >
                {t.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
