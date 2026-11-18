"""Tokens the raw-code skills saved, per chat and across chats: the numbers that make the
`/agent-spec-raw-code-full` rules visible on the dashboard.

Four levers, each priced from a request's own spans (bytes / 4 = tokens, labelled estimated):

  graph         a graphify query instead of reading files: one median indexed file per query
  ranged_reads  the unread rest of each file read in a range
  subagents     tool output that stayed in a subagent's throwaway context
  writes        a targeted Edit instead of re-generating the file: file size minus the edit

The first three come from `impact.tool_rows`, the per-request Impact tab's own model, so the
chat total always equals the sum of its requests' Impact cards. `writes` is new here.

The multiplier is what makes the skill matter: whatever enters the context is re-read on every
later model call in that chat. `resend_avoided` multiplies each saving by the number of model
calls after it in the same chat: the tool calls left in its own request, plus every later
tool call and request (each tool result triggers one more call, each request at least one).
That count is measured; the result is still an estimate and is labelled so.

The skill is not free: invoking it puts its SKILL.md into the context, where it is re-sent on
every later call as well. `skill_cost` prices each invocation the same way (file size / 4, times
the calls after it, which includes every tool call of the invoking request), and `net_*` is savings minus that cost, so a chat where the mode did not pay
for itself shows a negative net instead of hiding it.

A chat is in raw-code mode from the first request that invoked `/agent-spec-raw-code` or
`/agent-spec-raw-code-full` until one invoked `/agent-spec-verbose`, matching the skill's own
"persists until /agent-spec-verbose" contract.
"""
from __future__ import annotations

import os
from collections import defaultdict

from . import impact

BYTES_PER_TOKEN = 4
RAW_CODE = ("agent-spec-raw-code", "agent-spec-raw-code-full")
VERBOSE = "agent-spec-verbose"
MIN_COMPARE = 5
SKILL_DIRS = (os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "skills"),
              os.path.join(os.path.expanduser("~"), ".cursor", "skills"))


def skill_bytes(name: str) -> int:
    """Size of the skill body Cursor loads on invocation (package copy, then the installed one)."""
    for root in SKILL_DIRS:
        try:
            return os.path.getsize(os.path.join(root, name, "SKILL.md"))
        except OSError:
            continue
    return 0
LEVERS = ("graph", "ranged_reads", "subagents", "writes")
LEVER_LABEL = {
    "graph": "Graph queries instead of file reads",
    "ranged_reads": "Ranged reads instead of whole files",
    "subagents": "Sweeps kept in subagents",
    "writes": "Targeted edits instead of rewrites",
}


def _tok(b) -> int:
    return int((b or 0) / BYTES_PER_TOKEN)


def _edit_avoided(project: str, attrs: dict) -> int:
    """Bytes a full rewrite would have generated beyond the edit itself."""
    path = attrs.get("file_path") or ""
    if not path:
        return 0
    full = path if os.path.isabs(path) else os.path.join(project, path)
    try:
        size = os.path.getsize(full)
    except OSError:
        return 0
    changed = (attrs.get("chars_added") or 0) + (attrs.get("chars_removed") or 0)
    return max(0, size - changed) if changed else 0


def _mode_timeline(traces: list) -> list:
    """raw-code on/off for each request in chat order."""
    on, out = False, []
    for t in traces:
        skills = set(t.get("skills") or [])
        if skills & set(RAW_CODE):
            on = True
        if VERBOSE in skills:
            on = False
        out.append(on)
    return out


def for_session(project: str, conn, traces: list, spans_by_trace: dict) -> dict:
    """`traces` are one chat's requests; returns the chat's savings, per lever and per request."""
    traces = sorted(traces, key=lambda t: t.get("start") or "")
    modes = _mode_timeline(traces)
    # Every saving with its position in the chat, so later calls can be counted after it.
    events = []           # (request index, lever, bytes, calls left in that request after it)
    calls_per_request = []
    for i, t in enumerate(traces):
        spans = spans_by_trace.get(t["trace_id"], [])
        rows = impact.tool_rows(project, spans)
        main = [r for r in rows if not r["in_subagent"]]
        calls_per_request.append(sum(1 for s in spans if s.get("kind") == "tool"))
        for j, r in enumerate(main):
            left = len(main) - j - 1
            if r["category"] == "graph" and r["avoided"]:
                events.append((i, "graph", r["avoided"], left))
            elif r["category"] == "read" and r["avoided"]:
                events.append((i, "ranged_reads", r["avoided"], left))
        kept = sum(r["bytes"] or 0 for r in rows if r["in_subagent"])
        if kept:
            events.append((i, "subagents", kept, 0))
        ids = [r["span_id"] for r in main]
        for s in spans:
            if s.get("kind") == "edit":
                b = _edit_avoided(project, s.get("attributes") or {})
                if b:
                    pos = ids.index(s["span_id"]) if s["span_id"] in ids else len(ids) - 1
                    events.append((i, "writes", b, max(0, len(ids) - pos - 1)))

    later_calls = []      # model calls after request i ends
    for i in range(len(traces)):
        later_calls.append(sum(calls_per_request[i + 1:]) + (len(traces) - i - 1))
    by_lever = {k: 0 for k in LEVERS}
    resend = 0
    per_request = defaultdict(lambda: {k: 0 for k in LEVERS})
    for i, lever, b, left in events:
        tok = _tok(b)
        by_lever[lever] += tok
        per_request[i][lever] += tok
        resend += tok * (later_calls[i] + left)
    kept_out = sum(by_lever.values())
    cost = cost_resend = 0
    for i, t in enumerate(traces):
        for name in set(t.get("skills") or []) & set(RAW_CODE):
            tok = _tok(skill_bytes(name))
            cost += tok
            # Loaded before the request's first tool call, so every one of them re-sends it.
            cost_resend += tok * (later_calls[i] + calls_per_request[i])
    mode_on = [i for i, m in enumerate(modes) if m]
    kept_on = sum(sum(per_request[i].values()) for i in mode_on)
    return {
        "kept_out": kept_out,
        "resend_avoided": resend,
        "skill_cost": {"tokens": cost, "resend": cost_resend},
        "net_kept_out": kept_out - cost,
        "net_resend_avoided": resend - cost_resend,
        "later_calls": sum(calls_per_request) + len(traces),
        "by_lever": by_lever,
        "raw_code": {"active": bool(mode_on), "since_request": (mode_on[0] + 1) if mode_on else None,
                     "requests_on": len(mode_on), "requests": len(traces), "kept_out_while_on": kept_on},
        "requests": [{"trace_id": t["trace_id"], "raw_code": modes[i], "kept_out": sum(per_request[i].values()),
                      "by_lever": dict(per_request[i]), "later_calls": later_calls[i], "tools": calls_per_request[i],
                      "comparable": t.get("source") == "hook" and t.get("origin") != "local" and calls_per_request[i] > 0}
                     for i, t in enumerate(traces)],
        "provenance": "estimated",
    }


