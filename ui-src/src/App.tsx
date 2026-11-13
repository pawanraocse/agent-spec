import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import { Shell } from "./components/Shell";
import { TooltipProvider } from "./components/ui/tooltip";
import { lazy, Suspense, type ReactNode } from "react";
import { Live } from "./pages/Live";

// Live is the landing space; the other spaces (and Recharts with them) load on first visit.
const Coach = lazy(() => import("./pages/Coach").then((m) => ({ default: m.Coach })));
const Learning = lazy(() => import("./pages/Learning").then((m) => ({ default: m.Learning })));
const Project = lazy(() => import("./pages/Project").then((m) => ({ default: m.Project })));
const Console = lazy(() => import("./pages/Console").then((m) => ({ default: m.Console })));
const L = ({ children }: { children: ReactNode }) => <Suspense fallback={<p className="p-6 text-xs text-muted-foreground">Loading…</p>}>{children}</Suspense>;

const client = new QueryClient({ defaultOptions: { queries: { staleTime: 5_000, retry: 1, refetchOnWindowFocus: false } } });

/** v2 URLs keep working: they now live under Project. */
function Moved({ to }: { to: string }) {
  const params = useParams();
  const { search } = useLocation();
  const target = to.replace(/:(\w+)/g, (_, k) => encodeURIComponent(params[k] ?? ""));
  return <Navigate to={target + search} replace />;
}

export default function App() {
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Shell />}>
              <Route index element={<Live />} />
              <Route path="requests/:id" element={<Live />} />
              <Route path="coach" element={<L><Coach /></L>} />
              <Route path="learning" element={<L><Learning /></L>} />
              <Route path="project/*" element={<L><Project /></L>} />
              <Route path="console" element={<L><Console /></L>} />
              <Route path="sessions" element={<Moved to="/project/sessions" />} />
              <Route path="sessions/:id" element={<Moved to="/project/sessions/:id" />} />
              <Route path="runs" element={<Moved to="/project/runs" />} />
              <Route path="runs/:id" element={<Moved to="/project/runs/:id" />} />
              <Route path="knowledge" element={<Moved to="/project/memory" />} />
              <Route path="governance" element={<Moved to="/project/health" />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
}
