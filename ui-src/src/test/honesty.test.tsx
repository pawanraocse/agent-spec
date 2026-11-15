import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { Automations } from "../pages/Automations";
import { Coach } from "../pages/Coach";
import { Governance } from "../pages/Governance";
import { Home } from "../pages/Home";
import { Knowledge } from "../pages/Knowledge";
import { RunDetail, Runs } from "../pages/Runs";
import { SessionDetail, Sessions } from "../pages/Sessions";
import { Learning } from "../pages/Learning";
import { Live } from "../pages/Live";
import { Ask } from "../pages/Ask";
import { Impact } from "../features/Impact";
import { fixtureFetch } from "./fixtures";

/** DV-005: no figure on a v3 page unless it comes with provenance. A text node containing a
 *  digit must sit inside an element carrying data-provenance; identifiers, timestamps and
 *  code (font-mono, <code>, <pre>, <time>, aria-hidden chart internals) and headings are not
 *  figures; anything else that is a label rather than a measurement says so with data-figure-exempt. */
function unlabelledFigures(root: HTMLElement): string[] {
  const bad: string[] = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node: Node | null;
  while ((node = walker.nextNode())) {
    const text = node.textContent ?? "";
    if (!/(^|[^A-Za-z0-9])\d/.test(text)) continue; // "p95" is a label, not a figure
    const el = node.parentElement;
    if (!el) continue;
    if (el.closest("[data-provenance], code, pre, time, .font-mono, svg, h1, h2, h3, [data-figure-exempt]")) continue;
    bad.push(text.trim().slice(0, 60));
  }
  return bad;
}

class RO { observe() {} unobserve() {} disconnect() {} }

beforeAll(() => {
  vi.stubGlobal("fetch", vi.fn(fixtureFetch));
  vi.stubGlobal("ResizeObserver", RO);
  vi.stubGlobal("EventSource", undefined);
});
afterEach(cleanup);

