import { describe, expect, it } from "vitest";
import type { Span } from "../api/traces";
import type { Skill } from "./skillMeta";
import { buildView, planView } from "./spanTree";

const span = (span_id: string, kind: string, name: string, parent: string | null, seq = 0): Span =>
  ({ span_id, trace_id: "t", parent_span_id: parent, kind, name, status: "ok", seq, start: null, end: null, duration_ms: 1, attributes: {} }) as Span;

const skill = (name: string, emits: string[], steps: string[] = []): Skill => ({
  id: name, name, description: "", category: steps.length ? "Workflow" : "Diagnose", icon: "bug", emits, steps,
  self_described: true, is_workflow: steps.length > 0, uses: 0,
});

describe("planView (DV-055)", () => {
  const catalog = new Map([
    ["agent-spec-wf-rca", skill("agent-spec-wf-rca", ["workflow", "run_step"], ["fetch", "graph", "logs", "rca"])],
    ["agent-spec-investigate", skill("agent-spec-investigate", ["subagent", "tool"])],
  ]);

  it("adds planned nodes for declared steps with no run_step, in declared order", () => {
    const view = planView(buildView([
      span("wf", "workflow", "agent-spec-wf-rca", null),
      span("wf:fetch", "run_step", "fetch", "wf", 1),
      span("wf:graph", "run_step", "graph", "wf", 2),
    ]), catalog);
    const planned = view.filter((v) => v.planned);
    expect(planned.map((v) => v.span.name)).toEqual(["logs", "rca"]);
    expect(planned.every((v) => v.parent === "wf" && v.members.length === 0)).toBe(true);
    expect(view.find((v) => v.id === "wf")?.emits).toEqual([{ kind: "workflow", seen: false }, { kind: "run_step", seen: true }]);
  });

  it("checks declared emits against the kinds below the skill span", () => {
    const view = planView(buildView([
      span("root", "prompt", "p", null),
      span("sk", "skill", "agent-spec-investigate", "root"),
      span("a", "tool", "Read", "sk"),
      span("b", "edit", "a.py", "sk"),
    ]), catalog);
    const sk = view.find((v) => v.id === "sk")!;
    expect(sk.skill?.category).toBe("Diagnose");
    expect(sk.emits).toEqual([{ kind: "subagent", seen: false }, { kind: "tool", seen: true }]);
    expect(view.some((v) => v.planned)).toBe(false);
  });

  it("leaves the view unchanged without a catalog entry", () => {
    const base = buildView([span("sk", "skill", "unknown-skill", null), span("a", "tool", "Read", "sk")]);
    expect(planView(base, catalog)).toEqual(base);
    expect(planView(base, new Map())).toBe(base);
  });
});
