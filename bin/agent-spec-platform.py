#!/usr/bin/env python3
"""agent-spec-platform.py — local platform database, ingest and dashboard (Phase 2).

  agent-spec-platform.py init     [--project P]            create / migrate platform.db
  agent-spec-platform.py status   [--project P] [--json]   schema version, row counts, ingest lag
  agent-spec-platform.py ingest   [WHAT ...] [--rebuild]   transcripts gates memory graph backlog runs
  agent-spec-platform.py serve    [--port 8765]            dashboard (extra) or ROI fallback

The database is derived from files (DEC-04); `ingest --rebuild` recreates it. Stdlib only for the
data layer; `serve` needs the optional extra (requirements-platform.txt) and otherwise falls back
to `agent-spec-roi.py serve` on the same port. Fail-soft: errors print one line and exit non-zero,
never a traceback.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from aspec_platform import common, db  # noqa: E402

TABLES = ("requests", "steps", "subagent_runs", "events", "gate_events", "tasks", "memory_facts",
          "fact_injections", "experiences", "graph_stats", "quarantine_events")


def cmd_init(args) -> int:
    project = common.find_project(args.project)
    path = db.db_path(project)
    conn = db.open_ready(path)
    print("platform db ready: %s (schema v%d)" % (path, db.schema_version(conn)))
    conn.close()
    return 0


def cmd_status(args) -> int:
    project = common.find_project(args.project)
    path = db.db_path(project)
    if not os.path.isfile(path):
        print("no platform db at %s — run: agent-spec-platform.py init" % path)
        return 1
    conn = db.connect(path, readonly=True)
    counts = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in TABLES}
    out = {"path": path, "schema": db.schema_version(conn), "rows": counts}
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print("%s  schema v%d" % (path, out["schema"]))
        for name, n in counts.items():
            print("  %-18s %d" % (name, n))
    return 0


def cmd_ingest(args) -> int:
    from aspec_platform import ingest
    project = common.find_project(args.project)
    try:
        report = ingest.run(project, args.what or ["all"], rebuild=args.rebuild)
    except db.SchemaError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    for name, stats in report.items():
        print("%-12s %s" % (name, " ".join("%s=%s" % kv for kv in sorted(stats.items()))))
    return 0


def cmd_export(args) -> int:
    from aspec_platform import export
    project = common.find_project(args.project)
    path = db.db_path(project)
    if not os.path.isfile(path):
        print("no platform db at %s — run: agent-spec-platform.py init" % path, file=sys.stderr)
        return 1
    conn = db.connect(path, readonly=True)
    try:
        written = export.write(conn, args.out, args.format)
    finally:
        conn.close()
    print("proof pack (counts only, no prompts or paths): %s" % ", ".join(os.path.join(args.out, f) for f in written))
    return 0



def cmd_seed(args) -> int:
    from aspec_platform import demo_seed
    project = common.find_project(args.project)
    if args.remove:
        out = demo_seed.remove(project)
    else:
        out = demo_seed.seed(project)
    print(json.dumps(out))
    return 0


def cmd_trace(args) -> int:
    """DV-040: the review skill's read tool. Prints traces as compact span trees (or JSON)."""
    from aspec_platform import traces
    project = common.find_project(args.project)
    try:
        conn = db.connect(db.db_path(project), readonly=True) if os.path.isfile(db.db_path(project)) else None
    except Exception:
        conn = None
    all_t, spans = traces.all_traces(project, conn)
    if args.request:
        picked = [t for t in all_t if t["trace_id"] == args.request]
    elif args.session:
        picked = sorted((t for t in all_t if t["session_id"] == args.session), key=lambda t: t.get("start") or "")
    else:
        picked = all_t[:args.list]
    if args.json:
        ids = {t["trace_id"] for t in picked}
        print(json.dumps({"traces": picked, "spans": [s for s in spans if s["trace_id"] in ids]}, indent=1))
        return 0 if picked else 1
    if not args.request and not args.session:
        for t in picked:
            print("%s  %s  %-9s %6s ms  tools=%d sub=%d guard=%d err=%d  %s" % (
                t["trace_id"], t["session_id"][:12], t.get("status"), t.get("duration_ms") or "-", t["tool_count"],
                t["subagent_count"], t["guard_count"], t["error_count"], (t.get("prompt") or "")[:60].replace("\n", " ")))
        return 0
    for t in picked:
        print("# trace %s  session=%s  source=%s  status=%s  duration=%sms  skills=%s" % (
            t["trace_id"], t["session_id"], t["source"], t.get("status"), t.get("duration_ms"), ",".join(t.get("skills") or [])))
        print("# prompt: %s" % (t.get("prompt") or "")[:300].replace("\n", " "))
        mine = [s for s in spans if s["trace_id"] == t["trace_id"]]
        kids = {}
        for s in mine:
            kids.setdefault(s.get("parent_span_id"), []).append(s)

        def walk(parent, depth):
            for s in sorted(kids.get(parent, []), key=lambda x: (x.get("start") or "", x.get("seq") or 0)):
                a = s.get("attributes") or {}
                note = a.get("target") or a.get("task") or a.get("summary") or a.get("text") or a.get("error_message") or ""
                print("%s%s  %s %s  %s  %sms  in=%s out=%s  %s" % (
                    "  " * depth, s["span_id"], s["kind"], s["name"][:40], s.get("status"), s.get("duration_ms"),
                    a.get("bytes_in", "-"), a.get("bytes_out", "-"), str(note)[:120].replace("\n", " ")))
                walk(s["span_id"], depth + 1)
        walk(None, 0)
    return 0 if picked else 1


