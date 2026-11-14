import { useState } from "react";
import { Check, Copy, Info, RotateCcw } from "lucide-react";
import type { ContextBudget, ContextInfo } from "../api/traces";
import { Num, Prov } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { cn, copyText, fmtTokens } from "../lib/utils";

/** Cursor's own promptTokenBreakdown categories, in the order they sit in the prompt. */
export const CONTEXT_CATEGORIES: { id: string; label: string; color: string; fixed: boolean }[] = [
  { id: "system_prompt", label: "System prompt", color: "hsl(var(--k-prompt))", fixed: true },
  { id: "tools", label: "Tool definitions", color: "hsl(var(--k-tool))", fixed: true },
  { id: "rules", label: "Rules", color: "hsl(var(--k-edit))", fixed: true },
  { id: "skills", label: "Skills", color: "hsl(var(--k-skill))", fixed: true },
  { id: "mcp", label: "MCP & dynamic tools", color: "hsl(var(--k-workflow))", fixed: true },
  { id: "subagents", label: "Subagent definitions", color: "hsl(var(--k-subagent))", fixed: true },
  { id: "summarized_conversation", label: "Summarized conversation", color: "hsl(var(--k-compact))", fixed: false },
  { id: "conversation", label: "Conversation", color: "hsl(var(--primary))", fixed: false },
];

const COMPACT = "/agent-spec-compact";

type Segment = { id: string; label: string; color: string; tokens: number; fixed: boolean };

/** Segments to draw: Cursor's breakdown when it has one, else fixed floor + carried conversation. */
export function segments(b: ContextBudget): Segment[] {
  const bd = b.breakdown;
  if (bd && Object.keys(bd).length) {
    const known = CONTEXT_CATEGORIES.filter((c) => (bd[c.id] ?? 0) > 0).map((c) => ({ ...c, tokens: bd[c.id] }));
    const other = Object.entries(bd).filter(([k, v]) => v > 0 && !CONTEXT_CATEGORIES.some((c) => c.id === k));
    return [...known, ...other.map(([k, v]) => ({ id: k, label: k, color: "hsl(var(--muted-foreground))", tokens: v, fixed: true }))];
  }
  return [
    { id: "fixed", label: "Fresh-chat base", color: "hsl(var(--k-prompt))", tokens: b.floor, fixed: true },
    { id: "conversation", label: "Conversation", color: "hsl(var(--primary))", tokens: Math.max(0, b.used - b.floor), fixed: false },
  ];
}

export function verdictTone(v: ContextBudget["verdict"]): "danger" | "neutral" | "success" {
  return v === "reset" ? "danger" : v === "fresh" ? "success" : "neutral";
}

/** Stacked bar of what one model call sends, scaled to the context window, with the fresh-chat floor marked. */
export function CompositionBar({ b, height = 10, showFloor = true }: { b: ContextBudget; height?: number; showFloor?: boolean }) {
  const segs = segments(b);
  const scale = Math.max(b.limit ?? 0, b.used, 1);
  const pct = (n: number) => `${Math.max(0, Math.min(100, (n / scale) * 100))}%`;
  return (
    <div className="relative w-full" style={{ height }} role="img"
      aria-label={`Context ${b.used} of ${b.limit ?? "unknown"} tokens; a fresh chat is ${b.floor}`}>
      <div className="absolute inset-0 overflow-hidden rounded-full bg-muted">
        <div className="flex h-full" style={{ width: pct(b.used) }}>
          {segs.map((s) => (
            <div key={s.id} title={`${s.label}: ${s.tokens.toLocaleString("en-US")} tokens`}
              className="h-full transition-[flex-grow] duration-700 ease-out motion-reduce:transition-none"
              style={{ flexGrow: s.tokens, flexBasis: 0, background: s.color, opacity: s.fixed ? 0.75 : 1 }} />
          ))}
        </div>
      </div>
      {showFloor && b.floor < b.used ? (
        <div className="absolute -top-1 -bottom-1 w-px bg-foreground/70" style={{ left: pct(b.floor) }} title={`A fresh chat starts at ${b.floor.toLocaleString("en-US")} tokens`} />
      ) : null}
    </div>
  );
}