function mount(path: string, element: React.ReactNode, route = path) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes><Route path={route} element={element} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("page-level honesty (DV-005)", () => {
  it("Automations: every figure carries provenance, and an env switch locks the toggle (HA-006)", async () => {
    const { container, findByText, getByRole } = mount("/automations", <Automations />);
    await findByText("Refresh the knowledge graph");
    expect(unlabelledFigures(container)).toEqual([]);
    expect(getByRole("switch", { name: /Suggest a fresh chat/ })).toHaveProperty("disabled", true);
    expect(getByRole("switch", { name: /Refresh the knowledge graph: on/ }).getAttribute("aria-checked")).toBe("true");
  });

  it("Live: every figure carries provenance", async () => {
    const { container, findAllByText } = mount("/requests/gen-1", <Live />, "/requests/:id");
    await findAllByText(/why does login fail/);
    await waitFor(() => expect(container.querySelector('[aria-label="Orchestration graph"], .text-xs')).toBeTruthy());
    expect(unlabelledFigures(container)).toEqual([]);
    // DV-055: the skill node carries its catalog category and declared kinds, seen or not
    await waitFor(() => expect(container.querySelector('[aria-label="Declared span kinds"]')).toBeTruthy());
    const declared = [...container.querySelectorAll('[aria-label="Declared span kinds"] [aria-label]')].map((e) => e.getAttribute("aria-label"));
    expect(declared).toEqual(["declares subagent: seen in this request", "declares tool: seen in this request", "declares edit: not seen in this request"]);
    expect(container.textContent).toContain("Diagnose");
    expect(unlabelledFigures(container)).toEqual([]);
  });

  it("Impact: every figure carries provenance", () => {
    const { container } = render(
      <Impact impact={{
        bytes_per_token: 4, median_file_bytes: 5602,
        tools: { graph: 2, memory: 1, search: 3, read_whole: 1, read_ranged: 4, shell: 2, edit: 0, in_subagents: 61, subagents: 2, guard_blocks: 1 },
        tokens: { context_in: 2440, avoided: 17741, plain_cursor: 20181, provenance: "estimated", avoided_by: { graph: 936, ranged_reads: 0, subagents: 16805 } },
        rules: [{ rule: "No whole-file reads in the main context", pass: false, detail: "1 whole-file read" }],
        memory: { facts: Array.from({ length: 10 }, (_, i) => ({ fact_id: "f" + i, type: "constraint", subject: "fact " + i })), digest_bytes: 2379, provenance: "measured" },
        harness: { tokens: { rules: 3921, skills: 5642, subagents: 1454 }, total: 11017, provenance: "measured" },
        graph_queries: [{ name: "graphify context", target: "graphify-cli.py context", bytes: 1856, avoided: 3746 }],
        whole_reads: [{ target: "a.py", file_bytes: 1200 }],
      }} />,
    );
    expect(container.textContent).toContain("17,741");
    expect(unlabelledFigures(container)).toEqual([]);
  });

  it("Coach: every figure carries provenance", async () => {
    const { container, findByText } = mount("/coach", <Coach />);
    await findByText("Whole-file read of a large module");
    await findByText("Short chat");   // context budget panel
    expect(unlabelledFigures(container)).toEqual([]);
  });

  it("Live › Context tab: the reset arithmetic carries provenance", async () => {
    const { container, findAllByText, getByRole, findByText } = mount("/requests/gen-1", <Live />, "/requests/:id");
    await findAllByText(/why does login fail/);
    fireEvent.mouseDown(getByRole("tab", { name: /^Context/ }));
    fireEvent.click(getByRole("tab", { name: /^Context/ }));
    await findByText(/Start a new chat/);
    fireEvent.click(getByRole("button", { name: /Show the arithmetic/ }));
    await findByText(/Break-even/);
    expect(container.textContent).toContain("Hook nudged");
    expect(unlabelledFigures(container)).toEqual([]);
  });

  it("Live › Outcome tab: measured signals and AI-judged quality are labelled (PI-006)", async () => {
    const { container, findAllByText, getByRole, findByText } = mount("/requests/gen-1", <Live />, "/requests/:id");
    await findAllByText(/why does login fail/);
    fireEvent.mouseDown(getByRole("tab", { name: /^Outcome/ }));
    fireEvent.click(getByRole("tab", { name: /^Outcome/ }));
    await findByText("Measured signals");
    await findByText(/left the failing test unaddressed/);
    expect(container.textContent).toContain("no test, build or lint command after the last edit");
    expect(container.textContent).toContain("not assessable");
    expect(unlabelledFigures(container)).toEqual([]);
  });

  it("Ask: sources carry provenance and no answer is shown without a model (PI-005)", async () => {
    const { container, findByText } = mount("/ask?q=why%20does%20login%20fail", <Ask />, "/ask");
    await findByText("src/auth/login.py · login");
    expect(container.textContent).toContain("Copy prompt for Cursor");
    expect(container.textContent).not.toContain("Answer");
    expect(container.querySelector("mark")?.textContent).toBe("login");
    expect(unlabelledFigures(container)).toEqual([]);
  });

  it("Learning: every figure carries provenance", async () => {
    const { container, findByText } = mount("/learning", <Learning />);
    await findByText("input discipline");
    expect(unlabelledFigures(container)).toEqual([]);
  });

  const settle = () => new Promise((r) => setTimeout(r, 50));
  // [name, path, element, route pattern, tab buttons to visit after the default view]
  const v2: [string, string, React.ReactNode, string | undefined, RegExp[]][] = [
    ["Sessions", "/sessions", <Sessions />, undefined, []],
    ["Session detail", "/sessions/conv-1", <SessionDetail />, "/sessions/:id", [/^Savings Calculator/, /Compare$/]],
    ["Runs", "/runs", <Runs />, undefined, []],
    ["Run detail", "/runs/req-1", <RunDetail />, "/runs/:id", [/^Subagent health$/]],
    ["Memory", "/memory", <Knowledge />, undefined, [/^Bounded Memory/, /^Flywheel Experiences/, /^Skills & Personas/]],
    ["Health", "/health", <Governance />, undefined, [/^Caught by Harness/, /^Guard Log/, /^Doctor Health/, /^Backlog/]],
    ["Overview", "/overview", <Home />, undefined, []],
  ];
  for (const [name, path, el, route, tabs] of v2) {
    it(`${name}: every figure carries provenance, on every tab`, async () => {
      const { container, getByRole } = mount(path, el, route);
      await waitFor(() => expect(fetch).toHaveBeenCalled());
      await settle();
      expect(unlabelledFigures(container)).toEqual([]);
      for (const tab of tabs) {
        fireEvent.click(getByRole("button", { name: tab }));
        await settle();
        expect({ tab: String(tab), bad: unlabelledFigures(container) }).toEqual({ tab: String(tab), bad: [] });
      }
    });
  }

  it("the check catches a bare number", () => {
    const { container } = render(<div><span>42 requests</span><span data-provenance="measured">7</span></div>);
    expect(unlabelledFigures(container)).toEqual(["42 requests"]);
  });
});
