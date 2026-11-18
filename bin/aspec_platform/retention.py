"""Retention for the harness's append-only files (H-041).

Every hook appends; nothing trimmed. A file over its size cap has its rows older than the
retention window moved to a dated archive next to it (`metrics/archive/<name>.<YYYY-MM>.jsonl`),
so the live file stays small and nothing is deleted. Directories of per-session files
(hook payloads, receipts) move whole files by age. `graph/stats-history.jsonl` keeps its
newest MAX_HISTORY lines.

Derived rows follow on their own: ingest rebuilds traces and spans whole from events.jsonl
on every run, so rows archived here drop out of platform.db on the next ingest.

Config: `.agent-spec/retention.json` {"days": 90, "max_bytes": 5242880}. Allowed-code reason
(DEC-15): *plumbing* — byte and date arithmetic, no judgement.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timedelta, timezone

from . import common

DEFAULTS = {"days": 90, "max_bytes": 5 * 1024 * 1024}
JSONL = ("metrics/events.jsonl", "metrics/automation.jsonl", "metrics/injections.jsonl",
         "metrics/daily.jsonl")
DIRS = ("metrics/hook-payloads", "metrics/receipts")
HISTORY = "graph/stats-history.jsonl"
MAX_HISTORY = 5000


def config(project: str) -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(os.path.join(common.agent_spec_dir(project), "retention.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        for key in DEFAULTS:
            if isinstance(data.get(key), int) and data[key] > 0:
                cfg[key] = data[key]
    except (OSError, ValueError, AttributeError):
        pass
    return cfg


def _row_time(row: dict):
    """A row's timestamp as aware UTC, from `ts` (ISO, with or without offset) or epoch ms."""
    ts = row.get("ts") or row.get("timestamp") or row.get("time")
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000 if ts > 1e11 else ts, tz=timezone.utc)
    if not isinstance(ts, str) or not ts:
        return None
    text = ts.replace("Z", "+00:00")
    if len(text) >= 5 and text[-5] in "+-" and text[-3] != ":":  # +0530 -> +05:30
        text = text[:-2] + ":" + text[-2:]
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _archive_path(spec: str, rel: str, month: str) -> str:
    base = os.path.basename(rel)
    stem = base[:-len(".jsonl")] if base.endswith(".jsonl") else base
    return os.path.join(spec, os.path.dirname(rel), "archive", "%s.%s.jsonl" % (stem, month))


def _split_jsonl(path: str, cutoff: datetime):
    """(keep_lines, {month: old_lines}, bytes_read). Undated or unreadable lines are kept."""
    keep, old = [], {}
    with open(path, "rb") as fh:
        data = fh.read()
    end = data.rfind(b"\n") + 1  # a partial last line is still being written: leave it
    for line in data[:end].splitlines(keepends=True):
        try:
            row = json.loads(line)
            when = _row_time(row) if isinstance(row, dict) else None
        except ValueError:
            when = None
        if when is not None and when < cutoff:
            old.setdefault(when.strftime("%Y-%m"), []).append(line)
        else:
            keep.append(line)
    return keep, old, end


def _rewrite(path: str, lines: list, read_upto: int) -> None:
    """Replace `path` with `lines`, carrying over anything appended after `read_upto`."""
    tmp = path + ".retain.tmp"
    with open(tmp, "wb") as out:
        out.writelines(lines)
        with open(path, "rb") as src:
            src.seek(read_upto)
            shutil.copyfileobj(src, out)
    os.replace(tmp, path)


def plan(project: str) -> list:
    """What `apply` would do, without changing anything."""
    return _run(project, dry_run=True)


def apply(project: str) -> list:
    return _run(project, dry_run=False)


def _run(project: str, dry_run: bool) -> list:
    spec = common.agent_spec_dir(project)
    cfg = config(project)
    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg["days"])
    actions = []
    for rel in JSONL:
        path = os.path.join(spec, rel)
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        if size <= cfg["max_bytes"]:
            continue
        keep, old, upto = _split_jsonl(path, cutoff)
        moved = sum(len(v) for v in old.values())
        if not moved:
            actions.append({"file": rel, "bytes": size, "archived_rows": 0,
                            "note": "over the cap, but every row is inside the %d-day window" % cfg["days"]})
            continue
        archives = sorted(os.path.relpath(_archive_path(spec, rel, m), spec) for m in old)
        if not dry_run:
            for month, lines in old.items():
                target = _archive_path(spec, rel, month)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "ab") as fh:
                    fh.writelines(lines)
            _rewrite(path, keep, upto)
        actions.append({"file": rel, "bytes": size, "archived_rows": moved, "kept_rows": len(keep),
                        "archives": archives})
    horizon = time.time() - cfg["days"] * 86400
    for rel in DIRS:
        folder = os.path.join(spec, rel)
        if not os.path.isdir(folder):
            continue
        stale = []
        for name in os.listdir(folder):
            p = os.path.join(folder, name)
            try:
                if os.path.isfile(p) and os.path.getmtime(p) < horizon:
                    stale.append(name)
            except OSError:
                continue
        if not stale:
            continue
        if not dry_run:
            for name in stale:
                p = os.path.join(folder, name)
                month = datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m")
                target = os.path.join(folder, "archive", month)
                os.makedirs(target, exist_ok=True)
                os.replace(p, os.path.join(target, name))
        actions.append({"file": rel, "archived_files": len(stale)})
    hist = os.path.join(spec, HISTORY)
    if os.path.isfile(hist):
        with open(hist, "rb") as fh:
            data = fh.read()
        upto = data.rfind(b"\n") + 1
        lines = data[:upto].splitlines(keepends=True)
        if len(lines) > MAX_HISTORY:
            drop = lines[:-MAX_HISTORY]
            if not dry_run:
                target = os.path.join(spec, "graph", "archive", "stats-history.jsonl")
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "ab") as fh:
                    fh.writelines(drop)
                _rewrite(hist, lines[-MAX_HISTORY:], upto)
            actions.append({"file": HISTORY, "archived_rows": len(drop), "kept_rows": MAX_HISTORY})
    return actions


def archives(project: str) -> list:
    """Every archive file, for the Index health panel."""
    spec = common.agent_spec_dir(project)
    out = []
    for dirpath, _, names in os.walk(spec):
        if os.sep + "archive" not in dirpath + os.sep and not dirpath.endswith("archive"):
            continue
        for name in sorted(names):
            p = os.path.join(dirpath, name)
            try:
                out.append({"path": os.path.relpath(p, spec), "bytes": os.path.getsize(p)})
            except OSError:
                pass
    return out
