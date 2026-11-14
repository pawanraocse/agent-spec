"""Cursor's own hook log as a recording source (DV-002).

Cursor writes every hook invocation to
`<Cursor>/logs/<launch>/window*/output_*/cursor.hooks.*.log`: the step name, the command,
its exit code, the full JSON INPUT and the STDERR. It does this whether or not the hook
succeeds. The log is therefore a live recording that needs no environment variable and no
relaunch, and it still works when the hooks themselves cannot run. One case where they
cannot: a WSL folder opened over `\\\\wsl.localhost`, where Cursor spawns hooks on Windows
and fails with `spawn powershell ENOENT`.

This module parses those logs, keeps the invocations that belong to one project, explains
why they failed, and can:

- write the latest payload per event to `.agent-spec/metrics/hook-payloads/` (DV-002),
- write scrubbed copies over `tests/fixtures/hooks/` (`fixtures`),
- backfill `.agent-spec/metrics/events.jsonl` through the hook's own `handle_event`, so the
  dashboard shows traces even for sessions whose hooks never ran (DV-060).

Allowed-code reason: plumbing (log parsing) and security (redaction happens before anything
is written to disk).
"""
from __future__ import annotations

import calendar
import glob
import importlib.util
import json
import os
import re
import time

from . import cursor_sessions

_BLOCK = re.compile(
    r"═+\n(?P<step>[A-Za-z]+)\n═+\nCommand: (?P<cmd>.*?) \((?P<ms>\d+)ms\) exit code: (?P<code>-?\d+|N/A)\s*\n\s*INPUT:\s*\n"
)
_TS = re.compile(r"^\[(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.\d+)?Z\]", re.M)
_OURS = "agent-spec-"
FREE_TEXT = ("prompt", "text", "summary", "task", "tool_output", "description", "error_message")
_HOME = re.compile(r"(/home/|/Users/|[A-Za-z]:\\\\Users\\\\)[^/\\\"]+")  # on the JSON text: \ is \\
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def log_files(user_dir: str | None = None) -> list:
    """Every Cursor hook log on this machine, oldest first."""
    dirs = [user_dir] if user_dir else cursor_sessions.user_dir_candidates()
    out = []
    for d in dirs:
        logs = os.path.join(os.path.dirname(d.rstrip("/\\")), "logs")
        out.extend(glob.glob(os.path.join(logs, "*", "window*", "output_*", "cursor.hooks.*.log")))
    return sorted(set(out), key=lambda p: (os.path.getmtime(p), p))


def parse_log(text: str) -> list:
    """Hook invocations in one log: step, command, ms, exit code, input, stderr, epoch."""
    stamps = [(m.start(), m.group(1)) for m in _TS.finditer(text)]
    out, dec = [], json.JSONDecoder()
    for m in _BLOCK.finditer(text):
        try:
            payload, end = dec.raw_decode(text, m.end())
        except ValueError:
            continue
        if not isinstance(payload, dict):
            continue
        tail = text[end:end + 4000]
        stderr = ""
        if "STDERR:" in tail:
            stderr = tail.split("STDERR:", 1)[1].split("\n═", 1)[0].strip()
        ts = None
        for pos, stamp in stamps:
            if pos > m.start():
                break
            ts = stamp
        out.append({
            "step": m.group("step"),
            "command": m.group("cmd").strip(),
            "ms": int(m.group("ms")),
            "exit_code": -1 if m.group("code") == "N/A" else int(m.group("code")),  # N/A: never ran
            "input": payload,
            "stderr": stderr,
            "epoch": calendar.timegm(time.strptime(ts, "%Y-%m-%dT%H:%M:%S")) if ts else None,
        })
    return out


def _belongs(payload: dict, project: str) -> bool:
    proj = project.replace("\\", "/").rstrip("/")
    for root in payload.get("workspace_roots") or []:
        r = str(root).replace("\\", "/").rstrip("/")
        if r == proj or r.endswith(proj):
            return True
    return False


def harvest(project: str, files: list | None = None) -> list:
    """This project's invocations of agent-spec hooks across every log, oldest first."""
    out = []
    for path in log_files() if files is None else files:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        out.extend(e for e in parse_log(text) if _OURS in e["command"] and _belongs(e["input"], project))
    out.sort(key=lambda e: e["epoch"] or 0)
    return out


