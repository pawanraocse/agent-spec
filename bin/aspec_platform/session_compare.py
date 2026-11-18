"""PI-010: two conversations side by side — tokens, outcome signals, quality and context.

Every block carries its provenance: counts read from spans are `measured` for hook and run
traces and `estimated` otherwise; quality comes from the session-review skill and is
`ai_judged`; context is what the sessionStart hook recorded injecting, `measured`. A block
the data cannot support is None, never a zero.
"""
from __future__ import annotations

import re

from . import impact, savings, signals, traces as tr

SESSION_ID = re.compile(r"^[\w.:-]{1,160}$")
NUMERIC = ("requests", "tool_calls", "tool_failures", "files_edited", "verified_requests", "guard_blocks",
           "subagents", "compactions", "rework_files")


def summarize(project, conn, session_id, loaded=None):
    """One conversation's comparison row, or None when it has no traces."""
    all_t, all_s = loaded or tr.all_traces(project, conn)
    mine = sorted((t for t in all_t if t.get("session_id") == session_id), key=lambda t: t.get("start") or "")
    if not mine:
        return None
    ids = {t["trace_id"] for t in mine}
    spans = [s for s in all_s if s["trace_id"] in ids]
    per = [signals.for_trace(t, [s for s in spans if s["trace_id"] == t["trace_id"]], mine, spans) for t in mine]

    edited, rework, skills = set(), set(), []
    tokens, has_tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}, False
    with_edits = verified = 0
    for sig, t in zip(per, mine):
        edited.update(sig["files_edited"]["files"])
        rework.update((sig.get("rework_later") or {}).get("files") or [])
        ran = sig["verification"]["ran_after_last_edit"]
        if ran is not None:
            with_edits += 1
            verified += 1 if ran else 0
        if sig["tokens"]:
            has_tokens = True
            for k in tokens:
                tokens[k] += sig["tokens"][k]
        for name in t.get("skills") or []:
            if name not in skills:
                skills.append(name)

    measured = all(sig["provenance"] == "measured" for sig in per)
    out = {
        "session_id": session_id,
        "provenance": "measured" if measured else "estimated",
        "requests": len(mine),
        "tool_calls": sum(s["tool_calls"] for s in per),
        "tool_failures": sum(s["tool_failures"]["count"] for s in per),
        "files_edited": len(edited),
        "requests_with_edits": with_edits,
        "verified_requests": verified,
        "guard_blocks": sum(s["guard_blocks"] for s in per),
        "subagents": sum(s["subagents"]["count"] for s in per),
        "compactions": sum(s["compactions"] for s in per),
        "rework_files": len(rework),
        "tokens": dict(tokens, total=sum(tokens.values())) if has_tokens else None,
        "skills": skills,
        "quality": _quality(project, session_id),
        "context": _context(project, conn, session_id),
    }
    return out


def _quality(project, session_id):
    review = tr.load_review(project, session_id)
    if not review:
        return None
    dims = {}
    for name, d in (review.get("dimensions") or {}).items():
        score = d.get("score") if isinstance(d, dict) else d
        dims[str(name)] = score if isinstance(score, (int, float)) and not isinstance(score, bool) else None
    overall = review.get("overall")
    return {"provenance": "ai_judged",
            "overall": overall if isinstance(overall, (int, float)) and not isinstance(overall, bool) else None,
            "dimensions": dims}


def _context(project, conn, session_id):
    row = impact.injection_row(project, session_id)
    if not row:
        return None
    facts = row.get("facts") or []
    return {"provenance": "measured", "digest_bytes": row.get("digest_bytes"),
            "facts_injected": len(facts),
            "facts": [f.get("subject") for f in impact.injected_facts(conn, facts)][:20]}


def compare(project, conn, a, b):
    """Both rows, the a − b delta of every count, and the token tool's text when transcripts exist.

    Raises LookupError for a malformed id or a session with neither traces nor a transcript."""
    for sid in (a, b):
        if not SESSION_ID.match(sid or ""):
            raise LookupError("session not found: %s" % (sid or "")[:80])
    loaded = tr.all_traces(project, conn)
    rows = {sid: summarize(project, conn, sid, loaded) for sid in (a, b)}
    text = None
    if conn is not None:
        try:
            text = savings.compare(conn, a, b)["text"]
        except (LookupError, RuntimeError):
            text = None
    for sid in (a, b):
        if rows[sid] is None and text is None:
            raise LookupError("session not found: %s" % sid[:80])
    ra, rb = rows[a], rows[b]
    delta = None
    if ra and rb:
        delta = {k: ra[k] - rb[k] for k in NUMERIC}
        if ra["tokens"] and rb["tokens"]:
            delta["tokens_total"] = ra["tokens"]["total"] - rb["tokens"]["total"]
    return {"a": ra or {"session_id": a}, "b": rb or {"session_id": b}, "delta": delta, "text": text}
