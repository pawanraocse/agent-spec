import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Num, rowProv } from "../components/Num";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";

type RunRow = { request_id: string; status: string; tokens_total: number; workflow_id?: string; source?: string; tokens_estimated?: number };
type Step = {
  step_id: string;
  ordinal: number;
  kind: string;
  name: string;
  status: string;
  duration_ms?: number;
  tokens_input?: number;
  tokens_output?: number;
  tokens_cache_read?: number;
  bytes_in?: number;
};
type Subagent = { agent?: string; model?: string; status: string; latency_ms?: number; error?: string };
type RunDetailPayload = {
  run?: Record<string, unknown>;
  steps?: Step[];
  subagents?: Subagent[];
  waterfall?: { name: string; kind: string; ordinal: number; status: string; duration_ms?: number; tokens?: number }[];
};

const WORKFLOWS = [
  {
    id: "agent-spec-wf-rca",
    label: "RCA",
    placeholder: "PROJ-123",
    hint: "Jira issue key",
    validate: (v: string) => /^[A-Z][A-Z0-9]+-\d+$/.test(v.trim()),
    steps: ["gather context", "parse logs", "root cause", "report"],
  },
  {
    id: "agent-spec-wf-pr-review",
    label: "PR review",
    placeholder: "feature/my-branch",
    hint: "Branch name vs base",
    validate: (v: string) => v.trim().length >= 2,
    steps: ["diff summary", "deep review", "validation"],
  },
  {
    id: "agent-spec-wf-fix-plan",
    label: "Fix plan",
    placeholder: "run id or RCA text",
    hint: "Prior RCA run id or root cause",
    validate: (v: string) => v.trim().length >= 3,
    steps: ["scope fix", "test plan", "approval gate"],
  },
  {
    id: "agent-spec-wf-eval",
    label: "Eval",
    placeholder: "path/to/golden.csv",
    hint: "Golden ticket CSV",
    validate: (v: string) => v.trim().endsWith(".csv") && v.trim().length > 5,
    steps: ["load golden", "score runs", "report"],
  },
  {
    id: "agent-spec-wf-example",
    label: "Example",
    placeholder: "(optional) smoke prompt",
    hint: "Read-only smoke test",
    validate: () => true,
    steps: ["gather", "analyze", "summarize"],
  },
] as const;

function median(nums: number[]): number {
  if (!nums.length) return 0;
  const s = [...nums].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : Math.round((s[mid - 1] + s[mid]) / 2);
}

