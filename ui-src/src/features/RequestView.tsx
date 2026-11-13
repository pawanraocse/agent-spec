import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Copy, Gauge, Pause, Play, Rewind } from "lucide-react";
import type { RequestDetail, Span } from "../api/traces";
import { Num, Prov } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Empty } from "../components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { copyText, fmtMs } from "../lib/utils";
import { statusTone } from "./kinds";
import { SpanInspector } from "./SpanInspector";
import { timeBounds } from "./spanTree";
import { Waterfall } from "./Waterfall";

const OrchestrationGraph = lazy(() => import("./OrchestrationGraph"));
const SPEEDS = [1, 4, 16];

/** DV-034: replay a trace at real speed (or faster) — spans appear at their recorded offsets. */
function useReplay(spans: Span[]) {
  const [lo, hi] = useMemo(() => timeBounds(spans), [spans]);
  const [at, setAt] = useState<number | null>(null);
  const [speed, setSpeed] = useState(1);
  const [playing, setPlaying] = useState(false);
  const raf = useRef<number | null>(null);
  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = (now - last) * speed;
      last = now;
      setAt((cur) => {
        const next = (cur ?? 0) + dt;
        if (next >= hi - lo) {
          setPlaying(false);
          return hi - lo;
        }
        return next;
      });
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [playing, speed, lo, hi]);
  const visible = useMemo(() => {
    if (at === null) return spans;
    const cut = lo + at;
    return spans
      .filter((s) => !s.start || new Date(s.start).getTime() <= cut)
      .map((s) => {
        const end = s.end ? new Date(s.end).getTime() : null;
        return end !== null && end > cut ? { ...s, status: "running", end: null } : s;
      });
  }, [spans, at, lo]);
  return {
    visible, at, total: hi - lo, speed, playing,
    start: () => { setAt(0); setPlaying(true); },
    toggle: () => setPlaying((p) => !p),
    stop: () => { setPlaying(false); setAt(null); },
    cycleSpeed: () => setSpeed((s) => SPEEDS[(SPEEDS.indexOf(s) + 1) % SPEEDS.length]),
  };
}