def _index_conn(project, refresh: bool):
    """Writer connection after an incremental index pass (cheap when nothing changed)."""
    from aspec_platform import ingest
    if refresh:
        ingest.run(project, ["index"])
    return db.open_ready(db.db_path(project))


def _filters(args) -> dict:
    return {"kinds": [k for k in (args.kind or "").split(",") if k], "path": args.path,
            "since": args.since, "session": args.session}


def _print_hits(hits) -> None:
    for i, h in enumerate(hits, 1):
        where = h["ref"] if h["kind"] not in ("request", "review") else "%s %s" % (h["kind"], h["ref"])
        print("[%d] %-7s %s  (%s)" % (i, h["kind"], where, "+".join(h.get("matched_by") or [])))
        print("    %s" % h["title"][:120])
        snip = (h.get("snippet") or "").replace("\n", " ")
        if snip:
            print("    %s" % snip[:240])


def cmd_search(args) -> int:
    """PI-003: hybrid search over the local project index (code, docs, rules, memory, requests, reviews)."""
    from aspec_platform import retrieval
    project = common.find_project(args.project)
    conn = _index_conn(project, not args.no_refresh)
    try:
        result = retrieval.search(conn, " ".join(args.query), _filters(args), args.limit)
    finally:
        conn.close()
    if args.json:
        print(json.dumps(result, indent=1))
    else:
        print("# mode=%s hits=%d%s" % (result["mode"], len(result["hits"]),
                                       "".join("  warning: %s" % w for w in result["warnings"])))
        _print_hits(result["hits"])
    return 0 if result["hits"] else 1


def cmd_rag_embed(args) -> int:
    """Embed every pending chunk with AGENT_SPEC_EMBED (the ingest pass caps each run)."""
    from aspec_platform import retrieval
    project = common.find_project(args.project)
    embedder = retrieval.get_embedder()
    if embedder is None:
        print("error: set AGENT_SPEC_EMBED=ollama:<model> (e.g. ollama:nomic-embed-text)", file=sys.stderr)
        return 2
    conn = _index_conn(project, True)
    total = 0
    try:
        while True:
            with conn:
                done = retrieval.embed_pending(conn, embedder)
            total += done
            if done:
                print("embedded %d (total %d)" % (done, total), flush=True)
            if done < retrieval.EMBED_PER_PASS:
                break
    finally:
        conn.close()
    print("ok: %d chunk(s) embedded with %s" % (total, embedder.name))
    return 0


def cmd_rag_eval(args) -> int:
    """Retrieval accuracy (hit@1, hit@k, MRR) for keyword, semantic and hybrid search."""
    from aspec_platform import rag_eval
    project = common.find_project(args.project)
    conn = _index_conn(project, not args.no_refresh)
    try:
        if args.build or not rag_eval.load_golden(project):
            built = rag_eval.build_golden(conn, project, n=args.n, model=args.model)
            print("golden: %d case(s) -> %s (questions by %s)" % (built["cases"], built["path"], built["model"] or "docstrings"))
        with conn:
            result = rag_eval.run(conn, project, k=args.k, label=args.label)
    finally:
        conn.close()
    if args.json or not result.get("ok"):
        print(json.dumps(result, indent=1))
        return 0 if result.get("ok") else 1
    print("# %d cases, k=%d, embedder=%s" % (result["cases"], result["k"], result["embedder"] or "none"))
    for mode, sc in result["modes"].items():
        print("%-9s hit@1=%.0f%%  hit@%d=%.0f%%  MRR=%.3f" % (mode, sc["hit1"] * 100, result["k"], sc["hitk"] * 100, sc["mrr"]))
    return 0


