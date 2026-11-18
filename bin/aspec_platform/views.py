"""Dashboard read models that combine traces with the measurements built on top of them.

traces.py is the lower layer: it reads events and the Cursor store into traces and
spans. signals, impact and skill_savings each read traces, so the views that show all of
them together live here, above every one of them, and traces imports none of them.
"""
from . import impact, signals, skill_savings
from . import traces as tr

SAVINGS_KEYS = ("kept_out", "resend_avoided", "net_kept_out", "net_resend_avoided",
                "skill_cost", "raw_code")


def _spans_by_trace(spans, wanted=None):
    by_trace = {}
    for s in spans:
        if wanted is None or s["trace_id"] in wanted:
            by_trace.setdefault(s["trace_id"], []).append(s)
    return by_trace


def list_conversations(project, conn, filters, limit=200, offset=0):
    loaded = tr.all_traces(project, conn)
    out = tr.list_conversations(project, conn, filters, limit, offset, loaded=loaded)
    if not out["conversations"]:
        return out
    traces, spans = loaded
    groups = tr.conversation_groups(traces, filters)
    by_trace = _spans_by_trace(spans)
    for row in out["conversations"]:
        sv = skill_savings.for_session(project, conn, groups[row["session_id"]], by_trace)
        row["savings"] = {k: sv[k] for k in SAVINGS_KEYS}
    return out


def request_detail(project, conn, trace_id):
    loaded = tr.all_traces(project, conn)
    detail = tr.request_detail(project, conn, trace_id, loaded=loaded)
    if detail is None:
        return None
    traces, spans = loaded
    trace, mine = detail["trace"], detail["spans"]
    session = [t for t in traces if t["session_id"] == trace["session_id"]]
    sids = {t["trace_id"] for t in session}
    detail["signals"] = signals.for_trace(trace, mine, session, [s for s in spans if s["trace_id"] in sids])
    try:
        detail["impact"] = impact.for_request(project, conn, trace, mine, detail["context"])
    except Exception as exc:  # the impact view is additive; never take the request page down with it
        detail["impact"] = {"error": str(exc)[:200]}
    try:
        detail["session_savings"] = skill_savings.for_session(project, conn, session, _spans_by_trace(spans, sids))
    except Exception as exc:  # additive, like impact
        detail["session_savings"] = {"error": str(exc)[:200]}
    return detail


def session_savings(project, conn, session_id):
    """One chat's savings, the same model the request page and the chat list use."""
    traces, spans = tr.all_traces(project, conn)
    session = [t for t in traces if t["session_id"] == session_id]
    if not session:
        return None
    sids = {t["trace_id"] for t in session}
    try:
        return skill_savings.for_session(project, conn, session, _spans_by_trace(spans, sids))
    except Exception as exc:  # additive: never take the chat page down with it
        return {"error": str(exc)[:200]}
