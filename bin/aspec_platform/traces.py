"""Request traces (DEC-16 §14.3, DV-010..DV-013).

A user message is a trace (`generation_id`); every step the harness took to answer it is a
span: prompt (root), skill, subagent, tool, guard, edit, response, compact. Three sources:

- `hook`         `.agent-spec/metrics/events.jsonl` from hooks/cursor-event.py. Durations are
                 measured (Cursor's `duration` / `duration_ms`, or paired start/stop events).
- `cursor_store` Cursor's local store via cursor_sessions.store_conversations() (unofficial).
                 Durations are estimated from message timestamps.
- `run`          hub-runner workflow runs, written by ingest.ingest_runs.

The builders are pure functions of their input rows, so the API can serve hook traces
straight from the event file (live) and ingest can persist the same result for SQL.

Allowed-code reason: plumbing (shape conversion) and exact computation (durations,
percentiles). No judgement lives here; findings come from agent-spec-session-review.
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone

from . import common, context_budget, handoffs

SKILL_PROMPT = re.compile(r"^\s*/([a-z0-9][a-z0-9_:-]{1,63})(?=\s|$)", re.I)
SKILL_PATH = re.compile(r"skills(?:-cursor)?[/\\]([a-z0-9][a-z0-9_-]+)[/\\]SKILL\.md", re.I)
EDIT_TOOL = re.compile(r"edit|write|search_replace|apply_patch|create_file|delete_file", re.I)
SUBAGENT_TOOL = re.compile(r"^(task|task_v\d+|subagent|run_subagent)$", re.I)


def ms(ts):
    """ISO-8601 (with or without millis / Z) or epoch ms -> epoch ms (int), else None."""
    if isinstance(ts, (int, float)) and not isinstance(ts, bool):
        return int(ts)
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def iso(epoch_ms):
    if epoch_ms is None:
        return None
    dt = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (epoch_ms % 1000)


class _Builder:
    def __init__(self, source: str, provenance: str):
        self.source, self.provenance = source, provenance
        self.traces, self.spans, self.seq = {}, {}, 0

    def trace(self, tid, session, start, **meta):
        t = self.traces.get(tid)
        if t is None:
            t = {"trace_id": tid, "session_id": session, "source": self.source, "workspace": None,
                 "prompt": None, "model": None, "cursor_version": None, "start_ms": start, "end_ms": start,
                 "stopped": False, "status": "running", "skills": [], "transcript_path": None,
                 "provenance": self.provenance, "_parent": tid + "#root", "_open": {}}
            self.traces[tid] = t
            self.span(tid, tid + "#root", None, "prompt", "(prompt not captured)", start, None, "running", {})
        for key, val in meta.items():
            if val and not t.get(key):
                t[key] = val
        if start is not None:
            t["start_ms"] = min(t["start_ms"] if t["start_ms"] is not None else start, start)
        return t

    def touch(self, t, at):
        if at is not None:
            t["end_ms"] = max(t["end_ms"] or at, at)

    def span(self, tid, sid, parent, kind, name, start, end, status, attrs):
        self.seq += 1
        while sid in self.spans:  # never let a duplicate id overwrite a span
            sid += "'"
        self.spans[sid] = {"span_id": sid, "trace_id": tid, "parent_span_id": parent, "kind": kind,
                           "name": (name or kind)[:200], "start_ms": start, "end_ms": end, "status": status,
                           "seq": self.seq, "attributes": {k: v for k, v in attrs.items() if v is not None}}
        mark = end if end is not None else start
        if kind not in ("prompt", "skill") and mark is not None and tid in self.traces:
            self.traces[tid]["_last"] = max(self.traces[tid].get("_last") or mark, mark)
        return self.spans[sid]

    def skill(self, t, name, at, via):
        if not name or name in t["skills"]:
            return
        t["skills"].append(name)
        sid = "%s#skill:%s" % (t["trace_id"], name)
        self.span(t["trace_id"], sid, t["trace_id"] + "#root", "skill", name, at, None, "ok", {"detected_via": via})
        if t["_parent"] == t["trace_id"] + "#root":
            t["_parent"] = sid  # later steps hang under the first skill the request invoked

    def finish(self):
        """Close open spans, compute durations and per-trace counts; returns (traces, spans)."""
        traces, spans = [], []
        by_trace = {}
        for s in self.spans.values():
            by_trace.setdefault(s["trace_id"], []).append(s)
        for tid, t in self.traces.items():
            mine = by_trace.get(tid, [])
            end = t["end_ms"]
            for s in mine:
                if s["kind"] in ("prompt", "skill"):
                    s["end_ms"] = end
                    if s["kind"] == "prompt":
                        s["status"] = t["status"] if t["stopped"] else "running"
                        if t["prompt"]:
                            s["name"] = t["prompt"][:200]
                elif s["end_ms"] is None:
                    s["end_ms"] = end if t["stopped"] else None
                    if s["status"] == "running" and t["stopped"]:
                        s["status"] = "incomplete"
                if s["start_ms"] is not None and s["end_ms"] is not None:
                    s["duration_ms"] = max(0, s["end_ms"] - s["start_ms"])
                else:
                    s["duration_ms"] = s["attributes"].get("duration_ms")
                s["start"], s["end"] = iso(s["start_ms"]), iso(s["end_ms"])
            kinds = [s["kind"] for s in mine]
            trace = {k: v for k, v in t.items() if not k.startswith("_") and k not in ("start_ms", "end_ms", "stopped")}
            trace.update({
                "start": iso(t["start_ms"]), "end": iso(end),
                "duration_ms": (end - t["start_ms"]) if end is not None and t["start_ms"] is not None else None,
                "span_count": len(mine), "tool_count": kinds.count("tool"), "subagent_count": kinds.count("subagent"),
                "guard_count": kinds.count("guard"), "edit_count": kinds.count("edit"),
                "error_count": sum(1 for s in mine if s["status"] in ("error", "failed", "blocked")),
            })
            traces.append(trace)
            spans.extend(mine)
        traces.sort(key=lambda x: x["start"] or "", reverse=True)
        for s in spans:
            s.pop("start_ms", None)
            s.pop("end_ms", None)
        return traces, spans


def build_from_events(rows, source: str = "hook"):
    """events.jsonl rows (hooks/cursor-event.py + guard rows) -> (traces, spans)."""
    b = _Builder(source, "measured")
    sub_conv = {}   # subagent conversation id -> subagent span id
    sub_open = {}   # (trace, subagent_type) -> [open subagent span ids]
    conv_trace, conv_turn = {}, {}
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        at = ms(row.get("ts"))
        if at is None:
            continue
        ev = row.get("event") or ""
        conv = str(row.get("conversation_id") or "unknown")
        sid = str(row.get("id") or "ev%d" % idx)
        in_sub = sub_conv.get(conv) or sub_conv.get(str(row.get("parent_tool_call_id") or ""))
        if in_sub:
            sub_conv[conv] = in_sub   # later child rows may omit parent_tool_call_id
            tid = b.spans[in_sub]["trace_id"]
        elif row.get("generation_id"):
            tid = str(row["generation_id"])
        elif ev == "beforeSubmitPrompt" or conv not in conv_trace:
            conv_turn[conv] = conv_turn.get(conv, 0) + 1
            tid = "%s:%d" % (conv, conv_turn[conv])
        else:
            tid = conv_trace[conv]
        if not in_sub:
            conv_trace[conv] = tid
        start = at - int(row["duration_ms"]) if isinstance(row.get("duration_ms"), int) and ev.startswith("postToolUse") else at
        t = b.trace(tid, b.traces[tid]["session_id"] if tid in b.traces else conv, start,
                    model=row.get("model"), cursor_version=row.get("cursor_version"),
                    transcript_path=row.get("transcript_path"))
        b.touch(t, at)
        parent = in_sub or t["_parent"]

        if ev == "beforeSubmitPrompt":
            t["prompt"] = row.get("prompt") or t["prompt"]
            root = b.spans[tid + "#root"]
            root["start_ms"] = min(root["start_ms"] or at, at)
            root["attributes"].update({"prompt_chars": row.get("prompt_chars"), "attachments": row.get("attachments")})
            m = SKILL_PROMPT.match(row.get("prompt") or "")
            if m:
                b.skill(t, m.group(1), at, "prompt")
        elif ev in ("postToolUse", "postToolUseFailure"):
            name = row.get("tool_name") or "tool"
            m = SKILL_PATH.search(row.get("target") or "")
            if m and name.lower().startswith("read"):
                b.skill(t, m.group(1), start, "skill_read")
            kind = "edit" if EDIT_TOOL.search(name) else "tool"
            b.span(tid, sid, parent, kind, name, start, at, "error" if ev.endswith("Failure") else "ok", {
                "target": row.get("target"), "tool_use_id": row.get("tool_use_id"), "ranged": row.get("ranged"),
                "bytes_in": row.get("input_bytes"), "bytes_out": row.get("output_bytes"),
                "duration_ms": row.get("duration_ms"), "failure_type": row.get("failure_type"),
                "error_message": row.get("error_message"), "is_interrupt": row.get("is_interrupt")})
        elif ev == "guard":
            b.span(tid, sid, parent, "guard", row.get("rule") or "guard", at, at, "blocked", {
                "decision": row.get("decision"), "tool_name": row.get("tool_name"), "target": row.get("target"),
                "tool_use_id": row.get("tool_use_id")})
        elif ev == "subagentStart":
            s = b.span(tid, sid, parent, "subagent", row.get("subagent_type") or "subagent", at, None, "running", {
                "subagent_id": row.get("subagent_id"), "task": row.get("task"), "bytes_in": row.get("task_bytes"),
                "subagent_model": row.get("subagent_model"), "tool_call_id": row.get("tool_call_id"),
                "is_parallel_worker": row.get("is_parallel_worker")})
            if row.get("subagent_id"):
                sub_conv[str(row["subagent_id"])] = s["span_id"]
            sub_open.setdefault((tid, row.get("subagent_type")), []).append(s["span_id"])
        elif ev == "subagentStop":
            queue = sub_open.get((tid, row.get("subagent_type"))) or []
            task = row.get("task")
            match = next((x for x in queue if b.spans[x]["attributes"].get("task") == task), queue[0] if queue else None)
            attrs = {"summary": row.get("summary"), "bytes_out": row.get("summary_bytes"),
                     "description": row.get("description"), "message_count": row.get("message_count"),
                     "tool_call_count": row.get("tool_call_count"), "loop_count": row.get("loop_count"),
                     "modified_files": row.get("modified_files"), "agent_transcript_path": row.get("agent_transcript_path"),
                     "duration_ms": row.get("duration_ms")}
            if match:
                queue.remove(match)
                s = b.spans[match]
                s["end_ms"], s["status"] = at, row.get("status") or "completed"
                if isinstance(row.get("duration_ms"), int):
                    s["start_ms"] = at - row["duration_ms"]
                s["attributes"].update({k: v for k, v in attrs.items() if v is not None})
            else:
                dur = row.get("duration_ms") if isinstance(row.get("duration_ms"), int) else 0
                b.span(tid, sid, parent, "subagent", row.get("subagent_type") or "subagent", at - dur, at,
                       row.get("status") or "completed", dict(attrs, task=task, bytes_in=row.get("task_bytes")))
        elif ev == "afterFileEdit":
            path = row.get("file_path") or ""
            b.span(tid, sid, parent, "edit", os.path.basename(path) or "edit", at, at, "ok", {
                "file_path": path, "edit_count": row.get("edit_count"), "chars_added": row.get("chars_added"),
                "chars_removed": row.get("chars_removed")})
        elif ev == "afterAgentResponse":
            prev = t.get("_last") or b.spans[tid + "#root"]["start_ms"] or at
            b.span(tid, sid, in_sub or tid + "#root", "response", "response", min(prev, at), at, "ok", {
                "text": row.get("text"), "text_chars": row.get("text_chars"), "bytes_out": row.get("text_chars"),
                "timing": "gap since the previous step",
                **{k: row[k] for k in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")
                   if isinstance(row.get(k), int)}})
        elif ev == "preCompact":
            b.span(tid, sid, tid + "#root", "compact", "compaction (%s)" % (row.get("trigger") or "auto"), at, at, "ok", {
                k: row.get(k) for k in ("trigger", "context_usage_percent", "context_tokens", "context_window_size",
                                        "message_count", "messages_to_compact", "is_first_compaction")})
        elif ev == "stop" and not in_sub:
            t["stopped"], t["status"] = True, row.get("status") or "completed"
            t["end_ms"] = at
    return b.finish()


def build_from_store(conversations):
    """cursor_sessions.store_conversations() -> (traces, spans); durations estimated."""
    b = _Builder("cursor_store", "estimated")
    by_id = {c["composer_id"]: c for c in conversations}
    children = {sid for c in conversations for sid in c.get("subagent_ids") or []}
    for conv in conversations:
        if conv["composer_id"] in children:
            continue
        bubbles = [x for x in conv.get("bubbles") or [] if x.get("created") is not None]
        tid, turn, starts = None, 0, []
        for i, bub in enumerate(bubbles):
            at = bub["created"]
            nxt = bubbles[i + 1]["created"] if i + 1 < len(bubbles) else at
            if bub.get("type") == 1:
                if not bub.get("text"):
                    continue
                turn += 1
                tid = "cs:%s:%d" % (conv["composer_id"], turn)
                t = b.trace(tid, conv["composer_id"], at, workspace=conv.get("workspace"), model=conv.get("model"))
                t["prompt"], t["stopped"], t["status"] = bub["text"][:500], True, "completed"
                t["session_name"] = conv.get("name")
                starts.append((at, tid))
                m = SKILL_PROMPT.match(bub["text"])
                if m:
                    b.skill(t, m.group(1), at, "prompt")
                continue
            if tid is None:
                continue
            t = b.traces[tid]
            b.touch(t, nxt if bub.get("tool") else at)
            tool = bub.get("tool")
            sid = "%s#b%d" % (tid, i)
            if tool:
                m = SKILL_PATH.search(tool.get("params") or "")
                if m and "read" in tool["name"].lower():
                    b.skill(t, m.group(1), at, "skill_read")
                status = "error" if tool.get("status") in ("error", "failed", "cancelled") else "ok"
                kind = "subagent" if SUBAGENT_TOOL.match(tool["name"]) else ("edit" if EDIT_TOOL.search(tool["name"]) else "tool")
                b.span(tid, sid, t["_parent"], kind, tool["name"], at, max(at, nxt), status, {
                    "target": tool.get("params"), "bytes_in": tool.get("params_bytes"),
                    "bytes_out": tool.get("result_bytes"), "tool_call_id": tool.get("tool_call_id"),
                    "timing": "estimated from message timestamps"})
            elif bub.get("text"):
                b.span(tid, sid, tid + "#root", "response", "response", at, at, "ok", {
                    "text": bub["text"], "text_chars": bub.get("text_chars"), "bytes_out": bub.get("text_chars"),
                    "thinking_ms": bub.get("thinking_ms")})
        for child_id in conv.get("subagent_ids") or []:
            child = by_id.get(child_id)
            cb = [x for x in (child or {}).get("bubbles") or [] if x.get("created") is not None]
            if not cb or not starts:
                continue
            first, last = cb[0]["created"], cb[-1]["created"]
            owner = [tid for at, tid in starts if at <= first]
            tid = owner[-1] if owner else starts[0][1]
            t = b.traces[tid]
            prompt = next((x["text"] for x in cb if x.get("type") == 1 and x.get("text")), None)
            summary = next((x["text"] for x in reversed(cb) if x.get("type") == 2 and x.get("text")), None)
            tools = [x for x in cb if x.get("tool")]
            ssid = "%s#sub:%s" % (tid, child_id)
            b.span(tid, ssid, t["_parent"], "subagent", child.get("subagent_type") or child.get("name") or "subagent",
                   first, last, "completed" if (child.get("status") or "completed") != "aborted" else "aborted", {
                       "subagent_id": child_id, "task": prompt, "summary": summary,
                       "bytes_in": len(prompt or ""), "bytes_out": len(summary or ""),
                       "tool_call_count": len(tools), "message_count": len(cb), "model": child.get("model"),
                       "timing": "estimated from message timestamps"})
            for j, bub in enumerate(cb):
                if not bub.get("tool"):
                    continue
                nxt = cb[j + 1]["created"] if j + 1 < len(cb) else bub["created"]
                tool = bub["tool"]
                b.span(tid, "%s#b%d" % (ssid, j), ssid, "edit" if EDIT_TOOL.search(tool["name"]) else "tool",
                       tool["name"], bub["created"], max(bub["created"], nxt),
                       "error" if tool.get("status") in ("error", "failed") else "ok",
                       {"target": tool.get("params"), "bytes_in": tool.get("params_bytes"),
                        "bytes_out": tool.get("result_bytes"), "timing": "estimated from message timestamps"})
            b.touch(t, last)
    return b.finish()


# ---- live cache over events.jsonl (DV-012/DV-013) --------------------------------------------

_CACHE = {}
_LOCK = threading.Lock()


def events_path(project: str) -> str:
    return os.path.join(common.agent_spec_dir(project), "metrics", "events.jsonl")


def read_events(path: str, offset: int = 0, limit_bytes: int = 64 << 20):
    """(rows, new_offset) for complete lines after `offset`. A partial last line waits."""
    rows = []
    try:
        size = os.path.getsize(path)
    except OSError:
        return rows, 0
    if offset > size:  # truncated or rotated
        offset = 0
    with open(path, "rb") as fh:
        fh.seek(offset)
        data = fh.read(min(size - offset, limit_bytes))
    end = data.rfind(b"\n")
    if end < 0:
        return rows, offset
    for line in data[:end].splitlines():
        try:
            row = json.loads(line.decode("utf-8", "replace"))
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows, offset + end + 1


def hook_traces(project: str):
    """Hook traces from events.jsonl, re-parsing only the bytes appended since the last call."""
    path = events_path(project)
    with _LOCK:
        entry = _CACHE.get(path) or {"offset": 0, "rows": [], "result": ([], []), "ino": None}
        try:
            st = os.stat(path)
        except OSError:
            _CACHE.pop(path, None)
            return [], []
        if entry["ino"] != st.st_ino or st.st_size < entry["offset"]:
            entry = {"offset": 0, "rows": [], "result": ([], []), "ino": st.st_ino}
        if st.st_size != entry["offset"]:
            rows, entry["offset"] = read_events(path, entry["offset"])
            if rows:
                entry["rows"].extend(rows)
                built = build_from_events(entry["rows"])
                # cursor-event.py writes to <workspace_roots[0]>/.agent-spec, so this file's
                # project is the workspace of every trace in it.
                ws = os.path.abspath(project)
                for t in built[0]:
                    t["workspace"] = t.get("workspace") or ws
                entry["result"] = built
        _CACHE[path] = entry
        return entry["result"]


def db_traces(conn, exclude_source: str = "hook"):
    """Persisted traces/spans (cursor_store, run, demo_seed). Empty on a pre-v3 database."""
    try:
        traces = [dict(r) for r in conn.execute("SELECT * FROM traces WHERE source != ?", (exclude_source,))]
        spans = [dict(r) for r in conn.execute(
            "SELECT s.* FROM spans s JOIN traces t ON t.trace_id = s.trace_id WHERE t.source != ?", (exclude_source,))]
    except Exception:
        return [], []
    for t in traces:
        t["skills"] = json.loads(t.get("skills") or "[]")
    for s in spans:
        s["attributes"] = json.loads(s.get("attributes") or "{}")
    return traces, spans


def all_traces(project: str, conn):
    """Hook traces (live) + persisted ones; a run whose trace id matches a hook trace joins it."""
    h_traces, h_spans = hook_traces(project)
    d_traces, d_spans = db_traces(conn)
    hook_ids = {t["trace_id"] for t in h_traces}
    joined = {}  # run trace id -> hook trace id, from the workflow span's generation_id
    for s in d_spans:
        gid = s["attributes"].get("generation_id") if s["kind"] == "workflow" else None
        if gid in hook_ids:
            joined[s["trace_id"]] = gid
    traces = list(h_traces) + [t for t in d_traces if t["trace_id"] not in hook_ids and t["trace_id"] not in joined]
    spans = list(h_spans)
    for s in d_spans:
        if s["trace_id"] in joined:
            target = joined[s["trace_id"]]
            s = dict(s, trace_id=target, parent_span_id=s["parent_span_id"] or target + "#root")
        spans.append(s)
    traces.sort(key=lambda x: x.get("start") or "", reverse=True)
    return traces, spans


def persist(conn, traces, spans, sources) -> int:
    """Replace every persisted trace of `sources` with `traces`/`spans`. Caller owns the transaction."""
    for src in sources:
        conn.execute("DELETE FROM spans WHERE trace_id IN (SELECT trace_id FROM traces WHERE source = ?)", (src,))
        conn.execute("DELETE FROM traces WHERE source = ?", (src,))
    cols = ("trace_id", "session_id", "source", "workspace", "prompt", "model", "cursor_version", "start", "end",
            "duration_ms", "status", "span_count", "tool_count", "subagent_count", "error_count", "guard_count",
            "edit_count", "skills", "transcript_path", "provenance")
    for t in traces:
        vals = [json.dumps(t.get("skills") or []) if c == "skills" else t.get(c) for c in cols]
        conn.execute("INSERT OR REPLACE INTO traces (%s) VALUES (%s)" % (",".join(cols), ",".join("?" * len(cols))), vals)
    for s in spans:
        conn.execute(
            "INSERT OR REPLACE INTO spans (span_id, trace_id, parent_span_id, kind, name, start, end, duration_ms, status, "
            "seq, attributes) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (s["span_id"], s["trace_id"], s.get("parent_span_id"), s["kind"], s.get("name"), s.get("start"),
             s.get("end"), s.get("duration_ms"), s.get("status"), s.get("seq") or 0,
             json.dumps(s.get("attributes") or {})))
    return len(traces)


# ---- read API helpers (DV-012) ---------------------------------------------------------------

def _match(t, f):
    if f.get("session") and t["session_id"] != f["session"]:
        return False
    if f.get("status") and t.get("status") != f["status"]:
        return False
    if f.get("source") and t.get("source") != f["source"]:
        return False
    if f.get("skill") and f["skill"] not in (t.get("skills") or []):
        return False
    if f.get("workspace") and (t.get("workspace") or "") != f["workspace"]:
        return False
    if f.get("since") and (t.get("start") or "") < f["since"]:
        return False
    if f.get("until") and (t.get("start") or "") > f["until"]:
        return False
    if f.get("q"):
        hay = " ".join(str(t.get(k) or "") for k in ("prompt", "trace_id", "session_id", "model", "session_name"))
        if f["q"].lower() not in hay.lower():
            return False
    return True


def list_requests(project, conn, filters, limit=50, offset=0):
    traces, _ = all_traces(project, conn)
    rows = [t for t in traces if _match(t, filters)]
    facets = {"sources": sorted({t["source"] for t in traces}),
              "skills": sorted({s for t in traces for s in t.get("skills") or []}),
              "statuses": sorted({t.get("status") or "" for t in traces}),
              "workspaces": sorted({t.get("workspace") for t in traces if t.get("workspace")})}
    return {"total": len(rows), "limit": limit, "offset": offset, "requests": rows[offset:offset + limit],
            "facets": facets}


# ---- Context budget (exact: token arithmetic over Cursor's own counters) ------------------

_USAGE = {"at": 0.0, "value": {}}
_USAGE_LOCK = threading.Lock()
USAGE_TTL_S = 10.0


def context_usage():
    """cursor_sessions.context_usage(), cached for USAGE_TTL_S: the store's WAL changes on
    every turn, and each change costs a 0.3 s snapshot copy on WSL."""
    import time
    from . import cursor_sessions
    if os.environ.get("AGENT_SPEC_CURSOR_STORE", "1") == "0":
        return {}
    with _USAGE_LOCK:
        if time.time() - _USAGE["at"] > USAGE_TTL_S:
            try:
                _USAGE["value"] = cursor_sessions.context_usage() or {}
            except Exception:  # unofficial store: never break the API over it
                _USAGE["value"] = {}
            _USAGE["at"] = time.time()
        return _USAGE["value"]


def _billed_by_session(traces, spans, sessions=None):
    """session_id -> ordered per-request billed-token points from response spans (hooks).
    `sessions` limits the work to those chats."""
    session_of = {t["trace_id"]: t.get("session_id") for t in traces
                  if sessions is None or t.get("session_id") in sessions}
    out, seen = {}, set()
    for s in spans:
        a = s.get("attributes") or {}
        if s.get("kind") != "response" or not isinstance(a.get("input_tokens"), int):
            continue
        sid = session_of.get(s["trace_id"])
        if sid:
            key = (s["trace_id"], a.get("input_tokens"), a.get("output_tokens"))
            if key in seen:   # the hook and Cursor's hook log both record a generation
                continue
            seen.add(key)
            out.setdefault(sid, []).append({"ts": s.get("end") or s.get("start"), "generation_id": s["trace_id"],
                                            "input": context_budget.request_tokens(a), "output": a.get("output_tokens") or 0,
                                            "cache_read": a.get("cache_read_tokens") or 0})
    for pts in out.values():
        pts.sort(key=lambda p: p.get("ts") or "")
    return out


def session_context(project, session_id, usage=None, billed=None):
    """{"budget", "billed"} for one chat; either part may be None."""
    usage = context_usage() if usage is None else usage
    mine = (usage.get("by_id") or {}).get(session_id)
    b = None
    if mine:
        fixed = context_budget.fixed_tokens(mine.get("breakdown"))
        b = context_budget.budget(mine.get("used"), fixed or context_budget.machine_floor(usage), mine.get("limit"))
    if b:
        b["floor_source"] = "this chat's fixed categories" if fixed else "smallest chat on this machine"
        b["breakdown"] = mine.get("breakdown")
        b["nudged"] = os.path.exists(os.path.join(common.agent_spec_dir(project), ".context-nudged-%s" % session_id))
    pts = billed or []
    summary = context_budget.series_summary(pts)
    if summary:
        summary["generations"] = [p["generation_id"] for p in pts][::max(1, -(-len(pts) // context_budget.MAX_POINTS))]
    if not b and not summary:
        return None
    return {"budget": b, "billed": summary}


def context_overview(project, conn):
    """Every chat Cursor reports a context for, ranked by what it re-sends per call."""
    usage = context_usage()
    convs = list_conversations(project, conn, {}, limit=100000)["conversations"]
    rows = [c for c in convs if (c.get("context") or {}).get("budget")]
    known = {c["session_id"] for c in rows}
    floor = context_budget.machine_floor(usage)
    for cid, v in (usage.get("by_id") or {}).items():   # chats with no trace yet still count
        if cid not in known:
            ctx = session_context(project, cid, usage)
            if ctx and ctx.get("budget"):
                rows.append({"session_id": cid, "name": v.get("name"), "context": ctx})
    budgets = [r["context"]["budget"] for r in rows]
    resets = [b for b in budgets if b["verdict"] == "reset"]
    top = sorted(rows, key=lambda r: -r["context"]["budget"]["used"])[:12]
    return {
        "floor": floor,
        "chats": len(budgets),
        "by_verdict": {k: sum(1 for b in budgets if b["verdict"] == k) for k in ("reset", "carry", "fresh")},
        "carried_tokens": sum(b["carried_tokens"] for b in budgets),
        "reset_saving_per_call": sum(b["saving_per_call"] for b in resets),
        "breakeven_calls": context_budget.RESET_BREAKEVEN_CALLS,
        "weights": {"read": context_budget.READ_WEIGHT, "write": context_budget.WRITE_WEIGHT},
        "top": [{"session_id": r["session_id"], "name": r.get("name"), "workspace": r.get("workspace"),
                 "latest_trace_id": r.get("latest_trace_id"), **r["context"]} for r in top],
        "provenance": "measured",
        "source": "Cursor contextTokensUsed (local store); billed tokens from afterAgentResponse",
    }


def list_conversations(project, conn, filters, limit=200, offset=0):
    """Every Cursor conversation with at least one trace, newest first, rolled up from its requests.

    One row per session_id across sources, so a chat recorded by hooks and also read from
    Cursor's local store appears once. Counts are sums of the per-request counts; the
    provenance is "measured" only when every request came from hooks."""
    traces, spans = all_traces(project, conn)
    usage = context_usage()
    sub = {k: v for k, v in filters.items() if k in ("source", "workspace", "skill", "status", "since", "until")}
    groups = {}
    for t in traces:
        if not t.get("session_id") or not _match(t, sub):
            continue
        groups.setdefault(t["session_id"], []).append(t)
    reviews_dir = os.path.join(common.agent_spec_dir(project), "metrics", "reviews")
    rows = []
    for sid, ts in groups.items():
        ts.sort(key=lambda t: t.get("start") or "")
        name = next((t.get("session_name") for t in ts if t.get("session_name")), None)
        first_prompt = next((t.get("prompt") for t in ts if t.get("prompt")), None)
        row = {
            "session_id": sid,
            "name": name or ((usage.get("by_id") or {}).get(sid) or {}).get("name"),
            "first_prompt": first_prompt,
            "last_prompt": next((t.get("prompt") for t in reversed(ts) if t.get("prompt")), None),
            "workspace": next((t.get("workspace") for t in ts if t.get("workspace")), None),
            "sources": sorted({t.get("source") or "" for t in ts}),
            "provenance": "measured" if all(t.get("source") == "hook" for t in ts) else "estimated",
            "start": ts[0].get("start"),
            "end": max((t.get("end") or t.get("start") or "") for t in ts) or None,
            "requests": len(ts),
            "running": sum(1 for t in ts if t.get("status") == "running"),
            "skills": sorted({s for t in ts for s in t.get("skills") or []}),
            "models": sorted({t.get("model") for t in ts if t.get("model")}),
            "reviewed": os.path.isfile(os.path.join(reviews_dir, "%s.json" % sid)),
            "has_transcript": any(t.get("transcript_path") for t in ts),
            "latest_trace_id": ts[-1]["trace_id"],
        }
        for k in ("tool_count", "subagent_count", "error_count", "guard_count", "edit_count", "duration_ms"):
            row[k] = sum(t.get(k) or 0 for t in ts)
        rows.append(row)
    q = (filters.get("q") or "").lower()
    if q:
        rows = [r for r in rows if q in " ".join(str(r.get(k) or "") for k in
                                                 ("name", "first_prompt", "last_prompt", "session_id", "workspace")).lower()]
    rows.sort(key=lambda r: r.get("end") or r.get("start") or "", reverse=True)
    page = rows[offset:offset + limit]
    if page:  # the budget is per chat: compute it for the rows returned, not every chat
        billed = _billed_by_session(traces, spans, {r["session_id"] for r in page})
        for row in page:
            row["context"] = session_context(project, row["session_id"], usage, billed.get(row["session_id"]))
    return {"total": len(rows), "limit": limit, "offset": offset, "conversations": page,
            "facets": {"workspaces": sorted({r["workspace"] for r in rows if r.get("workspace")})}}


def load_review(project, session_id):
    path = os.path.join(common.agent_spec_dir(project), "metrics", "reviews", "%s.json" % session_id)
    if not re.match(r"^[\w.:-]{1,160}$", session_id or "") or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def request_detail(project, conn, trace_id):
    traces, spans = all_traces(project, conn)
    trace = next((t for t in traces if t["trace_id"] == trace_id), None)
    if trace is None:
        return None
    mine = sorted((s for s in spans if s["trace_id"] == trace_id), key=lambda s: (s.get("start") or "", s.get("seq") or 0))
    mine = handoffs.annotate(mine, handoffs.load_schemas(project))
    responses = [{"span_id": s["span_id"], "ts": s.get("end") or s.get("start"), "text": s["attributes"].get("text"),
                  "text_chars": s["attributes"].get("text_chars")} for s in mine if s["kind"] == "response"]
    review = load_review(project, trace["session_id"])
    if review:
        cited = {e.get("span_id") for e in review.get("evidence") or [] if isinstance(e, dict)}
        review = dict(review, findings_here=[e for e in review.get("evidence") or []
                                             if isinstance(e, dict) and e.get("span_id") in {s["span_id"] for s in mine}],
                      cites_this_request=bool(cited & {s["span_id"] for s in mine}))
    siblings = [t["trace_id"] for t in sorted((t for t in traces if t["session_id"] == trace["session_id"]),
                                               key=lambda t: t.get("start") or "")]
    ctx = session_context(project, trace["session_id"],
                          billed=_billed_by_session(traces, spans, {trace["session_id"]}).get(trace["session_id"]))
    return {"trace": trace, "spans": mine, "responses": responses, "review": review, "session_requests": siblings,
            "context": ctx}


# ---- Coach measurements (DV-041, exact) ------------------------------------------------------

def _pct(sorted_vals, p):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return round(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo))


def lag(project, conn, since=None):
    """Per span kind and per tool name: count, p50, p95, failure rate; plus guard blocks,
    compactions, whole-file reads and bytes handed to subagents. Exact over the spans shown."""
    traces, spans = all_traces(project, conn)
    keep = {t["trace_id"]: t for t in traces if not since or (t.get("start") or "") >= since}
    spans = [s for s in spans if s["trace_id"] in keep]

    def group(key):
        out = {}
        for s in spans:
            if s["kind"] in ("prompt", "skill"):
                continue
            k = key(s)
            g = out.setdefault(k, {"count": 0, "failed": 0, "durations": [], "sources": set()})
            g["count"] += 1
            g["failed"] += 1 if s.get("status") in ("error", "failed", "blocked") else 0
            g["sources"].add(keep[s["trace_id"]]["source"])
            if isinstance(s.get("duration_ms"), (int, float)):
                g["durations"].append(s["duration_ms"])
        rows = []
        for k, g in out.items():
            d = sorted(g["durations"])
            rows.append({"key": k, "count": g["count"], "failure_rate": round(g["failed"] / g["count"], 3),
                         "p50_ms": _pct(d, 0.5), "p95_ms": _pct(d, 0.95), "total_ms": sum(d),
                         "provenance": "measured" if g["sources"] <= {"hook", "run"} else "estimated"})
        return sorted(rows, key=lambda r: -(r["p95_ms"] or 0))

    reads = [s for s in spans if s["kind"] == "tool" and s["name"].lower().startswith("read")]
    subs = [s for s in spans if s["kind"] == "subagent"]
    slowest = sorted((s for s in spans if s["kind"] not in ("prompt", "skill") and s.get("duration_ms")),
                     key=lambda s: -s["duration_ms"])[:10]
    return {
        "requests": len(keep),
        "by_kind": group(lambda s: s["kind"]),
        "by_tool": group(lambda s: "%s:%s" % (s["kind"], s["name"]))[:25],
        "guard_blocks": sum(1 for s in spans if s["kind"] == "guard"),
        "compactions": sum(1 for s in spans if s["kind"] == "compact"),
        "whole_file_reads": sum(1 for s in reads if s["attributes"].get("ranged") is False),
        "subagent_bytes_in": sum(int(s["attributes"].get("bytes_in") or 0) for s in subs),
        "subagent_bytes_out": sum(int(s["attributes"].get("bytes_out") or 0) for s in subs),
        "slowest": [{"span_id": s["span_id"], "trace_id": s["trace_id"], "kind": s["kind"], "name": s["name"],
                     "duration_ms": s["duration_ms"], "source": keep[s["trace_id"]]["source"]} for s in slowest],
        "sources": sorted({t["source"] for t in keep.values()}),
    }
