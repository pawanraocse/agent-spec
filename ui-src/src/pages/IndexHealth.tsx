import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitBranch, HardDrive, RefreshCw } from "lucide-react";
import { apiGet, apiPost } from "../api/client";
import { Num, Stat } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Card, CardHeader, Empty } from "../components/ui/card";
import { fmtBytes, relTime } from "../lib/utils";

type GitState = { branch: string | null; head_sha: string; dirty: boolean | null; operation: string | null; conflicts: number };
type Failure = { finished: string; error: string | null };
type LogRow = { name: string; path: string; exists: boolean; bytes: number; lines?: number | null; files?: number | null };
export type HealthData = {
  graph: {
    state: "missing" | "failed" | "behind" | "current" | string; built: boolean; finished: string | null; age_s: number | null;
    duration_ms: number | null; reparsed: number | null; files: number | null; graph_git: GitState | null;
    head: { sha: string | null; branch: string | null }; last_failure: Failure | null; error: string | null;
    cache_bytes: number; graph_bytes: number;
  };
  mesh: { members: { id: string; path: string; exists: boolean; head_sha: string | null; built_sha: string | null; drifted: boolean }[]; drifted: number } | null;
  index: { ready: boolean; mode: string; sources: number; chunks: number; last: { ts?: string } | null } | null;
  logs: LogRow[]; total_log_bytes: number; problems: string[]; actions: string[];
  retention?: { days: number; max_bytes: number; archives: { path: string; bytes: number }[] };
};
type ActionResult = { ok: boolean; action: string; duration_ms: number; output: string[]; error?: string; health?: HealthData };

const STATE_TONE: Record<string, "success" | "danger" | "warning" | "neutral"> = {
  current: "success", failed: "danger", missing: "danger", behind: "warning",
};

const short = (sha?: string | null) => (sha ? sha.slice(0, 7) : "—");

/** H-020: is this project's index current? Graph freshness against git HEAD, the last build and
 *  any failure a background git-hook build left behind, the search index, and the size of every
 *  append-only log. Every figure is read from disk or git. */
