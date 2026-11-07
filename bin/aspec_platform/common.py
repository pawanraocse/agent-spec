"""Shared helpers for the platform extra. Stdlib only, Python 3.9+.

Kept deliberately small: ids, clocks, hashing, atomic writes, project discovery.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
import threading
import time
from datetime import datetime, timezone

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ulid_lock = threading.Lock()
_ulid_last = [0, 0]  # [ms, random]


def utc_now() -> str:
    """ISO-8601 UTC with millisecond precision, e.g. 2026-10-31T12:00:00.000Z."""
    return iso_from_epoch(time.time())


def iso_from_epoch(seconds: float) -> str:
    dt = datetime.fromtimestamp(seconds, timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (dt.microsecond // 1000)


def parse_iso(value):
    """Parse an ISO-8601 string to an aware datetime; None on any failure."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def ulid() -> str:
    """Sortable unique id (48-bit ms time + 80-bit randomness), monotonic within one process."""
    with _ulid_lock:
        ms = int(time.time() * 1000)
        if ms <= _ulid_last[0]:
            ms = _ulid_last[0]
            rand = _ulid_last[1] + 1
        else:
            rand = secrets.randbits(80)
        _ulid_last[0], _ulid_last[1] = ms, rand
    value = (ms << 80) | (rand & ((1 << 80) - 1))
    out = []
    for _ in range(26):
        out.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(out))


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()


def sha256(data) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8", "replace")
    return hashlib.sha256(data).hexdigest()


def canonical_json(obj) -> str:
    """Stable serialization used for idempotency keys and content hashes."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def atomic_write(path: str, text: str) -> None:
    """Write `text` to `path` so readers never see a partial file (tmp + os.replace)."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def find_project(start=None):
    """Nearest ancestor of `start` holding `.agent-spec/`; falls back to `start` itself."""
    cur = os.path.abspath(start or os.getcwd())
    probe = cur
    while True:
        if os.path.isdir(os.path.join(probe, ".agent-spec")):
            return probe
        parent = os.path.dirname(probe)
        if parent == probe:
            return cur
        probe = parent


def agent_spec_dir(project: str) -> str:
    return os.path.join(project, ".agent-spec")


def clamp(text, limit: int) -> str:
    text = text if isinstance(text, str) else ("" if text is None else str(text))
    return text if len(text) <= limit else text[:limit] + "…"
