import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Copy, FileCode2, FileText, History, Lightbulb, ScrollText, Search, Sparkles, Star } from "lucide-react";
import { apiGet } from "../api/client";
import { Num, Prov } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardHeader, Empty } from "../components/ui/card";
import { cn, copyText, relTime } from "../lib/utils";

export type Kind = "code" | "doc" | "rule" | "memory" | "request" | "review";
export type Hit = {
  chunk_id: number; kind: Kind; source: string; ref: string; title: string; start_line?: number | null; end_line?: number | null;
  session_id?: string | null; ts?: string | null; snippet?: string; matched_by: string[]; rrf: number; bm25?: number; cosine?: number;
};
export type AskResult = {
  query: string; mode: "keyword" | "hybrid"; hits: Hit[]; warnings: string[]; related?: { path: string; relation: string }[];
  cursor_prompt?: string; answer?: { text: string; model: string; cited: number[]; uncited: boolean } | null;
};
export type IndexStatus = {
  ready: boolean; mode?: string; embedder?: string | null; by_kind: Record<string, { sources: number; chunks: number }>;
  vectors?: Record<string, number>; last?: { ts: string; indexed: number; unchanged: number; removed: number } | null;
};

const KINDS: { id: Kind; label: string; icon: typeof FileCode2 }[] = [
  { id: "code", label: "Code", icon: FileCode2 },
  { id: "doc", label: "Docs", icon: FileText },
  { id: "rule", label: "Rules & skills", icon: ScrollText },
  { id: "memory", label: "Memory", icon: Lightbulb },
  { id: "request", label: "Past requests", icon: History },
  { id: "review", label: "Reviews", icon: Star },
];
const ICON = Object.fromEntries(KINDS.map((k) => [k.id, k.icon])) as Record<Kind, typeof FileCode2>;
const SINCE: [string, string][] = [["", "Any time"], ["1", "Past day"], ["7", "Past week"], ["30", "Past month"]];
const EXAMPLES = [
  "What changed in the last session?",
  "Why was the hook event spine built this way?",
  "Which skills were used to build the dashboard?",
  "Have we implemented retry handling before?",
  "Why did the previous request fail?",
];

function sinceIso(days: string): string | undefined {
  return days ? new Date(Date.now() - Number(days) * 86_400_000).toISOString() : undefined;
}

/** `[[term]]` marks from FTS5 snippet() become <mark>. Text stays text: no HTML is injected. */
function Snippet({ text }: { text?: string }) {
  if (!text) return null;
  const parts = text.split(/(\[\[.*?\]\])/g);
  return (
    <p className="mt-1 line-clamp-3 whitespace-pre-wrap break-words font-mono text-[11px] leading-relaxed text-muted-foreground">
      {parts.map((p, i) => (p.startsWith("[[") ? <mark key={i} className="rounded bg-primary/15 px-0.5 text-foreground">{p.slice(2, -2)}</mark> : p))}
    </p>
  );
}

function HitRow({ h, n }: { h: Hit; n: number }) {
  const Icon = ICON[h.kind] ?? FileText;
  const target = h.kind === "request" ? `/requests/${encodeURIComponent(h.ref)}` : h.kind === "review" && h.session_id ? `/project/sessions/${encodeURIComponent(h.session_id)}` : null;
  const where = h.kind === "request" || h.kind === "review" ? `${h.kind} ${h.ref}` : h.ref;
  return (
    <li className="px-4 py-3">
      <div className="flex items-center gap-2 text-xs">
        <span className="w-6 shrink-0 font-mono text-muted-foreground">[{n}]</span>
        <Icon size={14} className="shrink-0 text-muted-foreground" aria-hidden />
        {target ? <Link to={target} className="truncate font-medium hover:text-primary hover:underline">{h.title}</Link> : <span className="truncate font-medium">{h.title}</span>}
        <span className="ml-auto flex shrink-0 items-center gap-1">
          {h.matched_by.map((m) => <Badge key={m} tone={m === "semantic" ? "accent" : "primary"}>{m}</Badge>)}
        </span>
      </div>
      <div className="ml-8 mt-0.5 flex items-center gap-2">
        <button type="button" className="truncate font-mono text-[10px] text-muted-foreground hover:text-foreground" title="Copy citation" onClick={() => copyText(where)}>{where}</button>
        {h.ts && (h.kind === "request" || h.kind === "review") ? <time dateTime={h.ts} className="text-[10px] text-muted-foreground">{relTime(h.ts)}</time> : null}
      </div>
      <div className="ml-8"><Snippet text={h.snippet} /></div>
    </li>
  );
}

/** PI-005: ask the project. Retrieval over the local index is shown as Measured sources with
 *  citations; an answer appears only when a local model is configured, and is labelled. The
 *  default path hands the question and the sources to Cursor through /agent-spec-ask. */