def cmd_ask(args) -> int:
    """PI-004: retrieval + citations; a local model answers only when AGENT_SPEC_LLM is set."""
    from aspec_platform import retrieval
    project = common.find_project(args.project)
    conn = _index_conn(project, not args.no_refresh)
    try:
        result = retrieval.ask(conn, project, " ".join(args.query), _filters(args), args.limit)
        if args.sources:
            result["sources"] = retrieval._sources_block(conn, result["hits"], args.sources)
    finally:
        conn.close()
    if args.json:
        print(json.dumps(result, indent=1))
        return 0 if result["hits"] else 1
    print("# mode=%s hits=%d" % (result["mode"], len(result["hits"])))
    if result.get("answer"):
        print("## answer (%s, AI-generated)\n%s\n" % (result["answer"]["model"], result["answer"]["text"]))
    _print_hits(result["hits"])
    if result.get("related"):
        print("# related by import graph: " + ", ".join(r["path"] for r in result["related"]))
    if args.sources:
        print("\n## sources\n" + result["sources"])
    return 0 if result["hits"] else 1


def cmd_audit(args) -> int:
    """P3-011: export one conversation as hash-chained JSONL, or verify an export."""
    from aspec_platform import audit_export
    if args.verify:
        with open(args.verify, encoding="utf-8") as fh:
            result = audit_export.verify(fh.read())
        print(json.dumps(result))
        return 0 if result["ok"] else 1
    if not args.session:
        print("error: --session or --verify is required", file=sys.stderr)
        return 2
    project = common.find_project(args.project)
    try:
        conn = db.connect(db.db_path(project), readonly=True) if os.path.isfile(db.db_path(project)) else None
    except Exception:
        conn = None
    rows = audit_export.build(project, conn, args.session)
    if not rows:
        print("error: no traces for session %s" % args.session, file=sys.stderr)
        return 1
    text = audit_export.to_jsonl(rows)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("wrote %s (%d lines, head %s)" % (args.out, len(rows), rows[-1]["hash"][:12]))
    else:
        sys.stdout.write(text)
    return 0


def cmd_retain(args) -> int:
    """H-041: archive old rows of oversized append-only files (dry run unless --apply)."""
    from aspec_platform import retention
    project = common.find_project(args.project)
    actions = retention.apply(project) if args.apply else retention.plan(project)
    print(json.dumps({"applied": bool(args.apply), "config": retention.config(project), "actions": actions}, indent=2))
    return 0


def cmd_signals(args) -> int:
    """PI-006: measured outcome signals for one request (the review skill's quality evidence)."""
    from aspec_platform import signals
    project = common.find_project(args.project)
    try:
        conn = db.connect(db.db_path(project), readonly=True) if os.path.isfile(db.db_path(project)) else None
    except Exception:
        conn = None
    out = signals.for_request(project, conn, args.request)
    if out is None:
        print("error: request not found: %s" % args.request, file=sys.stderr)
        return 1
    print(json.dumps(out, indent=1))
    return 0


def cmd_serve(args) -> int:
    from aspec_platform import serve
    return serve.main(args)