function WorkflowCards() {
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [dryId, setDryId] = useState<string | null>(null);
  const [launchMsg, setLaunchMsg] = useState<string>("");

  const onDryRun = (id: string) => {
    const wf = WORKFLOWS.find((w) => w.id === id);
    const raw = inputs[id] ?? "";
    if (!wf?.validate(raw)) {
      setLaunchMsg("Fix input validation errors first.");
      return;
    }
    setDryId(id);
    setLaunchMsg("");
  };

  const onLaunch = async (id: string) => {
    const wf = WORKFLOWS.find((w) => w.id === id);
    const raw = inputs[id] ?? "";
    if (!wf?.validate(raw)) {
      setLaunchMsg("Fix input validation errors first.");
      return;
    }
    setLaunchMsg("");
    const res = await apiPost<{ ok?: boolean; job_id?: string; copy_command?: string; error?: string }>(
      `/api/workflows/${id}/start`,
      { input: raw.trim() },
    );
    if (res.ok && res.job_id) {
      setLaunchMsg(`Launched job ${res.job_id}. Open Console for the live stream.`);
      return;
    }
    const cmd = res.copy_command || `/agent-spec-hub-runner ${id} ${raw.trim()}`;
    setLaunchMsg(res.error === "cli_missing" ? `CLI unavailable — copy: ${cmd}` : `Launch blocked: ${cmd}`);
    try {
      await navigator.clipboard.writeText(cmd);
    } catch {
      /* noop */
    }
  };

  return (
    <section className="mb-8 space-y-3">
      <h2 className="text-sm font-medium text-muted-foreground">Launch workflow</h2>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {WORKFLOWS.map((wf) => {
          const raw = inputs[wf.id] ?? "";
          const valid = wf.validate(raw);
          return (
            <Card key={wf.id} className="p-3 text-sm">
              <p className="mb-1 font-medium">{wf.label}</p>
              <p className="mb-2 text-xs text-muted-foreground">{wf.hint}</p>
              <input
                className="mb-2 w-full rounded border border-border bg-background px-2 py-1 text-xs"
                placeholder={wf.placeholder}
                value={raw}
                onChange={(e) => setInputs((m) => ({ ...m, [wf.id]: e.target.value }))}
              />
              {dryId === wf.id && (
                <pre className="mb-2 max-h-24 overflow-auto rounded bg-background p-2 text-[10px] text-muted-foreground">
                  {wf.steps.map((s, i) => `${i + 1}. ${s}`).join("\n")}
                </pre>
              )}
              <div className="flex gap-2">
                <Button
                  type="button"
                  size="sm" variant="subtle"
                  onClick={() => onDryRun(wf.id)}
                  disabled={!valid}
                >
                  Dry-run
                </Button>
                <button
                  type="button"
                  className="rounded bg-primary px-2 py-1 text-xs hover:bg-primary/90 disabled:opacity-40"
                  onClick={() => onLaunch(wf.id)}
                  disabled={!valid}
                >
                  Launch
                </button>
              </div>
              {!valid && raw.length > 0 && <p className="mt-1 text-xs text-warning">Invalid input</p>}
            </Card>
          );
        })}
      </div>
      {launchMsg && <p className="text-xs text-muted-foreground">{launchMsg}</p>}
    </section>
  );
}

