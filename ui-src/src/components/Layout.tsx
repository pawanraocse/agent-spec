import { useEffect, useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { BookOpen, Brain, Gauge, LayoutDashboard, MessageSquare, PlayCircle } from "lucide-react";
import { apiGet } from "../api/client";

type StatusBarData = {
  graph?: { age_s?: number; text?: string; stale?: boolean };
  hooks?: { session_start?: boolean; pre_tool_use?: boolean; session_end?: boolean; git_reindex?: boolean };
  doctor?: { status?: "ok" | "warn" | "fail"; ok?: boolean };
  snapshot?: { size_bytes?: number; rotation_due?: boolean };
  active_jobs?: number;
};

const NAV = [
  { to: "/", label: "Home", icon: LayoutDashboard },
  { to: "/sessions", label: "Sessions", icon: MessageSquare },
  { to: "/runs", label: "Runs", icon: PlayCircle },
  { to: "/knowledge", label: "Knowledge", icon: Brain },
  { to: "/governance", label: "Governance", icon: BookOpen },
  { to: "/console", label: "Console", icon: Gauge },
];

export function Layout() {
  const [status, setStatus] = useState<StatusBarData | null>(null);

  useEffect(() => {
    apiGet<StatusBarData>("/api/status_bar")
      .then(setStatus)
      .catch(() => {});
    const iv = setInterval(() => {
      apiGet<StatusBarData>("/api/status_bar").then(setStatus).catch(() => {});
    }, 15000);
    return () => clearInterval(iv);
  }, []);

  const docColor =
    status?.doctor?.status === "fail"
      ? "bg-rose-500"
      : status?.doctor?.status === "warn"
      ? "bg-amber-500"
      : "bg-emerald-500";

  return (
    <div className="flex h-screen flex-col bg-slate-950 text-slate-100">
      <div className="flex flex-1 overflow-hidden">
        <aside className="w-52 shrink-0 border-r border-slate-800 bg-slate-950/80 p-4">
          <p className="mb-6 text-sm font-semibold tracking-tight text-slate-200">agent-spec</p>
          <nav className="flex flex-col gap-1">
            {NAV.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-md px-2 py-1.5 text-sm ${
                    isActive ? "bg-slate-800 text-white" : "text-slate-400 hover:bg-slate-900"
                  }`
                }
                end={to === "/"}
              >
                <Icon size={16} />
                {label}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>

      {/* 24px Calm Status Bar (§4.7 / CP-007) */}
      <footer className="flex h-6 items-center justify-between border-t border-slate-800/80 bg-slate-950 px-3 text-[11px] text-slate-400 select-none">
        <div className="flex items-center gap-4">
          <Link
            to="/knowledge"
            className={`flex items-center gap-1.5 hover:text-slate-200 ${
              status?.graph?.stale ? "text-amber-400" : "text-slate-400"
            }`}
            title="Graph Freshness (Knowledge space)"
          >
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${
                status?.graph?.stale ? "bg-amber-400" : "bg-emerald-400"
              }`}
            />
            <span>graph {status?.graph?.text ?? "fresh"}</span>
          </Link>

          <Link
            to="/governance"
            className="flex items-center gap-1.5 hover:text-slate-200"
            title="Doctor Health (Governance space)"
          >
            <span className={`inline-block h-1.5 w-1.5 rounded-full ${docColor}`} />
            <span>doctor {status?.doctor?.status ?? "ok"}</span>
          </Link>

          <div className="flex items-center gap-1.5 text-slate-400" title="Hooks status: sessionStart, preToolUse, sessionEnd, git reindex">
            <span>hooks:</span>
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${
                status?.hooks?.session_start ? "bg-emerald-400" : "bg-rose-400"
              }`}
              title="sessionStart hook"
            />
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${
                status?.hooks?.pre_tool_use ? "bg-emerald-400" : "bg-rose-400"
              }`}
              title="preToolUse hook"
            />
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${
                status?.hooks?.session_end ? "bg-emerald-400" : "bg-amber-400"
              }`}
              title="sessionEnd hook"
            />
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${
                status?.hooks?.git_reindex ? "bg-emerald-400" : "bg-slate-600"
              }`}
              title="git reindex hook"
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          {status?.snapshot?.rotation_due && (
            <Link to="/governance" className="text-amber-400 hover:underline">
              snapshot rotation due
            </Link>
          )}
          <Link to="/console" className="hover:text-slate-200">
            {status?.active_jobs ? `${status.active_jobs} job running` : "idle"}
          </Link>
          <span className="text-slate-600">|</span>
          <span className="text-slate-500 font-mono">press ? for help</span>
        </div>
      </footer>
    </div>
  );
}
