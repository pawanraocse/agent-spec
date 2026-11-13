import { lazy, Suspense } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../api/client";
import { Num, Prov } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { Card, CardHeader, Empty } from "../components/ui/card";
import { cn, relTime } from "../lib/utils";
import { skillIcon, type Skill } from "../features/skillMeta";
import { Governance } from "./Governance";
import { Home } from "./Home";
import { Knowledge } from "./Knowledge";
import { RunDetail, Runs } from "./Runs";
import { SessionDetail, Sessions } from "./Sessions";

const KnowledgeGraph = lazy(() => import("../features/KnowledgeGraph"));

type Panel = { skill: string; file: string; mtime: number; panel: { type: "kpi" | "table" | "timeline"; title: string; provenance: "measured" | "estimated" | "ai_judged" | "demo_seed"; value?: string | number; unit?: string; hint?: string; columns?: string[]; rows?: (string | number)[][]; events?: { ts: string; label: string; detail?: string }[] } };

function Catalog() {
  const q = useQuery({ queryKey: ["catalog"], queryFn: () => apiGet<{ skills: Skill[]; self_described: number }>("/api/catalog") });
  const groups = new Map<string, Skill[]>();
  (q.data?.skills ?? []).forEach((s) => groups.set(s.category, [...(groups.get(s.category) ?? []), s]));
  return (
    <div className="space-y-5 p-6">
      <p className="text-xs text-muted-foreground">
        <Num p="measured">{q.data?.skills.length ?? 0}</Num> skills · <Num p="measured">{q.data?.self_described ?? 0}</Num> describe themselves with a <code>dashboard:</code> block. Uses are counted from request traces.
      </p>
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
  if (q.data && !q.data.panels.length && !q.data.invalid.length) {
    return <Empty title="No skill panels yet" hint={<>Any skill can add a panel by writing <code>.agent-spec/metrics/panels/&lt;skill&gt;/&lt;name&gt;.json</code> (kpi, table or timeline, with provenance). See docs/DASHBOARD.md, "Make your skill show up in five minutes".</>} />;
  }
  return (
    <div className="grid gap-4 p-6 lg:grid-cols-2">
      {(q.data?.panels ?? []).map(({ skill, file, mtime, panel }) => (
        <Card key={file}>
          <CardHeader title={<span className="flex items-center gap-2">{panel.title}<Prov p={panel.provenance} /></span>} subtitle={<>/{skill} · updated {relTime(new Date(mtime * 1000).toISOString())}</>} />
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

const TABS = [
  { to: "skills", label: "Skills & workflows" },
  { to: "graph", label: "Knowledge graph" },
  { to: "panels", label: "Panels" },
  { to: "sessions", label: "Session history" },
  { to: "runs", label: "Runs" },
  { to: "memory", label: "Memory" },
  { to: "health", label: "Health" },
  { to: "overview", label: "Overview" },
];

/** Project space (§14.2): what the harness knows and has. Older v2 views live here unchanged. */
export function Project() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <nav className="flex gap-1 overflow-x-auto border-b border-border px-4 pt-3" aria-label="Project sections">
        {TABS.map((t) => (
          <NavLink key={t.to} to={t.to} className={({ isActive }) => cn("whitespace-nowrap border-b-2 px-3 pb-2 text-xs font-medium", isActive ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground")}>
            {t.label}
          </NavLink>
        ))}
      </nav>
      <div className="scrollbar-thin min-h-0 flex-1 overflow-auto">
        <Routes>
          <Route index element={<Navigate to="skills" replace />} />
          <Route path="skills" element={<Catalog />} />
          <Route path="graph" element={<div className="h-full"><Suspense fallback={<p className="p-6 text-xs text-muted-foreground">Loading graph…</p>}><KnowledgeGraph /></Suspense></div>} />
          <Route path="panels" element={<Panels />} />
          <Route path="sessions" element={<div className="p-6"><Sessions /></div>} />
          <Route path="sessions/:id" element={<div className="p-6"><SessionDetail /></div>} />
          <Route path="runs" element={<div className="p-6"><Runs /></div>} />
          <Route path="runs/:id" element={<div className="p-6"><RunDetail /></div>} />
          <Route path="memory" element={<div className="p-6"><Knowledge /></div>} />
          <Route path="health" element={<div className="p-6"><Governance /></div>} />
          <Route path="overview" element={<div className="p-6"><Home /></div>} />
        </Routes>
      </div>
    </div>
  );
}
