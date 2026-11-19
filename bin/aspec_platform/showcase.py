"""One-screen proof of what the harness changes: tokens, efficiency, accuracy, retrieval and the
prompts behind them. Read-only aggregation over request traces, the impact model, the savings
estimate, the RAG eval and the search index; `GET /api/showcase`.

Every figure carries its provenance: `measured` (counted from hooks or a real search call),
`estimated` (the impact model's tokens-avoided arithmetic) or `ai_judged` (session reviews).
"""
from __future__ import annotations

import json
import os
import statistics
from collections import defaultdict

from . import common, impact, observe, rag_eval, retrieval, savings, traces

RECENT = 150          # requests the per-request impact model runs over (it is O(spans))
PROMPTS = 15


def _pct(n, d):
    return round(100.0 * n / d, 1) if d else None


def _model_family(model: str | None) -> str:
    m = (model or "unknown").lower()
    if m.startswith(("ollama:", "groq:")):
        return m
    return m.split("-")[0] if m else "unknown"


def bench(project: str, name: str = "agent-bench-results.jsonl", pair: tuple = ("harness", "bare")) -> dict | None:
    """Latest A/B run of bin/agent-spec-bench.py, plus every earlier run's totals. The default pair
    is harness on vs off; `--skill` runs (skill-bench-results.jsonl) pair plain vs the skill."""
    path = os.path.join(common.agent_spec_dir(project), "eval", name)
    rows = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get("run_id") and r.get("arm") in pair:
                    rows.append(r)
    except OSError:
        return None
    if not rows:
        return None
    runs = defaultdict(list)
    for r in rows:
        runs[r["run_id"]].append(r)

    def arms(rs):
        out = {}
        for arm in pair:
            a = [r for r in rs if r["arm"] == arm]
            if a:
                out[arm] = {"cases": len(a), "correct": sum(1 for r in a if r.get("correct")),
                            "tokens_in": sum(r.get("tokens_in") or 0 for r in a),
                            "tokens_out": sum(r.get("tokens_out") or 0 for r in a),
                            "tools": sum(r.get("tools") or 0 for r in a), "ms": sum(r.get("ms") or 0 for r in a)}
        return out
    order = sorted(runs, key=lambda k: runs[k][0].get("ts") or "")
    latest = runs[order[-1]]
    cases = defaultdict(dict)
    for r in latest:
        cases[r["case"]][r["arm"]] = {k: r.get(k) for k in ("correct", "tokens_in", "tokens_out", "tools", "ms", "request_id", "answer")}
        cases[r["case"]]["prompt"] = r.get("prompt")
        cases[r["case"]]["expect"] = r.get("expect")
    return {"run_id": order[-1], "ts": latest[-1].get("ts"), "model": latest[0].get("model"),
            "skill": next((r.get("skill") for r in latest if r.get("skill")), None),
            "arms": arms(latest), "cases": [dict(case=k, **v) for k, v in sorted(cases.items())],
            "runs": [{"run_id": k, "ts": runs[k][0].get("ts"), "arms": arms(runs[k])} for k in order[-10:]],
            "provenance": "measured"}


