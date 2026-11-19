import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Pencil, Plus, Scissors, Search, Trash2, X } from "lucide-react";
import { apiGet, apiPost } from "../api/client";
import { Num } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardHeader, Empty } from "../components/ui/card";
import { cn } from "../lib/utils";

export type FactItem = {
  fact_id: string;
  type: string;
  subject: string;
  body?: string;
  status?: string;
  scope?: "local" | "team";
  created?: string;
  updated?: string;
  supersedes?: string | null;
  injections_count?: number;
};
export type MemoryData = {
  facts: FactItem[];
  types?: string[];
  index?: { bytes: number; limit: number };
  active?: number;
};
type ChangeResult = {
  ok?: boolean; error?: string; result?: string; preview?: boolean; older_than?: number;
  facts?: { fact_id: string; type: string; subject: string }[]; memory?: MemoryData;
};
type ExperienceItem = {
  exp_id: string; title: string; tier?: string; confidence?: number; uses?: number; successes?: number; task?: string;
};

const TYPES = ["decision", "constraint", "gotcha", "reference"];
const TEXT_MAX = 600;
const field = "w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary";

/** Add a fact, or edit one (which supersedes it, keeping the old version on disk). */
function FactForm({ initial, types, busy, onSave, onCancel }: {
  initial?: FactItem; types: string[]; busy: boolean;
  onSave: (v: { type: string; subject: string; text: string }) => void; onCancel: () => void;
}) {
  const [type, setType] = useState(initial?.type || "constraint");
  const [subject, setSubject] = useState(initial?.subject || "");
  const [text, setText] = useState(initial?.body || "");
  const ok = subject.trim().length >= 3 && text.trim().length >= 10 && text.length <= TEXT_MAX;
  return (
    <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); if (ok) onSave({ type, subject, text }); }}>
      <div className="flex flex-wrap gap-2">
        <select aria-label="Fact type" value={type} onChange={(e) => setType(e.target.value)} className={cn(field, "w-auto")}>
          {types.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <input aria-label="Subject" value={subject} maxLength={80} onChange={(e) => setSubject(e.target.value)}
          placeholder="Short subject, e.g. routes are a public contract" className={cn(field, "min-w-0 flex-1")} />
      </div>
      <textarea aria-label="Fact text" value={text} rows={3} onChange={(e) => setText(e.target.value)}
        placeholder="One sentence the agent must know at the start of every session." className={field} />
      <div className="flex items-center gap-2">
        <span className={cn("text-[11px] text-muted-foreground", text.length > TEXT_MAX && "text-danger")} data-figure-exempt>
          {text.length}/{TEXT_MAX} characters
        </span>
        <span className="ml-auto" />
        <Button type="button" size="sm" variant="ghost" onClick={onCancel}><X size={12} aria-hidden /> Cancel</Button>
        <Button type="submit" size="sm" disabled={!ok || busy}><Check size={12} aria-hidden /> {initial ? "Save new version" : "Remember"}</Button>
      </div>
    </form>
  );
}

/** Memory controls: every fact the digest can inject, with add, edit, forget and prune. Each change
 *  runs agent-spec-memory.py and is audited with the other decisions in proposals.jsonl. */
