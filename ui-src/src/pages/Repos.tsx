import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderPlus, GitBranch, Network, Trash2 } from "lucide-react";
import { useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { Num, Stat } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Card, CardHeader, Empty } from "../components/ui/card";
import { fmtTokens, relTime } from "../lib/utils";

type Repo = {
  repo_id: string; path: string; exists: boolean; files: number; branch: string | null; head_sha: string | null;
  built_sha: string | null; updated: string | null; drifted: boolean; usage: { requests: number; tokens: number } | null;
};
type Pair = { source: string; target: string; total: number; by_type: Record<string, number> };
export type MeshData = { built: boolean; repos: Repo[]; pairs: Pair[]; hot_files: { file: string; callers: number }[] };
type Query = { file: string; outgoing: { type: string; target: string; detail: string }[]; incoming: { type: string; source: string; detail: string }[];
  blast_radius: { file: string; depth: number }[]; repos_affected: string[] };

const short = (s: string | null) => (s ? s.slice(0, 7) : "—");

/** P3-006 / P3-007: every repo in the mesh with its freshness and drift, how the repos call each
 *  other, and a file's cross-repo blast radius; add or remove a repo without a terminal. */
export function Repos() {
  const qc = useQueryClient();
  const [path, setPath] = useState("");
  const [rid, setRid] = useState("");
  const [file, setFile] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["mesh"], queryFn: () => apiGet<MeshData>("/api/mesh"), refetchInterval: 30000 });
  const fq = useQuery({ queryKey: ["mesh-query", file], enabled: !!file,
    queryFn: () => apiGet<Query>(`/api/mesh/query?file=${encodeURIComponent(file ?? "")}`) });
  const change = useMutation({
    mutationFn: (v: { action: "add" | "remove"; path?: string; repo_id?: string }) =>
      apiPost<{ error?: string; duration_ms?: number; mesh?: MeshData }>("/api/mesh", v),
    onSuccess: (data) => { if (data.mesh) { qc.setQueryData(["mesh"], data.mesh); setPath(""); setRid(""); } },
  });
  const d = q.data;
  if (!d) return <p className="p-6 text-xs text-muted-foreground">{q.isError ? "Could not load the mesh." : "Loading…"}</p>;
  const drifted = d.repos.filter((r) => r.drifted).length;
  return (
    <div className="space-y-5 p-6">
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Repos" value={d.repos.length} p="measured" hint={<><Num p="measured">{d.repos.reduce((a, r) => a + r.files, 0)}</Num> files</>} />
        <Stat label="Cross-repo links" value={d.pairs.reduce((a, p) => a + p.total, 0)} p="measured" hint={<><Num p="measured">{d.pairs.length}</Num> repo pairs</>} />
        <Stat label="Drifted" value={drifted} p="measured" hint={drifted ? "HEAD moved since the mesh build" : "every repo at its built SHA"} />
      </div>

      <Card>
        <CardHeader title="Repos" subtitle="Built SHA against HEAD now; tokens are this machine's requests in that folder." />
        <form className="flex flex-wrap gap-2 border-b border-border px-4 py-3" onSubmit={(e) => { e.preventDefault(); if (path.trim()) change.mutate({ action: "add", path: path.trim(), repo_id: rid.trim() || undefined }); }}>
          <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="/absolute/path/to/repo" aria-label="Repo path"
            className="min-w-[16rem] flex-1 rounded-md border border-border bg-background px-2 py-1 font-mono text-xs" />
          <input value={rid} onChange={(e) => setRid(e.target.value)} placeholder="id (optional)" aria-label="Repo id"
            className="w-36 rounded-md border border-border bg-background px-2 py-1 font-mono text-xs" />
          <button type="submit" disabled={change.isPending || !path.trim()}
            className="inline-flex items-center gap-1 rounded-md bg-primary px-2 py-1 text-xs text-primary-foreground disabled:opacity-50">
            <FolderPlus size={12} aria-hidden /> {change.isPending ? "Building…" : "Add repo"}
          </button>
        </form>
        {change.data?.error ? <p className="border-b border-border px-4 py-2 text-xs text-danger">{change.data.error}</p> : null}
        {d.repos.length === 0 ? <Empty title="No repos in the mesh" hint="Add the repos this one calls or is called by." /> : (
          <table className="w-full text-xs">
            <thead className="text-left text-muted-foreground">
              <tr><th className="px-4 py-2 font-medium">Repo</th><th className="py-2 font-medium">Branch</th><th className="py-2 font-medium">Built → HEAD</th>
                <th className="py-2 text-right font-medium">Files</th><th className="py-2 text-right font-medium">Tokens</th><th className="px-4 py-2" /></tr>
            </thead>
            <tbody className="divide-y divide-border">
              {d.repos.map((r) => (
                <tr key={r.repo_id}>
                  <td className="px-4 py-1.5"><div className="font-mono">{r.repo_id}</div><div className="truncate font-mono text-[10px] text-muted-foreground">{r.path}</div></td>
                  <td className="py-1.5"><span className="inline-flex items-center gap-1 font-mono"><GitBranch size={11} aria-hidden />{r.branch ?? "—"}</span></td>
                  <td className="py-1.5 font-mono">{short(r.built_sha)} → {short(r.head_sha)}{" "}
                    <Badge tone={!r.exists ? "danger" : r.drifted ? "warning" : "success"}>{!r.exists ? "missing" : r.drifted ? "drifted" : "current"}</Badge>
                    {r.updated ? <time className="ml-1 text-muted-foreground" dateTime={r.updated}>{relTime(r.updated)}</time> : null}
                  </td>
                  <td className="py-1.5 text-right"><Num p="measured">{r.files}</Num></td>
                  <td className="py-1.5 text-right">{r.usage ? <Num p="measured">{fmtTokens(r.usage.tokens)}</Num> : "—"}</td>
                  <td className="px-4 py-1.5 text-right">
                    <button type="button" aria-label={`Remove ${r.repo_id}`} disabled={change.isPending}
                      onClick={() => change.mutate({ action: "remove", repo_id: r.repo_id })} className="text-muted-foreground hover:text-danger disabled:opacity-50">
                      <Trash2 size={13} aria-hidden />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Who calls whom" subtitle="Confident cross-repo edges per repo pair." right={<Network size={14} className="text-muted-foreground" aria-hidden />} />
          {d.pairs.length === 0 ? <Empty title="No cross-repo edges" hint="Add a repo that imports, calls or consumes another." /> : (
            <ul className="divide-y divide-border text-xs">
              {d.pairs.map((p) => (
                <li key={`${p.source}-${p.target}`} className="flex items-center gap-2 px-4 py-1.5">
                  <span className="font-mono">{p.source} → {p.target}</span>
                  <span className="ml-auto text-muted-foreground">{Object.entries(p.by_type).map(([t, n]) => <span key={t} className="ml-2">{t} <Num p="measured">{n}</Num></span>)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <CardHeader title="Most-called files" subtitle="Click one for its cross-repo blast radius." />
          {d.hot_files.length === 0 ? <Empty title="Nothing called across repos yet" hint="" /> : (
            <ul className="divide-y divide-border text-xs">
              {d.hot_files.map((h) => (
                <li key={h.file}>
                  <button type="button" onClick={() => setFile(h.file)} className="flex w-full items-center gap-2 px-4 py-1.5 text-left hover:bg-muted">
                    <span className="truncate font-mono">{h.file}</span><span className="ml-auto"><Num p="measured">{h.callers}</Num> callers</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {file ? (
        <Card>
          <CardHeader title={<span className="font-mono">{file}</span>} subtitle="graphify-mesh.py query --file" />
          {fq.isLoading ? <p className="px-4 py-3 text-xs text-muted-foreground">Querying…</p> : fq.data ? (
            <div className="grid gap-4 px-4 py-3 text-xs md:grid-cols-3">
              <div><h4 className="mb-1 font-medium">Depends on</h4>{fq.data.outgoing.map((e, i) => <div key={i} className="font-mono">{e.type} → {e.target}</div>)}{fq.data.outgoing.length ? null : "—"}</div>
              <div><h4 className="mb-1 font-medium">Depended on by</h4>{fq.data.incoming.map((e, i) => <div key={i} className="font-mono">{e.type} ← {e.source}</div>)}{fq.data.incoming.length ? null : "—"}</div>
              <div><h4 className="mb-1 font-medium">Blast radius (<Num p="measured">{fq.data.blast_radius.length}</Num> files)</h4>
                {fq.data.blast_radius.slice(0, 20).map((b) => <div key={b.file} className="font-mono">{b.file}</div>)}</div>
            </div>
          ) : <p className="px-4 py-3 text-xs text-danger">Query failed.</p>}
        </Card>
      ) : null}
    </div>
  );
}
