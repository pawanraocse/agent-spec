import { Copy, FileText } from "lucide-react";
import { useState } from "react";
import type { Handoff, Span, Trace } from "../api/traces";
import { Num, Prov } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Sheet } from "../components/ui/sheet";
import { copyText, fmtBytes, fmtMs } from "../lib/utils";
import { HandoffView } from "./HandoffView";
import { kindMeta, statusTone } from "./kinds";

const TEXT_KEYS = ["task", "summary", "text", "target", "error_message", "description", "detail"];

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-2 border-b border-border/60 py-1.5 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0 break-words">{children}</span>
    </div>
  );
}

/** DV-032 inspector: input, output, duration, subagent task/summary/files, transcript link,
 *  and a ready-made prompt to hand the span to an agent (AI-first: the agent investigates). */
export function SpanInspector({ span, members, trace, onClose }: { span: Span | null; members: Span[]; trace?: Trace; onClose: () => void }) {
  const [copied, setCopied] = useState<string | null>(null);
  if (!span) return null;
  const meta = kindMeta(span.kind);
  const a = span.attributes || {};
  const prov = trace?.provenance ?? "measured";
  const handoff = (a.handoff as Handoff | undefined) ?? null;
  // A typed side replaces its raw text; an untyped side keeps it (DV-057).
  const typedKeys = new Set([handoff?.input?.typed ? "task" : "", handoff?.output?.typed ? "summary" : ""]);
  const files = Array.isArray(a.modified_files) ? (a.modified_files as string[]) : [];
  const transcript = (a.agent_transcript_path as string) || trace?.transcript_path || "";
  const investigate = `/agent-spec-investigate In request ${span.trace_id}, the ${meta.label.toLowerCase()} span "${span.name}" (${span.span_id}) took ${fmtMs(span.duration_ms)} with status ${span.status}. Read it with \`agent-spec-platform.py trace --request ${span.trace_id}\` and explain why, citing span ids.`;
  const copy = async (key: string, text: string) => {
    if (await copyText(text)) {
      setCopied(key);
      window.setTimeout(() => setCopied(null), 1500);
    }
  };
  return (
    <Sheet
      open={!!span}
      onOpenChange={(o) => !o && onClose()}
      title={
        <span className="flex items-center gap-2">
          <meta.icon size={14} className={meta.color} />
          {span.kind === "prompt" ? "Request" : span.name}
          {members.length > 1 ? <Badge>×{members.length}</Badge> : null}
        </span>
      }
      description={<span className="font-mono">{span.span_id}</span>}
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge tone={statusTone(span.status)}>{span.status}</Badge>
        <Badge tone="accent">{meta.label}</Badge>
        <Prov p={prov} />
      </div>
      <Field label="Duration"><Num p={prov}>{fmtMs(members.length > 1 ? members.reduce((x, m) => x + (m.duration_ms ?? 0), 0) : span.duration_ms)}</Num>{a.timing ? <span className="ml-2 text-muted-foreground">({String(a.timing)})</span> : null}</Field>
      <Field label="Start">{span.start ?? "—"}</Field>
      <Field label="End">{span.end ?? (span.status === "running" ? "running" : "—")}</Field>
      {typeof a.bytes_in === "number" ? <Field label="Handed in"><Num p="measured">{fmtBytes(a.bytes_in as number)}</Num></Field> : null}
      {typeof a.bytes_out === "number" ? <Field label="Handed back"><Num p="measured">{fmtBytes(a.bytes_out as number)}</Num></Field> : null}
      {typeof a.tool_call_count === "number" ? <Field label="Tool calls"><Num p="measured">{a.tool_call_count as number}</Num></Field> : null}
      {typeof a.message_count === "number" ? <Field label="Messages"><Num p="measured">{a.message_count as number}</Num></Field> : null}
      {a.subagent_model || a.model ? <Field label="Model">{String(a.subagent_model || a.model)}</Field> : null}
      {a.failure_type ? <Field label="Failure">{String(a.failure_type)}</Field> : null}
      {a.ranged !== undefined ? <Field label="Ranged read">{a.ranged ? "yes" : "no — whole file"}</Field> : null}
      {a.rule ? <Field label="Guard rule">{String(a.rule)}</Field> : null}
      {files.length ? (
        <Field label="Files modified">
          <ul className="space-y-0.5 font-mono text-[11px]">{files.map((f) => <li key={f} className="truncate">{f}</li>)}</ul>
        </Field>
      ) : null}
      {handoff ? <HandoffView handoff={handoff} /> : null}
      {TEXT_KEYS.filter((k) => a[k] && !typedKeys.has(k)).map((k) => (
        <div key={k} className="mt-3">
          <p className="mb-1 text-[11px] uppercase tracking-wide text-muted-foreground">{k.replace("_", " ")}</p>
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-2 font-mono text-[11px] leading-relaxed">{String(a[k])}</pre>
        </div>
      ))}
      {members.length > 1 ? (
        <div className="mt-3">
          <p className="mb-1 text-[11px] uppercase tracking-wide text-muted-foreground">Folded calls</p>
          <ul className="space-y-1">
            {members.map((m) => (
              <li key={m.span_id} className="flex items-center justify-between gap-2 rounded bg-muted/60 px-2 py-1 text-[11px]">
                <span className="truncate font-mono">{String(m.attributes?.target ?? m.span_id)}</span>
                <Num p={prov} className="shrink-0 whitespace-nowrap">{fmtMs(m.duration_ms)}</Num>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="mt-5 flex flex-wrap gap-2">
        <Button size="sm" onClick={() => copy("inv", investigate)}><Copy size={12} />{copied === "inv" ? "Copied" : "Copy investigate prompt"}</Button>
        {transcript ? (
          <Button size="sm" variant="outline" onClick={() => copy("tr", transcript)} title={transcript}><FileText size={12} />{copied === "tr" ? "Copied" : "Copy transcript path"}</Button>
        ) : null}
      </div>
    </Sheet>
  );
}