export function IndexHealth() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["health"], queryFn: () => apiGet<HealthData>("/api/index-health"), refetchInterval: 15000 });
  const run = useMutation({
    mutationFn: (action: string) => apiPost<ActionResult>("/api/index-health", { action }),
    onSuccess: (data) => {
      if (data.health) qc.setQueryData(["health"], (old: HealthData | undefined) => ({ ...(old ?? data.health!), ...data.health!, index: old?.index ?? data.health!.index }));
      qc.invalidateQueries({ queryKey: ["automations"] });
    },
  });
  const d = q.data;
  if (!d) return <p className="p-6 text-xs text-muted-foreground">{q.isError ? "Could not load index health." : "Loading…"}</p>;
  const g = d.graph;
  const built = g.graph_git;
  return (
    <div className="space-y-5 p-6">
      {d.problems.length ? (
        <div role="status" className="rounded-md border border-warning/40 bg-warning/10 px-4 py-2 text-xs text-warning">
          {d.problems.join(" · ")}
        </div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Graph" value={<Badge tone={STATE_TONE[g.state] ?? "warning"}>{g.state}</Badge>} p="measured"
          hint={g.finished ? <>built <time dateTime={g.finished}>{relTime(g.finished)}</time></> : "never built"} />
        <Stat label="Files in graph" value={g.files ?? "—"} p="measured"
          hint={g.reparsed != null ? <><Num p="measured">{g.reparsed}</Num> reparsed in <Num p="measured">{g.duration_ms ?? 0}</Num> ms</> : undefined} />
        <Stat label="Search index" value={d.index ? d.index.chunks : "—"} p="measured"
          hint={d.index ? <>chunks from <Num p="measured">{d.index.sources}</Num> sources · {d.index.mode}</> : "database not open"} />
        <Stat label="Logs on disk" value={fmtBytes(d.total_log_bytes)} p="measured" hint={<><Num p="measured">{d.logs.filter((l) => l.exists).length}</Num> append-only files</>} />
      </div>

      <Card>
        <CardHeader title="Knowledge graph" subtitle="What the graph was built from, against what git says now."
          right={
            <div className="flex gap-2">
              {d.actions.includes("rebuild-graph") ? (
                <button type="button" disabled={run.isPending} onClick={() => run.mutate("rebuild-graph")}
                  className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50">
                  <RefreshCw size={12} className={run.isPending && run.variables === "rebuild-graph" ? "animate-spin" : ""} aria-hidden /> Rebuild graph
                </button>
              ) : null}
              {d.mesh ? (
                <button type="button" disabled={run.isPending} onClick={() => run.mutate("refresh-mesh")}
                  className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50">
                  <RefreshCw size={12} className={run.isPending && run.variables === "refresh-mesh" ? "animate-spin" : ""} aria-hidden /> Refresh mesh
                </button>
              ) : null}
            </div>
          } />
        <dl className="grid gap-x-6 gap-y-2 px-4 py-3 text-xs sm:grid-cols-2">
          <div className="flex items-center gap-2"><GitBranch size={12} aria-hidden className="text-muted-foreground" />
            <dt className="text-muted-foreground">Built from</dt>
            <dd className="font-mono">{built ? `${built.branch ?? "?"} @ ${short(built.head_sha)}` : "—"}{built?.dirty ? " (uncommitted changes)" : ""}</dd></div>
          <div className="flex items-center gap-2"><GitBranch size={12} aria-hidden className="text-muted-foreground" />
            <dt className="text-muted-foreground">HEAD now</dt>
            <dd className="font-mono">{g.head.sha ? `${g.head.branch ?? "?"} @ ${short(g.head.sha)}` : "not a git repository"}</dd></div>
          {built?.operation ? (
            <div className="sm:col-span-2 text-warning">Built during a {built.operation}{built.conflicts ? ` with ${built.conflicts} conflicted file(s)` : ""}; structure may be mid-change.</div>
          ) : null}
          <div className="flex items-center gap-2"><HardDrive size={12} aria-hidden className="text-muted-foreground" />
            <dt className="text-muted-foreground">Graph / cache</dt>
            <dd><Num p="measured">{fmtBytes(g.graph_bytes)}</Num> / <Num p="measured">{fmtBytes(g.cache_bytes)}</Num></dd></div>
          <div className="flex items-center gap-2"><dt className="text-muted-foreground">Last failure</dt>
            <dd className={g.last_failure ? "text-danger" : ""} data-figure-exempt>
              {g.last_failure ? <><time dateTime={g.last_failure.finished}>{relTime(g.last_failure.finished)}</time> — {g.last_failure.error}</> : "none recorded"}
            </dd></div>
        </dl>
        {run.data ? (
          <p className={`border-t border-border px-4 py-2 text-xs ${run.data.ok ? "text-muted-foreground" : "text-danger"}`} data-figure-exempt>
            {run.data.error ?? `${run.data.action} ${run.data.ok ? "finished" : "failed"} in ${run.data.duration_ms} ms${run.data.output.length ? " — " + run.data.output.join(" | ") : ""}`}
          </p>
        ) : null}
      </Card>

      {d.mesh ? (
        <Card>
          <CardHeader title="Repo mesh" subtitle="A member whose HEAD moved since the mesh build has stale cross-repo edges." />
          <ul className="divide-y divide-border text-xs">
            {d.mesh.members.map((m) => (
              <li key={m.id} className="flex items-center gap-3 px-4 py-2">
                <span className="font-mono">{m.id}</span>
                <span className="truncate text-muted-foreground" data-figure-exempt>{m.path}</span>
                <span className="ml-auto font-mono">{short(m.built_sha)} → {short(m.head_sha)}</span>
                <Badge tone={!m.exists ? "danger" : m.drifted ? "warning" : "success"}>{!m.exists ? "missing" : m.drifted ? "drifted" : "current"}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Append-only files"
          subtitle={d.retention
            ? <>Largest first. Over <Num p="measured">{fmtBytes(d.retention.max_bytes)}</Num>, rows older than <Num p="measured">{d.retention.days}</Num> days move to <code>archive/</code> at chat end (<Num p="measured">{d.retention.archives.length}</Num> archive files).</>
            : "Everything the harness keeps appending to, largest first."}
          right={d.actions.includes("apply-retention") ? (
            <button type="button" disabled={run.isPending} onClick={() => run.mutate("apply-retention")}
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50">
              <HardDrive size={12} aria-hidden /> Archive old rows
            </button>
          ) : undefined} />
        {d.logs.every((l) => !l.exists) ? (
          <Empty title="No logs yet" hint="Rows appear after the first chat in this project." />
        ) : (
          <table className="w-full text-xs">
            <thead className="text-left text-muted-foreground">
              <tr><th className="px-4 py-2 font-medium">File</th><th className="py-2 font-medium">Path</th><th className="py-2 text-right font-medium">Rows / files</th><th className="px-4 py-2 text-right font-medium">Size</th></tr>
            </thead>
            <tbody className="divide-y divide-border">
              {[...d.logs].sort((a, b) => b.bytes - a.bytes).map((l) => (
                <tr key={l.path} className={l.exists ? "" : "text-muted-foreground"}>
                  <td className="px-4 py-1.5">{l.name}</td>
                  <td className="py-1.5 font-mono" data-figure-exempt>.agent-spec/{l.path}</td>
                  <td className="py-1.5 text-right">{(l.lines ?? l.files) != null ? <Num p="measured">{l.lines ?? l.files}</Num> : "—"}</td>
                  <td className="px-4 py-1.5 text-right">{l.exists ? <Num p="measured">{fmtBytes(l.bytes)}</Num> : "absent"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
