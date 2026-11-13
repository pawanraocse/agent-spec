import { Num } from "../components/Num";
import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet } from "../api/client";
import {
  Brain,
  GitBranch,
  Search,
  Sparkles,
  BookOpen,
  Filter,
  Users,
  Terminal,
  ChevronRight,
  Shield,
  Layers,
} from "lucide-react";

type GraphNode = {
  id: string;
  type?: string;
  lang?: string;
  layer?: string;
  in_degree: number;
};

type BlastResult = {
  target: string;
  direct_dependents: string[];
  transitive_count: number;
  blast_files: string[];
};

type FactItem = {
  fact_id: string;
  type: string;
  subject: string;
  bytes?: number;
  confidence?: number;
  scope?: "local" | "team";
  updated?: string;
  injections_count?: number;
};

type ExperienceItem = {
  exp_id: string;
  title: string;
  tier?: string;
  confidence?: number;
  uses?: number;
  successes?: number;
  task?: string;
};

type SkillItem = {
  name: string;
  category: string;
  is_workflow?: boolean;
  description?: string;
};

export function Knowledge() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<"graph" | "memory" | "flywheel" | "skills">("graph");
  const [graph, setGraph] = useState<{ nodes: GraphNode[]; stats?: Record<string, unknown> } | null>(null);
  const [graphSearch, setGraphSearch] = useState("");
  const [blast, setBlast] = useState<BlastResult | null>(null);
  const [memory, setMemory] = useState<{ facts: FactItem[] } | null>(null);
  const [memoryScope, setMemoryScope] = useState<"all" | "local" | "team">("all");
  const [exp, setExp] = useState<{ experiences: ExperienceItem[] } | null>(null);
  const [skills, setSkills] = useState<{ skills: SkillItem[] } | null>(null);

  useEffect(() => {
    if (tab === "graph") apiGet<any>("/api/graph").then(setGraph).catch(console.error);
    if (tab === "memory") apiGet<any>("/api/memory").then(setMemory).catch(console.error);
    if (tab === "flywheel") apiGet<any>("/api/experiences").then(setExp).catch(console.error);
    if (tab === "skills") apiGet<any>("/api/skills").then(setSkills).catch(console.error);
  }, [tab]);

  // Filtered graph nodes
  const filteredNodes = useMemo(() => {
    return (graph?.nodes ?? []).filter((n) =>
      n.id.toLowerCase().includes(graphSearch.toLowerCase()),
    );
  }, [graph, graphSearch]);

  // Filtered memory facts (CP-037)
  const filteredFacts = useMemo(() => {
    const list = memory?.facts ?? [];
    if (memoryScope === "all") return list;
    return list.filter((f) => (f.scope || "local") === memoryScope);
  }, [memory, memoryScope]);

  function loadBlast(fileId: string) {
    apiGet<BlastResult>(`/api/graph/blast?file=${encodeURIComponent(fileId)}`)
      .then(setBlast)
      .catch(console.error);
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Knowledge Space</h1>
        <p className="text-xs text-slate-400">
          Knowledge graph, blast radius, bounded memory facts, and learning flywheel
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-800 text-xs">
        {[
          ["graph", "Knowledge Graph & Blast Radius"],
          ["memory", "Bounded Memory", memory?.facts?.length ?? 0],
          ["flywheel", "Flywheel Experiences", exp?.experiences?.length ?? 0],
          ["skills", "Skills & Personas", skills?.skills?.length ?? 0],
        ].map(([t, label, count]) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t as any)}
            className={`pb-2.5 font-medium border-b-2 transition-colors ${
              tab === t
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <span data-figure-exempt>{label}</span>{count !== undefined ? <> (<Num p="measured">{count}</Num>)</> : null}
          </button>
        ))}
      </div>

      {/* TAB 1: Graph & Blast Radius */}
      {tab === "graph" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search size={14} className="absolute left-3 top-2.5 text-slate-500" />
              <input
                className="w-full rounded-lg border border-slate-800 bg-slate-900 py-1.5 pl-9 pr-3 text-xs text-slate-200 placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                placeholder="Search file or symbol..."
                value={graphSearch}
                onChange={(e) => setGraphSearch(e.target.value)}
              />
            </div>
            <div className="text-xs text-slate-400 font-mono">
              Total nodes: {graph?.nodes?.length ?? 0}
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            {/* Node list */}
            <div className="max-h-[500px] overflow-auto rounded-xl border border-slate-800 bg-slate-900/40 text-xs divide-y divide-slate-800/80">
              {filteredNodes.slice(0, 100).map((n) => (
                <div
                  key={n.id}
                  className="flex items-center justify-between p-2.5 hover:bg-slate-900/70 transition-colors"
                >
                  <button
                    type="button"
                    className="text-left font-mono text-sky-400 hover:underline truncate max-w-md"
                    onClick={() => loadBlast(n.id)}
                  >
                    {n.id}
                  </button>
                  <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-mono text-slate-400 shrink-0">
                    in-degree: {n.in_degree}
                  </span>
                </div>
              ))}
            </div>

            {/* Blast radius inspector */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <span className="font-semibold text-slate-200">Blast Radius Halo</span>
                <span className="text-slate-500 font-mono">depth: 2</span>
              </div>
              {blast ? (
                <div className="space-y-3">
                  <div>
                    <span className="text-slate-500 block mb-0.5">Target File</span>
                    <span className="font-mono text-slate-200 font-semibold">{blast.target}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block mb-0.5">
                      Direct Dependents ({blast.direct_dependents.length})
                    </span>
                    <div className="rounded-lg bg-slate-950 p-2 font-mono text-emerald-400 max-h-32 overflow-auto space-y-0.5">
                      {blast.direct_dependents.length ? (
                        blast.direct_dependents.map((f, i) => <div key={i}>{f}</div>)
                      ) : (
                        <div className="text-slate-500">None</div>
                      )}
                    </div>
                  </div>
                  <div>
                    <span className="text-slate-500 block mb-0.5">
                      Transitive Dependents ({blast.transitive_count})
                    </span>
                    <div className="rounded-lg bg-slate-950 p-2 font-mono text-amber-400 max-h-32 overflow-auto space-y-0.5">
                      {blast.blast_files.length ? (
                        blast.blast_files.map((f, i) => <div key={i}>{f}</div>)
                      ) : (
                        <div className="text-slate-500">None</div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center text-slate-500">
                  Click any file on the left to compute its real-time blast radius and dependent halo.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: Bounded Memory & Team Filter (CP-037) */}
      {tab === "memory" && (
        <div className="space-y-4">
          {/* Scope filter chips */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-500">Scope:</span>
              {(["all", "local", "team"] as const).map((sc) => (
                <button
                  key={sc}
                  type="button"
                  className={`rounded-md px-2.5 py-1 uppercase text-[11px] font-medium transition-colors ${
                    memoryScope === sc
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-800 text-slate-400 hover:text-slate-200"
                  }`}
                  onClick={() => setMemoryScope(sc)}
                >
                  {sc}
                </button>
              ))}
            </div>
            <span className="text-xs text-slate-500">
              Showing <Num p="measured">{filteredFacts.length}</Num> fact(s)
            </span>
          </div>

          <div className="divide-y divide-slate-800 rounded-xl border border-slate-800 bg-slate-900/30 text-xs">
            {filteredFacts.length === 0 ? (
              <div className="p-6 text-center text-slate-500">No memory facts match scope.</div>
            ) : (
              filteredFacts.map((fact) => (
                <div key={fact.fact_id} className="p-3.5 space-y-1 hover:bg-slate-900/40">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-indigo-500/10 px-2 py-0.5 font-mono text-[10px] font-semibold text-indigo-300">
                        {fact.type}
                      </span>
                      <span className="font-semibold text-slate-200">{fact.subject}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] uppercase font-bold ${
                          fact.scope === "team"
                            ? "bg-purple-500/20 text-purple-300"
                            : "bg-slate-800 text-slate-400"
                        }`}
                      >
                        {fact.scope || "local"}
                      </span>
                      <span className="font-mono text-slate-500">
                        {fact.injections_count ?? 0} injections
                      </span>
                    </div>
                  </div>
                  {fact.updated && (
                    <span className="font-mono text-[10px] text-slate-500 block">
                      Updated: {fact.updated.slice(0, 10)}
                    </span>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* TAB 3: Flywheel Experiences */}
      {tab === "flywheel" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs text-slate-400">
            The learning flywheel promotes candidate corrections into trusted experiences and
            proposed skills.
          </div>
          <div className="divide-y divide-slate-800 rounded-xl border border-slate-800 bg-slate-900/30 text-xs">
            {(exp?.experiences ?? []).length === 0 ? (
              <div className="p-6 text-center text-slate-500">
                No flywheel experiences recorded yet.
              </div>
            ) : (
              (exp?.experiences ?? []).map((e) => (
                <div key={e.exp_id} className="p-3.5 space-y-1 hover:bg-slate-900/40">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-200">{e.title}</span>
                    <span className="rounded bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] text-emerald-300 uppercase font-bold">
                      {e.tier || "trusted"}
                    </span>
                  </div>
                  {e.task && <p className="text-slate-400">{e.task}</p>}
                  <div className="flex items-center gap-3 font-mono text-[10px] text-slate-500 pt-1">
                    <span>Uses: {e.uses ?? 0}</span>
                    <span>Successes: {e.successes ?? 0}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* TAB 4: Skills & Personas */}
      {tab === "skills" && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {(skills?.skills ?? []).map((sk) => (
            <div
              key={sk.name}
              className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 space-y-2 text-xs flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-400 uppercase">
                    {sk.category}
                  </span>
                  {sk.is_workflow && (
                    <span className="rounded bg-sky-500/20 px-1.5 py-0.5 text-[10px] font-bold text-sky-300 uppercase">
                      Workflow
                    </span>
                  )}
                </div>
                <div className="mt-1 font-semibold text-slate-200">{sk.name}</div>
                {sk.description && <p className="mt-1 text-slate-400 text-[11px]">{sk.description}</p>}
              </div>

              <button
                type="button"
                className="w-full mt-2 rounded bg-slate-800 py-1.5 text-center font-medium text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
                onClick={() => navigate("/console")}
              >
                Use in Console →
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
