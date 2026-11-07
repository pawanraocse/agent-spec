#!/usr/bin/env python3
"""agent-spec-receipt.py — one JSON receipt per Cursor session (T-050).

Answers "what did this session cost, and did the harness do its job?" from data already
on disk: the session transcript, the pipeline STATE.json and the digest the session was
given. Nothing is uploaded and no transcript text is stored — only counts, sizes and the
paths of whole-file reads.

  agent-spec-receipt.py                       # latest session of this workspace
  agent-spec-receipt.py --session <id>        # a specific conversation id
  agent-spec-receipt.py --transcript <path>   # explicit transcript (Cursor hook payload)
  agent-spec-receipt.py --stdout              # print, do not write
  agent-spec-receipt.py --daily               # also upsert a row in metrics/daily.jsonl

Writes .agent-spec/metrics/receipts/<session_id>.json. Stdlib only. Fail-open: every
public function returns None or an empty value rather than raising, so a hook that calls
it can never break a session.
"""
import argparse
import datetime
import importlib.util
import json
import os
import re
import subprocess
import sys

SCHEMA = 1
READ_CAP = 20000
READ_TOOLS = ("Read", "read_file", "ReadFile")
RANGE_KEYS = ("limit", "offset", "start_line", "end_line", "line_start", "line_end", "lines",
              "range", "view_range", "startline", "endline", "line_range")
GRAPH_RE = re.compile(
    r"graphify-cli(?:\.py)?\s+(?:query|search|stats|cycles|module|flow|services|endpoints|layers|context)\b")
DIGEST_RE = re.compile(r"<agent-spec-digest\b[^>]*>(.*?)</agent-spec-digest>", re.S)
HERE = os.path.dirname(os.path.abspath(__file__))


