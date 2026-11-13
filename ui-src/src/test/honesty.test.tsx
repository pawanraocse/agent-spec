import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { Coach } from "../pages/Coach";
import { Learning } from "../pages/Learning";
import { Live } from "../pages/Live";
import { fixtureFetch } from "./fixtures";

/** DV-005: no figure on a v3 page unless it comes with provenance. A text node containing a
 *  digit must sit inside an element carrying data-provenance; identifiers, timestamps and
 *  code (font-mono, <code>, <pre>, <time>, aria-hidden chart internals) are not figures. */
function unlabelledFigures(root: HTMLElement): string[] {
  const bad: string[] = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node: Node | null;
  while ((node = walker.nextNode())) {
    const text = node.textContent ?? "";
    if (!/(^|[^A-Za-z0-9])\d/.test(text)) continue; // "p95" is a label, not a figure
    const el = node.parentElement;
    if (!el) continue;
    if (el.closest("[data-provenance], code, pre, time, .font-mono, svg, [data-figure-exempt]")) continue;
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
  it("Live: every figure carries provenance", async () => {
    const { container, findAllByText } = mount("/requests/gen-1", <Live />, "/requests/:id");
    await findAllByText(/why does login fail/);
    await waitFor(() => expect(container.querySelector('[aria-label="Orchestration graph"], .text-xs')).toBeTruthy());
    expect(unlabelledFigures(container)).toEqual([]);
  });

  it("Coach: every figure carries provenance", async () => {
    const { container, findByText } = mount("/coach", <Coach />);
    await findByText("Whole-file read of a large module");
    expect(unlabelledFigures(container)).toEqual([]);
  });

  it("Learning: every figure carries provenance", async () => {
    const { container, findByText } = mount("/learning", <Learning />);
    await findByText("input discipline");
    expect(unlabelledFigures(container)).toEqual([]);
  });

  it("the check catches a bare number", () => {
    const { container } = render(<div><span>42 requests</span><span data-provenance="measured">7</span></div>);
    expect(unlabelledFigures(container)).toEqual(["42 requests"]);
  });
});
