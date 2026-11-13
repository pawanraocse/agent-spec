import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { Span } from "../api/traces";
import { SpanInspector } from "./SpanInspector";

afterEach(cleanup);

const sub = (attributes: Record<string, unknown>): Span => ({
  span_id: "e3", trace_id: "gen-1", parent_span_id: "gen-1#root", kind: "subagent", name: "agent-spec-search",
  status: "completed", seq: 0, start: "2026-11-13T10:00:01.500Z", end: "2026-11-13T10:00:04.000Z", duration_ms: 2500, attributes,
});

describe("typed handoff (DV-057)", () => {
  it("shows typed fields in place of the raw summary", () => {
    const span = sub({
      task: "find callers", summary: '{"matches":[{"path":"a.py","line":3}]}',
      handoff: {
        agent: "agent-spec-search", version: "1.0.0",
        input: { typed: false, value: null, errors: ["not JSON"] },
        output: { typed: true, value: { matches: [{ path: "a.py", line: 3 }] }, errors: [] },
      },
    });
    const { baseElement } = render(<SpanInspector span={span} members={[span]} onClose={() => {}} />);
    const box = baseElement.querySelector('[aria-label="Typed handoff"]') as HTMLElement;
    expect(box.textContent).toContain("agent-spec-search@1.0.0");
    expect(box.querySelector("table")?.textContent).toBe("pathlinea.py3");
    expect(box.textContent).toContain("not JSON");
    // the untyped input keeps its raw text; the typed output's raw JSON is not repeated
    expect(baseElement.textContent).toContain("find callers");
    expect(baseElement.textContent).not.toContain('{"matches"');
  });

  it("without a schema the inspector is unchanged", () => {
    const span = sub({ task: "find callers", summary: "3 callers" });
    const { baseElement } = render(<SpanInspector span={span} members={[span]} onClose={() => {}} />);
    expect(baseElement.querySelector('[aria-label="Typed handoff"]')).toBeNull();
    expect(baseElement.textContent).toContain("3 callers");
  });
});