def overview(project: str, conn, traces: list, spans: list, limit: int = 12) -> dict:
    """Every chat's savings, the raw-code vs plain comparison and the top chats."""
    by_trace = defaultdict(list)
    for s in spans:
        by_trace[s["trace_id"]].append(s)
    chats = defaultdict(list)
    for t in traces:
        if t.get("session_id"):
            chats[t["session_id"]].append(t)
    rows, totals = [], {k: 0 for k in LEVERS}
    resend = cost = cost_resend = 0
    # The skill's price belongs only to the chats that loaded it: always-on rules cost nothing extra.
    skill = {"chats": 0, "kept_out": 0, "resend_avoided": 0, "cost_resend": 0}
    groups = {"raw_code": {"requests": 0, "kept_out": 0}, "plain": {"requests": 0, "kept_out": 0}}
    for sid, ts in chats.items():
        sv = for_session(project, conn, ts, by_trace)
        for k in LEVERS:
            totals[k] += sv["by_lever"][k]
        resend += sv["resend_avoided"]
        cost += sv["skill_cost"]["tokens"]
        cost_resend += sv["skill_cost"]["resend"]
        if sv["skill_cost"]["tokens"]:
            skill["chats"] += 1
            skill["kept_out"] += sv["kept_out"]
            skill["resend_avoided"] += sv["resend_avoided"]
            skill["cost_resend"] += sv["skill_cost"]["resend"]
        for r in sv["requests"]:
            # Like for like: Cursor requests recorded by hooks that made at least one tool call.
            if not r["comparable"]:
                continue
            g = groups["raw_code" if r["raw_code"] else "plain"]
            g["requests"] += 1
            g["kept_out"] += r["kept_out"]
        first = min(ts, key=lambda t: t.get("start") or "")
        rows.append({"session_id": sid, "name": first.get("session_name"), "prompt": (first.get("prompt") or "")[:120],
                     "start": first.get("start"), "requests": len(ts), "kept_out": sv["kept_out"],
                     "resend_avoided": sv["resend_avoided"], "net_resend_avoided": sv["net_resend_avoided"],
                     "raw_code": sv["raw_code"]["active"],
                     "latest_trace_id": max(ts, key=lambda t: t.get("start") or "")["trace_id"]})
    for g in groups.values():
        g["per_request"] = round(g["kept_out"] / g["requests"]) if g["requests"] else None
    on, off = groups["raw_code"]["per_request"], groups["plain"]["per_request"]
    rows.sort(key=lambda r: -r["kept_out"])
    return {
        "kept_out": sum(totals.values()), "resend_avoided": resend, "by_lever": totals,
        "skill_cost": {"tokens": cost, "resend": cost_resend},
        "net_kept_out": sum(totals.values()) - cost, "net_resend_avoided": resend - cost_resend,
        "skill_chats": dict(skill, net=skill["resend_avoided"] - skill["cost_resend"]),
        "labels": LEVER_LABEL, "chats": len(rows),
        "chats_with_raw_code": sum(1 for r in rows if r["raw_code"]),
        # A ratio from a handful of requests is noise; below MIN_COMPARE per group the UI shows counts only.
        "compare": dict(groups, min_requests=MIN_COMPARE,
                        lift=round(on / off, 1) if on and off and min(groups["raw_code"]["requests"],
                                                                     groups["plain"]["requests"]) >= MIN_COMPARE else None),
        "top": [r for r in rows if r["kept_out"]][:limit],
        "provenance": "estimated",
    }