/** Compact chip for list rows: mini bar + context size + verdict dot. */
export function ContextChip({ b }: { b: ContextBudget }) {
  const title = b.verdict === "reset"
    ? `Re-sends ${b.used.toLocaleString("en-US")} tokens per model call; a new chat pays back in ${b.breakeven_calls} calls`
    : `Re-sends ${b.used.toLocaleString("en-US")} tokens per model call (${b.growth}x a fresh chat)`;
  return (
    <span className="inline-flex items-center gap-1.5" title={title}>
      <span className="w-12"><CompositionBar b={b} height={5} showFloor={false} /></span>
      <Num p="measured" className={cn(b.verdict === "reset" && "font-medium text-danger")}>{fmtTokens(b.used)}</Num>
      {b.verdict === "reset" ? <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-danger motion-reduce:animate-none" aria-label="Reset recommended" /> : null}
    </span>
  );
}

function CopyCompact({ label = "Copy " + COMPACT }: { label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <Button size="sm" variant="outline" onClick={async () => { if (await copyText(COMPACT)) { setDone(true); setTimeout(() => setDone(false), 1500); } }}
      title="Writes the state to disk; then continue in a new Cursor chat">
      {done ? <Check size={12} /> : <Copy size={12} />}{done ? "Copied" : label}
    </Button>
  );
}

/** Per-request billed input as bars; the current request is highlighted. */
function BilledBars({ points, generations, current }: { points: number[]; generations?: string[]; current?: string }) {
  const max = Math.max(...points, 1);
  const w = 100 / points.length;
  return (
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" className="h-12 w-full" role="img" aria-label="Input tokens billed per request">
      {points.map((v, i) => {
        const h = Math.max(1.5, (v / max) * 30);
        const on = current && generations?.[i] === current;
        return (
          <rect key={i} x={i * w + w * 0.15} width={w * 0.7} y={32 - h} height={h} rx={0.6}
            fill={on ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))"} opacity={on ? 1 : 0.45}>
            <title>{`Request ${i + 1}: ${v.toLocaleString("en-US")} input tokens billed`}</title>
          </rect>
        );
      })}
    </svg>
  );
}

