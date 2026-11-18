import { Card } from "../components/ui/card";
import { Num } from "../components/Num";
import { useEffect, useState, useMemo } from "react";
import { apiGet } from "../api/client";

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

export function Knowledge() {
  const [tab, setTab] = useState<"memory" | "flywheel">("memory");
  const [memory, setMemory] = useState<{ facts: FactItem[] } | null>(null);
  const [memoryScope, setMemoryScope] = useState<"all" | "local" | "team">("all");
  const [exp, setExp] = useState<{ experiences: ExperienceItem[] } | null>(null);

  // Both lists load up front so each tab shows its real count before it is opened.
  useEffect(() => {
    apiGet<any>("/api/memory").then(setMemory).catch(console.error);
    apiGet<any>("/api/experiences").then(setExp).catch(console.error);
  }, []);

  // Filtered memory facts (CP-037)
  const filteredFacts = useMemo(() => {
    const list = memory?.facts ?? [];
    if (memoryScope === "all") return list;
    return list.filter((f) => (f.scope || "local") === memoryScope);
  }, [memory, memoryScope]);


  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-foreground">Memory</h1>
        <p className="text-xs text-muted-foreground">
          Durable project facts read back at every session start, and the experiences the learning loop reuses
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border text-xs">
        {[
          ["memory", "Bounded Memory", memory?.facts?.length ?? 0],
          ["flywheel", "Flywheel Experiences", exp?.experiences?.length ?? 0],
        ].map(([t, label, count]) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t as any)}
            className={`pb-2.5 font-medium border-b-2 transition-colors ${
              tab === t
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <span data-figure-exempt>{label}</span>{count !== undefined ? <> (<Num p="measured">{count}</Num>)</> : null}
          </button>
        ))}
      </div>

      {/* TAB 1: Graph & Blast Radius */}

      {/* TAB 2: Bounded Memory & Team Filter (CP-037) */}
      {tab === "memory" && (
        <div className="space-y-4">
          {/* Scope filter chips */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground">Scope:</span>
              {(["all", "local", "team"] as const).map((sc) => (
                <button
                  key={sc}
                  type="button"
                  className={`rounded-md px-2.5 py-1 uppercase text-[11px] font-medium transition-colors ${
                    memoryScope === sc
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground hover:text-foreground"
                  }`}
                  onClick={() => setMemoryScope(sc)}
                >
                  {sc}
                </button>
              ))}
            </div>
            <span className="text-xs text-muted-foreground">
              Showing <Num p="measured">{filteredFacts.length}</Num> fact(s)
            </span>
          </div>

          <Card className="divide-y divide-border text-xs">
            {filteredFacts.length === 0 ? (
              <div className="p-6 text-center text-muted-foreground">No memory facts match scope.</div>
            ) : (
              filteredFacts.map((fact) => (
                <div key={fact.fact_id} className="p-3.5 space-y-1 hover:bg-muted/60">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-semibold text-primary">
                        {fact.type}
                      </span>
                      <span className="font-semibold text-foreground">{fact.subject}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] uppercase font-bold ${
                          fact.scope === "team"
                            ? "bg-accent/20 text-accent"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {fact.scope || "local"}
                      </span>
                      <span className="font-mono text-muted-foreground">
                        {fact.injections_count ?? 0} injections
                      </span>
                    </div>
                  </div>
                  {fact.updated && (
                    <span className="font-mono text-[10px] text-muted-foreground block">
                      Updated: {fact.updated.slice(0, 10)}
                    </span>
                  )}
                </div>
              ))
            )}
          </Card>
        </div>
      )}

      {/* TAB 3: Flywheel Experiences */}
      {tab === "flywheel" && (
        <div className="space-y-4">
          <Card className="p-4 text-xs text-muted-foreground">
            The learning flywheel promotes candidate corrections into trusted experiences and
            proposed skills.
          </Card>
          <Card className="divide-y divide-border text-xs">
            {(exp?.experiences ?? []).length === 0 ? (
              <div className="p-6 text-center text-muted-foreground">
                No flywheel experiences recorded yet.
              </div>
            ) : (
              (exp?.experiences ?? []).map((e) => (
                <div key={e.exp_id} className="p-3.5 space-y-1 hover:bg-muted/60">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-foreground">{e.title}</span>
                    <span className="rounded bg-success/10 px-2 py-0.5 font-mono text-[10px] text-success uppercase font-bold">
                      {e.tier || "trusted"}
                    </span>
                  </div>
                  {e.task && <p className="text-muted-foreground">{e.task}</p>}
                  <div className="flex items-center gap-3 font-mono text-[10px] text-muted-foreground pt-1">
                    <span>Uses: {e.uses ?? 0}</span>
                    <span>Successes: {e.successes ?? 0}</span>
                  </div>
                </div>
              ))
            )}
          </Card>
        </div>
      )}

      {/* TAB 4: Skills & Personas */}
    </div>
  );
}
