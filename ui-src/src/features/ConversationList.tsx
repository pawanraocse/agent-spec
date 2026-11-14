import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, Bot, ChevronDown, ChevronRight, Copy, FileText, Pencil, Search, ShieldAlert, Wrench } from "lucide-react";
import { useConversations, useRequests, type Conversation } from "../api/traces";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Num } from "../components/Num";
import { cn, copyText, fmtMs, relTime } from "../lib/utils";
import { ContextChip } from "./ContextMeter";

const SOURCE_LABEL: Record<string, string> = { hook: "Live hooks", cursor_store: "Cursor history", run: "Workflow run", demo_seed: "Demo seed" };

function base(path?: string | null) {
  return path ? path.replace(/[\\/]+$/, "").split(/[\\/]/).pop() || path : "—";
}

function title(c: Conversation) {
  return (c.name || c.first_prompt || "(untitled chat)").replace(/\s+/g, " ");
}

/** Project → Sessions: every Cursor chat, expandable to its requests; a request opens its trace. */
export function ConversationList() {
  const [q, setQ] = useState("");
  const [source, setSource] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const { data, isLoading, error } = useConversations({ q, source, workspace });
  const rows = data?.conversations ?? [];
  const totals = useMemo(() => rows.reduce((a, c) => ({ requests: a.requests + c.requests, tools: a.tools + c.tool_count, subs: a.subs + c.subagent_count }), { requests: 0, tools: 0, subs: 0 }), [rows]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Cursor sessions</h1>
          <p className="text-xs text-muted-foreground">
            Every chat Cursor recorded — live hook traces and its local history — newest first. Expand a chat to see its requests; open one to see its trace.
          </p>
        </div>
        <p className="text-xs text-muted-foreground tabular-nums">
          <Num p="measured">{data?.total ?? 0}</Num> chats · <Num p="measured">{totals.requests}</Num> requests · <Num p="measured">{totals.tools}</Num> tool calls · <Num p="measured">{totals.subs}</Num> subagents
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="relative w-72">
          <Search size={14} className="absolute left-3 top-2.5 text-muted-foreground" />
          <input
            aria-label="Search chats"
            className="w-full rounded-lg border border-border bg-card py-1.5 pl-9 pr-3 text-xs text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
            placeholder="Search chat names, prompts, ids"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </label>
        <select aria-label="Source" value={source} onChange={(e) => setSource(e.target.value)} className="rounded-lg border border-border bg-card px-2 py-1.5 text-xs">
          <option value="">All sources</option>
          <option value="hook">Live hooks</option>
          <option value="cursor_store">Cursor history</option>
        </select>
        <select aria-label="Workspace" value={workspace} onChange={(e) => setWorkspace(e.target.value)} className="rounded-lg border border-border bg-card px-2 py-1.5 text-xs">
          <option value="">All workspaces</option>
          {(data?.facets.workspaces ?? []).map((w) => <option key={w} value={w}>{base(w)}</option>)}
        </select>
      </div>

      <Card className="divide-y divide-border text-sm">
        {isLoading ? (
          <div className="p-6 text-center text-xs text-muted-foreground">Loading chats…</div>
        ) : error ? (
          <div className="p-6 text-center text-xs text-danger">Could not load chats: {String((error as Error).message || error)}</div>
        ) : rows.length === 0 ? (
          <div className="p-6 text-center text-xs text-muted-foreground">
            No chats match. Cursor history is read from its local store; live chats need the hooks (<code>install.sh --register</code>).
          </div>
        ) : (
          rows.map((c) => <Row key={c.session_id} c={c} open={open === c.session_id} onToggle={() => setOpen(open === c.session_id ? null : c.session_id)} />)
        )}
      </Card>
    </div>
  );
}