def overview(project: str, conn) -> dict:
    all_t, all_s = traces.all_traces(project, conn)
    by_trace = defaultdict(list)
    for s in all_s:
        by_trace[s["trace_id"]].append(s)
    recent = [t for t in all_t if t.get("status") != "demo_seed"][:RECENT]

    rows = []
    totals = defaultdict(int)
    rules_pass = rules_total = 0
    first_graph = with_tools = 0
    for t in recent:
        spans = by_trace.get(t["trace_id"], [])
        try:
            imp = impact.for_request(project, conn, t, spans, None)
        except Exception:  # noqa: BLE001 — one malformed trace never blanks the showcase
            imp = {}
        tok = imp.get("tokens") or {}
        tools = imp.get("tools") or {}
        resp = [s["attributes"] for s in spans if s.get("kind") == "response" and isinstance(s["attributes"].get("input_tokens"), int)]
        tin = sum(a.get("input_tokens") or 0 for a in resp)
        tout = sum(a.get("output_tokens") or 0 for a in resp)
        cache = sum(a.get("cache_read_tokens") or 0 for a in resp)
        for r in imp.get("rules") or []:
            if r.get("pass") is not None:
                rules_total += 1
                rules_pass += 1 if r["pass"] else 0
        tool_spans = sorted((s for s in spans if s.get("kind") == "tool"), key=lambda s: (s.get("start") or "", s.get("seq") or 0))
        if tool_spans:
            with_tools += 1
            if (tool_spans[0]["attributes"].get("category") or "") in ("graph", "memory"):
                first_graph += 1
        for key, val in (("avoided", tok.get("avoided") or 0), ("plain", tok.get("plain_cursor") or 0),
                         ("context_in", tok.get("context_in") or 0), ("billed_in", tin), ("billed_out", tout),
                         ("cache_read", cache), ("tools", t.get("tool_count") or 0), ("errors", t.get("error_count") or 0),
                         ("guard", t.get("guard_count") or 0), ("read_whole", tools.get("read_whole") or 0),
                         ("read_ranged", tools.get("read_ranged") or 0), ("graph", tools.get("graph") or 0),
                         ("subagents", tools.get("subagents") or 0)):
            totals[key] += val
        rows.append({"trace_id": t["trace_id"], "session_id": t.get("session_id"), "prompt": (t.get("prompt") or "")[:160],
                     "model": t.get("model"), "status": t.get("status"), "start": t.get("start"),
                     "duration_ms": t.get("duration_ms"), "tools": t.get("tool_count") or 0,
                     "errors": t.get("error_count") or 0, "guard": t.get("guard_count") or 0,
                     "tokens_in": tin, "tokens_out": tout, "avoided": tok.get("avoided") or 0,
                     "plain": tok.get("plain_cursor") or 0, "origin": t.get("origin")})

    n = len(rows)
    durations = sorted(r["duration_ms"] for r in rows if isinstance(r["duration_ms"], int) and r["duration_ms"] > 0)
    completed = sum(1 for r in rows if r["status"] == "completed")

    models = defaultdict(lambda: {"requests": 0, "tokens_in": 0, "tokens_out": 0, "avoided": 0, "tools": 0, "ms": []})
    for r in rows:
        m = models[_model_family(r["model"])]
        m["requests"] += 1
        m["tokens_in"] += r["tokens_in"]
        m["tokens_out"] += r["tokens_out"]
        m["avoided"] += r["avoided"]
        m["tools"] += r["tools"]
        if r["duration_ms"]:
            m["ms"].append(r["duration_ms"])
    by_model = sorted(({"model": k, "requests": v["requests"], "tokens_in": v["tokens_in"], "tokens_out": v["tokens_out"],
                        "avoided": v["avoided"], "tools_per_request": round(v["tools"] / v["requests"], 2),
                        "median_ms": int(statistics.median(v["ms"])) if v["ms"] else None,
                        "local": k.startswith("ollama:")} for k, v in models.items()), key=lambda x: -x["requests"])

    days = defaultdict(lambda: {"requests": 0, "avoided": 0, "billed": 0, "tools": 0})
    for r in rows:
        d = days[(r["start"] or "")[:10] or "unknown"]
        d["requests"] += 1
        d["avoided"] += r["avoided"]
        d["billed"] += r["tokens_in"] + r["tokens_out"]
        d["tools"] += r["tools"]
    trend = [dict(day=k, **v) for k, v in sorted(days.items()) if k != "unknown"][-14:]

    est = savings.savings(conn, {k: v[0] for k, v in savings.WEIGHTS.items()}) if conn is not None else None
    quality = []
    for rev in observe.reviews(project):
        if isinstance(rev.get("score"), (int, float)):
            quality.append(rev["score"])
    idx = retrieval.index_status(conn) if conn is not None else {"ready": False, "by_kind": {}}
    rag = rag_eval.latest(conn) if conn is not None else None

    return {
        "requests": n,
        "tokens": {
            "avoided": totals["avoided"], "plain_cursor": totals["plain"], "context_in": totals["context_in"],
            "reduction_pct": _pct(totals["avoided"], totals["plain"]),
            "billed_in": totals["billed_in"], "billed_out": totals["billed_out"], "cache_read": totals["cache_read"],
            "cache_share_pct": _pct(totals["cache_read"], totals["billed_in"]),
            "whole_file_estimate": est, "provenance": "estimated",
        },
        "efficiency": {
            "tools_per_request": round(totals["tools"] / n, 2) if n else None,
            "graph_first_pct": _pct(first_graph, with_tools),
            "ranged_read_pct": _pct(totals["read_ranged"], totals["read_ranged"] + totals["read_whole"]),
            "graph_queries": totals["graph"], "subagents": totals["subagents"], "guard_blocks": totals["guard"],
            "median_ms": int(statistics.median(durations)) if durations else None,
            "p90_ms": durations[int(0.9 * (len(durations) - 1))] if durations else None,
            "provenance": "measured",
        },
        "accuracy": {
            "completed_pct": _pct(completed, n),
            "tool_error_pct": _pct(totals["errors"], totals["tools"]),
            "rules_pass_pct": _pct(rules_pass, rules_total), "rules_checked": rules_total,
            "review_score_avg": round(statistics.mean(quality), 2) if quality else None, "reviews": len(quality),
            "provenance": "measured",
        },
        "rag": {"index": idx, "eval": rag, "history": rag_eval.history(conn) if conn is not None else [],
                "fusion": retrieval.fusion_weight(conn) if conn is not None else None},
        "bench": bench(project),
        "skill_bench": bench(project, "skill-bench-results.jsonl", ("plain", "skill")),
        "by_model": by_model,
        "trend": trend,
        "prompts": rows[:PROMPTS],
    }