export function Ask() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const [draft, setDraft] = useState(q);
  const [kinds, setKinds] = useState<Kind[]>([]);
  const [since, setSince] = useState("");
  const [copied, setCopied] = useState(false);
  useEffect(() => setDraft(q), [q]);

  const status = useQuery({ queryKey: ["index"], queryFn: () => apiGet<IndexStatus>("/api/index"), refetchInterval: 60_000 });
  const qs = new URLSearchParams({ q, limit: "10" });
  if (kinds.length) qs.set("kind", kinds.join(","));
  const s = sinceIso(since);
  if (s) qs.set("since", s);
  const result = useQuery({ queryKey: ["ask", q, kinds, since], enabled: q.length > 0, queryFn: () => apiGet<AskResult>(`/api/ask?${qs}`) });

  const submit = (text: string) => setParams(text.trim() ? { q: text.trim() } : {});
  const toggle = (k: Kind) => setKinds((cur) => (cur.includes(k) ? cur.filter((x) => x !== k) : [...cur, k]));
  const st = status.data;
  const r = result.data;
  const total = st ? Object.values(st.by_kind).reduce((a, b) => a + b.chunks, 0) : 0;

  return (
    <div className="mx-auto max-w-5xl space-y-5 p-6">
      <form onSubmit={(e) => { e.preventDefault(); submit(draft); }} className="space-y-3">
        <div className="flex items-center gap-2 rounded-xl border border-border bg-card px-3 focus-within:ring-2 focus-within:ring-primary/40">
          <Search size={16} className="text-muted-foreground" aria-hidden />
          <input aria-label="Ask about this project" value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus
            placeholder="Ask about the code, the docs, or what Cursor did in past sessions…" className="h-12 w-full bg-transparent text-sm outline-none" />
          <Button type="submit" size="sm" disabled={!draft.trim()}>Ask</Button>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {KINDS.map((k) => (
            <button key={k.id} type="button" onClick={() => toggle(k.id)} aria-pressed={kinds.includes(k.id)}
              className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs ring-1 ring-inset",
                kinds.includes(k.id) ? "bg-primary/10 text-primary ring-primary/40" : "text-muted-foreground ring-border hover:bg-muted")}>
              <k.icon size={12} aria-hidden />{k.label}
              {st?.by_kind[k.id] ? <Num p="measured" className="text-[10px] opacity-70">{st.by_kind[k.id].sources}</Num> : null}
            </button>
          ))}
          <select aria-label="Time range" value={since} onChange={(e) => setSince(e.target.value)} className="ml-auto h-7 rounded-md border border-border bg-card px-2 text-xs">
            {SINCE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <p className="text-[11px] text-muted-foreground">
          {st?.ready ? (
            <>Local index: <Num p="measured">{total}</Num> passages from <Num p="measured">{Object.values(st.by_kind).reduce((a, b) => a + b.sources, 0)}</Num> sources ·
              {" "}<span className="font-medium">{st.mode === "hybrid" ? `keyword + semantic (${st.embedder})` : "keyword (BM25); semantic turns on by itself once the index has vectors and Ollama serves that model (agent-spec-live.py embeds them)"}</span>
              {st.last ? <> · updated <time dateTime={st.last.ts}>{relTime(st.last.ts)}</time></> : null} · nothing leaves this machine</>
          ) : status.isLoading ? "Loading index…" : "The index is empty. It builds in the background while the dashboard runs, or run: agent-spec-platform.py ingest index"}
        </p>
      </form>

      {!q ? (
        <Card>
          <CardHeader title="Try a question" subtitle="Answers come from this project's code, docs, rules, memory and its recorded Cursor requests." />
          <ul className="divide-y divide-border">
            {EXAMPLES.map((e) => (
              <li key={e}><button type="button" onClick={() => submit(e)} className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm hover:bg-muted/50"><Sparkles size={13} className="text-accent" aria-hidden />{e}</button></li>
            ))}
          </ul>
        </Card>
      ) : result.isLoading ? (
        <p className="text-xs text-muted-foreground">Searching…</p>
      ) : result.isError || !r ? (
        <Empty title="Search failed" hint={String(result.error ?? "")} />
      ) : (
        <>
          {r.answer ? (
            <Card>
              <CardHeader title="Answer" subtitle={<span className="font-mono">{r.answer.model} · from the sources below only</span>} right={<Prov p="ai_judged" />} />
              <div className="whitespace-pre-wrap px-4 pb-4 text-sm leading-relaxed">{r.answer.text}</div>
              {r.answer.uncited ? <p className="px-4 pb-3 text-xs text-warning">The answer cites no source; treat it as unverified.</p> : null}
            </Card>
          ) : r.hits.length ? (
            <Card>
              <div className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1 text-xs">
                  <div className="font-medium">Get a cited answer from Cursor</div>
                  <p className="text-muted-foreground">Paste into Cursor: the agent reads these sources with <span className="font-mono">/agent-spec-ask</span> and answers with citations. No answer is generated here without a local model (<span className="font-mono">AGENT_SPEC_LLM=ollama:&lt;model&gt;</span>).</p>
                </div>
                <Button size="sm" onClick={async () => { if (r.cursor_prompt && await copyText(r.cursor_prompt)) { setCopied(true); setTimeout(() => setCopied(false), 1500); } }}>
                  <Copy size={12} />{copied ? "Copied" : "Copy prompt for Cursor"}
                </Button>
              </div>
            </Card>
          ) : null}

          {r.warnings.map((w) => <p key={w} className="text-xs text-warning">{w}</p>)}

          <Card>
            <CardHeader title="Sources" subtitle={<>Ranked by {r.mode === "hybrid" ? "reciprocal rank fusion of BM25 and embedding similarity" : "BM25 over text and split identifiers"}</>}
              right={<span className="flex items-center gap-2"><Num p="measured" className="text-xs">{r.hits.length}</Num><Prov p="measured" /></span>} />
            {r.hits.length ? <ul className="divide-y divide-border">{r.hits.map((h, i) => <HitRow key={h.chunk_id} h={h} n={i + 1} />)}</ul> : (
              <Empty title="Nothing matched" hint="Try different words, remove a filter, or widen the time range." />
            )}
          </Card>

          {r.related?.length ? (
            <Card>
              <CardHeader title="Related by the import graph" subtitle="Files one import away from the matching code (Graphify, exact)." right={<Prov p="measured" />} />
              <ul className="flex flex-wrap gap-2 px-4 pb-4">
                {r.related.map((x) => <li key={x.path}><Badge title={x.relation}>{x.path}</Badge></li>)}
              </ul>
            </Card>
          ) : null}
        </>
      )}
    </div>
  );
}