function Row({ c, open, onToggle }: { c: Conversation; open: boolean; onToggle: () => void }) {
  return (
    <div>
      <button type="button" onClick={onToggle} aria-expanded={open} className={cn("flex w-full items-start gap-3 p-3 text-left transition-colors hover:bg-muted/50", open && "bg-muted/40")}>
        {open ? <ChevronDown size={14} className="mt-0.5 shrink-0" /> : <ChevronRight size={14} className="mt-0.5 shrink-0" />}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {c.running ? <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-primary" title="A request is still running" /> : null}
            <span className="line-clamp-1 text-xs font-medium text-foreground">{title(c)}</span>
            {c.reviewed ? <Badge tone="success">reviewed</Badge> : null}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted-foreground">
            <time dateTime={c.end ?? undefined}>{relTime(c.end || c.start)}</time>
            <span>{base(c.workspace)}</span>
            <span><Num p="measured">{c.requests}</Num> requests</span>
            <span className="inline-flex items-center gap-0.5"><Wrench size={10} /><Num p="measured">{c.tool_count}</Num></span>
            {c.subagent_count ? <span className="inline-flex items-center gap-0.5 text-k-subagent"><Bot size={10} /><Num p="measured">{c.subagent_count}</Num></span> : null}
            {c.edit_count ? <span className="inline-flex items-center gap-0.5"><Pencil size={10} /><Num p="measured">{c.edit_count}</Num></span> : null}
            {c.guard_count ? <span className="inline-flex items-center gap-0.5 text-k-guard"><ShieldAlert size={10} /><Num p="measured">{c.guard_count}</Num></span> : null}
            {c.error_count ? <span className="inline-flex items-center gap-0.5 text-danger"><AlertTriangle size={10} /><Num p="measured">{c.error_count}</Num></span> : null}
            <span><Num p={c.provenance}>{fmtMs(c.duration_ms)}</Num></span>
            {c.context?.budget ? <ContextChip b={c.context.budget} /> : null}
            {c.skills.slice(0, 3).map((s) => <Badge key={s} tone="accent" className="normal-case">{s.replace(/^agent-spec-/, "")}</Badge>)}
            <span className="ml-auto">{c.sources.map((s) => SOURCE_LABEL[s] ?? s).join(" + ")}</span>
          </div>
        </div>
      </button>
      {open ? <Detail c={c} /> : null}
    </div>
  );
}

function Detail({ c }: { c: Conversation }) {
  const navigate = useNavigate();
  const { data, isLoading } = useRequests({ session: c.session_id }, 500);
  const [copied, setCopied] = useState(false);
  const reqs = [...(data?.requests ?? [])].sort((a, b) => (a.start || "").localeCompare(b.start || ""));
  const review = `/agent-spec-session-review ${c.session_id}`;

  return (
    <div className="space-y-3 border-t border-border/60 bg-muted/20 px-9 py-3">
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
        <span className="font-mono">{c.session_id}</span>
        {c.models.length ? <span>· {c.models.join(", ")}</span> : null}
        <span className="ml-auto flex gap-2">
          <Button size="sm" variant="outline" onClick={async () => { if (await copyText(review)) { setCopied(true); setTimeout(() => setCopied(false), 1500); } }} title="Paste into Cursor to have the agent grade this chat">
            <Copy size={12} />{copied ? "Copied" : "Copy review prompt"}
          </Button>
          {c.has_transcript ? (
            <Button size="sm" variant="outline" onClick={() => navigate(`/project/sessions/${encodeURIComponent(c.session_id)}`)}>
              <FileText size={12} />Transcript analysis
            </Button>
          ) : null}
        </span>
      </div>
      {isLoading ? <p className="text-xs text-muted-foreground">Loading requests…</p> : (
        <ol className="space-y-1">
          {reqs.map((t, i) => (
            <li key={t.trace_id}>
              <button type="button" onClick={() => navigate(`/requests/${encodeURIComponent(t.trace_id)}`)} className="flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-left text-xs hover:bg-card" title="Open this request's trace: graph, waterfall, responses, replay">
                <span className="w-6 shrink-0 text-right tabular-nums text-muted-foreground">{i + 1}</span>
                <span className={cn("h-2 w-2 shrink-0 rounded-full", t.status === "running" ? "animate-pulse bg-primary" : t.error_count ? "bg-danger" : "bg-success")} />
                <span className="line-clamp-1 flex-1">{(t.prompt || "(prompt not captured)").replace(/\s+/g, " ")}</span>
                <span className="shrink-0 tabular-nums text-[10px] text-muted-foreground">
                  <Num p="measured">{t.tool_count}</Num> tools{t.subagent_count ? <> · <Num p="measured">{t.subagent_count}</Num> sub</> : null} · <Num p={t.provenance}>{fmtMs(t.duration_ms)}</Num>
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