def load_tokens():
    """The sibling agent-spec-tokens.py as a module, or None."""
    path = os.path.join(HERE, "agent-spec-tokens.py")
    try:
        spec = importlib.util.spec_from_file_location("agent_spec_tokens", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def metrics_dir(project):
    return os.path.join(project, ".agent-spec", "metrics")


def is_ranged(args):
    if not isinstance(args, dict):
        return False
    for k, v in args.items():
        if str(k).lower() in RANGE_KEYS and v not in (None, "", False):
            return True
        if isinstance(v, dict) and is_ranged(v):
            return True
    return False


def scan_transcript(path, project):
    """One pass: graph-query count, whole-file reads, and the digest the session received."""
    graph = 0
    whole = []
    digest = None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if digest is None and "<agent-spec-digest" in line:
                    m = DIGEST_RE.search(_flatten(entry))
                    if m:
                        digest = m.group(1)
                content = (entry.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    name = block.get("name", "")
                    args = block.get("input") or {}
                    if not isinstance(args, dict):
                        continue
                    if GRAPH_RE.search(str(args.get("command", ""))):
                        graph += 1
                    if name in READ_TOOLS and not is_ranged(args):
                        target = args.get("path") or args.get("file_path") or args.get("target_file") or ""
                        full = target if os.path.isabs(target) else os.path.join(project, target)
                        try:
                            size = os.path.getsize(full)
                        except OSError:
                            continue
                        if size >= READ_CAP:
                            whole.append({"path": os.path.relpath(full, project)
                                          if full.startswith(project + os.sep) else full,
                                          "bytes": size})
    except OSError:
        pass
    return graph, whole, digest


def _flatten(obj):
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return "\n".join(_flatten(v) for v in obj.values())
    if isinstance(obj, list):
        return "\n".join(_flatten(v) for v in obj)
    return ""


def facts_in_digest(digest):
    """Number of remembered-fact lines the digest carried; None when no digest was seen."""
    if digest is None:
        return None
    lines = digest.splitlines()
    if "remembered:" not in lines:
        return 0
    count = 0
    for line in lines[lines.index("remembered:") + 1:]:
        if line.startswith("Do NOT open"):
            break
        if line.strip():
            count += 1
    return count


def gates(project):
    script = os.path.join(project, ".agent-spec", "bin", "agent-spec-gate.py")
    if not os.path.isfile(script):
        script = os.path.join(HERE, "agent-spec-gate.py")
    try:
        res = subprocess.run([sys.executable, script, "status", "--json"], cwd=project,
                             capture_output=True, text=True, timeout=3)
        data = json.loads(res.stdout)
    except Exception:
        return None
    return {"gate": data.get("gate"), "gate_name": data.get("gate_name"),
            "feature": data.get("feature"), "next_command": data.get("next_command"),
            "artifacts_present": sum(1 for a in data.get("artifacts") or []
                                     if a.get("status") != "MISSING")}


def find_transcript(tokens, project, session=None, explicit=None):
    if explicit and os.path.isfile(explicit):
        return explicit
    if tokens is None:
        return None
    found = tokens.cursor_transcripts(project)
    if session and session != "latest":
        for p in found:
            if os.path.basename(p) == session + ".jsonl":
                return p
        return None
    return found[0] if found else None


def build_receipt(project, session=None, transcript=None):
    """The receipt dict, or None when no transcript can be found."""
    tokens = load_tokens()
    path = find_transcript(tokens, project, session, transcript)
    if not path or tokens is None:
        return None
    try:
        usage = tokens.read_usage(path)
    except Exception:
        return None
    sid = os.path.basename(path)[:-len(".jsonl")]
    graph, whole, digest = scan_transcript(path, project)
    totals = usage["totals"]
    calls = dict(usage["tool_calls"])
    return {
        "schema": SCHEMA,
        "session_id": sid,
        "ts": datetime.datetime.now().replace(microsecond=0).isoformat(),
        "project": os.path.basename(os.path.abspath(project)),
        "turns": usage["turns"],
        "tokens": {
            "input": totals.get("input_tokens", 0),
            "output": totals.get("output_tokens", 0),
            "cache_read": totals.get("cache_read_input_tokens", 0),
            "cache_write": totals.get("cache_creation_input_tokens", 0),
            "estimated": bool(usage["estimated"]),
        },
        "tool_calls": calls,
        "tool_calls_total": sum(calls.values()),
        "graph_queries": graph,
        "whole_file_reads": {"count": len(whole), "files": whole[:10]},
        "gates": gates(project),
        "facts_injected": facts_in_digest(digest),
    }


def write_receipt(project, receipt):
    """Write receipts/<session_id>.json atomically; returns the path or None."""
    try:
        out_dir = os.path.join(metrics_dir(project), "receipts")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, receipt["session_id"] + ".json")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(receipt, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
        return path
    except OSError:
        return None


def daily_row(receipt):
    t = receipt["tokens"]
    return {
        "date": receipt["ts"][:10],
        "session_id": receipt["session_id"],
        "turns": receipt["turns"],
        "tokens_total": t["input"] + t["output"] + t["cache_read"] + t["cache_write"],
        "tokens_output": t["output"],
        "estimated": t["estimated"],
        "tool_calls": receipt["tool_calls_total"],
        "graph_queries": receipt["graph_queries"],
        "whole_file_reads": receipt["whole_file_reads"]["count"],
        "gate": (receipt.get("gates") or {}).get("gate"),
    }


def upsert_daily(project, receipt):
    """Append the session's row to metrics/daily.jsonl, replacing an earlier row for the
    same session (the stop hook fires every turn, so the row is rewritten, not duplicated)."""
    try:
        os.makedirs(metrics_dir(project), exist_ok=True)
        path = os.path.join(metrics_dir(project), "daily.jsonl")
        row = daily_row(receipt)
        kept = []
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        if json.loads(line).get("session_id") == row["session_id"]:
                            continue
                    except ValueError:
                        continue
                    kept.append(line.rstrip("\n"))
        except OSError:
            pass
        kept.append(json.dumps(row))
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(kept) + "\n")
        os.replace(tmp, path)
        return path
    except OSError:
        return None


QUERY_RE = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.S)
CORRECTION_RE = re.compile(r"^(no|nope|wrong|not|don'?t|stop|actually|instead|undo|revert)\b", re.I)