def cmd_hooks(args) -> int:
    from aspec_platform import hook_logs
    project = os.path.abspath(common.find_project(args.project))
    entries = hook_logs.harvest(project)
    report = hook_logs.diagnose(entries)
    report["coverage"] = hook_logs.coverage(entries, project)
    hook = hook_logs.load_hook(project, os.path.dirname(HERE))
    redact = getattr(hook, "_redact", None) or (lambda s: s)
    metrics = os.path.join(common.agent_spec_dir(project), "metrics")
    if args.payloads:
        report["payloads"] = hook_logs.write_payloads(entries, os.path.join(metrics, "hook-payloads"), redact)
    if args.fixtures:
        report["fixtures"] = hook_logs.write_payloads(entries, args.fixtures, redact, project, fixture=True)
    if args.backfill:
        report["backfilled"] = hook_logs.backfill(entries, os.path.join(metrics, "events.jsonl"), hook) if hook else 0
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print("hook invocations: %d (%d failed) | events: %s | cursor %s" % (
        report["invocations"], report["failed"], ", ".join(report["events"]) or "none",
        report["cursor_version"] or "?"))
    for reason, n in report["reasons"].items():
        print("  %3d x %s" % (n, reason))
    if report["fix"]:
        print("fix: " + report["fix"])
    cov = report["coverage"]
    print("coverage: %d/%d registered events fired%s" % (
        cov["fired"], cov["registered"], "" if cov["missing"] else " — complete"))
    for ev in cov["missing"]:
        print("  missing %-20s %s" % (ev, cov["hints"][ev]))
    for key in ("payloads", "fixtures"):
        if key in report:
            print("%s: %d file(s)" % (key, len(report[key])))
    if "backfilled" in report:
        print("backfilled: %d row(s) into events.jsonl" % report["backfilled"])
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent-spec-platform.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="create or migrate platform.db")
    p.add_argument("--project")
    p.set_defaults(fn=cmd_init)
    p = sub.add_parser("status", help="schema version and row counts")
    p.add_argument("--project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("ingest", help="import files into platform.db (idempotent)")
    p.add_argument("what", nargs="*",
                   help="events transcripts gates memory graph quarantine runs experiences traces index (default: all)")
    p.add_argument("--project")
    p.add_argument("--rebuild", action="store_true", help="drop and recreate the database first")
    p.set_defaults(fn=cmd_ingest)
    p = sub.add_parser("export", help="write the proof pack (CSV/JSON metrics, no prompts or paths)")
    p.add_argument("--project")
    p.add_argument("--out", default="proof-pack")
    p.add_argument("--format", choices=("csv", "json"), default="csv")
    p.set_defaults(fn=cmd_export)
    p = sub.add_parser("seed", help="add or remove demo_seed rows in platform.db")
    p.add_argument("--project")
    p.add_argument("--remove", action="store_true")
    p.set_defaults(fn=cmd_seed)
    p = sub.add_parser("trace", help="print request traces as span trees (the review skill reads this)")
    p.add_argument("--project")
    p.add_argument("--session", help="every request of one conversation_id, in order")
    p.add_argument("--request", help="one request (generation_id / trace id)")
    p.add_argument("--list", type=int, default=20, help="latest N requests, one line each")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_trace)
    p = sub.add_parser("hooks", help="read Cursor's hook log: why hooks fail, payloads, backfill")
    p.add_argument("--project")
    p.add_argument("--payloads", action="store_true", help="latest payload per event -> metrics/hook-payloads/")
    p.add_argument("--fixtures", metavar="DIR", help="scrubbed payloads (email, paths masked) -> DIR")
    p.add_argument("--backfill", action="store_true", help="append missing rows to metrics/events.jsonl")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_hooks)
    for name, fn, hlp in (("search", cmd_search, "hybrid search over the local project index"),
                          ("ask", cmd_ask, "retrieve cited sources for a question (answer only with AGENT_SPEC_LLM)")):
        p = sub.add_parser(name, help=hlp)
        p.add_argument("query", nargs="+")
        p.add_argument("--project")
        p.add_argument("--kind", help="comma list: code,doc,rule,memory,request,review")
        p.add_argument("--path", help="source path prefix, e.g. bin/aspec_platform/")
        p.add_argument("--since", help="ISO timestamp; requests, reviews and files changed after it")
        p.add_argument("--session", help="one conversation_id")
        p.add_argument("--limit", type=int, default=8)
        p.add_argument("--no-refresh", action="store_true", help="skip the incremental index pass")
        p.add_argument("--json", action="store_true")
        if name == "ask":
            p.add_argument("--sources", type=int, default=0, metavar="CHARS",
                           help="also print each source body, capped at CHARS")
        p.set_defaults(fn=fn)
    p = sub.add_parser("rag-embed", help="embed all pending index chunks (needs AGENT_SPEC_EMBED)")
    p.add_argument("--project")
    p.set_defaults(fn=cmd_rag_embed)
    p = sub.add_parser("rag-eval", help="retrieval accuracy: hit@1, hit@k, MRR per search mode")
    p.add_argument("--project")
    p.add_argument("--build", action="store_true", help="regenerate the golden set first")
    p.add_argument("--n", type=int, default=30, help="golden cases to generate")
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--model", help="Ollama model that writes the questions")
    p.add_argument("--label", help="name this run in the dashboard's accuracy history")
    p.add_argument("--no-refresh", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_rag_eval)
    p = sub.add_parser("audit", help="hash-chained JSONL audit of one conversation, or verify one (P3-011)")
    p.add_argument("--project")
    p.add_argument("--session", help="conversation id to export")
    p.add_argument("--out", help="file to write (default stdout)")
    p.add_argument("--verify", metavar="FILE", help="check an export's hash chain; exit 1 on any edit")
    p.set_defaults(fn=cmd_audit)
    p = sub.add_parser("retain", help="archive old rows of append-only logs over their size cap (H-041)")
    p.add_argument("--project")
    p.add_argument("--apply", action="store_true", help="move rows; without it, print the plan only")
    p.set_defaults(fn=cmd_retain)
    p = sub.add_parser("signals", help="measured outcome signals for one request (JSON)")
    p.add_argument("--project")
    p.add_argument("--request", required=True, help="trace id (generation_id)")
    p.set_defaults(fn=cmd_signals)
    p = sub.add_parser("serve", help="start the dashboard")
    p.add_argument("--project")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(fn=cmd_serve)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # fail-soft: one line, no traceback
        print("error: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        if os.environ.get("AGENT_SPEC_DEBUG"):
            raise
        return 1


if __name__ == "__main__":
    sys.exit(main())