/** Full context card: verdict, composition, the reset arithmetic, and per-request billing. */
export function ContextMeter({ ctx, currentGeneration }: { ctx: ContextInfo; currentGeneration?: string }) {
  const b = ctx.budget;
  const billed = ctx.billed;
  const [why, setWhy] = useState(false);
  return (
    <div className="space-y-4">
      {b ? (
        <>
          <div className={cn("flex flex-wrap items-center gap-3 rounded-lg border px-4 py-3",
            b.verdict === "reset" ? "border-danger/40 bg-danger/5" : b.verdict === "fresh" ? "border-success/30 bg-success/5" : "border-border bg-card")}>
            <RotateCcw size={16} className={b.verdict === "reset" ? "text-danger" : "text-muted-foreground"} />
            <div className="min-w-0 flex-1 text-sm">
              {b.verdict === "reset" ? (
                <>Start a new chat: it pays for itself in <Num p="estimated" className="font-semibold">{b.breakeven_calls}</Num> model calls, then saves <Num p="estimated" className="font-semibold">{fmtTokens(b.saving_per_call)}</Num> weighted tokens on every call.</>
              ) : b.verdict === "carry" ? (
                <>Carry on. A new chat would take <Num p="estimated" className="font-semibold">{b.breakeven_calls}</Num> model calls to pay back.</>
              ) : (
                <>This chat is at its fresh-chat size; there is nothing to reset.</>
              )}
            </div>
            {b.nudged ? <Badge tone="warning">Hook nudged</Badge> : null}
            <Prov p="measured" />
            {b.verdict === "reset" ? <CopyCompact /> : null}
          </div>

          <div>
            <div className="mb-1.5 flex items-baseline justify-between text-xs">
              <span className="text-muted-foreground">Every model call re-sends</span>
              <span>
                <Num p="measured" className="text-base font-semibold">{b.used.toLocaleString("en-US")}</Num>
                <span className="text-muted-foreground"> tokens{b.limit ? <> of <Num p="measured">{fmtTokens(b.limit)}</Num> (<Num p="measured">{b.percent}</Num>%)</> : null}</span>
              </span>
            </div>
            <CompositionBar b={b} height={14} />
            <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
              <span>fresh chat <Num p="measured">{fmtTokens(b.floor)}</Num></span>
              <span><Num p="measured">{b.growth}</Num>× a fresh chat</span>
            </div>
            <ul className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-[11px] sm:grid-cols-3">
              {segments(b).map((s) => (
                <li key={s.id} className="flex items-center gap-1.5">
                  <span className="h-2 w-2 shrink-0 rounded-sm" style={{ background: s.color, opacity: s.fixed ? 0.75 : 1 }} />
                  <span className="truncate text-muted-foreground">{s.label}</span>
                  <Num p="estimated" className="ml-auto" title="Cursor's own estimate per category">{fmtTokens(s.tokens)}</Num>
                </li>
              ))}
            </ul>
            <p className="mt-1 text-[10px] text-muted-foreground">
              Categories are Cursor's own breakdown. Faded segments stay after a reset; the conversation does not. Floor: {b.floor_source ?? "fresh chat"}.
            </p>
          </div>

          <div>
            <button type="button" onClick={() => setWhy(!why)} className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground">
              <Info size={11} />{why ? "Hide" : "Show"} the arithmetic
            </button>
            {why ? (
              <table className="mt-2 w-full max-w-md text-[11px]">
                <tbody className="[&_td]:py-0.5">
                  <tr><td className="text-muted-foreground">Carry: context × read weight</td><td className="text-right"><Num p="estimated" title="Weighted tokens: price ratios configured in context_budget.py (cache read 0.1x, write 1.25x), not measured">{b.carry_per_call.toLocaleString("en-US")}</Num> per call</td></tr>
                  <tr><td className="text-muted-foreground">Reset once: floor × write weight</td><td className="text-right"><Num p="estimated" title="Weighted tokens: price ratios configured in context_budget.py (cache read 0.1x, write 1.25x), not measured">{b.reset_once.toLocaleString("en-US")}</Num></td></tr>
                  <tr><td className="text-muted-foreground">Saving after reset</td><td className="text-right"><Num p="estimated" title="Weighted tokens: price ratios configured in context_budget.py (cache read 0.1x, write 1.25x), not measured">{b.saving_per_call.toLocaleString("en-US")}</Num> per call</td></tr>
                  <tr><td className="text-muted-foreground">Break-even (reset under <Num p="estimated" title="Configured threshold, not measured">{b.reset_threshold_calls}</Num>)</td><td className="text-right font-medium"><Num p="estimated" title="Weighted tokens: price ratios configured in context_budget.py (cache read 0.1x, write 1.25x), not measured">{b.breakeven_calls ?? "—"}</Num> calls</td></tr>
                  <tr><td className="text-muted-foreground">Weights: read / write</td><td className="text-right"><Num p="estimated" title="Weighted tokens: price ratios configured in context_budget.py (cache read 0.1x, write 1.25x), not measured">{b.weights.read}</Num> / <Num p="estimated" title="Weighted tokens: price ratios configured in context_budget.py (cache read 0.1x, write 1.25x), not measured">{b.weights.write}</Num></td></tr>
                </tbody>
              </table>
            ) : null}
          </div>
        </>
      ) : (
        <p className="text-xs text-muted-foreground">Cursor has not reported a context size for this chat (it is written to Cursor's local store as the chat runs).</p>
      )}

      {billed && billed.points.length ? (
        <div>
          <div className="mb-1 flex items-baseline justify-between text-xs">
            <span className="text-muted-foreground">Input billed per request (every call in the agent loop)</span>
            <span><Num p="measured" className="font-medium">{fmtTokens(billed.input_total)}</Num> over <Num p="measured">{billed.requests}</Num> requests{billed.cache_read_share !== null ? <> · <Num p="measured">{Math.round(billed.cache_read_share * 100)}</Num>% cache reads</> : null}</span>
          </div>
          <BilledBars points={billed.points} generations={billed.generations} current={currentGeneration} />
        </div>
      ) : null}
    </div>
  );
}
