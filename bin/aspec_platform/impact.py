"""Per-request impact: what the harness changed in one request, against a plain Cursor chat.

Read-only and derived from the request's spans, the memory tables and Cursor's own context
breakdown. Every number carries its provenance:

- measured:  counted from hook rows (tool calls, read extents, guard blocks, injected facts).
- estimated: a counterfactual. A graph query is priced as the one whole-file read of the
  median indexed file it replaced; a ranged read as the rest of the file it did not read; a
  subagent as the tool output that stayed in its own context instead of the parent's.

Bytes become tokens at `BYTES_PER_TOKEN`, the same default the savings calculator uses.
"""
from __future__ import annotations

import json
import os
import re
import statistics
import threading

from . import common
from .traces import tool_category

BYTES_PER_TOKEN = 4.0
LARGE_OUTPUT_BYTES = 8000     # a tool result this big should have been capped (| head, -q)
HARNESS_PARTS = ("rules", "skills", "subagents")

_median_cache: dict = {}
_median_lock = threading.Lock()


def median_file_bytes(project) -> int | None:
    """Median size of the files in the project's dependency graph; None without a graph."""
    path = os.path.join(common.agent_spec_dir(project), "graph", "knowledge-graph.json")
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    with _median_lock:
        hit = _median_cache.get(path)
        if hit and hit[0] == mtime:
            return hit[1]
    try:
        with open(path, encoding="utf-8") as fh:
            nodes = json.load(fh).get("nodes") or []
    except (OSError, ValueError):
        return None
    sizes = []
    for n in nodes:
        rel = n.get("path") if isinstance(n, dict) else None
        if not rel:
            continue
        try:
            sizes.append(os.path.getsize(os.path.join(project, rel)))
        except OSError:
            continue
    value = int(statistics.median(sizes)) if sizes else None
    with _median_lock:
        _median_cache[path] = (mtime, value)
    return value


def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None


def _file_bytes(project, attrs):
    known = _int(attrs.get("file_bytes"))
    if known is not None:
        return known
    target = attrs.get("target")
    if not target:
        return None
    path = target if os.path.isabs(str(target)) else os.path.join(project, str(target))
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def _category(span):
    if span.get("kind") in ("edit", "subagent"):
        return span["kind"]
    attrs = span.get("attributes") or {}
    if attrs.get("category"):
        return attrs["category"]
    return tool_category(attrs.get("tool_name") or span.get("name"), attrs.get("target"))[0]


def _subagent_of(spans):
    """span_id -> id of the subagent span it ran under (None for the parent context)."""
    by_id = {s["span_id"]: s for s in spans}
    out = {}
    for s in spans:
        cur, seen = s.get("parent_span_id"), set()
        owner = None
        while cur and cur in by_id and cur not in seen:
            seen.add(cur)
            if by_id[cur].get("kind") == "subagent":
                owner = cur
                break
            cur = by_id[cur].get("parent_span_id")
        out[s["span_id"]] = owner
    return out


def _tok(b):
    return int(round(b / BYTES_PER_TOKEN)) if b is not None else None


def tool_rows(project, spans):
    """One dict per tool span: category, where it ran, bytes it put into a context, bytes avoided."""
    median = median_file_bytes(project)
    owner = _subagent_of(spans)
    rows = []
    for s in spans:
        if s.get("kind") not in ("tool", "edit"):
            continue
        attrs = s.get("attributes") or {}
        cat = _category(s)
        out_b = _int(attrs.get("bytes_out"))
        row = {"span_id": s["span_id"], "name": s.get("name"), "category": cat, "target": attrs.get("target"),
               "in_subagent": owner.get(s["span_id"]) is not None, "status": s.get("status"),
               "bytes": out_b, "avoided": 0, "basis": None}
        if cat == "read":
            size = _file_bytes(project, attrs)
            chars = _int(attrs.get("read_chars"))
            # None = the source did not say (Cursor's store, older hook rows): neither ranged nor whole.
            ranged = attrs.get("ranged") if isinstance(attrs.get("ranged"), bool) else None
            row.update(file_bytes=size, ranged=ranged is True, whole=ranged is False)
            row["bytes"] = chars if chars is not None else (size if ranged is False else None)
            if ranged and size is not None and chars is not None and size > chars:
                row["avoided"], row["basis"] = size - chars, "rest of the file left unread"
        elif cat == "graph" and median:
            row["avoided"] = max(0, median - (out_b or 0))
            row["basis"] = "one median file read (%d B) replaced by the query answer" % median
        rows.append(row)
    return rows


