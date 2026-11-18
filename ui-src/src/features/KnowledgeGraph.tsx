import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D, { type ForceGraphMethods } from "react-force-graph-2d";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { apiGet } from "../api/client";
import { Num } from "../components/Num";

type GNode = { id: string; type?: string; layer?: string | null; in_degree: number; x?: number; y?: number };
type GEdge = { source: string; target: string };
type Blast = { target: string; direct_dependents: string[]; transitive_count: number; blast_files: string[] };

const LAYER_COLORS = ["#38bdf8", "#a78bfa", "#34d399", "#fbbf24", "#f472b6", "#60a5fa", "#f87171", "#2dd4bf"];

/** DV-058: force graph, lazy chunk. Click a file to see its blast halo and callers; search jumps to it. */
export default function KnowledgeGraph() {
  const graph = useQuery({ queryKey: ["graph"], queryFn: () => apiGet<{ nodes: GNode[]; edges: GEdge[]; stats: Record<string, number> }>("/api/graph") });
  const [focus, setFocus] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const blast = useQuery({
    queryKey: ["blast", focus],
    enabled: !!focus,
    queryFn: () => apiGet<Blast>(`/api/graph/blast?file=${encodeURIComponent(focus!)}&depth=3`),
  });
  const fg = useRef<ForceGraphMethods<GNode, GEdge> | undefined>(undefined);
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: 520 });
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const [showAll, setShowAll] = useState(false);
  // Files with no import edge are scattered dots that hide the structure; they stay one click away.
  const linked = useMemo(() => {
    const ids = new Set<string>();
    (graph.data?.edges ?? []).forEach((e) => { ids.add(e.source); ids.add(e.target); });
    return ids;
  }, [graph.data]);
  const unlinked = (graph.data?.nodes ?? []).filter((n) => !linked.has(n.id)).length;
  const data = useMemo(() => ({
    nodes: (graph.data?.nodes ?? []).filter((n) => showAll || linked.has(n.id)).map((n) => ({ ...n })),
    links: (graph.data?.edges ?? []).map((e) => ({ source: e.source, target: e.target })),
  }), [graph.data, linked, showAll]);
  const hot = useMemo(() => [...(graph.data?.nodes ?? [])].filter((n) => n.in_degree > 0).sort((a, b) => b.in_degree - a.in_degree).slice(0, 10), [graph.data]);
  const layerOf = (n: GNode) => (!n.layer || n.layer === "unknown" ? "other" : n.layer);
  const layers = useMemo(() => Array.from(new Set(data.nodes.map(layerOf))), [data]);
  const halo = useMemo(() => new Set(blast.data?.blast_files ?? []), [blast.data]);
  const direct = useMemo(() => new Set(blast.data?.direct_dependents ?? []), [blast.data]);

  const jump = () => {
    const hit = data.nodes.find((n) => n.id.toLowerCase().includes(q.toLowerCase()));
    if (hit && fg.current && hit.x !== undefined && hit.y !== undefined) {
      setFocus(hit.id);
      fg.current.centerAt(hit.x, hit.y, 600);
      fg.current.zoom(3, 600);
    }
  };

  return (
    <div className="grid h-full min-h-0 grid-cols-[1fr_300px]">
      <div ref={box} className="relative min-h-[480px] overflow-hidden">
        <form className="absolute left-3 top-3 z-10 flex h-8 items-center gap-2 rounded-md border border-border bg-card/90 px-2 text-xs backdrop-blur" onSubmit={(e) => { e.preventDefault(); jump(); }}>
          <Search size={12} className="text-muted-foreground" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Jump to file" className="w-48 bg-transparent outline-none" aria-label="Jump to file" />
        </form>
        {graph.data ? (
          <ForceGraph2D
            ref={fg}
            width={size.w}
            height={size.h}
            graphData={data}
            backgroundColor="rgba(0,0,0,0)"
            nodeRelSize={3}
            nodeVal={(n) => 1 + Math.min(n.in_degree, 12)}
            nodeLabel={(n) => `${n.id} · ${n.in_degree} dependents`}
            nodeColor={(n) => n.id === focus ? "#f8fafc" : direct.has(n.id) ? "#f87171" : halo.has(n.id) ? "#fbbf24" : LAYER_COLORS[layers.indexOf(layerOf(n)) % LAYER_COLORS.length]}
            linkColor={(l) => (typeof l.target === "object" && (l.target as GNode).id === focus) || (typeof l.source === "object" && direct.has((l.source as GNode).id)) ? "rgba(248,113,113,0.8)" : "rgba(148,163,184,0.18)"}
            linkDirectionalArrowLength={2.5}
            cooldownTicks={120}
            onNodeClick={(n) => setFocus(n.id)}
          />
        ) : <p className="p-6 text-xs text-muted-foreground">Loading graph…</p>}
      </div>
      <aside className="scrollbar-thin overflow-auto border-l border-border p-4 text-xs">
        <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Graph</p>
        <p className="mt-1"><Num p="measured">{graph.data?.nodes.length ?? 0}</Num> files · <Num p="measured">{graph.data?.edges.length ?? 0}</Num> import edges</p>
        {unlinked ? (
          <button type="button" className="mt-1 text-primary hover:underline" onClick={() => setShowAll(!showAll)}>
            {showAll ? "Hide" : "Show"} <Num p="measured">{unlinked}</Num> files with no imports
          </button>
        ) : null}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {layers.length > 1 && layers.map((l, i) => (
            <span key={l} className="inline-flex items-center gap-1 text-[10px] text-muted-foreground"><span className="h-2 w-2 rounded-full" style={{ background: LAYER_COLORS[i % LAYER_COLORS.length] }} />{l}</span>
          ))}
        </div>
        {focus ? (
          <div className="mt-5 space-y-3">
            <div>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Selected</p>
              <p className="mt-1 break-all font-mono">{focus}</p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Blast radius (depth 3)</p>
              <p className="mt-1"><Num p="measured">{blast.data?.transitive_count ?? 0}</Num> files affected</p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wide text-danger">Direct callers</p>
              <ul className="mt-1 space-y-0.5 font-mono text-[11px]">
                {(blast.data?.direct_dependents ?? []).map((d) => <li key={d}><button type="button" className="text-left hover:text-primary" onClick={() => setFocus(d)}>{d}</button></li>)}
              </ul>
            </div>
          </div>
        ) : (
          <div className="mt-5 space-y-2">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Most depended on</p>
            <ol className="space-y-1 font-mono text-[11px]">
              {hot.map((n) => (
                <li key={n.id} className="flex items-center gap-2">
                  <button type="button" className="truncate text-left hover:text-primary" title={n.id} onClick={() => setFocus(n.id)}>{n.id}</button>
                  <Num p="measured" className="ml-auto shrink-0 text-muted-foreground">{n.in_degree}</Num>
                </li>
              ))}
            </ol>
            <p className="text-muted-foreground">Click a file, here or in the graph, to see what breaks if it changes.</p>
          </div>
        )}
      </aside>
    </div>
  );
}
