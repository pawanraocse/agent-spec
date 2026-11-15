import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Check, Copy, Cpu, ExternalLink, Loader2, Send, Square, Wrench, User } from "lucide-react";
import { apiGet, apiPost, getToken } from "../api/client";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardHeader } from "../components/ui/card";
import { cn, copyText, fmtMs } from "../lib/utils";

type AgentStatus = {
  enabled: boolean; backend: "ollama" | "cursor-agent" | "fake" | null; models: string[];
  default_model: string | null; endpoint: string | null; hint: string | null;
};
type ToolChip = { id: string; name: string; status: string; args?: Record<string, unknown> };
type Turn = {
  prompt: string; text: string; tools: ToolChip[]; state: "running" | "done" | "error";
  requestId?: string; model?: string; usage?: { input_tokens?: number; output_tokens?: number };
  started: number; ms?: number; error?: string; jobId?: string;
};

/** Prompts that exercise the harness: graph-first context, ranged reads, memory, RAG. */
const TEMPLATES = [
  { label: "Find the code", prompt: "Which source file computes the dashboard's tokens-saved estimate from whole-file reads? Name the file and the function." },
  { label: "Blast radius", prompt: "What depends on bin/aspec_platform/retrieval.py? List the files a change there could break." },
  { label: "How it works", prompt: "How does the Agent Console pick its agent backend? Name the file and the function." },
  { label: "Review a file", prompt: "Read bin/aspec_platform/ollama.py in ranges and name the single biggest risk in it, with the line." },
  { label: "Past sessions", prompt: "What did the last session change? Use the project's memory and past requests." },
];

function argSummary(args?: Record<string, unknown>): string {
  if (!args) return "";
  const v = args.file_path ?? args.pattern ?? args.command ?? args.task ?? "";
  const range = args.offset !== undefined || args.limit !== undefined ? ` [${args.offset ?? 1}+${args.limit ?? ""}]` : "";
  return String(v).replace(/^.*graphify-cli\.py /, "graphify ").slice(0, 90) + range;
}

async function streamJob(jobId: string, onFrame: (event: string, data: Record<string, unknown>) => void, signal: AbortSignal) {
  const res = await fetch(`/api/agent/jobs/${jobId}/stream`, { headers: { "X-Agent-Spec-Token": getToken() }, signal });
  if (!res.ok || !res.body) throw new Error(`stream ${res.status}`);
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let cut: number;
    while ((cut = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, cut);
      buf = buf.slice(cut + 2);
      const ev = /^event: (.*)$/m.exec(block)?.[1] ?? "message";
      const raw = /^data: (.*)$/m.exec(block)?.[1];
      if (!raw) continue;
      try { onFrame(ev, JSON.parse(raw)); } catch { /* a malformed frame is skipped, not fatal */ }
    }
  }
}