def diagnose(entries: list) -> dict:
    """Pass/fail counts, distinct failure reasons, and a fix when the cause is known."""
    # Cursor can log exit code 0 for a hook it never started; the stderr says so.
    is_failed = lambda e: e["exit_code"] != 0 or e["stderr"].startswith("execution error")  # noqa: E731
    failed = [e for e in entries if is_failed(e)]
    last_ok = max((e["epoch"] or 0 for e in entries if not is_failed(e)), default=0)
    ok_by_event: dict = {}
    for e in entries:
        if not is_failed(e):
            ok_by_event[e["step"]] = max(ok_by_event.get(e["step"], 0), e["epoch"] or 0)
    # A failure is current until the same event succeeds later. An event that never succeeded
    # falls back to any later success: one working hook proves the window can start hooks.
    current = [e for e in failed if (e["epoch"] or 0) > ok_by_event.get(e["step"], last_ok)]
    reasons: dict = {}
    for e in failed:
        line = (e["stderr"].splitlines() or ["(no stderr)"])[-1][:200]
        reasons[line] = reasons.get(line, 0) + 1
    fix = ""
    teardown = "MainThreadShellExec not initialized"  # Cursor-side, not a window problem
    roots = [r for e in current if teardown not in e["stderr"]
             for r in (e["input"].get("workspace_roots") or [])]
    unc = next((r for r in roots if re.match(r"^/[^/]+/home/", str(r))), "")
    if any("spawn powershell ENOENT" in e["stderr"] for e in current) or unc:
        distro = unc.split("/")[1] if unc else "<distro>"
        path = "/" + unc.split("/", 2)[2] if unc else "<path>"
        fix = ("Cursor opened this folder over \\\\wsl.localhost, so it runs hooks on Windows "
               "where they cannot start. Reopen it inside WSL: "
               "cursor --remote wsl+%s %s" % (distro, path))
    elif any(teardown in e["stderr"] for e in current):
        fix = ("Cursor closes its shell before sessionEnd hooks run on window_close (seen in "
               "3.30.8), so they cannot start. Nothing to fix here: the stop hook writes the same "
               "receipt after every turn.")
    events = sorted({e["input"].get("hook_event_name") or e["step"] for e in entries})
    return {"invocations": len(entries), "failed": len(failed), "failing_now": len(current),
            "failing_events": sorted({e["step"] for e in current}),
            "action_needed": any(teardown not in e["stderr"] for e in current),
            "reasons": reasons, "fix": fix,
            "events": events,
            "cursor_version": next((e["input"].get("cursor_version") for e in reversed(entries)
                                    if e["input"].get("cursor_version")), "")}


# Why a registered event has not fired yet; anything else is answered by running the probe.
_PROBE = "run /agent-spec-hook-probe in the Cursor IDE"
COVERAGE_HINTS = {
    "preCompact": "fires only when Cursor compacts a long chat",
    "subagentStart": "needs an IDE chat that delegates: " + _PROBE,
    "subagentStop": "needs an IDE chat that delegates: " + _PROBE,
}


def registered_events(project: str) -> list:
    try:
        with open(os.path.join(project, ".cursor", "hooks.json"), encoding="utf-8") as fh:
            return sorted((json.load(fh).get("hooks") or {}).keys())
    except (OSError, ValueError, AttributeError):
        return []


def coverage(entries: list, project: str) -> dict:
    """Registered hook events versus events Cursor actually invoked for this project."""
    registered = registered_events(project)
    seen = {e["input"].get("hook_event_name") or e["step"] for e in entries}
    missing = [ev for ev in registered if ev not in seen]
    return {"registered": len(registered), "fired": len(registered) - len(missing),
            "missing": missing, "hints": {ev: COVERAGE_HINTS.get(ev, _PROBE) for ev in missing}}


def latest_by_event(entries: list) -> dict:
    out = {}
    for e in entries:
        out[e["input"].get("hook_event_name") or e["step"]] = e["input"]
    return out


