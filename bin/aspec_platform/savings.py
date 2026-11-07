"""Savings calculator and session compare (D-010): read-only helpers behind `/api/savings`,
`/api/sessions` and `/api/compare`.

The savings model is an estimate, and says so: every whole-file read the harness would have
replaced is priced against one `graphify context` answer (default 152 B). Weights are editable
per request. Compare never accepts a path from the client: it takes two session ids, resolves
each to the transcript recorded by the ingestor, and runs `agent-spec-tokens.py compare`.
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOKENS_SCRIPT = os.path.normpath(os.path.join(HERE, "..", "agent-spec-tokens.py"))
COMPARE_TIMEOUT_S = 20
MAX_OUTPUT = 20000

# name -> (default, minimum exclusive-or-inclusive handled in _weight, maximum)
WEIGHTS = {
    "bytes_per_token": (4.0, 0.5, 64.0),
    "context_bytes": (152.0, 1.0, 100000.0),
    "price_per_mtok": (3.0, 0.0, 1000.0),
    "resend_turns": (1.0, 1.0, 1000.0),
}


class InvalidWeight(ValueError):
    pass


def parse_weights(params) -> dict:
    """Weights from a parsed query string (`{name: [value]}`); raises `InvalidWeight`."""
    out = {}
    for name, (default, low, high) in WEIGHTS.items():
        raw = (params.get(name) or [None])[0]
        if raw is None or raw == "":
            out[name] = default
            continue
        try:
            value = float(raw)
        except ValueError:
            raise InvalidWeight("%s must be a number" % name)
        if value != value or value < low or value > high:
            raise InvalidWeight("%s must be between %g and %g" % (name, low, high))
        out[name] = value
    return out


def savings(conn, weights: dict, session_id: str | None = None) -> dict:
    if session_id:
        reads, size = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(s.bytes_in), 0) FROM steps s "
            "JOIN requests r ON r.request_id = s.request_id "
            "WHERE s.whole_file = 1 AND r.session_id = ?", (session_id,)).fetchone()
        queries = conn.execute(
            "SELECT COUNT(*) FROM steps s "
            "JOIN requests r ON r.request_id = s.request_id "
            "WHERE s.kind = 'tool' AND s.detail_json LIKE '%graphify-cli%' AND r.session_id = ?",
            (session_id,)).fetchone()[0]
    else:
        reads, size = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(bytes_in), 0) FROM steps WHERE whole_file = 1").fetchone()
        queries = conn.execute(
            "SELECT COUNT(*) FROM steps WHERE kind = 'tool' AND detail_json LIKE '%graphify-cli%'").fetchone()[0]
    naive = int(size / weights["bytes_per_token"])
    graph = int(reads * weights["context_bytes"] / weights["bytes_per_token"])
    saved = max(naive - graph, 0)
    usd = saved * weights["resend_turns"] * weights["price_per_mtok"] / 1e6
    return {
        "estimate": True,
        "weights": weights,
        "measured": {"whole_file_reads": reads, "whole_file_bytes": size, "graph_queries": queries},
        "naive_tokens": naive,
        "graph_tokens": graph,
        "saved_tokens": saved,
        "saved_usd": usd,
    }


def sessions(conn, limit: int = 100) -> list:
    rows = conn.execute(
        "SELECT session_id, COUNT(*) AS runs, MIN(started) AS started, "
        "SUM(tokens_input + tokens_output + tokens_cache_read) AS tokens_total "
        "FROM requests WHERE session_id IS NOT NULL AND transcript_path IS NOT NULL "
        "GROUP BY session_id ORDER BY started DESC, session_id LIMIT ?", (limit,))
    return [dict(r) for r in rows]


def _transcript(conn, session_id):
    row = conn.execute(
        "SELECT transcript_path FROM requests WHERE session_id = ? AND transcript_path IS NOT NULL "
        "ORDER BY ordinal LIMIT 1", (session_id,)).fetchone()
    return row[0] if row else None


def compare(conn, a: str, b: str) -> dict:
    """Run `agent-spec-tokens.py compare` on two ingested sessions. Returns `{a, b, text}`.

    Raises `LookupError` for an unknown session and `RuntimeError` when the tool fails.
    """
    paths = []
    for sid in (a, b):
        path = _transcript(conn, sid)
        if not path or not os.path.isfile(path):
            raise LookupError("session not found: %s" % sid[:80])
        paths.append(path)
    try:
        proc = subprocess.run([sys.executable, TOKENS_SCRIPT, "compare", paths[0], paths[1]],
                              capture_output=True, text=True, timeout=COMPARE_TIMEOUT_S, check=False)
    except (OSError, subprocess.SubprocessError):
        raise RuntimeError("compare tool unavailable")
    if proc.returncode != 0:
        raise RuntimeError("compare failed")
    return {"a": a, "b": b, "text": proc.stdout[:MAX_OUTPUT]}
