import { lazy, Suspense, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../api/client";
import { Num, Prov } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Card, CardHeader } from "../components/ui/card";
import { relTime } from "../lib/utils";
import { Space, type SpaceTab } from "../components/Space";
import { skillIcon, type Skill } from "../features/skillMeta";
import { Governance } from "./Governance";
import { IndexHealth } from "./IndexHealth";
import { Repos } from "./Repos";
import { SkillEffectiveness } from "../features/SkillEffectiveness";
import { Knowledge } from "./Knowledge";

const KnowledgeGraph = lazy(() => import("../features/KnowledgeGraph"));

type Panel = { skill: string; file: string; mtime: number; panel: { type: "kpi" | "table" | "timeline"; title: string; provenance: "measured" | "estimated" | "ai_judged" | "demo_seed"; value?: string | number; unit?: string; hint?: string; columns?: string[]; rows?: (string | number)[][]; events?: { ts: string; label: string; detail?: string }[] } };

function Catalog() {
  const q = useQuery({ queryKey: ["catalog"], queryFn: () => apiGet<{ skills: Skill[]; self_described: number }>("/api/catalog") });
  const [all, setAll] = useState(false);
  const skills = q.data?.skills ?? [];
  const used = skills.filter((s) => s.uses > 0);
  // Unused skills are noise on a first look; they stay one click away.
  const shown = all || !used.length ? skills : used;
  const groups = new Map<string, Skill[]>();
  [...shown].sort((a, b) => b.uses - a.uses).forEach((s) => groups.set(s.category, [...(groups.get(s.category) ?? []), s]));
  return (
    <div className="space-y-5 p-6">
      <p className="text-xs text-muted-foreground">
        <Num p="measured">{skills.length}</Num> skills, <Num p="measured">{used.length}</Num> used so far (counted from request traces).{" "}
        {used.length && used.length < skills.length ? (
          <button type="button" className="text-primary hover:underline" onClick={() => setAll(!all)}>
            {all ? "Show only used skills" : `Show all ${skills.length}`}
          </button>
        ) : null}
      </p>
      <Panels />
      <SkillEffectiveness />
      {[...groups.entries()].map(([cat, list]) => (
        <section key={cat}>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{cat}</h3>
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {list.map((s) => (
              <div key={s.id} className="rounded-lg border border-border bg-card p-3">
                <div className="flex items-center gap-2">
                  {(() => { const I = skillIcon(s.icon); return I ? <I size={14} className="shrink-0 text-k-skill" aria-hidden /> : null; })()}
                  <span className="truncate text-sm font-medium">/{s.name}</span>
                  {s.is_workflow ? <Badge tone="accent">workflow</Badge> : null}
                  <span className="ml-auto text-[11px] text-muted-foreground"><Num p="measured">{s.uses}</Num> uses</span>
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{s.description}</p>
                {s.emits.length || s.steps.length ? (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {s.emits.map((e) => <Badge key={e} tone="primary" className="normal-case">{e}</Badge>)}
                    {s.steps.map((e, i) => <Badge key={e} className="normal-case">{i + 1}. {e}</Badge>)}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function Panels() {
  const q = useQuery({ queryKey: ["panels"], queryFn: () => apiGet<{ panels: Panel[]; invalid: { skill: string; file: string; error: string }[] }>("/api/panels") });
  // Skills that publish a panel show it above the catalog; nothing is rendered when none do.
  if (!q.data || (!q.data.panels.length && !q.data.invalid.length)) return null;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {(q.data?.panels ?? []).map(({ skill, file, mtime, panel }) => (
        <Card key={file}>
          <CardHeader title={<span className="flex items-center gap-2">{panel.title}<Prov p={panel.provenance} /></span>} subtitle={<>/{skill} · updated <time dateTime={new Date(mtime * 1000).toISOString()}>{relTime(new Date(mtime * 1000).toISOString())}</time></>} />
          <div className="p-4 text-xs">
            {panel.type === "kpi" ? (
              <div className="text-2xl font-semibold"><Num p={panel.provenance}>{panel.value}</Num>{panel.unit ? <span className="ml-1 text-sm text-muted-foreground">{panel.unit}</span> : null}{panel.hint ? <p className="mt-1 text-xs font-normal text-muted-foreground">{panel.hint}</p> : null}</div>
            ) : panel.type === "table" ? (
              <table className="w-full">
                <thead><tr className="border-b border-border text-left text-[10px] uppercase text-muted-foreground">{panel.columns!.map((c) => <th key={c} className="py-1">{c}</th>)}</tr></thead>
                <tbody>{panel.rows!.map((r, i) => <tr key={i} className="border-b border-border/50">{r.map((c, j) => <td key={j} className="py-1">{typeof c === "number" ? <Num p={panel.provenance}>{c}</Num> : c}</td>)}</tr>)}</tbody>
              </table>
            ) : (
              <ol className="space-y-2 border-l border-border pl-3">
                {panel.events!.map((e, i) => <li key={i}><span className="text-muted-foreground">{e.ts}</span> <span className="font-medium">{e.label}</span>{e.detail ? <p className="text-muted-foreground">{e.detail}</p> : null}</li>)}
              </ol>
            )}
          </div>
        </Card>
      ))}
      {(q.data?.invalid ?? []).map((b) => (
        <Card key={b.file} className="border-danger/40"><CardHeader title={`Invalid panel: ${b.file}`} subtitle={b.error} /></Card>
      ))}
    </div>
  );
}

const TABS: SpaceTab[] = [
  { to: "skills", label: "Skills & workflows" },
  { to: "graph", label: "Knowledge graph" },
  { to: "memory", label: "Memory" },
  { to: "repos", label: "Repos" },
  { to: "index", label: "Search index" },
  { to: "health", label: "Health" },
];

/** Project space: what the harness knows about this codebase and whether it is healthy. */
export function Project() {
  return (
    <Space tabs={TABS}>
      <Routes>
        <Route index element={<Navigate to="skills" replace />} />
        <Route path="skills" element={<Catalog />} />
        <Route path="graph" element={<div className="h-full"><Suspense fallback={<p className="p-6 text-xs text-muted-foreground">Loading graph…</p>}><KnowledgeGraph /></Suspense></div>} />
        <Route path="panels" element={<Navigate to="../skills" replace />} />
        <Route path="memory" element={<div className="p-6"><Knowledge /></div>} />
        <Route path="repos" element={<Repos />} />
        <Route path="index" element={<IndexHealth />} />
        <Route path="health" element={<div className="p-6"><Governance /></div>} />
      </Routes>
    </Space>
  );
}
