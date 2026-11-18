import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Check, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { Num, Stat } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Card, CardHeader, Empty } from "../components/ui/card";
import { relTime } from "../lib/utils";

type Item = {
  kind: "fact" | "skill" | "experience"; id: string; title: string; body: string | null; evidence?: string | null;
  proposed_at?: string; diff_against?: string | null; target?: string; reuses?: number;
};
type Decided = { ts: string; kind: string; id: string; decision: string; result: string; title?: string; by: string };
export type ProposalsData = { pending: Item[]; counts: Record<string, number>; decided: Decided[]; log: string };

const ACTIONS: Record<Item["kind"], [string, string]> = {
  fact: ["approve", "reject"], skill: ["approve", "reject"], experience: ["promote", "deprecate"],
};
const KIND_LABEL: Record<Item["kind"], string> = { fact: "fact", skill: "workflow skill", experience: "experience" };

/** PI-009: what the learning loop proposes — facts, workflow skills, reusable experiences — waits
 *  here. Nothing is remembered, published or promoted until a person clicks; every decision is
 *  audited in proposals.jsonl. */
export function Proposals() {
  const qc = useQueryClient();
  const [open, setOpen] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["proposals"], queryFn: () => apiGet<ProposalsData>("/api/proposals"), refetchInterval: 15000 });
  const decide = useMutation({
    mutationFn: (v: { kind: string; id: string; decision: string }) =>
      apiPost<{ error?: string; result?: string; proposals?: ProposalsData }>("/api/proposals", v),
    onSuccess: (data) => { if (data.proposals) qc.setQueryData(["proposals"], data.proposals); },
  });
  const d = q.data;
  if (!d) return <p className="p-6 text-xs text-muted-foreground">{q.isError ? "Could not load proposals." : "Loading…"}</p>;
  return (
    <div className="space-y-5 p-6">
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Facts proposed" value={d.counts.fact ?? 0} p="measured" hint={<code>agent-spec-memory.py propose</code>} />
        <Stat label="Workflow skills" value={d.counts.skill ?? 0} p="measured" hint={<code>/agent-spec-learn propose</code>} />
        <Stat label="Experiences to judge" value={d.counts.experience ?? 0} p="measured" hint={<span data-figure-exempt>reused 3+ times</span>} />
      </div>
      <Card>
        <CardHeader title="Waiting for you" subtitle="Approving runs the same CLI you would; nothing changes until you click."
          right={<Sparkles size={14} className="text-muted-foreground" aria-hidden />} />
        {d.pending.length === 0 ? (
          <Empty title="Inbox empty" hint="Session reviews and /agent-spec-learn put proposals here." />
        ) : (
          <ul className="divide-y divide-border">
            {d.pending.map((p) => {
              const key = `${p.kind}:${p.id}`;
              const [yes, no] = ACTIONS[p.kind];
              return (
                <li key={key} className="px-4 py-3">
                  <div className="flex flex-wrap items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={p.kind === "fact" ? "primary" : p.kind === "skill" ? "accent" : "neutral"}>{KIND_LABEL[p.kind]}</Badge>
                        <span className="text-sm font-medium" data-figure-exempt>{p.title}</span>
                        {p.proposed_at ? <time className="text-xs text-muted-foreground" dateTime={p.proposed_at}>{relTime(p.proposed_at)}</time> : null}
                      </div>
                      {p.kind === "fact" ? <p className="mt-1 text-xs" data-figure-exempt>{p.body}</p> : null}
                      {p.evidence ? <p className="mt-1 text-xs text-muted-foreground" data-figure-exempt>Evidence: {p.evidence}</p> : null}
                      {p.kind === "skill" ? (
                        <button type="button" className="mt-1 inline-flex items-center gap-1 text-xs text-primary" onClick={() => setOpen(open === key ? null : key)}>
                          <BookOpen size={12} aria-hidden /> {open === key ? "Hide" : "Show"} draft{p.diff_against ? " and the version it replaces" : ""} → <code>{p.target}</code>
                        </button>
                      ) : null}
                    </div>
                    <div className="flex gap-2">
                      <button type="button" disabled={decide.isPending} onClick={() => decide.mutate({ kind: p.kind, id: p.id, decision: yes })}
                        className="inline-flex items-center gap-1 rounded-md bg-primary px-2 py-1 text-xs capitalize text-primary-foreground disabled:opacity-50">
                        <Check size={12} aria-hidden /> {yes}
                      </button>
                      <button type="button" disabled={decide.isPending} onClick={() => decide.mutate({ kind: p.kind, id: p.id, decision: no })}
                        className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs capitalize hover:bg-muted disabled:opacity-50">
                        <X size={12} aria-hidden /> {no}
                      </button>
                    </div>
                  </div>
                  {open === key ? (
                    <div className="mt-2 grid gap-2 md:grid-cols-2">
                      {p.diff_against ? <pre className="max-h-72 overflow-auto rounded bg-muted p-2 text-[11px]">{p.diff_against}</pre> : null}
                      <pre className="max-h-72 overflow-auto rounded bg-muted p-2 text-[11px]">{p.body}</pre>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
        {decide.data?.error ? <p className="border-t border-border px-4 py-2 text-xs text-danger">{decide.data.error}</p> : null}
      </Card>
      <Card>
        <CardHeader title="Decided" subtitle={<>Newest first, from <code>{d.log}</code>.</>} />
        {d.decided.length === 0 ? <Empty title="No decisions yet" hint="Each approve or reject is recorded here." /> : (
          <ul className="divide-y divide-border text-xs">
            {d.decided.map((r, i) => (
              <li key={`${r.ts}-${i}`} className="flex flex-wrap items-center gap-2 px-4 py-1.5">
                <time dateTime={r.ts}>{relTime(r.ts)}</time>
                <Badge tone={r.decision === "approve" || r.decision === "promote" ? "success" : "neutral"}>{r.decision}</Badge>
                <span className="truncate" data-figure-exempt>{r.title || r.id}</span>
                <span className="ml-auto text-muted-foreground" data-figure-exempt>{r.result} · {r.by}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <p className="text-xs text-muted-foreground"><Num p="measured">{d.pending.length}</Num> pending.</p>
    </div>
  );
}