def scan_prompts(path):
    """(task, corrections): the first `<user_query>` text and the later user turns that open with a
    correction word. Counts a heuristic only; the learn skill decides what a correction means."""
    task, corrections = None, 0
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if entry.get("role") != "user":
                    continue
                content = (entry.get("message") or {}).get("content")
                text = content if isinstance(content, str) else "\n".join(
                    b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")
                m = QUERY_RE.search(text)
                if task is None:
                    if m:
                        task = m.group(1)
                    continue
                body = (m.group(1) if m else text).strip()
                if CORRECTION_RE.match(body):
                    corrections += 1
    except OSError:
        pass
    return task, corrections


def build_experience(project, receipt, session=None, transcript=None):
    """The experience-store line (L-001) for a receipt. The task text is redacted and capped at 200
    characters; without the redactor it is dropped rather than stored raw."""
    try:  # loaded by path, like load_tokens: the core never imports the platform package (DEC-03)
        spec = importlib.util.spec_from_file_location(
            "aspec_redact", os.path.join(HERE, "aspec_platform", "redact.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        redact = mod.redact
    except Exception:
        redact = None
    path = find_transcript(load_tokens(), project, session, transcript)
    task, corrections = scan_prompts(path) if path else (None, 0)
    t = receipt["tokens"]
    return {"schema": 1, "exp_id": "session:" + receipt["session_id"], "kind": "session", "ts": receipt["ts"],
            "task": redact(" ".join(task.split()))[:200] if (task and redact) else "",
            "status": "success", "tokens": {"input": t["input"], "output": t["output"], "cache_read": t["cache_read"]},
            "gates": (receipt.get("gates") or {}).get("gate"), "retries": 0, "corrections": corrections,
            "facts_injected": receipt.get("facts_injected"), "run_id": None}


def upsert_experience(project, line):
    """Replace this session's line in `.agent-spec/experience.jsonl` (the stop hook fires every turn)."""
    try:
        path = os.path.join(project, ".agent-spec", "experience.jsonl")
        kept = []
        try:
            with open(path, encoding="utf-8") as fh:
                for raw in fh:
                    try:
                        if json.loads(raw).get("exp_id") == line["exp_id"]:
                            continue
                    except ValueError:
                        pass
                    if raw.strip():
                        kept.append(raw.rstrip("\n"))
        except OSError:
            pass
        kept.append(json.dumps(line, sort_keys=True))
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(kept) + "\n")
        os.replace(tmp, path)
        return path
    except OSError:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a per-session receipt")
    ap.add_argument("--session", help="conversation id, or 'latest' (default)")
    ap.add_argument("--transcript", help="explicit transcript path")
    ap.add_argument("--project", default=os.getcwd(), help="workspace root (default: cwd)")
    ap.add_argument("--stdout", action="store_true", help="print instead of writing")
    ap.add_argument("--daily", action="store_true", help="also upsert metrics/daily.jsonl")
    ap.add_argument("--experience", action="store_true", help="also upsert this session's experience.jsonl line")
    args = ap.parse_args(argv)

    receipt = build_receipt(args.project, args.session, args.transcript)
    if receipt is None:
        sys.stderr.write("no Cursor transcript found for %s\n" % args.project)
        return 1
    if args.stdout:
        print(json.dumps(receipt, indent=2))
        return 0
    path = write_receipt(args.project, receipt)
    if args.daily:
        upsert_daily(args.project, receipt)
    if args.experience:
        upsert_experience(args.project, build_experience(args.project, receipt, args.session, args.transcript))
    print(path or "could not write receipt")
    return 0 if path else 1


if __name__ == "__main__":
    sys.exit(main())
