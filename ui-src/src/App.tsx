import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import { Shell } from "./components/Shell";
import { Space, type SpaceTab } from "./components/Space";
import { TooltipProvider } from "./components/ui/tooltip";
import { lazy, Suspense, type ReactNode } from "react";
import { useInboxCounts } from "./api/inbox";
import { Live } from "./pages/Live";

// Impact is the landing space; the others (and Recharts with them) load on first visit.
const Showcase = lazy(() => import("./pages/Showcase").then((m) => ({ default: m.Showcase })));
const Coach = lazy(() => import("./pages/Coach").then((m) => ({ default: m.Coach })));
const Learning = lazy(() => import("./pages/Learning").then((m) => ({ default: m.Learning })));
const Ask = lazy(() => import("./pages/Ask").then((m) => ({ default: m.Ask })));
const Console = lazy(() => import("./pages/Console").then((m) => ({ default: m.Console })));
const Project = lazy(() => import("./pages/Project").then((m) => ({ default: m.Project })));
const Sessions = lazy(() => import("./pages/Sessions").then((m) => ({ default: m.Sessions })));
const SessionDetail = lazy(() => import("./pages/Sessions").then((m) => ({ default: m.SessionDetail })));
const Runs = lazy(() => import("./pages/Runs").then((m) => ({ default: m.Runs })));
const RunDetail = lazy(() => import("./pages/Runs").then((m) => ({ default: m.RunDetail })));
const Risk = lazy(() => import("./pages/Risk").then((m) => ({ default: m.Risk })));
const Proposals = lazy(() => import("./pages/Proposals").then((m) => ({ default: m.Proposals })));
const Automations = lazy(() => import("./pages/Automations").then((m) => ({ default: m.Automations })));
const L = ({ children }: { children: ReactNode }) => <Suspense fallback={<p className="p-6 text-xs text-muted-foreground">Loading…</p>}>{children}</Suspense>;

const client = new QueryClient({ defaultOptions: { queries: { staleTime: 5_000, retry: 1, refetchOnWindowFocus: false } } });

const IMPACT: SpaceTab[] = [
  { to: "/", label: "Summary", end: true },
  { to: "/coach", label: "Coach" },
  { to: "/learning", label: "Learning" },
];
const ACTIVITY: SpaceTab[] = [
  { to: "/requests", label: "Requests" },
  { to: "/chats", label: "Chats" },
  { to: "/runs", label: "Workflow runs" },
];
const ASK: SpaceTab[] = [
  { to: "/ask", label: "Search the project" },
  { to: "/console", label: "Run the agent" },
];

function Inbox({ children }: { children: ReactNode }) {
  const c = useInboxCounts();
  return (
    <Space tabs={[
      { to: "/risk", label: "Risky edits", count: c.risk },
      { to: "/proposals", label: "Proposals", count: c.proposals },
      { to: "/automations", label: "Automations" },
    ]}><L>{children}</L></Space>
  );
}

/** Old URLs keep working. */
function Moved({ to }: { to: string }) {
  const params = useParams();
  const { search } = useLocation();
  const target = to.replace(/:(\w+)/g, (_, k) => encodeURIComponent(params[k] ?? ""));
  return <Navigate to={target + search} replace />;
}

const MOVED: [string, string][] = [
  ["showcase", "/"], ["project/overview", "/"],
  ["sessions", "/chats"], ["sessions/:id", "/chats/:id"], ["project/sessions", "/chats"], ["project/sessions/:id", "/chats/:id"],
  ["project/runs", "/runs"], ["project/runs/:id", "/runs/:id"],
  ["project/risk", "/risk"], ["project/proposals", "/proposals"], ["project/automations", "/automations"],
  ["knowledge", "/project/memory"], ["governance", "/project/health"], ["inbox", "/risk"], ["activity", "/requests"],
];

export default function App() {
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Shell />}>
              <Route index element={<Space tabs={IMPACT}><L><Showcase /></L></Space>} />
              <Route path="coach" element={<Space tabs={IMPACT}><L><Coach /></L></Space>} />
              <Route path="learning" element={<Space tabs={IMPACT}><L><Learning /></L></Space>} />

              <Route path="requests" element={<Space tabs={ACTIVITY} scroll={false}><Live /></Space>} />
              <Route path="requests/:id" element={<Space tabs={ACTIVITY} scroll={false}><Live /></Space>} />
              <Route path="chats" element={<Space tabs={ACTIVITY}><div className="p-6"><L><Sessions /></L></div></Space>} />
              <Route path="chats/:id" element={<Space tabs={ACTIVITY}><div className="p-6"><L><SessionDetail /></L></div></Space>} />
              <Route path="runs" element={<Space tabs={ACTIVITY}><div className="p-6"><L><Runs /></L></div></Space>} />
              <Route path="runs/:id" element={<Space tabs={ACTIVITY}><div className="p-6"><L><RunDetail /></L></div></Space>} />

              <Route path="ask" element={<Space tabs={ASK}><L><Ask /></L></Space>} />
              <Route path="console" element={<Space tabs={ASK}><L><Console /></L></Space>} />

              <Route path="risk" element={<Inbox><Risk /></Inbox>} />
              <Route path="proposals" element={<Inbox><Proposals /></Inbox>} />
              <Route path="automations" element={<Inbox><Automations /></Inbox>} />

              <Route path="project/*" element={<L><Project /></L>} />
              {MOVED.map(([from, to]) => <Route key={from} path={from} element={<Moved to={to} />} />)}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
}