def _mask_paths(value, project: str):
    """Any string naming the project, in `/`, `\\` or `\\\\wsl.localhost` form -> /workspace/project."""
    if isinstance(value, dict):
        return {k: _mask_paths(v, project) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_paths(v, project) for v in value]
    if isinstance(value, str) and project:
        flat = value.replace("\\", "/")
        at = flat.find(project)
        if at >= 0:
            return "/workspace/project" + flat[at + len(project):]
    return value


def scrub(payload: dict, redact, project: str = "", fixture: bool = False) -> dict:
    """Redact free text. For a committed fixture also mask the email, local paths and ids."""
    safe = dict(payload)
    for key in FREE_TEXT:
        if isinstance(safe.get(key), str):
            safe[key] = redact(safe[key])[:400]
    if fixture:
        real_ids = {str(safe[k]): fake for k, fake in (("conversation_id", "conv-recorded-1"),
                    ("session_id", "conv-recorded-1"), ("generation_id", "gen-recorded-1")) if safe.get(k)}
        safe = _mask_paths(safe, project.replace("\\", "/").rstrip("/"))
        blob = json.dumps(safe)
        for real, fake in real_ids.items():  # ids also appear inside paths
            blob = blob.replace(real, fake)
        blob = _HOME.sub(r"\1developer", blob)
        safe = json.loads(blob)
        safe = json.loads(_EMAIL.sub("developer@example.com", json.dumps(safe)))
        for key, fake in (("conversation_id", "conv-recorded-1"), ("session_id", "conv-recorded-1"),
                          ("generation_id", "gen-recorded-1")):
            if safe.get(key):
                safe[key] = fake
    return safe


def write_payloads(entries: list, out_dir: str, redact, project: str = "", fixture: bool = False) -> list:
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for event, payload in sorted(latest_by_event(entries).items()):
        name = re.sub(r"[^A-Za-z]", "", event) or "unknown"
        path = os.path.join(out_dir, name + ".json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(scrub(payload, redact, project, fixture), fh, indent=2, sort_keys=True)
            fh.write("\n")
        written.append(path)
    return written


def load_hook(project: str, package_root: str):
    """The cursor-event hook module: the project's installed copy, else the package's."""
    for path in (os.path.join(project, ".cursor", "hooks", "agent-spec-cursor-event.py"),
                 os.path.join(package_root, "hooks", "cursor-event.py")):
        if os.path.isfile(path):
            spec = importlib.util.spec_from_file_location("agent_spec_cursor_event", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


# Differ between the live hook's row and a replay of it: a random id, ms vs s timestamps, the
# source tag, and the Read extent, which stats the file at write time (relative to the cwd).
_VOLATILE = ("id", "ts", "source", "file_bytes", "file_chars", "ranged")


def _row_key(row: dict) -> str:
    """Identity of one recorded event, equal for the live hook's row and its backfilled replay.

    The hook stamps `ts` with milliseconds; Cursor's log has whole seconds, so `ts` is compared
    at second resolution and every other field (tool_use_id, target, text, ...) must match.
    """
    body = {k: v for k, v in row.items() if k not in _VOLATILE}
    return str(row.get("ts") or "")[:19] + json.dumps(body, sort_keys=True, default=str)


def backfill(entries: list, events_path: str, hook) -> int:
    """Append rows the hook would have written; skip any already present. Returns rows added."""
    seen = set()
    if os.path.isfile(events_path):
        with open(events_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    seen.add(_row_key(r))
    rows, done = [], set()
    for e in entries:
        # One step runs several of our hooks with the same input; distinct calls in the same
        # second differ in their input (tool_use_id, tool_input), so the whole input is the key.
        key_in = (e["step"], e["epoch"], json.dumps(e["input"], sort_keys=True, default=str))
        if key_in in done:
            continue
        done.add(key_in)
        if e["step"] not in getattr(hook, "EVENTS", (e["step"],)):
            continue  # e.g. sessionStart: the event spine is not registered for it
        row = hook.handle_event(json.dumps(e["input"]), e["step"], now=e["epoch"])
        if not row:
            continue
        row["source"] = "cursor-hook-log"
        key = _row_key(row)
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    if rows:
        os.makedirs(os.path.dirname(events_path), exist_ok=True)
        with open(events_path, "a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    return len(rows)
