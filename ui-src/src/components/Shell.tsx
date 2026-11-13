import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { Command } from "cmdk";
import { useQuery } from "@tanstack/react-query";
import { Activity, BookOpen, GraduationCap, Moon, Search, Settings, Sun, Monitor, Boxes } from "lucide-react";
import { apiGet } from "../api/client";
import type { RequestList } from "../api/traces";
import { Sheet } from "./ui/sheet";
import { cn } from "../lib/utils";

const NAV = [
  { to: "/", label: "Live", icon: Activity, hint: "What is my agent doing right now?" },
  { to: "/coach", label: "Coach", icon: GraduationCap, hint: "Where is it slow or wasteful?" },
  { to: "/learning", label: "Learning", icon: BookOpen, hint: "Is it getting better?" },
  { to: "/project", label: "Project", icon: Boxes, hint: "What does the harness know?" },
];

type Theme = "dark" | "light" | "system";
type StatusBar = { graph?: { text?: string; stale?: boolean }; doctor?: { status?: string }; hooks?: Record<string, boolean>; active_jobs?: number };

function applyTheme(t: Theme) {
  const dark = t === "dark" || (t === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
  document.documentElement.classList.toggle("light", !dark);
}

function readTheme(): Theme {
  try {
    return (localStorage.getItem("aspec-theme") as Theme) || "dark";
  } catch {
    return "dark";
  }
}

function Palette({ open, setOpen }: { open: boolean; setOpen: (o: boolean) => void }) {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const reqs = useQuery({
    queryKey: ["palette", q],
    enabled: open,
    queryFn: () => apiGet<RequestList>(`/api/requests?limit=8${q ? `&q=${encodeURIComponent(q)}` : ""}`),
  });
  const skills = useQuery({ queryKey: ["catalog"], enabled: open, queryFn: () => apiGet<{ skills: { id: string; name: string }[] }>("/api/catalog") });
  const go = (to: string) => { setOpen(false); nav(to); };
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-[12vh]" onClick={() => setOpen(false)}>
      <Command label="Command palette" shouldFilter={false} className="w-[620px] max-w-[92vw] overflow-hidden rounded-xl border border-border bg-card shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b border-border px-3">
          <Search size={14} className="text-muted-foreground" />
          <Command.Input autoFocus value={q} onValueChange={setQ} placeholder="Search requests and skills, or jump to a space…" className="h-11 w-full bg-transparent text-sm outline-none" />
        </div>
        <Command.List className="scrollbar-thin max-h-[50vh] overflow-auto p-1.5 text-sm">
          <Command.Group heading="Spaces" className="px-1 text-[10px] uppercase text-muted-foreground">
            {NAV.map((n) => (
              <Command.Item key={n.to} onSelect={() => go(n.to)} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm normal-case text-foreground data-[selected=true]:bg-muted">
                <n.icon size={14} />{n.label}<span className="ml-auto text-xs text-muted-foreground">{n.hint}</span>
              </Command.Item>
            ))}
          </Command.Group>
          <Command.Group heading="Requests" className="px-1 text-[10px] uppercase text-muted-foreground">
            {(reqs.data?.requests ?? []).map((r) => (
              <Command.Item key={r.trace_id} onSelect={() => go(`/requests/${encodeURIComponent(r.trace_id)}`)} className="cursor-pointer truncate rounded px-2 py-1.5 text-sm normal-case text-foreground data-[selected=true]:bg-muted">
                {(r.prompt || r.trace_id).slice(0, 90)}
              </Command.Item>
            ))}
          </Command.Group>
          <Command.Group heading="Skills" className="px-1 text-[10px] uppercase text-muted-foreground">
            {(skills.data?.skills ?? []).filter((s) => !q || s.name.includes(q.toLowerCase())).slice(0, 8).map((s) => (
              <Command.Item key={s.id} onSelect={() => go(`/project/skills`)} className="cursor-pointer rounded px-2 py-1.5 font-mono text-xs normal-case text-foreground data-[selected=true]:bg-muted">
                /{s.name}
              </Command.Item>
            ))}
          </Command.Group>
        </Command.List>
      </Command>
    </div>
  );
}