export function Console() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["agent-status"], queryFn: () => apiGet<AgentStatus>("/api/agent/status"), refetchInterval: 30000 });
  const [model, setModel] = useState("");
  const [mode, setMode] = useState<"ask" | "plan">("ask");
  const [prompt, setPrompt] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [chatId, setChatId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const s = status.data;
  const running = turns.some((t) => t.state === "running");

  useEffect(() => { if (s?.default_model && !model) setModel(s.default_model); }, [s?.default_model, model]);
  useEffect(() => { bottom.current?.scrollIntoView({ block: "end" }); }, [turns]);

  const patch = (i: number, f: (t: Turn) => Turn) => setTurns((ts) => ts.map((t, j) => (j === i ? f(t) : t)));

  async function send(text: string) {
    const p = text.trim();
    if (!p || running || !s?.enabled) return;
    const idx = turns.length;
    setTurns((ts) => [...ts, { prompt: p, text: "", tools: [], state: "running", started: Date.now() }]);
    setPrompt("");
    const body = { prompt: p, mode, ...(s.backend === "ollama" && model ? { model } : {}) };
    const path = chatId ? `/api/agent/sessions/${encodeURIComponent(chatId)}/messages` : "/api/agent/sessions";
    type Launch = { ok?: boolean; job_id?: string; error?: string; hint?: string };
    const r: Launch = await apiPost<Launch>(path, body).catch((e): Launch => ({ ok: false, error: String(e) }));
    if (!r.ok || !r.job_id) {
      patch(idx, (t) => ({ ...t, state: "error", error: [r.error, r.hint].filter(Boolean).join(" — ") }));
      return;
    }
    const jobId = r.job_id;
    patch(idx, (t) => ({ ...t, jobId }));
    abort.current = new AbortController();
    try {
      await streamJob(jobId, (ev, d) => {
        if (ev === "session") {
          if (typeof d.session_id === "string") setChatId(d.session_id);
          patch(idx, (t) => ({ ...t, requestId: (d.request_id as string) ?? t.requestId, model: (d.model as string) ?? t.model }));
        } else if (ev === "message") {
          patch(idx, (t) => ({ ...t, text: t.text + String(d.chunk ?? "") }));
        } else if (ev === "tool") {
          patch(idx, (t) => {
            const id = String(d.call_id || d.name);
            const known = t.tools.find((x) => x.id === id);
            const chip = { id, name: String(d.name), status: String(d.status), args: known?.args ?? (d.args as Record<string, unknown>) };
            return { ...t, tools: known ? t.tools.map((x) => (x.id === id ? chip : x)) : [...t.tools, chip] };
          });
        } else if (ev === "done") {
          patch(idx, (t) => {
            if (d.final) {
              const failed = d.exit_code !== 0 && t.state !== "done";
              return { ...t, state: failed ? "error" : "done", ms: t.ms ?? Date.now() - t.started,
                       error: failed ? String(d.stderr || `agent exited ${d.exit_code}`) : t.error };
            }
            return { ...t, state: "done", text: String(d.chunk || t.text), ms: Date.now() - t.started,
                     usage: (d.usage as Turn["usage"]) ?? t.usage, requestId: (d.request_id as string) ?? t.requestId,
                     error: String(d.chunk || "").startsWith("error:") ? String(d.chunk) : undefined };
          });
        } else if (ev === "error") {
          patch(idx, (t) => ({ ...t, state: "error", error: String(d.error ?? "stream error") }));
        }
      }, abort.current.signal);
    } catch (e) {
      patch(idx, (t) => (t.state === "running" ? { ...t, state: "error", error: String(e) } : t));
    } finally {
      patch(idx, (t) => (t.state === "running" ? { ...t, state: "done", ms: Date.now() - t.started } : t));
      qc.invalidateQueries();
    }
  }

  async function stop() {
    const t = turns.find((x) => x.state === "running");
    abort.current?.abort();
    if (t?.jobId) await apiPost(`/api/agent/jobs/${t.jobId}/cancel`, {}).catch(() => undefined);
  }

  const backendLabel = s?.backend === "ollama" ? "Ollama · local · $0" : s?.backend === "cursor-agent" ? "cursor-agent" : s?.backend ?? "none";

  return (
    <div className="mx-auto flex h-full max-w-5xl flex-col gap-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border pb-4">
        <div>
          <h1 className="text-xl font-semibold">Agent Console</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Ask the harnessed agent from the dashboard. Every answer is traced: tools, tokens, savings and rules land in Live.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Badge tone={s?.enabled ? "success" : "warning"}><Cpu size={11} />{backendLabel}</Badge>
          {s?.backend === "ollama" && (
            <select aria-label="Model" value={model} onChange={(e) => setModel(e.target.value)}
                    className="h-7 rounded border border-border bg-card px-2 text-xs" disabled={running}>
              {s.models.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          )}
          <select aria-label="Mode" value={mode} onChange={(e) => setMode(e.target.value as "ask" | "plan")}
                  className="h-7 rounded border border-border bg-card px-2 text-xs" disabled={running}>
            <option value="ask">ask (read-only)</option>
            <option value="plan">plan</option>
          </select>
          {chatId && <Button size="sm" variant="outline" disabled={running} onClick={() => { setChatId(null); setTurns([]); }}>New chat</Button>}
        </div>
      </div>

      {s && !s.enabled && (
        <Card className="border-warning/40 p-4 text-xs text-warning">{s.hint}</Card>
      )}

      <div className="flex flex-wrap gap-1.5" aria-label="Prompt templates">
        {TEMPLATES.map((t) => (
          <button key={t.label} type="button" disabled={running || !s?.enabled}
                  onClick={() => setPrompt(t.prompt)}
                  className="rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground hover:border-primary hover:text-primary disabled:opacity-50">
            {t.label}
          </button>
        ))}
      </div>

      <div className="min-h-[240px] flex-1 space-y-4 overflow-auto" aria-live="polite">
        {turns.length === 0 && (
          <Card className="p-6 text-center text-xs text-muted-foreground">
            Pick a template or type a question. The agent reads the dependency graph before files, reads in ranges,
            and the harness guard blocks wasteful calls — watch the tool chips.
          </Card>
        )}
        {turns.map((t, i) => (
          <div key={i} className="space-y-2">
            <div className="flex items-start gap-2 text-sm">
              <User size={15} className="mt-0.5 shrink-0 text-muted-foreground" />
              <p className="whitespace-pre-wrap">{t.prompt}</p>
            </div>
            <Card className="ml-6 overflow-hidden">
              <CardHeader
                title={<span className="flex items-center gap-1.5"><Bot size={14} />{t.model ?? "agent"}</span>}
                right={
                  <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                    {t.state === "running" && <Loader2 size={13} className="animate-spin text-primary" />}
                    {t.usage && <span className="tabular">{(t.usage.input_tokens ?? 0).toLocaleString()} in · {(t.usage.output_tokens ?? 0).toLocaleString()} out</span>}
                    {t.ms !== undefined && <span className="tabular">{fmtMs(t.ms)}</span>}
                    {t.requestId && t.state !== "running" && (
                      <Link to={`/requests/${t.requestId}`} className="flex items-center gap-1 text-primary hover:underline">
                        trace <ExternalLink size={11} />
                      </Link>
                    )}
                  </div>
                }
              />
              {t.tools.length > 0 && (
                <div className="flex flex-wrap gap-1.5 border-b border-border px-4 py-2">
                  {t.tools.map((c) => (
                    <span key={c.id} className={cn("inline-flex max-w-full items-center gap-1 truncate rounded border px-1.5 py-0.5 font-mono text-[11px]",
                      c.status === "completed" ? "border-success/40 text-success" : c.status === "error" ? "border-danger/40 text-danger" : "border-primary/40 text-primary")}>
                      <Wrench size={10} />{c.name} <span className="truncate text-muted-foreground">{argSummary(c.args)}</span>
                    </span>
                  ))}
                </div>
              )}
              <div className="whitespace-pre-wrap px-4 py-3 text-sm leading-relaxed">
                {t.text || (t.state === "running" ? <span className="text-muted-foreground">thinking…</span> : null)}
                {t.error && <p className="mt-2 text-xs text-danger">{t.error}</p>}
              </div>
            </Card>
          </div>
        ))}
        <div ref={bottom} />
      </div>

      <form className="sticky bottom-0 flex items-end gap-2 bg-background pt-2"
            onSubmit={(e) => { e.preventDefault(); void send(prompt); }}>
        <textarea aria-label="Prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={2}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(prompt); } }}
                  placeholder={chatId ? "Follow up in this chat…" : "Ask about this project…"}
                  disabled={!s?.enabled}
                  className="min-h-[44px] flex-1 resize-y rounded-lg border border-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
        <Button type="button" variant="outline" size="icon" title="Copy for Cursor chat" aria-label="Copy for Cursor chat"
                disabled={!prompt.trim()} onClick={async () => { if (await copyText(prompt)) { setCopied(true); setTimeout(() => setCopied(false), 2000); } }}>
          {copied ? <Check size={14} /> : <Copy size={14} />}
        </Button>
        {running
          ? <Button type="button" variant="danger" size="icon" aria-label="Stop" onClick={() => void stop()}><Square size={14} /></Button>
          : <Button type="submit" size="icon" aria-label="Send" disabled={!prompt.trim() || !s?.enabled}><Send size={14} /></Button>}
      </form>
    </div>
  );
}
