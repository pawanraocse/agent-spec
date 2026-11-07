#!/usr/bin/env python3
"""agent-spec-roi.py — read per-session receipts: list, 7-day rollup, CSV, local viewer (T-055).

  agent-spec-roi.py list                    # one line per receipt, newest first
  agent-spec-roi.py rollup [--days 7]       # totals and averages over the window
  agent-spec-roi.py export --csv [-o FILE]  # receipts as CSV (stdout by default)
  agent-spec-roi.py serve [--port 8765]     # single HTML page on 127.0.0.1 only

Reads only .agent-spec/metrics/receipts/*.json written by agent-spec-receipt.py. It never
touches transcripts and never makes a network call; `serve` binds loopback and sends
nothing off the machine. A lite form of the Phase 2 proof pack (D-014).
"""
import argparse
import csv
import datetime
import html
import io
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

COLUMNS = ["ts", "session_id", "turns", "tokens_total", "tokens_output", "estimated",
           "tool_calls", "graph_queries", "whole_file_reads", "facts_injected", "gate"]


def receipts_dir(project):
    return os.path.join(project, ".agent-spec", "metrics", "receipts")


def load_receipts(project):
    """Receipts as flat rows, newest first. Unreadable files are skipped, never fatal."""
    rows = []
    try:
        names = os.listdir(receipts_dir(project))
    except OSError:
        return rows
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(receipts_dir(project), name), encoding="utf-8") as fh:
                r = json.load(fh)
            t = r.get("tokens") or {}
            rows.append({
                "ts": r.get("ts", ""),
                "session_id": r.get("session_id", name[:-5]),
                "turns": r.get("turns", 0),
                "tokens_total": sum(t.get(k, 0) or 0 for k in ("input", "output", "cache_read", "cache_write")),
                "tokens_output": t.get("output", 0) or 0,
                "estimated": bool(t.get("estimated")),
                "tool_calls": r.get("tool_calls_total", 0),
                "graph_queries": r.get("graph_queries", 0),
                "whole_file_reads": (r.get("whole_file_reads") or {}).get("count", 0),
                "facts_injected": r.get("facts_injected"),
                "gate": (r.get("gates") or {}).get("gate"),
            })
        except (OSError, ValueError, AttributeError, TypeError):
            continue
    rows.sort(key=lambda x: x["ts"], reverse=True)
    return rows


def within(rows, days, now=None):
    now = now or datetime.datetime.now()
    cutoff = (now - datetime.timedelta(days=days)).replace(microsecond=0).isoformat()
    return [r for r in rows if r["ts"] >= cutoff]


def rollup(rows):
    """Totals and averages; averages are over sessions, never over zero."""
    n = len(rows)
    total = lambda key: sum(r[key] or 0 for r in rows)
    reads = total("whole_file_reads")
    queries = total("graph_queries")
    return {
        "sessions": n,
        "turns": total("turns"),
        "tokens_total": total("tokens_total"),
        "tokens_output": total("tokens_output"),
        "tool_calls": total("tool_calls"),
        "graph_queries": queries,
        "whole_file_reads": reads,
        "sessions_with_whole_file_reads": sum(1 for r in rows if r["whole_file_reads"]),
        "avg_tokens_per_session": total("tokens_total") // n if n else 0,
        "graph_queries_per_whole_file_read": round(queries / reads, 2) if reads else None,
        "estimated_sessions": sum(1 for r in rows if r["estimated"]),
    }


def to_csv(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if r[k] is None else r[k]) for k in COLUMNS})
    return buf.getvalue()


def render_html(rows, days):
    roll = rollup(within(rows, days))
    cells = "".join("<tr><th>%s</th><td>%s</td></tr>" % (html.escape(k.replace("_", " ")),
                                                          html.escape(str(v)))
                    for k, v in roll.items())
    head = "".join("<th>%s</th>" % html.escape(c) for c in COLUMNS)
    body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % html.escape("" if r[c] is None else str(r[c]))
                                           for c in COLUMNS) for r in rows)
    return (
        "<!doctype html><meta charset=utf-8><title>agent-spec ROI</title>"
        "<style>body{font:14px system-ui;margin:2em}table{border-collapse:collapse}"
        "td,th{border:1px solid #bbb;padding:3px 8px;text-align:right}th{background:#eee}"
        "</style><h1>agent-spec receipts</h1>"
        "<p>Local only. <a href='/export.csv'>Download CSV</a>. Token counts marked "
        "estimated are transcript-length estimates, not billed usage.</p>"
        "<h2>Last %d days</h2><table>%s</table>"
        "<h2>Sessions (%d)</h2><table><tr>%s</tr>%s</table>" % (days, cells, len(rows), head, body))


def make_handler(project, days):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            rows = load_receipts(project)
            if self.path.split("?")[0] == "/export.csv":
                body, ctype = to_csv(rows).encode(), "text/csv"
            elif self.path.split("?")[0] in ("/", "/index.html"):
                body, ctype = render_html(rows, days).encode(), "text/html; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass
    return Handler


def serve(project, port, days):
    server = HTTPServer(("127.0.0.1", port), make_handler(project, days))
    print("agent-spec ROI viewer on http://127.0.0.1:%d (Ctrl-C to stop)" % server.server_address[1])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Receipt / ROI viewer")
    ap.add_argument("--project", default=os.getcwd())
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p = sub.add_parser("rollup")
    p.add_argument("--days", type=int, default=7)
    p = sub.add_parser("export")
    p.add_argument("--csv", action="store_true", required=True)
    p.add_argument("-o", "--output")
    p = sub.add_parser("serve")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--days", type=int, default=7)
    args = ap.parse_args(argv)

    rows = load_receipts(args.project)
    if args.cmd == "serve":
        return serve(args.project, args.port, args.days)
    if args.cmd == "export":
        text = to_csv(rows)
        if args.output:
            with open(args.output, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
        else:
            sys.stdout.write(text)
        return 0
    if args.cmd == "rollup":
        for k, v in rollup(within(rows, args.days)).items():
            print("%-36s %s" % (k, v))
        return 0
    if not rows:
        print("no receipts yet — they are written when a Cursor session ends "
              "(or run: ./.agent-spec/bin/agent-spec-receipt.py)")
        return 0
    for r in rows:
        print("%s  %s  turns=%-4s tokens=%-9s graph=%-3s whole-file-reads=%s%s" % (
            r["ts"], r["session_id"][:8], r["turns"], r["tokens_total"], r["graph_queries"],
            r["whole_file_reads"], "  (est)" if r["estimated"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
