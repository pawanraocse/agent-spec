"""Proof-pack export (D-014): CSV or JSON metrics for a demo or an audit, built from platform.db.

Counts, token totals, rule names and run ids only. No prompt text, file paths, transcript paths,
tool inputs or events leave the database through here.
"""
from __future__ import annotations

import csv
import json
import os

from . import common, insights

RUN_COLS = ("request_id", "started", "status", "source", "workflow_id", "tokens_input", "tokens_output",
            "tokens_cache_read", "tokens_total", "cost_usd", "step_count", "whole_file_reads", "graph_queries")
TOOL_COLS = ("kind", "name", "calls", "failed", "tokens", "whole_file_reads")
GAP_COLS = ("rule", "flags")


def collect(conn, now=None) -> dict:
    runs = [dict(r) for r in conn.execute(
        "SELECT r.request_id, r.started, r.status, r.source, r.workflow_id, r.tokens_input, r.tokens_output, "
        "r.tokens_cache_read, (r.tokens_input + r.tokens_output + r.tokens_cache_read) AS tokens_total, r.cost_usd, "
        "(SELECT COUNT(*) FROM steps s WHERE s.request_id = r.request_id) AS step_count, "
        "(SELECT COUNT(*) FROM steps s WHERE s.request_id = r.request_id AND s.whole_file = 1) AS whole_file_reads, "
        "(SELECT COUNT(*) FROM steps s WHERE s.request_id = r.request_id AND s.detail_json LIKE '%graphify-cli%') "
        "AS graph_queries FROM requests r ORDER BY r.started, r.request_id")]
    tools = [dict(r) for r in conn.execute(
        "SELECT kind, name, COUNT(*) AS calls, SUM(status = 'failed') AS failed, "
        "SUM(tokens_input + tokens_output + tokens_cache_read) AS tokens, SUM(whole_file) AS whole_file_reads "
        "FROM steps GROUP BY kind, name ORDER BY tokens DESC, kind, name")]
    counts = {}
    for g in insights.gaps(conn, now=now, limit=100000):
        counts[g["rule"]] = counts.get(g["rule"], 0) + 1
    gaps = [{"rule": k, "flags": v} for k, v in sorted(counts.items())]
    home = insights.home(conn, now=now)
    summary = {"estimate": True, "generated": home["now"],
               "totals": {"runs": len(runs), "tokens": sum(r["tokens_total"] for r in runs),
                          "whole_file_reads": sum(r["whole_file_reads"] for r in runs),
                          "graph_queries": sum(r["graph_queries"] for r in runs)},
               "last_7d": home["last_7d"], "saved_vs_baseline": home["saved_vs_baseline"],
               "learning": home["learning"], "graph": home["graph"]}
    return {"summary": summary, "runs": runs, "tools": tools, "gaps": gaps}


def _csv(path, cols, rows) -> None:
    def cell(value):  # spreadsheet formula injection guard for any text that ever reaches a cell
        return "'" + value if isinstance(value, str) and value[:1] in "=+-@" else value

    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow([cell(r.get(c)) for c in cols])


def write(conn, out_dir, fmt="csv", now=None) -> list:
    """Write the pack into `out_dir`; returns the file names written."""
    data = collect(conn, now=now)
    os.makedirs(out_dir, exist_ok=True)
    if fmt == "json":
        common.atomic_write(os.path.join(out_dir, "proof-pack.json"), json.dumps(data, indent=2, sort_keys=True) + "\n")
        return ["proof-pack.json"]
    _csv(os.path.join(out_dir, "runs.csv"), RUN_COLS, data["runs"])
    _csv(os.path.join(out_dir, "tools.csv"), TOOL_COLS, data["tools"])
    _csv(os.path.join(out_dir, "gaps.csv"), GAP_COLS, data["gaps"])
    common.atomic_write(os.path.join(out_dir, "summary.json"),
                        json.dumps(data["summary"], indent=2, sort_keys=True) + "\n")
    return ["runs.csv", "tools.csv", "gaps.csv", "summary.json"]