export function Runs() {
  const [runs, setRuns] = useState<{ runs: RunRow[] }>();
  useEffect(() => {
    apiGet<{ runs: RunRow[] }>("/api/runs?limit=50").then(setRuns).catch(console.error);
  }, []);
  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Runs & workflows</h1>
      <WorkflowCards />
      <ul className="divide-y divide-border rounded-lg border border-border text-sm">
        {(runs?.runs ?? []).map((r) => (
          <li key={r.request_id} className="flex justify-between px-3 py-2">
            <Link to={`/runs/${r.request_id}`} className="font-mono text-primary">
              {r.request_id}
            </Link>
            <span className="text-muted-foreground">
              {r.status} · <Num p={rowProv(r)}>{r.tokens_total}</Num> tok
              {r.workflow_id ? ` · ${r.workflow_id}` : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function RunDetail() {
  const { id = "" } = useParams();
  const [detail, setDetail] = useState<RunDetailPayload | null>(null);
  const [events, setEvents] = useState<{ events: unknown[] } | null>(null);
  const [tab, setTab] = useState<"inspector" | "subagents">("inspector");
  const [selectedStep, setSelectedStep] = useState<Step | null>(null);

  useEffect(() => {
    apiGet<RunDetailPayload>(`/api/runs/${id}`).then(setDetail).catch(console.error);
    apiGet<{ events: unknown[] }>(`/api/runs/${id}/events`).then(setEvents).catch(() => setEvents({ events: [] }));
  }, [id]);

  useEffect(() => {
    const first = detail?.steps?.[0];
    if (first && !selectedStep) setSelectedStep(first);
  }, [detail, selectedStep]);

  const health = useMemo(() => {
    const agents = detail?.subagents ?? [];
    const byType: Record<string, { total: number; failed: number; latencies: number[] }> = {};
    for (const a of agents) {
      const key = a.agent || "unknown";
      const bucket = byType[key] ?? { total: 0, failed: 0, latencies: [] };
      bucket.total += 1;
      if (a.status === "failed") bucket.failed += 1;
      if (a.latency_ms != null) bucket.latencies.push(a.latency_ms);
      byType[key] = bucket;
    }
    return Object.entries(byType).map(([agent, s]) => ({
      agent,
      failureRate: s.total ? Math.round((100 * s.failed) / s.total) : 0,
      medianLatencyMs: median(s.latencies),
      samples: s.total,
    }));
  }, [detail?.subagents]);

  const waterfall = detail?.waterfall ?? [];
  const stepProv = rowProv(detail?.run as { source?: string; tokens_estimated?: number } | undefined);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Run {id}</h1>
      <div className="rounded-lg border border-border p-3">
        <p className="mb-2 text-xs text-muted-foreground">Step graph (waterfall)</p>
        <ol className="flex flex-wrap gap-2 text-xs">
          {waterfall.map((s) => (
            <li key={`${s.ordinal}-${s.name}`}>
              <button
                type="button"
                className={`rounded border px-2 py-1 ${
                  selectedStep?.name === s.name ? "border-primary bg-primary/10" : "border-border"
                }`}
                onClick={() => {
                  const full = detail?.steps?.find((st) => st.name === s.name && st.ordinal === s.ordinal);
                  if (full) setSelectedStep(full);
                }}
              >
                <span className="font-mono">{s.ordinal}.</span> {s.name}{" "}
                <span className={s.status === "failed" ? "text-danger" : "text-success"}>({s.status})</span>
              </button>
            </li>
          ))}
        </ol>
      </div>
      <div className="rounded-lg border border-border">
        <div className="flex border-b border-border text-xs">
          <button
            type="button"
            className={`px-3 py-2 ${tab === "inspector" ? "border-b border-primary text-primary" : "text-muted-foreground"}`}
            onClick={() => setTab("inspector")}
          >
            Inspector
          </button>
          <button
            type="button"
            className={`px-3 py-2 ${tab === "subagents" ? "border-b border-primary text-primary" : "text-muted-foreground"}`}
            onClick={() => setTab("subagents")}
          >
            Subagent health
          </button>
        </div>
        <div className="p-3 text-xs">
          {tab === "inspector" && selectedStep && (
            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <div>
                <dt className="text-muted-foreground">Step</dt>
                <dd>{selectedStep.name}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Kind</dt>
                <dd>{selectedStep.kind}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Status</dt>
                <dd>{selectedStep.status}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Latency</dt>
                <dd><Num p="measured">{selectedStep.duration_ms ?? "—"}</Num> ms</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Tokens in</dt>
                <dd><Num p={stepProv}>{selectedStep.tokens_input ?? 0}</Num></dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Tokens out</dt>
                <dd><Num p={stepProv}>{selectedStep.tokens_output ?? 0}</Num></dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Bytes in</dt>
                <dd><Num p="measured">{selectedStep.bytes_in ?? 0}</Num></dd>
              </div>
            </dl>
          )}
          {tab === "subagents" && (
            <table className="w-full text-left">
              <thead className="text-muted-foreground">
                <tr>
                  <th className="py-1">Type</th>
                  <th>Failure %</th>
                  <th>Median latency</th>
                  <th>n</th>
                </tr>
              </thead>
              <tbody>
                {health.map((h) => (
                  <tr key={h.agent} className="border-t border-border">
                    <td className="py-1">{h.agent}</td>
                    <td><Num p="measured">{h.failureRate}%</Num></td>
                    <td><Num p="measured">{h.medianLatencyMs}</Num> ms</td>
                    <td><Num p="measured">{h.samples}</Num></td>
                  </tr>
                ))}
                {!health.length && <tr><td colSpan={4} className="py-2 text-muted-foreground">No subagent runs</td></tr>}
              </tbody>
            </table>
          )}
        </div>
      </div>
      <div className="rounded-lg border border-border p-3 text-xs">
        <p className="mb-2 text-muted-foreground">Live events (<Num p="measured">{events?.events?.length ?? 0}</Num>)</p>
        <pre className="max-h-48 overflow-auto">{JSON.stringify(events?.events?.slice(0, 20), null, 2)}</pre>
      </div>
    </div>
  );
}
