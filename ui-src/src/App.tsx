import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Console } from "./pages/Console";
import { Governance } from "./pages/Governance";
import { Home } from "./pages/Home";
import { Knowledge } from "./pages/Knowledge";
import { RunDetail, Runs } from "./pages/Runs";
import { SessionDetail, Sessions } from "./pages/Sessions";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="sessions" element={<Sessions />} />
          <Route path="sessions/:id" element={<SessionDetail />} />
          <Route path="runs" element={<Runs />} />
          <Route path="runs/:id" element={<RunDetail />} />
          <Route path="knowledge" element={<Knowledge />} />
          <Route path="governance" element={<Governance />} />
          <Route path="console" element={<Console />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
