"""Measured outcome signals for one request (DEC-17, PI-006).

Allowed-code reason (DEC-15): *exact* — every value is a count or a fact read from spans.
There is deliberately no score here: the `agent-spec-session-review` skill (rubric 2.1.0)
reads these signals as evidence and writes the AI-judged quality dimensions. Each signal carries
the span ids it was computed from so a reviewer, and the dashboard, can point at them.
"""
from __future__ import annotations

import re

# A shell command that runs tests, a build, a type checker or a linter. Recognising the command
# is exact; whether it was the *right* verification is for the reviewer to judge.
VERIFY = re.compile(
    r"\b(pytest|unittest|tox|nox|vitest|jest|mocha|playwright|cypress|go (?:test|vet|build)|cargo (?:test|check|build|clippy)|"
    r"mvn|gradle|npm (?:run )?(?:test|build|lint|typecheck)|pnpm (?:run )?(?:test|build|lint)|yarn (?:test|build|lint)|"
    r"tsc|eslint|ruff|mypy|pyright|flake8|pylint|make (?:test|check|build)|selftest|ctest|dotnet (?:test|build))\b", re.I)
MISSING = re.compile(r"(no such file|not found|does not exist|ENOENT|cannot find|could not find|unknown file)", re.I)
FAILED = ("error", "failed", "blocked")


KEY_PREFIX = re.compile(r"^\w+=")


def _target(s: dict) -> str:
    """`file_path=/p/a.py` (tool spans) and `/p/a.py` (afterFileEdit) name the same file."""
    a = s.get("attributes") or {}
    return KEY_PREFIX.sub("", str(a.get("file_path") or a.get("target") or ""), count=1)


def _edited(spans: list) -> list:
    """Successful edits. Cursor reports one edit twice (the Write/StrReplace tool and
    afterFileEdit); when afterFileEdit spans exist they alone are counted."""
    ok = [s for s in spans if s["kind"] == "edit" and s.get("status") not in FAILED]
    file_events = [s for s in ok if (s.get("attributes") or {}).get("file_path")]
    return file_events or ok


def for_trace(trace: dict, spans: list, session_traces=None, session_spans=None) -> dict:
    """Signals for `trace` from its `spans`. `session_traces`/`session_spans` (the same
    session's other requests) enable the rework signal; without them it is reported as None."""
    spans = sorted(spans, key=lambda s: (s.get("start") or "", s.get("seq") or 0))
    tools = [s for s in spans if s["kind"] in ("tool", "edit")]
    failed = [s for s in tools if s.get("status") in FAILED]
    edits = _edited(spans)
    files = {}
    for s in edits:
        files.setdefault(_target(s), []).append(s["span_id"])
    files.pop("", None)

    # Same tool + same target failing more than once: a retry that did not change anything.
    groups = {}
    for s in failed:
        groups.setdefault((s.get("name"), _target(s)), []).append(s["span_id"])
    repeated = [{"tool": k[0], "target": k[1], "span_ids": v} for k, v in groups.items() if len(v) > 1]

    missing = [s["span_id"] for s in failed
               if MISSING.search(str((s.get("attributes") or {}).get("error_message") or ""))]

    last_edit = edits[-1]["start"] if edits else None
    verify = [s for s in spans if s["kind"] == "tool" and (s.get("name") or "").lower() in ("shell", "terminal", "bash", "run_terminal_cmd")
              and VERIFY.search(_target(s))]
    verified_after = [s for s in verify if last_edit and (s.get("start") or "") >= last_edit]

    tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    has_tokens = False
    for s in spans:
        a = s.get("attributes") or {}
        if s["kind"] == "response":
            for key, field in (("input", "input_tokens"), ("output", "output_tokens"),
                               ("cache_read", "cache_read_tokens"), ("cache_write", "cache_write_tokens")):
                if isinstance(a.get(field), int):
                    tokens[key] += a[field]
                    has_tokens = True

    rework = None
    if session_traces is not None and session_spans is not None and files:
        later = [t for t in session_traces if t["session_id"] == trace["session_id"]
                 and (t.get("start") or "") > (trace.get("start") or "") and t["trace_id"] != trace["trace_id"]]
        later_ids = {t["trace_id"] for t in later}
        again = {}
        for s in _edited([s for s in session_spans if s["trace_id"] in later_ids]):
            if _target(s) in files:
                again.setdefault(_target(s), []).append({"trace_id": s["trace_id"], "span_id": s["span_id"]})
        rework = {"files": sorted(again), "later_edits": again}

    measured = "measured" if trace.get("source") in ("hook", "run") else "estimated"
    return {
        "trace_id": trace["trace_id"],
        "provenance": measured,
        "tool_calls": len(tools),
        "tool_failures": {"count": len(failed), "span_ids": [s["span_id"] for s in failed]},
        "repeated_failures": repeated,
        "missing_path_errors": {"count": len(missing), "span_ids": missing},
        "files_edited": {"count": len(files), "files": sorted(files), "edit_spans": len(edits),
                         "churn": sorted(f for f, ids in files.items() if len(ids) >= 3)},
        "verification": {"ran_after_last_edit": bool(verified_after) if edits else None,
                         "commands": [{"span_id": s["span_id"], "command": _target(s)[:200], "status": s.get("status")}
                                      for s in verify][:10]},
        "guard_blocks": sum(1 for s in spans if s["kind"] == "guard"),
        "compactions": sum(1 for s in spans if s["kind"] == "compact"),
        "subagents": {"count": sum(1 for s in spans if s["kind"] == "subagent"),
                      "failed": [s["span_id"] for s in spans if s["kind"] == "subagent" and s.get("status") in FAILED]},
        "responded": any(s["kind"] == "response" for s in spans),
        "tokens": tokens if has_tokens else None,
        "rework_later": rework,
    }


def for_request(project: str, conn, trace_id: str):
    from . import traces as tr
    all_t, all_s = tr.all_traces(project, conn)
    trace = next((t for t in all_t if t["trace_id"] == trace_id), None)
    if trace is None:
        return None
    session = [t for t in all_t if t["session_id"] == trace["session_id"]]
    ids = {t["trace_id"] for t in session}
    sspans = [s for s in all_s if s["trace_id"] in ids]
    return for_trace(trace, [s for s in sspans if s["trace_id"] == trace_id], session, sspans)
