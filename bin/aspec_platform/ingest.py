"""Idempotent, redacting ingestor: files on disk -> platform.db rows (D-002..D-006, S-003).

`run(project, what, rebuild)` -> {source: {stat: n}}. Sources: transcripts gates memory graph
quarantine (+ `compact`, not part of `all`). Each source runs in ONE transaction; a bad line or file
is counted in `errors` and never raises. The database stays derived data (DEC-04): `rebuild`
deletes it and re-reads everything. Single writer (DEC-09).

Transcript idempotency (IMPLEMENTATION-GUIDE §5): `ingest_offsets` keeps a byte offset and the sha
of the consumed prefix. Appended file -> continue from the offset; prefix changed (rewritten or
truncated) -> that transcript's rows are deleted and it is re-ingested from byte 0.

Privacy: `thinking` blocks are dropped before anything is counted or stored; prompts and tool
inputs go through `redact`. Tokens are estimates (chars // 4, tokens_estimated = 1).

Known limits: Cursor transcripts hold tool_use blocks only (no results, no per-line timestamps,
no Task calls), so request time comes from the `<timestamp>` tag in the prompt and subagent links
are by order/time (see `_link_children`).
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone

from . import common, db
from .redact import redact, redact_obj

READ_CAP = 20000  # same threshold as bin/agent-spec-receipt.py
READ_TOOLS = ("Read", "read_file", "ReadFile")
# Copy of RANGE_KEYS in bin/agent-spec-receipt.py (a hyphenated script, not importable).
RANGE_KEYS = ("limit", "offset", "start_line", "end_line", "line_start", "line_end", "lines",
              "range", "view_range", "startline", "endline", "line_range")
TASK_TOOLS = ("Task", "Subagent")
SKILL_TOOLS = ("Skill", "skill")
PROMPT_CAP = 2000
VALUE_CAP = 300
ALL = ("events", "transcripts", "gates", "memory", "graph", "quarantine", "runs", "experiences")

_USER_QUERY = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.S)
_TS_TAG = re.compile(r"<timestamp>.*?</timestamp>\s*", re.S)
_TS = re.compile(r"<timestamp>.*?(\w{3}) (\d{1,2}), (\d{4}), (\d{1,2}):(\d{2}) (AM|PM)"
                 r"(?: \(UTC([+-])(\d{1,2})(?::(\d{2}))?\))?")


# ---- small helpers -------------------------------------------------------------------------

def _sha(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _is_ranged(args) -> bool:
    if not isinstance(args, dict):
        return False
    for k, v in args.items():
        if str(k).lower() in RANGE_KEYS and v not in (None, "", False):
            return True
        if isinstance(v, dict) and _is_ranged(v):
            return True
    return False


def _trim(obj):
    if isinstance(obj, str):
        return common.clamp(obj, VALUE_CAP)
    if isinstance(obj, dict):
        return {k: _trim(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_trim(v) for v in obj]
    return obj


def _to_utc(value) -> str:
    """ISO string -> UTC ISO (naive input is local time); unparseable input is kept as text."""
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    return common.iso_from_epoch(dt.timestamp())


def _prompt_time(text):
    m = _TS.search(text)
    if not m:
        return None
    try:
        dt = datetime.strptime("%s %s %s %s:%s %s" % m.group(1, 2, 3, 4, 5, 6), "%b %d %Y %I:%M %p")
    except ValueError:
        return None
    if not m.group(8):
        return common.iso_from_epoch(dt.timestamp())
    offset = (int(m.group(8)) * 3600 + int(m.group(9) or 0) * 60) * (1 if m.group(7) == "+" else -1)
    return common.iso_from_epoch(dt.replace(tzinfo=timezone.utc).timestamp() - offset)


def _blocks(entry) -> list:
    content = (entry.get("message") or {}).get("content") if isinstance(entry.get("message"), dict) else None
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _text(entry) -> str:
    return "\n".join(str(b.get("text") or "") for b in _blocks(entry) if b.get("type") == "text")


def _read_jsonl(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    yield obj
    except OSError:
        return


# ---- transcripts ---------------------------------------------------------------------------

def transcript_root(project: str) -> str:
    override = os.environ.get("AGENT_SPEC_TRANSCRIPT_ROOT")
    if override:
        return override
    slug = os.path.abspath(project).lstrip(os.sep).replace(os.sep, "-").replace(".", "-")
    return os.path.join(os.path.expanduser("~"), ".cursor", "projects", slug, "agent-transcripts")


def discover(root: str) -> list:
    """[(main_path, [subagent_paths])]: `<id>/<id>.jsonl` (+ `<id>/subagents/*.jsonl`) or flat `<id>.jsonl`."""
    out = []
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return out
    for name in names:
        full = os.path.join(root, name)
        if os.path.isfile(full) and name.endswith(".jsonl"):
            out.append((full, []))
        elif os.path.isdir(full):
            subs = sorted(glob.glob(os.path.join(full, "subagents", "*.jsonl")))
            main = os.path.join(full, name + ".jsonl")
            if os.path.isfile(main) or subs:
                out.append((main, subs))
    return out


def _forget_transcript(conn, path: str) -> None:
    mine = "(SELECT request_id FROM requests WHERE transcript_path = ?)"
    conn.execute("DELETE FROM subagent_runs WHERE parent_request_id IN " + mine, (path,))
    conn.execute("DELETE FROM subagent_runs WHERE parent_step_id IS NULL AND child_request_id IN " + mine, (path,))
    conn.execute("UPDATE subagent_runs SET child_request_id = NULL WHERE child_request_id IN " + mine, (path,))
    conn.execute("DELETE FROM fact_injections WHERE request_id IN " + mine, (path,))
    conn.execute("DELETE FROM requests WHERE transcript_path = ?", (path,))  # steps cascade
    conn.execute("DELETE FROM ingest_offsets WHERE source_path = ?", (path,))


class _Transcript:
    """Turns the new lines of one transcript into requests / steps / subagent_runs rows."""

    def __init__(self, conn, project, path, stats):
        self.conn, self.project, self.path, self.stats = conn, project, path, stats
        self.session = os.path.basename(path)[:-len(".jsonl")]
        self.fallback_ts = common.iso_from_epoch(os.path.getmtime(path))
        row = conn.execute("SELECT request_id, ordinal FROM requests WHERE transcript_path = ? "
                           "ORDER BY ordinal DESC LIMIT 1", (path,)).fetchone()
        self.req = row[0] if row else None
        self.req_ordinal = row[1] + 1 if row else 0
        self.step_ordinal = 0
        if self.req:
            self.step_ordinal = conn.execute("SELECT COALESCE(MAX(ordinal) + 1, 0) FROM steps WHERE request_id = ?",
                                             (self.req,)).fetchone()[0]
        self.tokens_out = 0

    def flush(self):
        if self.req and self.tokens_out:
            self.conn.execute("UPDATE requests SET tokens_output = tokens_output + ? WHERE request_id = ?",
                              (self.tokens_out, self.req))
        self.tokens_out = 0

    def line(self, line_no, entry):
        role = entry.get("role")
        if role == "user":
            self.flush()
            self.new_request(line_no, _text(entry))
        elif role == "assistant" and self.req:
            for idx, block in enumerate(_blocks(entry)):
                self.block(line_no, idx, block)
        elif entry.get("type") == "turn_ended" and self.req:
            status = "success" if entry.get("status") == "success" else "error"
            self.conn.execute("UPDATE requests SET status = ? WHERE request_id = ?", (status, self.req))
        else:
            self.stats["skipped"] += 1

    def new_request(self, line_no, raw):
        self.req = common.sha1("%s:%d" % (self.path, line_no))
        found = _USER_QUERY.search(raw)
        body = found.group(1) if found else _TS_TAG.sub("", raw).strip()
        self.conn.execute(
            "INSERT INTO requests (request_id, session_id, source, ordinal, prompt_redacted, started, "
            "tokens_input, tokens_estimated, transcript_path) VALUES (?,?,?,?,?,?,?,1,?)",
            (self.req, self.session, "ide", self.req_ordinal, common.clamp(redact(body), PROMPT_CAP),
             _prompt_time(raw) or self.fallback_ts, len(raw) // 4, self.path))
        self.req_ordinal += 1
        self.step_ordinal = 0
        self.stats["requests"] += 1

    def add_step(self, step_id, kind, name, detail, tokens, bytes_in=0, whole=0):
        self.conn.execute(
            "INSERT INTO steps (step_id, request_id, ordinal, kind, name, tokens_output, bytes_in, whole_file, "
            "detail_json) VALUES (?,?,?,?,?,?,?,?,?)",
            (step_id, self.req, self.step_ordinal, kind, name, tokens, bytes_in, whole,
             json.dumps(detail, ensure_ascii=False)))
        self.step_ordinal += 1
        self.tokens_out += tokens
        self.stats["steps"] += 1

    def block(self, line_no, idx, block):
        kind = block.get("type")
        step_id = common.sha1("%s:%d:%d" % (self.path, line_no, idx))
        if kind == "text":
            text = str(block.get("text") or "")
            self.add_step(step_id, "message", "assistant", {"text": common.clamp(redact(text), VALUE_CAP)},
                          len(text) // 4)
        elif kind == "tool_use":
            self.tool(step_id, str(block.get("name") or ""), block.get("input"))
        # `thinking` (and anything unknown) is dropped on purpose: never counted, never stored.

    def tool(self, step_id, name, args):
        args = args if isinstance(args, dict) else {}
        tokens = len(json.dumps(args, default=str)) // 4
        detail = {"input": _trim(redact_obj(args))}
        step_kind, step_name, bytes_in, whole = "tool", name, 0, 0
        if name in READ_TOOLS:
            target = str(args.get("path") or args.get("file_path") or args.get("target_file") or "")
            full = target if os.path.isabs(target) else os.path.join(self.project, target)
            if not _is_ranged(args):
                try:
                    bytes_in = os.path.getsize(full)
                except OSError:
                    bytes_in = 0
                whole = 1 if bytes_in >= READ_CAP else 0
            if os.path.basename(target) == "SKILL.md":
                step_kind, step_name = "skill", os.path.basename(os.path.dirname(target)) or "SKILL.md"
        elif name in SKILL_TOOLS:
            step_kind, step_name = "skill", str(args.get("skill") or args.get("name") or name)
        elif name in TASK_TOOLS:
            agent = str(args.get("subagent_type") or args.get("agent") or "")
            step_kind, step_name = "subagent", agent or name
            self.conn.execute(
                "INSERT INTO subagent_runs (id, parent_request_id, parent_step_id, agent, model, started) "
                "VALUES (?,?,?,?,?,(SELECT started FROM requests WHERE request_id = ?))",
                (step_id, self.req, step_id, agent, args.get("model") and str(args["model"]), self.req))
            self.stats["subagent_runs"] += 1
        self.add_step(step_id, step_kind, step_name, detail, tokens, bytes_in, whole)


def _ingest_transcript(conn, project, path, stats) -> None:
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        stats["errors"] += 1
        return
    row = conn.execute("SELECT byte_offset, prefix_sha FROM ingest_offsets WHERE source_path = ?", (path,)).fetchone()
    offset = 0
    if row:
        if row[0] <= len(data) and _sha(data[:row[0]]) == row[1]:
            offset = row[0]
        else:
            _forget_transcript(conn, path)
            stats["rewritten"] += 1
            row = None
    end = max(data.rfind(b"\n") + 1, offset)
    tail = data[end:].strip()
    if tail:  # an unterminated last line counts only once it is complete JSON
        try:
            json.loads(tail.decode("utf-8", "replace"))
            end = len(data)
        except ValueError:
            pass
    if row and end == offset:
        stats["unchanged"] += 1
        return
    work = _Transcript(conn, project, path, stats)
    base = data.count(b"\n", 0, offset)
    for i, raw in enumerate(data[offset:end].split(b"\n")):
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            entry = None
        if not isinstance(entry, dict):
            stats["errors"] += 1
            continue
        work.line(base + i + 1, entry)
    work.flush()
    conn.execute("INSERT OR REPLACE INTO ingest_offsets (source_path, byte_offset, prefix_sha, ingested_at) "
                 "VALUES (?,?,?,?)", (path, end, _sha(data[:end]), common.utc_now()))
    stats["files"] += 1


def _last_error(path):
    error = None
    for entry in _read_jsonl(path):
        if entry.get("type") == "turn_ended":
            error = entry.get("error")
    return str(error) if error else None


def _link_children(conn, main_path, child_paths) -> None:
    """Attach `<id>/subagents/*.jsonl` transcripts to the parent's subagent_runs.

    Cursor transcripts carry no Task calls and no timestamps on lines, so the link is by order:
    children (oldest first) fill the parent's Task runs that have no child yet; any child left over
    gets its own run row on the latest parent request that started before it (else the first).
    """
    parents = conn.execute("SELECT request_id FROM requests WHERE transcript_path = ? ORDER BY ordinal",
                           (main_path,)).fetchall()
    if not parents:
        return
    linked = {r[0] for r in conn.execute("SELECT child_request_id FROM subagent_runs "
                                         "WHERE child_request_id IS NOT NULL")}
    children = []
    for path in sorted(child_paths, key=lambda p: (os.path.getmtime(p), p)):
        first = conn.execute("SELECT request_id, started FROM requests WHERE transcript_path = ? "
                             "ORDER BY ordinal LIMIT 1", (path,)).fetchone()
        last = conn.execute("SELECT status FROM requests WHERE transcript_path = ? ORDER BY ordinal DESC LIMIT 1",
                            (path,)).fetchone()
        if first:
            children.append((first[0], first[1], last[0], path))
    free = [c for c in children if c[0] not in linked]
    open_runs = [r[0] for r in conn.execute(
        "SELECT sr.id FROM subagent_runs sr JOIN steps s ON s.step_id = sr.parent_step_id "
        "JOIN requests r ON r.request_id = s.request_id WHERE r.transcript_path = ? AND sr.child_request_id IS NULL "
        "ORDER BY r.ordinal, s.ordinal", (main_path,))]
    for run_id, (child_req, _, status, path) in zip(open_runs, free):
        conn.execute("UPDATE subagent_runs SET child_request_id = ?, status = ?, error = ? WHERE id = ?",
                     (child_req, status, _last_error(path), run_id))
        conn.execute("UPDATE requests SET parent_request_id = (SELECT parent_request_id FROM subagent_runs "
                     "WHERE id = ?) WHERE request_id = ?", (run_id, child_req))
    for child_req, started, status, path in free[len(open_runs):]:
        parent = conn.execute("SELECT request_id FROM requests WHERE transcript_path = ? AND started <= ? "
                              "ORDER BY ordinal DESC LIMIT 1", (main_path, started or "")).fetchone()
        parent_req = (parent or parents[0])[0]
        conn.execute("INSERT OR IGNORE INTO subagent_runs (id, parent_request_id, child_request_id, agent, "
                     "status, error, started) VALUES (?,?,?,?,?,?,?)",
                     (common.sha1("child:" + child_req), parent_req, child_req, "", status, _last_error(path), started))
        conn.execute("UPDATE requests SET parent_request_id = ? WHERE request_id = ?", (parent_req, child_req))


def ingest_transcripts(conn, project) -> dict:
    stats = Counter({k: 0 for k in ("files", "requests", "steps", "subagent_runs", "unchanged",
                                    "rewritten", "skipped", "errors")})
    for main, subs in discover(transcript_root(project)):
        for path in [main] + subs:
            if not os.path.isfile(path):
                continue
            part = Counter()
            conn.execute("SAVEPOINT file")
            try:
                _ingest_transcript(conn, project, path, part)
                conn.execute("RELEASE file")
                stats.update(part)
            except Exception:
                conn.execute("ROLLBACK TO file")
                conn.execute("RELEASE file")
                stats["errors"] += 1
        if subs and os.path.isfile(main):
            _link_children(conn, main, subs)
    return dict(stats)


def compact(conn, days: int = 7, now=None) -> int:
    """Retention: drop step details and prompt text of requests older than `days`; keep every row
    total and subagent summary. `prompt_redacted IS NULL` marks a compacted request (the schema has
    no per-request flag; ingest always writes a string). Returns the number of requests compacted."""
    cutoff = common.iso_from_epoch((time.time() if now is None else now) - days * 86400)
    old = "(SELECT request_id FROM requests WHERE started < ? AND prompt_redacted IS NOT NULL)"
    conn.execute("UPDATE steps SET detail_json = NULL WHERE request_id IN " + old, (cutoff,))
    conn.execute("UPDATE subagent_runs SET compacted = 1 WHERE parent_request_id IN " + old, (cutoff,))
    cur = conn.execute("UPDATE requests SET prompt_redacted = NULL, interpreted_json = NULL "
                       "WHERE started < ? AND prompt_redacted IS NOT NULL", (cutoff,))
    return cur.rowcount


def ingest_compact(conn, project) -> dict:
    return {"requests_compacted": compact(conn)}


# ---- gates ---------------------------------------------------------------------------------

def ingest_gates(conn, project) -> dict:
    """One gate_events row per `history` entry of each STATE.json (sdlc/ and pipeline/*/)."""
    spec = common.agent_spec_dir(project)
    paths = [os.path.join(spec, "sdlc", "STATE.json")] + sorted(glob.glob(os.path.join(spec, "pipeline", "*", "STATE.json")))
    stats = {"added": 0, "skipped": 0, "errors": 0}
    for path in paths:
        if not os.path.isfile(path):
            continue
        state = common.read_json(path)
        if not isinstance(state, dict) or not isinstance(state.get("history", []), list):
            stats["errors"] += 1
            continue
        feature = str(state.get("feature") or (os.path.basename(os.path.dirname(path))
                                               if os.path.basename(os.path.dirname(path)) != "sdlc" else ""))
        artifacts = state.get("artifacts") if isinstance(state.get("artifacts"), dict) else {}
        for item in state.get("history", []):
            try:
                at = str(item["at"])
                artifact = next((k for k, v in artifacts.items() if v == at), "")
                cur = conn.execute("INSERT OR IGNORE INTO gate_events (feature, gate, gate_name, ts, artifact) "
                                   "VALUES (?,?,?,?,?)",
                                   (feature, int(item["gate"]), str(item.get("name") or ""), _to_utc(at), artifact))
                stats["added" if cur.rowcount else "skipped"] += 1
            except (KeyError, TypeError, ValueError):
                stats["errors"] += 1
    return stats


# ---- memory --------------------------------------------------------------------------------

def _frontmatter(path):
    """{key: value} from a `---` delimited header; {} when absent or unterminated."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return meta
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    return {}


def _fact_files(directory):
    nested = os.path.join(directory, "facts")
    return sorted(glob.glob(os.path.join(nested if os.path.isdir(nested) else directory, "*.md")))


def ingest_memory(conn, project) -> dict:
    """Mirror local + team facts into memory_facts; note receipt fact counts in `meta`.

    Limitation: receipts only record HOW MANY facts the digest carried (`facts_injected`), not which,
    so `fact_injections` gets no rows; the per-session counts go to meta keys `receipt:<session>`."""
    spec = common.agent_spec_dir(project)
    stats = {"facts": 0, "added": 0, "removed": 0, "receipts": 0, "errors": 0}
    before = {r[0] for r in conn.execute("SELECT fact_id FROM memory_facts")}
    rows = {}
    for scope, directory in (("local", os.path.join(spec, "memory", "facts")),
                             ("team", os.path.join(spec, "team-facts"))):
        for path in _fact_files(directory) if os.path.isdir(directory) else []:
            try:
                meta = _frontmatter(path)
                fact_id = meta.get("id") or os.path.splitext(os.path.basename(path))[0]
                if fact_id in rows:
                    fact_id = "%s:%s" % (scope, fact_id)
                rows[fact_id] = (fact_id, meta.get("type", ""), meta.get("subject", ""), os.path.getsize(path),
                                 meta.get("confidence"), meta.get("status") or "active", meta.get("expires"),
                                 scope, os.path.relpath(path, project),
                                 meta.get("updated") or meta.get("created") or "")
            except OSError:
                stats["errors"] += 1
    conn.execute("DELETE FROM memory_facts")
    conn.executemany("INSERT INTO memory_facts (fact_id, type, subject, bytes, confidence, status, expires, "
                     "scope, source_path, updated) VALUES (?,?,?,?,?,?,?,?,?,?)", list(rows.values()))
    stats.update(facts=len(rows), added=len(set(rows) - before), removed=len(before - set(rows)))
    for path in sorted(glob.glob(os.path.join(spec, "metrics", "receipts", "*.json"))):
        receipt = common.read_json(path)
        if not isinstance(receipt, dict) or receipt.get("facts_injected") is None:
            continue
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)",
                     ("receipt:%s" % (receipt.get("session_id") or os.path.basename(path)[:-5]),
                      json.dumps({"facts_injected": receipt["facts_injected"], "ts": receipt.get("ts")})))
        stats["receipts"] += 1
    return stats


# ---- graph + quarantine (append-only JSONL, UNIQUE keys make re-reads idempotent) -------------

def _ingest_jsonl(conn, path, sql, build) -> dict:
    stats = {"added": 0, "skipped": 0, "errors": 0}
    if not os.path.isfile(path):
        return stats
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                cur = conn.execute(sql, build(json.loads(line)))
                stats["added" if cur.rowcount else "skipped"] += 1
            except (ValueError, KeyError, TypeError, AttributeError):
                stats["errors"] += 1
    return stats


def ingest_graph(conn, project) -> dict:
    # sha is coerced to '' because UNIQUE(ts, sha) treats NULLs as distinct.
    return _ingest_jsonl(
        conn, os.path.join(common.agent_spec_dir(project), "graph", "stats-history.jsonl"),
        "INSERT OR IGNORE INTO graph_stats (ts, files, edges, symbols, cycles, sha, age_s) VALUES (?,?,?,?,?,?,?)",
        lambda d: (_to_utc(d["ts"]), int(d.get("files", 0)), int(d.get("edges", 0)), int(d.get("symbols", 0)),
                   int(d.get("cycles", 0)), str(d.get("sha") or ""), int(d.get("age_s", 0))))


def ingest_quarantine(conn, project) -> dict:
    return _ingest_jsonl(
        conn, os.path.join(common.agent_spec_dir(project), "metrics", "quarantine.jsonl"),
        "INSERT OR IGNORE INTO quarantine_events (ts, tool, pattern, path_redacted, session_id) VALUES (?,?,?,?,?)",
        lambda d: (_to_utc(d["ts"]), str(d.get("tool") or ""), str(d.get("pattern") or ""),
                   redact(d.get("path_redacted") or d.get("path") or ""), d.get("session_id")))


# ---- workflow runs (O-010) and the experience store (L-001) --------------------------------

def _run_steps(events, result) -> list:
    """Step records in finish order: from `step.finished` events, else from result.json (compacted run)."""
    done = {}
    for ev in events:
        if ev["type"] == "step.finished" and ev.get("step_id"):
            done[ev["step_id"]] = ev
    if done:
        return list(done.values())
    return [{"step_id": sid, "payload": {"status": info.get("status"), "attempt": info.get("attempts"),
                                         "error": info.get("error")}, "actor": {}, "ts": None,
             "tokens": {}, "duration_ms": 0} for sid, info in (result.get("steps") or {}).items()
            if info.get("status") != "pending"]


def _ingest_run_dir(conn, rd, stats) -> None:
    run = common.read_json(os.path.join(rd, "run.json"))
    if not isinstance(run, dict) or not run.get("run_id"):
        raise ValueError("run.json")
    rid = str(run["run_id"])
    result = common.read_json(os.path.join(rd, "result.json")) if os.path.isfile(os.path.join(rd, "result.json")) else {}
    result = result if isinstance(result, dict) else {}
    events = []
    path = os.path.join(rd, "events.jsonl")
    if os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            for seq, line in enumerate(fh):
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                    tok = ev.get("tokens") or {}
                    conn.execute(
                        "INSERT OR IGNORE INTO events (event_id, run_id, trace_id, span_id, parent_span_id, ts, seq, "
                        "source, type, step_id, actor_json, payload_json, tokens_input, tokens_output, "
                        "tokens_cache_read, tokens_estimated, cost_usd, duration_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (str(ev["event_id"]), rid, ev.get("trace_id"), ev.get("span_id"), ev.get("parent_span_id"),
                         str(ev["ts"]), seq, ev.get("source") or "ide", str(ev["type"]), ev.get("step_id"),
                         json.dumps(redact_obj(ev.get("actor") or {})), json.dumps(redact_obj(ev.get("payload") or {})),
                         int(tok.get("input", 0)), int(tok.get("output", 0)), int(tok.get("cache_read", 0)),
                         1 if tok.get("estimated", True) else 0, float(ev.get("cost_usd") or 0),
                         int(ev.get("duration_ms") or 0)))
                    events.append(ev)
                    stats["events"] += 1
                except (ValueError, KeyError, TypeError, AttributeError):
                    stats["errors"] += 1
    steps = _run_steps(events, result)
    tok = result.get("tokens") or {}
    tin = int(tok.get("input", sum(int((s.get("tokens") or {}).get("input", 0)) for s in steps)))
    tout = int(tok.get("output", sum(int((s.get("tokens") or {}).get("output", 0)) for s in steps)))
    cost = float(result.get("cost_usd", sum(float(s.get("cost_usd") or 0) for s in steps)))
    conn.execute("DELETE FROM requests WHERE request_id = ?", (rid,))  # cascades to its steps
    conn.execute(
        "INSERT INTO requests (request_id, run_id, source, prompt_redacted, status, started, finished, tokens_input, "
        "tokens_output, tokens_estimated, cost_usd, workflow_id, workflow_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (rid, rid, "ide" if run.get("source") != "headless" else "headless", redact(str(run.get("request") or ""))[:PROMPT_CAP],
         str(run.get("status") or "running"), _to_utc(run["started"]) if run.get("started") else None,
         _to_utc(run["finished"]) if run.get("finished") else None, tin, tout, 1, cost,
         run.get("workflow_id"), run.get("workflow_version")))
    for n, s in enumerate(steps):
        p, actor, tk = s.get("payload") or {}, s.get("actor") or {}, s.get("tokens") or {}
        conn.execute(
            "INSERT INTO steps (step_id, request_id, ordinal, kind, name, status, started, duration_ms, tokens_input, "
            "tokens_output, detail_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("%s:%s" % (rid, s["step_id"]), rid, n, "ai" if actor.get("agent") else "run", str(s["step_id"]),
             str(p.get("status") or "success"), s.get("ts"), int(s.get("duration_ms") or 0),
             int(tk.get("input", 0)), int(tk.get("output", 0)),
             json.dumps(redact_obj({"agent": actor.get("agent"), "model": actor.get("model"),
                                    "skill": actor.get("skill"), "attempt": p.get("attempt"),
                                    "error": p.get("error")}))))
        stats["steps"] += 1
    stats["runs"] += 1


def ingest_runs(conn, project) -> dict:
    """`.agent-spec/runs/<id>/{run,result}.json` + `events.jsonl` -> requests, steps, events (idempotent)."""
    stats = Counter({k: 0 for k in ("runs", "steps", "events", "errors")})
    for rd in sorted(glob.glob(os.path.join(common.agent_spec_dir(project), "runs", "*"))):
        if not os.path.isfile(os.path.join(rd, "run.json")):
            continue
        try:
            _ingest_run_dir(conn, rd, stats)
        except (ValueError, KeyError, TypeError, OSError):
            stats["errors"] += 1
    return dict(stats)


def ingest_experiences(conn, project) -> dict:
    """`.agent-spec/experience.jsonl` -> experiences. A later line for the same exp_id updates the record
    but keeps `uses`, `tier` and `confidence`, which the learn skill and humans own."""
    stats = {"added": 0, "skipped": 0, "errors": 0}
    path = os.path.join(common.agent_spec_dir(project), "experience.jsonl")
    if not os.path.isfile(path):
        return stats
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                task = redact(str(d.get("task") or ""))[:200]
                existed = conn.execute("SELECT 1 FROM experiences WHERE exp_id = ?", (str(d["exp_id"]),)).fetchone()
                conn.execute(
                    "INSERT INTO experiences (exp_id, signature, title, successes, created, run_id, record_json) "
                    "VALUES (?,?,?,?,?,?,?) ON CONFLICT(exp_id) DO UPDATE SET signature = excluded.signature, "
                    "title = excluded.title, successes = excluded.successes, record_json = excluded.record_json",
                    (str(d["exp_id"]), " ".join(sorted(set(re.findall(r"[a-z0-9]{4,}", task.lower()))))[:200], task,
                     1 if d.get("status") == "success" else 0, _to_utc(d["ts"]) if d.get("ts") else None,
                     d.get("run_id"), json.dumps(redact_obj(d))))
                stats["skipped" if existed else "added"] += 1
            except (ValueError, KeyError, TypeError, AttributeError):
                stats["errors"] += 1
    return stats


def ingest_events(conn, project) -> dict:
    """Ingest .agent-spec/metrics/events.jsonl from hook spine (DEC-15 / AF-002)."""
    stats = Counter({"events": 0, "requests": 0, "steps": 0, "subagent_runs": 0, "errors": 0})
    path = os.path.join(common.agent_spec_dir(project), "metrics", "events.jsonl")
    if not os.path.isfile(path):
        return dict(stats)
    with open(path, encoding="utf-8", errors="replace") as fh:
        for idx, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                stats["events"] += 1
                session_id = ev.get("session_id") or "sess-default"
                req_id = f"hook-{session_id[:16]}"
                ts = ev.get("ts")
                tok = ev.get("tokens") or {}
                tin = tok.get("input", 0) if isinstance(tok, dict) else 0
                tout = tok.get("output", 0) if isinstance(tok, dict) else 0

                # Ensure parent request exists
                conn.execute(
                    "INSERT OR IGNORE INTO requests (request_id, session_id, ordinal, source, started, status, tokens_input, tokens_output, prompt_redacted) "
                    "VALUES (?, ?, 0, 'hook_events', ?, 'completed', ?, ?, 'Hook event session')",
                    (req_id, session_id, ts, tin, tout),
                )
                stats["requests"] += 1

                # If tool step
                if ev.get("tool"):
                    step_id = f"st-{idx}-{req_id}"
                    conn.execute(
                        "INSERT OR IGNORE INTO steps (step_id, request_id, ordinal, kind, name, status, duration_ms, tokens_input, tokens_output) "
                        "VALUES (?, ?, ?, 'tool', ?, ?, ?, ?, ?)",
                        (step_id, req_id, idx, ev.get("tool"), ev.get("status", "success"), ev.get("duration_ms"), tin, tout),
                    )
                    stats["steps"] += 1

                # If subagent
                if ev.get("subagent"):
                    sa_id = f"sa-{idx}-{req_id}"
                    conn.execute(
                        "INSERT OR IGNORE INTO subagent_runs (id, parent_request_id, agent, status, latency_ms) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (sa_id, req_id, ev.get("subagent"), ev.get("status", "completed"), ev.get("duration_ms")),
                    )
                    stats["subagent_runs"] += 1
            except Exception:
                stats["errors"] += 1
    return dict(stats)


SOURCES = {"events": ingest_events, "transcripts": ingest_transcripts, "gates": ingest_gates, "memory": ingest_memory,
           "graph": ingest_graph, "quarantine": ingest_quarantine, "runs": ingest_runs,
           "experiences": ingest_experiences, "compact": ingest_compact}


def run(project, what, rebuild=False) -> dict:
    """Ingest `what` (names or ["all"]); returns {name: {stat: n}}. `rebuild` recreates the database."""
    project = os.path.abspath(project)
    path = db.db_path(project)
    if rebuild:
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(path + suffix)
            except OSError:
                pass
    conn = db.open_ready(path)
    conn.isolation_level = None  # explicit BEGIN/COMMIT/SAVEPOINT below
    names = list(ALL) if "all" in what else list(dict.fromkeys(what))
    report = {}
    try:
        for name in names:
            fn = SOURCES.get(name)
            if fn is None:
                report[name] = {"unsupported": 1}
                continue
            conn.execute("BEGIN IMMEDIATE")
            try:
                report[name] = fn(conn, project)
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                report[name] = {"errors": 1}
    finally:
        conn.close()
    return report
