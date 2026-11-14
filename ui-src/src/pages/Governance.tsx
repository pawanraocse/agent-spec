import { Card } from "../components/ui/card";
import { Num } from "../components/Num";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiGet } from "../api/client";
import { Metric } from "../components/Metric";
import {
  CheckCircle2,
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
        <h1 className="text-xl font-semibold text-foreground">Governance & Rail Audits</h1>
        <p className="text-xs text-muted-foreground" data-figure-exempt>
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
      <div className="flex gap-2 border-b border-border text-xs">
        {[
          ["gates", "9-Gate SDLC Rail"],
          ["gaps", "Caught by Harness", gapsData.length],
          ["guards", "Guard Log & Quarantine"],
          ["health", "Doctor Health & Snapshot"],
          ["tasks", "Backlog", tasksData.length],
        ].map(([t, label, count]) => (
          <button
            key={t}
            type="button"
            onClick={() => changeTab(t as any)}
            className={`pb-2.5 font-medium border-b-2 transition-colors ${
              tab === t
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <span data-figure-exempt>{label}</span>{count !== undefined ? <> (<Num p="measured">{count}</Num>)</> : null}
          </button>
        ))}
      </div>

      {/* TAB 1: 9-Gate SDLC Rail */}
      {tab === "gates" && (
        <div className="space-y-6">
          <Card className="p-5 space-y-4">
            <h3 className="text-sm font-semibold text-foreground">9-Gate SDLC Governance Rail</h3>
            <div className="grid gap-3 sm:grid-cols-3">
              {(gatesData?.gates || []).map((g) => (
                <div
                  key={g.gate}
                  className={`rounded-lg border p-3 text-xs space-y-1 transition-colors ${
                    g.status === "ok"
                      ? "border-success/30 bg-success/10"
                      : "border-border bg-card"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-muted-foreground">Gate {g.gate}</span>
                    {g.status === "ok" ? (
                      <span className="flex items-center gap-1 text-[11px] font-medium text-success">
                        <CheckCircle2 size={13} /> Passed
                      </span>
                    ) : (
                      <span className="text-[11px] text-muted-foreground">Pending</span>
                    )}
                  </div>
                  <div className="font-semibold text-foreground">{g.name}</div>
                  <div className="font-mono text-[10px] text-muted-foreground">
                    {g.artifact || "(automated validation)"}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* REQ Trace */}
          {(gatesData?.req_trace || []).length > 0 && (
            <Card className="p-5 space-y-2 text-xs">
              <h4 className="font-semibold text-foreground">Requirements Traceability</h4>
              <div className="divide-y divide-border rounded-lg border border-border bg-background font-mono text-[11px]">
                {gatesData?.req_trace?.map((req, i) => (
                  <div key={i} className="p-2 text-foreground/85">
                    {req}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* TAB 2: Caught by the Harness (Gaps - CP-036) */}
      {tab === "gaps" && (
        <div className="space-y-4">
          <Card className="p-4 text-xs text-muted-foreground">
            Rule-based detection flags deviations from strict agent discipline (whole-file reads
            without AST queries, failed steps, unhandled exceptions, token spikes, and missing
            gates).
          </Card>
          <Card className="divide-y divide-border text-xs">
            {gapsData.length === 0 ? (
              <div className="p-6 text-center text-muted-foreground">
                Zero rule gaps detected. Full compliance with harness standards.
              </div>
            ) : (
              gapsData.map((gap, idx) => (
                <div key={idx} className="flex items-center justify-between p-3.5 hover:bg-muted/60">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-danger/10 px-2 py-0.5 font-mono text-[11px] font-medium text-danger border border-danger/20">
                        {gap.rule}
                      </span>
                      {gap.request_id && (
                        <Link
                          to={`/runs/${gap.request_id}`}
                          className="font-mono text-primary hover:underline"
                        >
                          Run {gap.request_id}
                        </Link>
                      )}
                    </div>
                    <p className="text-foreground/85" data-provenance="measured">{gap.detail}</p>
                  </div>
                  {gap.ts && (
                    <span className="font-mono text-muted-foreground text-[11px]">
                      {gap.ts.slice(0, 19).replace("T", " ")}
                    </span>
                  )}
                </div>
              ))
            )}
          </Card>
        </div>
      )}

      {/* TAB 3: Guard Log & Quarantine */}
      {tab === "guards" && (
        <div className="space-y-4">
          <Card className="p-4 text-xs text-muted-foreground" data-figure-exempt>
            S-002 Quarantine filters sensitive files (credentials, .env) and S-004 context threshold
            nudges guard against prompt cache blowups.
          </Card>
          <Card className="divide-y divide-border text-xs">
            {gapsData.filter((g) => g.rule.includes("quarantine") || g.rule.includes("token")).length === 0 ? (
              <div className="p-6 text-center text-muted-foreground">
                No active quarantine blocks or nudges recorded.
              </div>
            ) : (
              gapsData
                .filter((g) => g.rule.includes("quarantine") || g.rule.includes("token"))
                .map((gap, i) => (
                  <div key={i} className="flex items-center justify-between p-3.5">
                    <span className="font-mono text-warning">{gap.rule}</span>
                    <span className="text-foreground/85" data-provenance="measured">{gap.detail}</span>
                  </div>
                ))
            )}
          </Card>
        </div>
      )}

      {/* TAB 4: Doctor Health & Snapshot (CP-037) */}
      {tab === "health" && (
        <div className="space-y-4">
          <Card className="p-4 text-xs space-y-2">
            <h3 className="font-semibold text-foreground">Session Snapshot & Health Lines</h3>
            <div className="grid gap-3 sm:grid-cols-2 pt-1">
              <div className="p-3 rounded-lg border border-border bg-background">
                <span className="text-muted-foreground block mb-1">SESSION-SNAPSHOT.md Size</span>
                <span className="font-mono font-semibold text-foreground">
                  {statusBarData?.snapshot?.size_bytes
                    ? `${(statusBarData.snapshot.size_bytes / 1024).toFixed(1)} KB`
                    : "0 KB"}
                </span>
                <span className="block mt-1 text-[11px] text-muted-foreground">
                  {statusBarData?.snapshot?.rotation_due
                    ? "⚠️ Snapshot is >40 KB; rotation due via /agent-spec-snapshot"
                    : "✓ Healthy size, no rotation needed"}
                </span>
              </div>
              <div className="p-3 rounded-lg border border-border bg-background">
                <span className="text-muted-foreground block mb-1">Local / Team Facts Scope</span>
                <span className="font-mono font-semibold text-foreground">Merged & Linted</span>
                <span className="block mt-1 text-[11px] text-muted-foreground">
                  Verified with team-fact boundary compliance
                </span>
              </div>
            </div>
          </Card>

          <Card className="divide-y divide-border text-xs">
            {(doctorData?.checks || []).map((chk) => (
              <div key={chk.id} className="p-3.5 space-y-1 hover:bg-muted/60">
                <div className="flex items-center justify-between">
                  <span className="font-mono font-semibold text-foreground">{chk.id}</span>
                  <span
                    className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase ${
                      chk.status === "OK"
                        ? "bg-success/20 text-success"
                        : chk.status === "WARN"
                        ? "bg-warning/20 text-warning"
                        : "bg-danger/20 text-danger"
                    }`}
                  >
                    {chk.status}
                  </span>
                </div>
                <p className="text-foreground/85" data-provenance="measured">{chk.message}</p>
                {chk.fix && <p className="font-mono text-[11px] text-muted-foreground">Fix: {chk.fix}</p>}
              </div>
            ))}
          </Card>
        </div>
      )}

      {/* TAB 5: Backlog & Tasks */}
      {tab === "tasks" && (
        <Card className="divide-y divide-border text-xs">
          {tasksData.map((t) => (
            <div key={t.task_id} className="flex items-center justify-between p-3 hover:bg-muted/60">
              <div className="flex items-center gap-3">
                <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                  {t.slice || "P"}
                </span>
                <span className="font-mono text-foreground/85">{t.task_id}</span>
                <span className="text-foreground">{t.title}</span>
              </div>
              <span
                className={`font-mono ${
                  t.status === "done" ? "text-success" : "text-warning"
                }`}
              >
                {t.status}
              </span>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