function MemoryPanel() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["memory"], queryFn: () => apiGet<MemoryData>("/api/memory"), refetchInterval: 30000 });
  const [scope, setScope] = useState<"all" | "local" | "team">("all");
  const [type, setType] = useState("all");
  const [text, setText] = useState("");
  const [retired, setRetired] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [days, setDays] = useState(90);
  const [preview, setPreview] = useState<ChangeResult | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const change = useMutation({
    mutationFn: (body: Record<string, unknown>) => apiPost<ChangeResult>("/api/memory", body),
    onSuccess: (data, body) => {
      if (data.memory) qc.setQueryData(["memory"], data.memory);
      if (data.error) return setMessage({ ok: false, text: data.error });
      if (data.preview) return setPreview(data);
      setMessage({ ok: true, text: data.result || "done" });
      setEditing(null); setAdding(false); setConfirm(null);
      if (body.action === "prune") setPreview(null);
    },
    onError: () => setMessage({ ok: false, text: "The dashboard server did not answer." }),
  });

  const d = q.data;
  const types = d?.types?.length ? d.types : TYPES;
  const shown = useMemo(() => {
    const needle = text.trim().toLowerCase();
    return (d?.facts ?? []).filter((f) =>
      (scope === "all" || (f.scope || "local") === scope)
      && (type === "all" || f.type === type)
      && (retired || (f.status || "active") === "active")
      && (!needle || `${f.subject} ${f.body ?? ""}`.toLowerCase().includes(needle)));
  }, [d, scope, type, text, retired]);

  if (!d) return <p className="p-6 text-xs text-muted-foreground">{q.isError ? "Could not load memory." : "Loading…"}</p>;
  const over = d.index ? d.index.bytes > d.index.limit : false;
  const pct = d.index ? Math.min(100, Math.round((d.index.bytes / d.index.limit) * 100)) : 0;
  const retiredCount = d.facts.filter((f) => (f.status || "active") !== "active").length;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Card className="px-4 py-3">
          <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Active facts</div>
          <div className="mt-1 text-xl font-semibold"><Num p="measured">{d.active ?? d.facts.length}</Num></div>
          <div className="text-[11px] text-muted-foreground"><Num p="measured">{retiredCount}</Num> retired, kept on disk</div>
        </Card>
        <Card className="px-4 py-3">
          <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Memory index</div>
          <div className={cn("mt-1 text-xl font-semibold", over && "text-warning")}>
            <Num p="measured">{d.index?.bytes ?? 0}</Num> <span className="text-xs font-normal text-muted-foreground">/ <Num p="measured">{d.index?.limit ?? 0}</Num> B</span>
          </div>
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted" role="meter" aria-label="Memory index size"
            aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
            <div className={cn("h-full rounded-full", over ? "bg-warning" : "bg-success")} style={{ width: `${pct}%` }} />
          </div>
        </Card>
        <Card className="px-4 py-3">
          <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Injected into chats</div>
          <div className="mt-1 text-xl font-semibold">
            <Num p="measured">{d.facts.reduce((n, f) => n + (f.injections_count ?? 0), 0)}</Num>
          </div>
          <div className="text-[11px] text-muted-foreground">times the session-start digest carried a fact</div>
        </Card>
      </div>

      <Card>
        <CardHeader title="Prune old facts" subtitle="Preview first. Constraints are never pruned by age; pruned facts are deleted."
          right={<Scissors size={14} className="text-muted-foreground" aria-hidden />} />
        <div className="flex flex-wrap items-center gap-2 px-4 pb-3 text-xs">
          <label className="flex items-center gap-2">Older than
            <input type="number" min={1} max={3650} value={days} aria-label="Days"
              onChange={(e) => { setDays(Number(e.target.value)); setPreview(null); }} className={cn(field, "w-20")} />
            days
          </label>
          <Button size="sm" variant="outline" disabled={change.isPending}
            onClick={() => change.mutate({ action: "prune", older_than: days })}>Preview</Button>
          {preview?.facts ? (
            preview.facts.length ? (
              <Button size="sm" variant="danger" disabled={change.isPending}
                onClick={() => change.mutate({ action: "prune", older_than: preview.older_than, apply: true })}>
                <Trash2 size={12} aria-hidden /> Delete <Num p="measured">{preview.facts.length}</Num> facts
              </Button>
            ) : <span className="text-muted-foreground">Nothing that old.</span>
          ) : null}
        </div>
        {preview?.facts?.length ? (
          <ul className="max-h-48 overflow-auto border-t border-border text-xs">
            {preview.facts.map((f) => (
              <li key={f.fact_id} className="flex gap-2 px-4 py-1" data-figure-exempt>
                <Badge>{f.type}</Badge><span className="truncate">{f.subject}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </Card>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <label className="relative">
          <Search size={12} className="absolute left-2 top-2 text-muted-foreground" aria-hidden />
          <input aria-label="Search facts" value={text} onChange={(e) => setText(e.target.value)} placeholder="Search facts"
            className={cn(field, "w-56 pl-6")} />
        </label>
        <select aria-label="Filter by type" value={type} onChange={(e) => setType(e.target.value)} className={cn(field, "w-auto")}>
          <option value="all">all types</option>
          {types.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        {(["all", "local", "team"] as const).map((sc) => (
          <button key={sc} type="button" onClick={() => setScope(sc)}
            className={cn("rounded-md px-2.5 py-1 text-[11px] font-medium uppercase transition-colors",
              scope === sc ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground")}>
            {sc}
          </button>
        ))}
        <label className="flex items-center gap-1 text-muted-foreground">
          <input type="checkbox" checked={retired} onChange={(e) => setRetired(e.target.checked)} /> show retired
        </label>
        <span className="ml-auto text-muted-foreground">Showing <Num p="measured">{shown.length}</Num> fact(s)</span>
        <Button size="sm" onClick={() => { setAdding(true); setEditing(null); }}><Plus size={12} aria-hidden /> Add fact</Button>
      </div>

      {message ? (
        <p role="status" className={cn("text-xs", message.ok ? "text-success" : "text-danger")} data-figure-exempt>{message.text}</p>
      ) : null}

      {adding ? (
        <Card className="p-4">
          <FactForm types={types} busy={change.isPending} onCancel={() => setAdding(false)}
            onSave={(v) => change.mutate({ action: "add", ...v })} />
        </Card>
      ) : null}

      <Card className="divide-y divide-border text-xs">
        {shown.length === 0 ? (
          <Empty title="No facts match" hint="Facts come from /agent-spec-remember, approved proposals, or Add fact above." />
        ) : shown.map((f) => {
          const team = f.scope === "team";
          const active = (f.status || "active") === "active";
          return (
            <div key={f.fact_id} className={cn("space-y-1.5 p-3.5", !active && "opacity-60")}>
              {editing === f.fact_id ? (
                <FactForm initial={f} types={types} busy={change.isPending} onCancel={() => setEditing(null)}
                  onSave={(v) => change.mutate({ action: "edit", id: f.fact_id, ...v })} />
              ) : (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={f.type === "constraint" ? "primary" : f.type === "gotcha" ? "warning" : "neutral"}>{f.type}</Badge>
                    <span className="font-semibold text-foreground" data-figure-exempt>{f.subject}</span>
                    {!active ? <Badge>{f.status}</Badge> : null}
                    {team ? <Badge tone="accent">team</Badge> : null}
                    <span className="ml-auto flex items-center gap-1">
                      <span className="mr-2 font-mono text-muted-foreground"><Num p="measured">{f.injections_count ?? 0}</Num> injections</span>
                      {!team && active ? (
                        <>
                          <Button size="sm" variant="ghost" aria-label={`Edit ${f.subject}`}
                            onClick={() => { setEditing(f.fact_id); setAdding(false); setConfirm(null); }}>
                            <Pencil size={12} aria-hidden />
                          </Button>
                          {confirm === f.fact_id ? (
                            <Button size="sm" variant="danger" disabled={change.isPending}
                              onClick={() => change.mutate({ action: "forget", id: f.fact_id })}>Forget?</Button>
                          ) : (
                            <Button size="sm" variant="ghost" aria-label={`Forget ${f.subject}`} onClick={() => setConfirm(f.fact_id)}>
                              <Trash2 size={12} aria-hidden />
                            </Button>
                          )}
                        </>
                      ) : null}
                    </span>
                  </div>
                  {f.body ? <p className="text-foreground/90" data-figure-exempt>{f.body}</p> : null}
                  <div className="font-mono text-[10px] text-muted-foreground" data-figure-exempt>
                    {f.created ? `created ${f.created}` : null}{f.supersedes ? ` · replaces ${f.supersedes}` : null}
                    {team ? " · synced by merge-team; edit at its source" : null}
                  </div>
                </>
              )}
            </div>
          );
        })}
      </Card>
    </div>
  );
}

export function Knowledge() {
  const [tab, setTab] = useState<"memory" | "flywheel">("memory");
  const memory = useQuery({ queryKey: ["memory"], queryFn: () => apiGet<MemoryData>("/api/memory"), refetchInterval: 30000 });
  const exp = useQuery({ queryKey: ["experiences"], queryFn: () => apiGet<{ experiences: ExperienceItem[] }>("/api/experiences") });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Memory</h1>
        <p className="text-xs text-muted-foreground">
          Durable project facts read back at every session start, and the experiences the learning loop reuses
        </p>
      </div>

      <div className="flex gap-2 border-b border-border text-xs">
        {([
          ["memory", "Bounded Memory", memory.data?.active ?? memory.data?.facts?.length ?? 0],
          ["flywheel", "Flywheel Experiences", exp.data?.experiences?.length ?? 0],
        ] as const).map(([t, label, count]) => (
          <button key={t} type="button" onClick={() => setTab(t)}
            className={cn("border-b-2 pb-2.5 font-medium transition-colors",
              tab === t ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground")}>
            <span data-figure-exempt>{label}</span> (<Num p="measured">{count}</Num>)
          </button>
        ))}
      </div>

      {tab === "memory" && <MemoryPanel />}

      {tab === "flywheel" && (
        <div className="space-y-4">
          <Card className="p-4 text-xs text-muted-foreground">
            The learning flywheel promotes candidate corrections into trusted experiences and proposed skills.
            Promote or deprecate them in Inbox › Proposals.
          </Card>
          <Card className="divide-y divide-border text-xs">
            {(exp.data?.experiences ?? []).length === 0 ? (
              <div className="p-6 text-center text-muted-foreground">No flywheel experiences recorded yet.</div>
            ) : (
              (exp.data?.experiences ?? []).map((e) => (
                <div key={e.exp_id} className="space-y-1 p-3.5 hover:bg-muted/60">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-foreground" data-figure-exempt>{e.title}</span>
                    <Badge tone="success">{e.tier || "trusted"}</Badge>
                  </div>
                  {e.task && <p className="text-muted-foreground" data-figure-exempt>{e.task}</p>}
                  <div className="flex items-center gap-3 pt-1 font-mono text-[10px] text-muted-foreground">
                    <span>Uses: <Num p="measured">{e.uses ?? 0}</Num></span>
                    <span>Successes: <Num p="measured">{e.successes ?? 0}</Num></span>
                  </div>
                </div>
              ))
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
