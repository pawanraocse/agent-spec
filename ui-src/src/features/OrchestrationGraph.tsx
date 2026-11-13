import { createContext, memo, useContext, useMemo } from "react";
import { Background, Controls, Handle, MarkerType, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "@dagrejs/dagre";
import { motion, useReducedMotion } from "motion/react";
import type { Span } from "../api/traces";
import { cn, fmtBytes, fmtMs } from "../lib/utils";
import { buildView, bytesOf, planView, type ViewNode } from "./spanTree";
import { KIND, kindMeta, statusTone, STATUS_RING } from "./kinds";
import { skillIcon, useCatalog } from "./skillMeta";

type NodeData = { view: ViewNode; provenance: "measured" | "estimated" };
// Hover/selection travel by context so a hover never rebuilds the node array (a rebuild
// between mousedown and mouseup swallows the click).
const FocusCtx = createContext<string | null>(null);
const W = 210;
const H = 62;
const ROWS = 6;

const SpanNode = memo(function SpanNode({ data }: NodeProps<Node<NodeData>>) {
  const { view, provenance } = data;
  const focus = useContext(FocusCtx);
  const highlighted = !!focus && (view.id === focus || view.members.some((m) => m.span_id === focus));
  const dimmed = false;
  const s = view.span;
  const meta = kindMeta(s.kind);
  const Icon = skillIcon(view.skill?.icon) ?? meta.icon;
  const tone = statusTone(s.status);
  const reduce = useReducedMotion();
  const total = view.members.reduce((a, m) => a + (m.duration_ms ?? 0), 0);
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, scale: 0.85, y: 6 }}
      animate={{ opacity: dimmed ? 0.35 : 1, scale: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 380, damping: 28 }}
      className={cn(
        "relative flex h-[62px] w-[210px] cursor-pointer flex-col justify-center rounded-lg border border-border bg-card px-3 shadow-sm ring-1",
        STATUS_RING[tone],
        view.planned && "border-dashed bg-card/40 opacity-60 ring-0",
        highlighted && "ring-2 ring-primary",
        s.status === "running" && "animate-pulse-ring",
      )}
    >
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-0 !bg-border" />
      <div className="flex items-center gap-1.5">
        <span className={cn("flex h-5 w-5 items-center justify-center rounded", meta.bg, meta.color)}>
          <Icon size={12} />
        </span>
        <span className="truncate text-xs font-medium">{s.kind === "prompt" ? "Prompt" : s.name}</span>
        {view.count > 1 ? <span className="ml-auto rounded bg-muted px-1 text-[10px] text-muted-foreground">×{view.count}</span> : null}
      </div>
      <div className="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground">
        <span className={cn("truncate uppercase", meta.color)}>{view.skill?.category ?? meta.label}</span>
        {view.planned ? (
          <span title="Declared in the workflow's dashboard.steps; no run step recorded">planned · not run</span>
        ) : (
          <span data-provenance={provenance} className="tabular">{fmtMs(view.count > 1 ? total : s.duration_ms)}</span>
        )}
        {tone === "danger" ? <span className="text-danger">{s.status}</span> : null}
        {s.status === "running" ? <span className="text-primary">running</span> : null}
        {view.emits?.length ? (
          <span className="ml-auto flex shrink-0 items-center gap-0.5" aria-label="Declared span kinds">
            {view.emits.map(({ kind, seen }) => {
              const k = KIND[kind as keyof typeof KIND];
              const title = `declares ${kind}: ${seen ? "seen in this request" : "not seen in this request"}`;
              return k ? (
                <k.icon key={kind} size={10} className={seen ? k.color : "text-muted-foreground/40"} aria-label={title}><title>{title}</title></k.icon>
              ) : (
                <span key={kind} title={title} className={seen ? "text-foreground" : "text-muted-foreground/50"}>{kind}</span>
              );
            })}
          </span>
        ) : null}
      </div>
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-0 !bg-border" />
    </motion.div>
  );
});

const nodeTypes = { span: SpanNode };