/** DV-021 four-space shell: Live, Coach, Learning, Project; Cmd-K; settings drawer; status bar. */
export function Shell() {
  const [palette, setPalette] = useState(false);
  const [settings, setSettings] = useState(false);
  const [theme, setTheme] = useState<Theme>(readTheme);
  const status = useQuery({ queryKey: ["status_bar"], queryFn: () => apiGet<StatusBar>("/api/status_bar"), refetchInterval: 15000 });

  useEffect(() => {
    applyTheme(theme);
    try { localStorage.setItem("aspec-theme", theme); } catch { /* storage blocked */ }
  }, [theme]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPalette((p) => !p);
      }
      if (e.key === "Escape") setPalette(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const s = status.data;
  const hookOk = s?.hooks ? Object.values(s.hooks).filter(Boolean).length : 0;

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <div className="flex min-h-0 flex-1">
        <aside className="flex w-[64px] shrink-0 flex-col items-center gap-1 border-r border-border py-3 lg:w-48 lg:items-stretch lg:px-3">
          <Link to="/" className="mb-4 flex items-center gap-2 px-1">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-gradient-to-br from-primary to-accent text-[11px] font-bold text-primary-foreground">as</span>
            <span className="hidden text-sm font-semibold tracking-tight lg:inline">agent-spec</span>
          </Link>
          {NAV.map(({ to, label, icon: Icon, hint }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              title={hint}
              className={({ isActive }) => cn("flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors", isActive ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/60 hover:text-foreground")}
            >
              <Icon size={16} />
              <span className="hidden lg:inline">{label}</span>
            </NavLink>
          ))}
          <div className="mt-auto flex flex-col gap-1">
            <button type="button" onClick={() => setPalette(true)} className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-muted-foreground hover:bg-muted/60" title="Search (Ctrl/Cmd-K)">
              <Search size={16} /><span className="hidden lg:inline">Search</span><kbd className="ml-auto hidden rounded border border-border px-1 text-[10px] lg:inline">⌘K</kbd>
            </button>
            <button type="button" onClick={() => setSettings(true)} className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-muted-foreground hover:bg-muted/60" title="Settings">
              <Settings size={16} /><span className="hidden lg:inline">Settings</span>
            </button>
          </div>
        </aside>
        <main className="min-w-0 flex-1 overflow-auto focus:outline-none" tabIndex={0} aria-label="Content">
          <Outlet />
        </main>
      </div>
      <footer className="flex h-6 items-center gap-4 border-t border-border px-3 text-[11px] text-muted-foreground">
        <Link to="/project/graph" className={cn("flex items-center gap-1.5 hover:text-foreground", s?.graph?.stale && "text-warning")}>
          <span className={cn("h-1.5 w-1.5 rounded-full", s?.graph?.stale ? "bg-warning" : "bg-success")} />graph {s?.graph?.text ?? "…"}
        </Link>
        <Link to="/project/health" className="flex items-center gap-1.5 hover:text-foreground">
          <span className={cn("h-1.5 w-1.5 rounded-full", s?.doctor?.status === "fail" ? "bg-danger" : s?.doctor?.status === "warn" ? "bg-warning" : "bg-success")} />doctor {s?.doctor?.status ?? "…"}
        </Link>
        <span title="Registered Cursor hooks">hooks {hookOk}/{s?.hooks ? Object.keys(s.hooks).length : 0}</span>
        <span className="ml-auto">Ctrl/⌘-K to search</span>
      </footer>
      <Palette open={palette} setOpen={setPalette} />
      <Sheet open={settings} onOpenChange={setSettings} title="Settings" width="w-[380px]">
        <div className="space-y-5 text-xs">
          <div>
            <p className="mb-2 font-medium">Theme</p>
            <div className="inline-flex rounded-md bg-muted p-1">
              {([["dark", Moon], ["light", Sun], ["system", Monitor]] as const).map(([t, Icon]) => (
                <button key={t} type="button" onClick={() => setTheme(t)} className={cn("flex items-center gap-1.5 rounded px-2.5 py-1 capitalize", theme === t ? "bg-background shadow-sm" : "text-muted-foreground")}>
                  <Icon size={12} />{t}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-1.5">
            <p className="font-medium">Data sources</p>
            <p className="text-muted-foreground"><b className="text-foreground">Live hook</b> — Cursor hook events in <code>.agent-spec/metrics/events.jsonl</code>; durations measured.</p>
            <p className="text-muted-foreground"><b className="text-foreground">Cursor store</b> — history from Cursor's local database (unofficial); durations estimated from message times. Refresh with <code>agent-spec-platform.py ingest traces</code>; disable with <code>AGENT_SPEC_CURSOR_STORE=0</code>.</p>
            <p className="text-muted-foreground"><b className="text-foreground">Workflow</b> — hub-runner runs, joined to the request that started them.</p>
          </div>
          <div className="space-y-1.5">
            <p className="font-medium">Pricing and demo data</p>
            <p className="text-muted-foreground">Pricing presets, the demo seed and the frozen Console live under <Link className="text-primary" to="/project/health" onClick={() => setSettings(false)}>Project › Health</Link>.</p>
          </div>
        </div>
      </Sheet>
    </div>
  );
}
