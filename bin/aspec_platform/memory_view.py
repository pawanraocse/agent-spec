"""Memory page: every remembered fact with its text and how often the digest injected it, plus
the controls to add, edit, forget and prune facts from the dashboard.

Reads the fact files directly, so a fact added from Cursor a minute ago is listed without an
ingest; the injection counts come from the database. Every change goes through
agent-spec-memory.py (the one writer of fact files), is re-ingested so the Impact and Learning
views agree, and leaves an audit row in metrics/proposals.jsonl beside the other decisions on
what the agent learns (P3-012).

Ids from the client are only matched against the listing, never joined into a path. Team facts
are synced wholesale by `merge-team`, so they are read-only here.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

from . import common, ingest, proposals

TYPES = ("decision", "constraint", "gotcha", "reference")
INDEX_LIMIT = 8000  # bytes; the same limit agent-spec-doctor.py checks (MEMORY_INDEX_LIMIT)
TEXT_MIN, TEXT_MAX = 10, 600  # agent-spec-memory.py add refuses anything outside this
SUBJECT_MAX = 80
PRUNE_LINE = re.compile(r"^(?:would remove|removed) (\S+)\s+\[(\w+)\] (.*)$")


def _body(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    m = re.match(r"---\n.*?\n---\n(.*)", raw, re.S)
    return (m.group(1) if m else raw).strip()


def _files(project: str):
    spec = common.agent_spec_dir(project)
    for scope, directory in (("local", os.path.join(spec, "memory", "facts")),
                             ("team", os.path.join(spec, "team-facts"))):
        if os.path.isdir(directory):
            for path in ingest._fact_files(directory):
                yield scope, path


def _injections(conn) -> dict:
    if conn is None:
        return {}
    try:
        return {r[0]: r[1] for r in conn.execute(
            "SELECT fact_id, COUNT(*) FROM fact_injections GROUP BY fact_id")}
    except Exception:  # noqa: BLE001 — an old or missing table just means no counts yet
        return {}


def facts(project: str, conn=None) -> list:
    counts = _injections(conn)
    out = []
    for scope, path in _files(project):
        try:
            meta = ingest._frontmatter(path)
            body = _body(path)
        except OSError:
            continue
        fid = meta.get("id") or os.path.splitext(os.path.basename(path))[0]
        out.append({"fact_id": fid, "type": meta.get("type", ""), "subject": meta.get("subject", ""),
                    "body": body, "scope": scope, "status": meta.get("status") or "active",
                    "confidence": meta.get("confidence"), "created": meta.get("created", ""),
                    "updated": meta.get("updated") or meta.get("created") or "",
                    "supersedes": meta.get("supersedes"), "bytes": os.path.getsize(path),
                    "injections_count": counts.get(fid, 0)})
    out.sort(key=lambda f: f["created"], reverse=True)
    return out


def overview(project: str, conn=None) -> dict:
    index = os.path.join(common.agent_spec_dir(project), "memory", "INDEX.md")
    listing = facts(project, conn)
    return {"facts": listing, "types": list(TYPES),
            "index": {"bytes": os.path.getsize(index) if os.path.isfile(index) else 0, "limit": INDEX_LIMIT},
            "active": sum(1 for f in listing if f["scope"] == "local" and f["status"] == "active"),
            "provenance": "measured"}


def _cli(project: str) -> str:
    path = proposals._bin(project, "agent-spec-memory.py")
    if not path:
        raise ValueError("agent-spec-memory.py is not installed in this project")
    return path


def _run(project: str, *argv) -> str:
    res = subprocess.run([sys.executable, _cli(project)] + list(argv), cwd=project, capture_output=True,
                         text=True, timeout=30)
    if res.returncode != 0:
        raise ValueError((res.stderr or res.stdout).strip()[:300] or "agent-spec-memory.py failed")
    return res.stdout


def _local(project: str, fact_id: str) -> dict:
    fact = next((f for f in facts(project) if f["fact_id"] == fact_id), None)
    if fact is None:
        raise ValueError("no fact %r" % fact_id)
    if fact["scope"] != "local":
        raise ValueError("team facts are synced by merge-team; change them at their source")
    return fact


def _fields(body: dict):
    kind = str(body.get("type") or "")
    subject = " ".join(str(body.get("subject") or "").split())
    text = " ".join(str(body.get("text") or "").split())
    if kind not in TYPES:
        raise ValueError("type must be one of %s" % ", ".join(TYPES))
    if not 3 <= len(subject) <= SUBJECT_MAX:
        raise ValueError("subject must be 3-%d characters" % SUBJECT_MAX)
    if not TEXT_MIN <= len(text) <= TEXT_MAX:
        raise ValueError("a fact is one sentence of %d-%d characters" % (TEXT_MIN, TEXT_MAX))
    return kind, subject, text


def _days(value) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError):
        raise ValueError("older_than must be a whole number of days") from None
    if not 1 <= days <= 3650:
        raise ValueError("older_than must be 1-3650 days")
    return days


def change(project: str, body: dict) -> dict:
    """body.action: add {type, subject, text} | edit {id, type, subject, text} | forget {id} |
    prune {older_than, apply}. A prune without apply is a preview and changes nothing."""
    action = str(body.get("action") or "")
    if action == "add":
        kind, subject, text = _fields(body)
        out = _run(project, "add", "--type", kind, "--subject", subject, "--source", "dashboard", "--", text)
        target = subject
    elif action == "edit":
        old = _local(project, str(body.get("id") or ""))
        kind, subject, text = _fields(body)
        if (kind, subject, text) == (old["type"], old["subject"], " ".join(old["body"].split())):
            raise ValueError("nothing changed")
        out = _run(project, "add", "--type", kind, "--subject", subject, "--source", "dashboard",
                   "--supersedes", old["fact_id"], "--", text)
        target = old["fact_id"]
    elif action == "forget":
        target = _local(project, str(body.get("id") or ""))["fact_id"]
        out = _run(project, "forget", target)
    elif action == "prune":
        days, apply = _days(body.get("older_than")), body.get("apply") is True
        out = _run(project, "prune", "--older-than", str(days), *([] if apply else ["--dry-run"]))
        doomed = [{"fact_id": m.group(1), "type": m.group(2), "subject": m.group(3)}
                  for m in (PRUNE_LINE.match(l.strip()) for l in out.splitlines()) if m]
        if not apply:
            return {"ok": True, "action": "prune", "preview": True, "older_than": days, "facts": doomed}
        target = "%d facts older than %d days" % (len(doomed), days)
    else:
        raise ValueError("action must be add, edit, forget or prune")
    result = next((l.strip() for l in out.splitlines() if l.strip()), "done")
    ingest.run(project, ["memory"])  # the server never re-ingests on its own
    proposals.audit(project, {"kind": "memory", "id": target, "decision": action, "result": result})
    return {"ok": True, "action": action, "result": result}