def rule_checks(rows, spans):
    """The raw-code-full rules this request can be checked against, from its spans."""
    main = [r for r in rows if not r["in_subagent"]]
    first = lambda cat: next((i for i, r in enumerate(main) if r["category"] == cat), None)
    g, srch = first("graph"), first("search")
    whole = [r for r in main if r["category"] == "read" and r.get("whole")]
    big = [r for r in main if (r.get("bytes") or 0) > LARGE_OUTPUT_BYTES and r["category"] in ("shell", "search", "graph")]
    subs = [s for s in spans if s.get("kind") == "subagent"]
    if srch is None:
        graph_first = {"pass": None, "detail": "no search in the main context" + (
            "" if g is None else "; first graph query is call %d" % (g + 1))}
    elif g is None:
        graph_first = {"pass": False, "detail": "searched (call %d) without a graph query" % (srch + 1)}
    else:
        graph_first = {"pass": g <= srch, "detail": "first graph query is call %d, first search call %d" % (g + 1, srch + 1)}
    # "pass": None means the rule did not apply to this request; it is left out of the score.
    checks = [
        dict(rule="Query the graph before searching", **graph_first),
        {"rule": "No whole-file reads in the main context",
         "pass": not whole,
         "detail": "%d whole-file read%s" % (len(whole), "" if len(whole) == 1 else "s")},
        {"rule": "Broad sweeps run in a subagent",
         "pass": bool(subs) or sum(1 for r in main if r["category"] == "search") <= 10,
         "detail": "%d subagent%s, %d searches in the main context" % (
             len(subs), "" if len(subs) == 1 else "s", sum(1 for r in main if r["category"] == "search"))},
        {"rule": "Tool output capped",
         "pass": not big,
         "detail": "%d result%s over %d B" % (len(big), "" if len(big) == 1 else "s", LARGE_OUTPUT_BYTES)},
    ]
    return checks


DIGEST_LINE = re.compile(r"^- \[([\w-]+)\] (.+?): ")


def injection_row(project, session_id):
    """The sessionStart hook's latest injections.jsonl row for one conversation, or None.
    Read live, not from `fact_injections`: the server never re-ingests memory, and a request
    shown while its chat is open must still list what the digest injected."""
    if not session_id:
        return None
    path = os.path.join(common.agent_spec_dir(project), "metrics", "injections.jsonl")
    needle = session_id.encode()
    last = None
    try:
        with open(path, "rb") as fh:
            for line in fh:
                if needle not in line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("conversation_id") == session_id:
                    last = row
    except OSError:
        return None
    return last


def injected_facts(conn, lines):
    """Digest lines -> [{fact_id, type, subject}], matched to memory_facts when the database has
    them; a line no fact matches is still listed, parsed from the digest text itself."""
    known = {}
    if conn is not None:
        try:
            known = {r[0]: (r[1], r[2]) for r in conn.execute("SELECT fact_id, type, subject FROM memory_facts")}
        except Exception:
            known = {}
    from .ingest import match_facts
    out = []
    for line in lines or []:
        fid = (match_facts([line], known) or [None])[0]
        if fid:
            out.append({"fact_id": fid, "type": known[fid][0], "subject": known[fid][1]})
            continue
        m = DIGEST_LINE.match(str(line))
        if m:
            out.append({"fact_id": "digest:%d" % len(out), "type": m.group(1), "subject": m.group(2)})
    return sorted(out, key=lambda f: 0 if f["type"] == "constraint" else 1)


def for_request(project, conn, trace, spans, context=None) -> dict:
    rows = tool_rows(project, spans)
    main = [r for r in rows if not r["in_subagent"]]
    sub = [r for r in rows if r["in_subagent"]]
    count = lambda rs, cat: sum(1 for r in rs if r["category"] == cat)
    ctx_bytes = sum(r["bytes"] or 0 for r in main)
    kept_out = sum(r["bytes"] or 0 for r in sub)
    avoided = {
        "graph": sum(r["avoided"] for r in rows if r["category"] == "graph" and not r["in_subagent"]),
        "ranged_reads": sum(r["avoided"] for r in main if r["category"] == "read"),
        "subagents": kept_out,
    }
    total_avoided = sum(avoided.values())
    breakdown = ((context or {}).get("budget") or {}).get("breakdown") or {}
    harness = {k: breakdown.get(k) for k in HARNESS_PARTS if isinstance(breakdown.get(k), int)}
    injection = injection_row(project, trace.get("session_id") or "")
    facts = injected_facts(conn, (injection or {}).get("facts"))
    return {
        "bytes_per_token": BYTES_PER_TOKEN,
        "median_file_bytes": median_file_bytes(project),
        "tools": {
            "graph": count(main, "graph"), "memory": count(main, "memory"), "search": count(main, "search"),
            "read_whole": sum(1 for r in main if r["category"] == "read" and r.get("whole")),
            "read_ranged": sum(1 for r in main if r["category"] == "read" and r.get("ranged")),
            "shell": count(main, "shell"), "edit": count(main, "edit"), "in_subagents": len(sub),
            "subagents": sum(1 for s in spans if s.get("kind") == "subagent"),
            "guard_blocks": sum(1 for s in spans if s.get("kind") == "guard"),
        },
        "tokens": {
            "context_in": _tok(ctx_bytes), "avoided": _tok(total_avoided),
            "avoided_by": {k: _tok(v) for k, v in avoided.items()},
            "plain_cursor": _tok(ctx_bytes + total_avoided),
            "provenance": "estimated",
        },
        "rules": rule_checks(rows, spans),
        "memory": {"facts": facts, "digest_bytes": _int((injection or {}).get("digest_bytes")),
                   "recorded": injection is not None, "provenance": "measured"},
        "harness": {"tokens": harness, "total": sum(harness.values()) if harness else None,
                    "provenance": "measured" if harness else None},
        "graph_queries": [{"name": r["name"], "target": r["target"], "bytes": r["bytes"], "avoided": r["avoided"]}
                          for r in main if r["category"] in ("graph", "memory")][:20],
        "whole_reads": [{"target": r["target"], "file_bytes": r.get("file_bytes")}
                        for r in main if r["category"] == "read" and r.get("whole")][:20],
    }
