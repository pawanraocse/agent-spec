"""Hash-chained session audit export (P3-011, P3-012).

One JSONL file per conversation: a header, then every request, its tool actions, the risk
gate's decisions for the session and the outcome signals, in time order. Each line carries
`prev` (the previous line's hash) and `hash` = sha256(prev + canonical JSON of the line
without `hash`). `verify` recomputes the chain, so an edited, dropped or reordered line is
reported with its line number.

Prompts and tool targets are redacted on the way out; the export is meant to leave the
machine (a compliance reviewer, a ticket), so it carries no raw secrets.

Allowed-code reason (DEC-15): *exact* — hashing and copying recorded facts; no model.
"""
from __future__ import annotations

import hashlib
import json
import os

from . import common, redact, signals
from . import traces as tr

GENESIS = "0" * 64
FORMAT = "agent-spec-audit/1"


def _canon(row: dict) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _seal(rows: list) -> list:
    prev, out = GENESIS, []
    for row in rows:
        body = dict(row, prev=prev)
        body["hash"] = hashlib.sha256((prev + _canon(body)).encode("utf-8")).hexdigest()
        out.append(body)
        prev = body["hash"]
    return out


def _risk_rows(project: str, session_id: str) -> list:
    path = os.path.join(common.agent_spec_dir(project), "metrics", "risk.jsonl")
    keys, rows = set(), []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            events = [json.loads(line) for line in fh if line.strip()]
    except (OSError, ValueError):
        return []
    for e in events:  # decisions carry no session; they join to it through the action key
        if isinstance(e, dict) and e.get("session") == session_id and e.get("key"):
            keys.add(e["key"])
    for e in events:
        if isinstance(e, dict) and (e.get("session") == session_id or e.get("key") in keys):
            rows.append({"type": "risk", "ts": e.get("ts"), "event": e.get("event"), "tier": e.get("tier"),
                         "tool": e.get("tool"), "target": redact.redact(str(e.get("target") or "")),
                         "by": e.get("by"), "key": e.get("key")})
    return rows


def build(project: str, conn, session_id: str) -> list:
    """Sealed rows for one conversation, or [] when it has no traces."""
    all_t, all_s = tr.all_traces(project, conn)
    session = sorted((t for t in all_t if t.get("session_id") == session_id), key=lambda t: t.get("start") or "")
    if not session:
        return []
    by_trace = {}
    for s in all_s:
        by_trace.setdefault(s["trace_id"], []).append(s)
    rows = [{"type": "header", "format": FORMAT, "session_id": session_id, "exported_at": common.utc_now(),
             "project": os.path.basename(os.path.realpath(project)), "requests": len(session)}]
    timeline = []
    for t in session:
        spans = sorted(by_trace.get(t["trace_id"], []), key=lambda s: (s.get("start") or "", s.get("seq") or 0))
        timeline.append((t.get("start") or "", 0, {
            "type": "request", "ts": t.get("start"), "request_id": t["trace_id"], "status": t.get("status"),
            "model": t.get("model"), "source": t.get("source"), "skills": t.get("skills") or [],
            "prompt": redact.redact(str(t.get("prompt") or ""))[:2000] or None}))
        for s in spans:
            if s.get("kind") not in ("tool", "edit", "guard", "subagent"):
                continue
            a = s.get("attributes") or {}
            timeline.append((s.get("start") or "", 1, {
                "type": "action", "ts": s.get("start"), "request_id": t["trace_id"], "span_id": s.get("span_id"),
                "kind": s.get("kind"), "name": s.get("name"), "status": s.get("status"),
                "target": redact.redact(str(a.get("file_path") or a.get("target") or ""))[:500] or None}))
        sig = signals.for_trace(t, spans, session, [s for x in session for s in by_trace.get(x["trace_id"], [])])
        timeline.append(((t.get("end") or t.get("start") or "") + "~", 2, {
            "type": "outcome", "ts": t.get("end"), "request_id": t["trace_id"], "status": t.get("status"),
            "tool_failures": sig["tool_failures"]["count"], "files_edited": sig["files_edited"]["files"],
            "verified_after_last_edit": sig["verification"]["ran_after_last_edit"], "guard_blocks": sig["guard_blocks"]}))
    for r in _risk_rows(project, session_id):
        timeline.append((r.get("ts") or "", 1, r))
    timeline.sort(key=lambda x: (x[0], x[1]))
    rows.extend(row for _, _, row in timeline)
    return _seal(rows)


def to_jsonl(rows: list) -> str:
    return "".join(_canon(r) + "\n" for r in rows)


def verify(text: str) -> dict:
    """{"ok", "lines", "error"?, "line"?}: the first line whose hash or link does not hold."""
    prev, n = GENESIS, 0
    for n, line in enumerate((l for l in text.splitlines() if l.strip()), 1):
        try:
            row = json.loads(line)
        except ValueError:
            return {"ok": False, "lines": n, "line": n, "error": "not JSON"}
        claimed = row.pop("hash", None)
        if row.get("prev") != prev:
            return {"ok": False, "lines": n, "line": n, "error": "broken link: a line before this one was removed, added or reordered"}
        if hashlib.sha256((prev + _canon(row)).encode("utf-8")).hexdigest() != claimed:
            return {"ok": False, "lines": n, "line": n, "error": "hash mismatch: this line was edited"}
        prev = claimed
    if n == 0:
        return {"ok": False, "lines": 0, "error": "empty export"}
    return {"ok": True, "lines": n, "head": prev}