export function RequestView({ detail }: { detail: RequestDetail }) {
  const { trace, spans, responses, review } = detail;
  const [sel, setSel] = useState<{ span: Span; members: Span[] } | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const replay = useReplay(spans);
  const shown = replay.visible;
  const prov = trace.provenance;
  const reviewPrompt = `/agent-spec-session-review ${trace.session_id}`;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="border-b border-border px-5 py-3">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="line-clamp-2 text-sm font-medium" title={trace.prompt ?? ""}>{(trace.prompt || "(prompt not captured)").slice(0, 200)}</p>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
              <Badge tone={statusTone(trace.status)}>{trace.status}</Badge>
              <span>Duration <Num p={prov} className="text-foreground">{fmtMs(trace.duration_ms)}</Num></span>
              {trace.model ? <span>Model <span className="font-mono text-foreground">{trace.model}</span></span> : null}
              {trace.cursor_version ? <span>Cursor <span className="font-mono text-foreground">{trace.cursor_version}</span></span> : null}
              <span>Spans <Num p="measured" className="text-foreground">{trace.span_count}</Num></span>
              {trace.skills.map((s) => <Badge key={s} tone="accent" className="normal-case">/{s}</Badge>)}
              <Prov p={prov} />
              {trace.source === "cursor_store" ? <span title="Read from Cursor's local database; not a documented interface">Cursor local store (unofficial)</span> : null}
              {replay.at !== null ? <Badge tone="warning">Recorded · replay</Badge> : null}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            {replay.at === null ? (
              <Button size="sm" variant="outline" onClick={replay.start} title="Replay this request at recorded speed"><Play size={12} />Replay</Button>
            ) : (
              <>
                <Button size="icon" variant="outline" onClick={replay.toggle} aria-label={replay.playing ? "Pause" : "Play"}>{replay.playing ? <Pause size={13} /> : <Play size={13} />}</Button>
                <Button size="sm" variant="outline" onClick={replay.cycleSpeed} aria-label="Replay speed"><Gauge size={12} />{replay.speed}×</Button>
                <Button size="icon" variant="ghost" onClick={replay.stop} aria-label="Stop replay"><Rewind size={13} /></Button>
              </>
            )}
          </div>
        </div>
        {replay.at !== null ? (
          <div className="mt-2 h-1 overflow-hidden rounded bg-muted">
            <div className="h-full bg-warning transition-[width]" style={{ width: `${Math.min(100, (replay.at / Math.max(replay.total, 1)) * 100)}%` }} />
          </div>
        ) : null}
      </header>

      <Tabs defaultValue="graph" className="flex min-h-0 flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-border px-5 py-2">
          <TabsList>
            <TabsTrigger value="graph">Orchestration</TabsTrigger>
            <TabsTrigger value="waterfall">Waterfall</TabsTrigger>
            <TabsTrigger value="responses">Responses <span className="ml-1 text-muted-foreground"><Num p="measured">{responses.length}</Num></span></TabsTrigger>
            <TabsTrigger value="review">Review {review?.grade ? <Badge tone="accent" className="ml-1">{review.grade}</Badge> : null}</TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="graph" className="flex min-h-0 flex-1 flex-col">
          <div className="min-h-[300px] flex-[3] border-b border-border">
            <Suspense fallback={<div className="p-6 text-xs text-muted-foreground">Loading graph…</div>}>
              <OrchestrationGraph spans={shown} provenance={prov} selected={sel?.span.span_id} hovered={hover} onHover={setHover} onSelect={(span, members) => setSel({ span, members })} />
            </Suspense>
          </div>
          <div className="scrollbar-thin min-h-[140px] flex-[2] overflow-auto">
            <Waterfall spans={shown} provenance={prov} selected={sel?.span.span_id} hovered={hover} onHover={setHover} onSelect={(span, members) => setSel({ span, members })} />
          </div>
        </TabsContent>
        <TabsContent value="waterfall" className="scrollbar-thin min-h-0 flex-1 overflow-auto">
          <Waterfall spans={shown} provenance={prov} selected={sel?.span.span_id} hovered={hover} onHover={setHover} onSelect={(span, members) => setSel({ span, members })} />
        </TabsContent>
        <TabsContent value="responses" className="scrollbar-thin min-h-0 flex-1 overflow-auto px-5 py-4">
          {responses.length === 0 ? <Empty title="No responses recorded" hint="afterAgentResponse fires when the agent finishes a message; the hook must be registered (install.sh --register)." /> : (
            <ol className="space-y-3">
              {responses.map((r, i) => (
                <li key={r.span_id} className="rounded-lg border border-border bg-card p-3">
                  <div className="mb-1.5 flex items-center justify-between text-[10px] text-muted-foreground">
                    <span>Response <Num p="measured">{i + 1}</Num></span>
                    <time>{r.ts}</time>
                  </div>
                  <p className="whitespace-pre-wrap text-xs leading-relaxed">{r.text}</p>
                </li>
              ))}
            </ol>
          )}
        </TabsContent>
        <TabsContent value="review" className="scrollbar-thin min-h-0 flex-1 overflow-auto px-5 py-4">
          {!review ? (
            <Empty
              title="Not reviewed"
              hint="Reviews are written by the agent-spec-session-review skill, never computed. Paste this into Cursor to have the agent judge this conversation; the result appears here."
              action={
                <Button size="sm" onClick={async () => { if (await copyText(reviewPrompt)) { setCopied(true); setTimeout(() => setCopied(false), 1500); } }}>
                  <Copy size={12} />{copied ? "Copied" : reviewPrompt}
                </Button>
              }
            />
          ) : (
            <div className="space-y-4">
              <div className="flex items-start gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-lg bg-accent/10 text-2xl font-bold text-accent" data-provenance="ai_judged">{review.grade ?? "?"}</div>
                <div className="min-w-0 text-xs">
                  <div className="flex items-center gap-2"><Prov p="ai_judged" /><span className="font-mono text-muted-foreground">{review.model} · rubric {review.rubric_version}</span></div>
                  <p className="mt-1.5 leading-relaxed">{review.summary}</p>
                </div>
              </div>
              <ul className="space-y-2">
                {(review.findings ?? []).map((f, i) => (
                  <li
                    key={i}
                    onMouseEnter={() => f.span_id && setHover(f.span_id)}
                    onMouseLeave={() => setHover(null)}
                    className="rounded-lg border border-border bg-card p-3 text-xs hover:border-primary/50"
                  >
                    <div className="flex items-center gap-2">
                      <Badge tone={f.severity === "high" ? "danger" : f.severity === "low" ? "neutral" : "warning"}>{f.severity}</Badge>
                      <span className="font-medium">{f.title}</span>
                      <span className="ml-auto font-mono text-[10px] text-muted-foreground">{f.category}</span>
                    </div>
                    {f.detail ? <p className="mt-1.5 text-muted-foreground">{f.detail}</p> : null}
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {f.span_id ? (
                        <button type="button" className="font-mono text-[10px] text-primary hover:underline" onClick={() => {
                          const s = spans.find((x) => x.span_id === f.span_id);
                          if (s) setSel({ span: s, members: [s] });
                        }}>{f.span_id}</button>
                      ) : null}
                      {f.fix_prompt ? <Button size="sm" variant="subtle" onClick={() => copyText(f.fix_prompt!)}><Copy size={11} />Copy fix prompt</Button> : null}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </TabsContent>
      </Tabs>
      <SpanInspector span={sel?.span ?? null} members={sel?.members ?? []} trace={trace} onClose={() => setSel(null)} />
    </div>
  );
}
