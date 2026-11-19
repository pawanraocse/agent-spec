"""Proposals inbox (PI-009, absorbs P3-017): everything the learning loop suggests, waiting for
a person. Nothing here is applied without a click.

Kinds:
  fact        .agent-spec/memory/proposed/<id>.json (agent-spec-memory.py propose)
              approve -> agent-spec-memory.py add (the existing CLI), reject -> proposed/rejected/
  skill       .agent-spec/skill-proposals/<slug>.md (agent-spec-learn propose)
              approve -> validated with agent-spec-run.py, copied to skills/agent-spec-wf-<slug>/
              (the package clone) or .cursor/skills/agent-spec-wf-<slug>/ (any other project)
  experience  experiences reused 3+ times (experience-reuse.jsonl)
              promote / deprecate -> one row in experience-overrides.jsonl; experience.jsonl,
              which the ingestor and hooks own, is never edited

Every decision appends {ts, kind, id, decision, by, result} to metrics/proposals.jsonl (P3-012).
Ids from the client are only ever matched against the listing, never joined into a path.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter

from . import common

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
REUSE_MIN = 3


def _spec(project):
    return common.agent_spec_dir(project)


def _bin(project, name):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for path in (os.path.join(_spec(project), "bin", name), os.path.join(here, name)):
        if os.path.isfile(path):
            return path
    return None


def _read_jsonl(path):
    rows = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        pass
    return rows


def _facts(project):
    folder = os.path.join(_spec(project), "memory", "proposed")
    out = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                row = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(row, dict) and row.get("text"):
            out.append({"kind": "fact", "id": name[:-5], "title": "[%s] %s" % (row.get("type"), row.get("subject")),
                        "body": row.get("text"), "evidence": row.get("evidence") or row.get("source"),
                        "proposed_at": row.get("proposed_at"), "_row": row,
                        "_path": os.path.join(folder, name)})
    return out


def _skills(project):
    folder = os.path.join(_spec(project), "skill-proposals")
    out = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        slug = name[:-3] if name.endswith(".md") else ""
        if not SLUG.match(slug):
            continue
        path = os.path.join(folder, name)
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read(20000)
        except OSError:
            continue
        target = _skill_target(project, slug)
        current = ""
        if os.path.isfile(target):
            with open(target, encoding="utf-8", errors="replace") as fh:
                current = fh.read(20000)
        out.append({"kind": "skill", "id": slug, "title": "agent-spec-wf-%s" % slug, "body": text,
                    "diff_against": current or None, "target": os.path.relpath(target, project),
                    "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(path))),
                    "_path": path})
    return out


def _skill_target(project, slug):
    root = os.path.join(project, "skills") if os.path.isdir(os.path.join(project, "skills")) \
        else os.path.join(project, ".cursor", "skills")
    return os.path.join(root, "agent-spec-wf-%s" % slug, "SKILL.md")


def _overrides(project):
    out = {}
    for row in _read_jsonl(os.path.join(_spec(project), "experience-overrides.jsonl")):
        if row.get("exp_id"):
            out[row["exp_id"]] = row.get("status")
    return out


def _experiences(project):
    reuse = Counter(r.get("exp_id") for r in _read_jsonl(os.path.join(_spec(project), "experience-reuse.jsonl"))
                    if r.get("exp_id"))
    if not reuse:
        return []
    decided = _overrides(project)
    by_id = {r.get("exp_id"): r for r in _read_jsonl(os.path.join(_spec(project), "experience.jsonl"))}
    out = []
    for exp_id, n in reuse.most_common(50):
        if n < REUSE_MIN or exp_id in decided or exp_id not in by_id:
            continue
        e = by_id[exp_id]
        out.append({"kind": "experience", "id": exp_id, "title": (e.get("task") or exp_id)[:120],
                    "body": e.get("task"), "evidence": "reused %d times · %s · %s retries" % (
                        n, e.get("status"), e.get("retries")), "reuses": n})
    return out


def overview(project: str) -> dict:
    items = _facts(project) + _skills(project) + _experiences(project)
    public = [{k: v for k, v in i.items() if not k.startswith("_")} for i in items]
    log = _read_jsonl(os.path.join(_spec(project), "metrics", "proposals.jsonl"))
    return {"pending": public, "counts": dict(Counter(i["kind"] for i in public)),
            "decided": list(reversed(log[-30:])), "log": ".agent-spec/metrics/proposals.jsonl",
            "provenance": "measured"}


def audit(project, row):
    """One row in metrics/proposals.jsonl: every dashboard decision on what the agent learns (P3-012)."""
    metrics = os.path.join(_spec(project), "metrics")
    os.makedirs(metrics, exist_ok=True)
    row = dict({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "by": "dashboard"}, **row)
    with open(os.path.join(metrics, "proposals.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")


def _reject(path):
    folder = os.path.join(os.path.dirname(path), "rejected")
    os.makedirs(folder, exist_ok=True)
    os.replace(path, os.path.join(folder, os.path.basename(path)))


def decide(project: str, kind: str, item_id: str, decision: str) -> dict:
    allowed = {"fact": ("approve", "reject"), "skill": ("approve", "reject"),
               "experience": ("promote", "deprecate")}
    if kind not in allowed or decision not in allowed[kind]:
        raise ValueError("decision for %s must be one of %s" % (kind, ", ".join(allowed.get(kind, ()))))
    source = {"fact": _facts, "skill": _skills, "experience": _experiences}[kind](project)
    item = next((i for i in source if i["id"] == item_id), None)
    if item is None:
        raise ValueError("no pending %s %r" % (kind, item_id))
    result = ""
    if kind == "fact":
        if decision == "approve":
            row = item["_row"]
            cli = _bin(project, "agent-spec-memory.py")
            argv = [sys.executable, cli, "add", "--type", str(row.get("type")), "--subject", str(row.get("subject"))]
            for key in ("source", "addresses"):
                if row.get(key):
                    argv += ["--" + key, str(row[key])]
            argv += ["--provenance", "proposal %s" % item_id, str(row.get("text"))]
            res = subprocess.run(argv, cwd=project, capture_output=True, text=True, timeout=30)
            if res.returncode != 0:
                raise ValueError("memory add refused it: %s" % (res.stderr or res.stdout).strip()[:300])
            result = res.stdout.strip().splitlines()[0] if res.stdout.strip() else "remembered"
            os.remove(item["_path"])
        else:
            _reject(item["_path"])
            result = "moved to memory/proposed/rejected/"
    elif kind == "skill":
        if decision == "approve":
            runner = _bin(project, "agent-spec-run.py")
            if runner:
                res = subprocess.run([sys.executable, runner, "validate", item["_path"]], cwd=project,
                                     capture_output=True, text=True, timeout=30)
                if res.returncode != 0:
                    raise ValueError("workflow does not validate: %s" % (res.stderr or res.stdout).strip()[-300:])
            target = _skill_target(project, item_id)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(item["_path"], target)
            os.remove(item["_path"])
            result = "published to %s" % os.path.relpath(target, project)
        else:
            _reject(item["_path"])
            result = "moved to skill-proposals/rejected/"
    else:
        with open(os.path.join(_spec(project), "experience-overrides.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "exp_id": item_id,
                                 "status": "promoted" if decision == "promote" else "deprecated"}) + "\n")
        result = decision + "d"
    audit(project, {"kind": kind, "id": item_id, "decision": decision, "result": result,
                     "title": item.get("title")})
    return {"ok": True, "kind": kind, "id": item_id, "decision": decision, "result": result}