export default function OrchestrationGraph({ spans, provenance, selected, hovered, onSelect, onHover }: {
  spans: Span[];
  provenance: "measured" | "estimated";
  selected?: string | null;
  hovered?: string | null;
  onSelect: (s: Span, members: Span[]) => void;
  onHover?: (id: string | null) => void;
}) {
  const catalog = useCatalog();
  const view = useMemo(() => planView(buildView(spans), catalog), [spans, catalog]);
  const { nodes, edges } = useMemo(() => {
    const g = new dagre.graphlib.Graph();
    g.setGraph({ rankdir: "LR", nodesep: 14, ranksep: 70, marginx: 10, marginy: 10 });
    g.setDefaultEdgeLabel(() => ({}));
    view.forEach((v) => g.setNode(v.id, { width: W, height: H }));
    view.forEach((v) => v.parent && g.setEdge(v.parent, v.id));
    dagre.layout(g);
    // Wide fan-out of leaves: wrap into columns of ROWS so the graph stays readable.
    const pos = new Map(view.map((v) => [v.id, { x: g.node(v.id).x, y: g.node(v.id).y }]));
    const kids = new Map<string, ViewNode[]>();
    view.forEach((v) => v.parent && kids.set(v.parent, [...(kids.get(v.parent) ?? []), v]));
    const hasKids = new Set(view.map((v) => v.parent));
    const wide = new Set<string>();
    kids.forEach((list, parent) => {
      if (list.length <= ROWS || list.some((c) => hasKids.has(c.id))) return;
      wide.add(parent);
      const p = pos.get(parent)!;
      const rows = Math.min(list.length, ROWS);
      list.forEach((c, i) => pos.set(c.id, { x: p.x + W + 50 + Math.floor(i / ROWS) * (W + 20), y: p.y - ((rows - 1) * (H + 12)) / 2 + (i % ROWS) * (H + 12) }));
    });
    const nodes: Node<NodeData>[] = view.map((v) => {
      const p = pos.get(v.id)!;
      return {
        id: v.id,
        type: "span",
        position: { x: p.x - W / 2, y: p.y - H / 2 },
        data: { view: v, provenance },
      };
    });
    const edges: Edge[] = view.filter((v) => v.parent).map((v) => {
      const bin = v.members.reduce((a, m) => a + (bytesOf(m, "bytes_in") ?? 0), 0);
      const bout = v.members.reduce((a, m) => a + (bytesOf(m, "bytes_out") ?? 0), 0);
      const label = bin || bout ? `${bin ? "→ " + fmtBytes(bin) : ""}${bin && bout ? "  " : ""}${bout ? "← " + fmtBytes(bout) : ""}` : undefined;
      const danger = statusTone(v.span.status) === "danger";
      return {
        id: `${v.parent}->${v.id}`,
        source: v.parent!,
        target: v.id,
        label: wide.has(v.parent!) ? undefined : label,
        animated: v.span.status === "running",
        markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14 },
        style: { stroke: danger ? "hsl(var(--danger))" : "hsl(var(--border))", strokeWidth: 1.4 },
      };
    });
    return { nodes, edges };
  }, [view, provenance]);

  return (
    <FocusCtx.Provider value={hovered || selected || null}>
    <div className="h-full w-full [&_.react-flow]:!bg-transparent" aria-label="Orchestration graph">
      <ReactFlow
        colorMode={document.documentElement.classList.contains("light") ? "light" : "dark"}
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15, maxZoom: 1.1 }}
        minZoom={0.15}
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, n) => !(n.data as NodeData).view.planned && onSelect((n.data as NodeData).view.span, (n.data as NodeData).view.members)}
        onNodeMouseEnter={(_, n) => onHover?.(n.id)}
        onNodeMouseLeave={() => onHover?.(null)}
      >
        <Background gap={18} size={1} color="hsl(var(--border))" />
        <Controls showInteractive={false} className="!border-border !bg-card" />
      </ReactFlow>
    </div>
    </FocusCtx.Provider>
  );
}
