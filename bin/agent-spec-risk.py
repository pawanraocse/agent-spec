#!/usr/bin/env python3
"""Blast-radius risk classifier (P4-011) and one-use approvals (H-030).

  agent-spec-risk.py classify --tool Write --target src/api/client.ts   tier + reasons (JSON)
  agent-spec-risk.py pending                                             blocked actions awaiting a decision
  agent-spec-risk.py approve <key> | deny <key>                          decide one (the dashboard does the same)

Tiers, from the dependency graph and the action itself:
  0  read, search, list, run tests or a build
  1  edit a file few others depend on; an ordinary shell command
  2  edit a file with >= tier2_fan_in direct dependents, or in a core layer
  3  edit a file with >= tier3_fan_in dependents, one another repo calls (mesh), a migration,
     or a destructive shell command (rm -rf, force push, reset --hard, DROP TABLE)

Thresholds live in .agent-spec/risk.json; `enforce` is "block" (tier 3 waits for approval,
the default), "warn" (tier 3 is only recorded) or "off". The preToolUse hook imports this
file; any error here allows the action and records the error (fail-open).

Allowed-code reason (DEC-15): *exact* — counts from the graph and fixed patterns; no model.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import sys
import time

DEFAULTS = {
    "enforce": "block",
    "tier2_fan_in": 10,
    "tier3_fan_in": 20,
    "core_layers": ["domain", "core"],
    "core_globs": [],
    "migration_globs": ["*migrations/*", "*migrate/*", "*.migration.*", "*/alembic/versions/*", "*flyway*/*.sql"],
    "approval_ttl_s": 1800,
}
READ_TOOLS = {"read", "read_file", "grep", "glob", "ls", "list_dir", "codebase_search", "grep_search",
              "file_search", "search", "webfetch", "websearch", "fetch", "semsearch"}
EDIT_TOOLS = {"write", "edit", "multiedit", "strreplace", "str_replace", "search_replace", "edit_file",
              "delete", "delete_file", "notebookedit", "edit_notebook", "applypatch", "apply_patch"}
SHELL_TOOLS = {"shell", "bash", "run_terminal_cmd", "terminal", "run_command"}
VERIFY = re.compile(r"^\s*(?:\S+=\S+\s+)*(?:python3? -m )?(pytest|unittest|vitest|jest|tsc|eslint|ruff|mypy|"
                    r"go test|cargo test|npm (?:run )?(?:test|build|lint)|make (?:test|check)|git (?:status|diff|log|show))\b")
DESTRUCTIVE = re.compile(
    r"(\brm\s+-[a-zA-Z]*[rf][a-zA-Z]*\s|\bgit\s+push\b[^|;&]*(--force\b|-f\b)|\bgit\s+reset\s+--hard\b|"
    r"\bgit\s+clean\s+-[a-zA-Z]*f|\bdrop\s+(table|database|schema)\b|\btruncate\s+table\b|"
    r"\bkubectl\s+delete\b|\bterraform\s+(destroy|apply)\b|\bmkfs\b|\bdd\s+if=)", re.I)


# The gate's own state and code. The agent the gate constrains must not change them, and an
# approval cannot unlock them: only a person editing outside the agent can.
PROTECTED = (".agent-spec/risk.json", ".agent-spec/risk/*", ".agent-spec/bin/*", ".agent-spec/bin/*/*",
             ".cursor/hooks/*", ".cursor/hooks.json")
PROTECTED_HINTS = ("agent-spec/risk.json", "agent-spec/risk/", "agent-spec/bin/", ".cursor/hooks")
SHELL_WRITE = re.compile(r"(>>?|\btee\b|\bsed\s+-[a-zA-Z]*i|\bmv\b|\bcp\b|\brm\b|\btruncate\b|\bln\b|"
                         r"\bchmod\b|\bpython3?\b|\bperl\b|\bnode\b|\bruby\b|\bdd\b|\binstall\b)")
REDIRECT = re.compile(r">>?\s*['\"]?([^\s'\";|&<>]+)")
OPERANDS = re.compile(r"\b(?:tee(?:\s+-a)?|sed\s+-[a-zA-Z]*i(?:\s+\S+)?|mv|cp|rm(?:\s+-[a-zA-Z]+)*|truncate(?:\s+-s\s*\S+)?)"
                      r"\s+((?:[^\s;|&<>]+\s*)+)")


# Neither of these writes a protected file, and both are everyday: discarding output
# (`ls .agent-spec/bin/x 2>/dev/null`) and running a harness script with an interpreter
# (`python3 .agent-spec/bin/agent-spec-memory.py handoff`). Both made the protected-path check
# below fire on a read or a run (bench run cef508: a search subagent's `ls ... 2>/dev/null` was
# denied as a change to the gate's code). `python3 -c "open('.agent-spec/risk.json', 'w')"` and
# `> .agent-spec/bin/x` still match: only the interpreter in front of a harness script is dropped.
HARMLESS = re.compile(r"\d*>>?\s*(?:/dev/null\b|&\d)|\b(?:python3?|bash|sh)\s+(?=\.?/?\.agent-spec/bin/)")


def _without_harmless(command):
    return HARMLESS.sub(" ", command)


def is_protected(rel):
    return any(fnmatch.fnmatch(rel, g) for g in PROTECTED)


def shell_paths(command):
    """Files a shell command writes, best effort: redirect targets, and operands of tee, sed -i,
    mv, cp, rm and truncate. Flags and quoted sed scripts are skipped."""
    paths = set(REDIRECT.findall(command))
    for m in OPERANDS.finditer(command):
        for tok in m.group(1).split():
            tok = tok.strip("'\"")
            if tok and not tok.startswith("-") and not tok.startswith("s/") and ("/" in tok or "." in tok):
                paths.add(tok)
    return sorted(p for p in paths if p not in ("/dev/null", "&1", "&2"))


def spec_dir(project):
    return os.path.join(project, ".agent-spec")


def config(project):
    cfg = dict(DEFAULTS)
    try:
        with open(os.path.join(spec_dir(project), "risk.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            cfg.update({k: v for k, v in data.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return cfg


_GRAPH = {}


def _load(path):
    try:
        st = os.stat(path)
    except OSError:
        return None
    hit = _GRAPH.get(path)
    if hit and hit[0] == st.st_mtime_ns:
        return hit[1]
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    _GRAPH[path] = (st.st_mtime_ns, data)
    return data


def _rel(project, target):
    target = re.sub(r"^\w+=", "", str(target or "")).strip()
    if not target:
        return ""
    path = target if os.path.isabs(target) else os.path.join(project, target)
    try:
        rel = os.path.relpath(os.path.realpath(path), os.path.realpath(project))
    except ValueError:  # another drive on Windows
        return target.replace("\\", "/")
    return rel.replace(os.sep, "/")


def graph_facts(project, rel):
    """(direct dependents, layer, cross-repo callers) for one project-relative file."""
    graph = _load(os.path.join(spec_dir(project), "graph", "knowledge-graph.json")) or {}
    fan_in = sum(1 for e in graph.get("edges") or []
                 if e.get("target") == rel and e.get("type") in ("imports", "http", "message"))
    layer = next((n.get("layer") for n in graph.get("nodes") or [] if n.get("id") == rel), None)
    cross = 0
    mesh = _load(os.path.join(spec_dir(project), "graph", "mesh-graph.json"))
    if isinstance(mesh, dict):
        # Mesh node ids are "<repo_id>:<path>". This project's repo_id comes from mesh.json;
        # without it, any member with the same relative path would count as this file.
        manifest = _load(os.path.join(spec_dir(project), "mesh.json")) or {}
        here = os.path.realpath(project)
        own = [r.get("repo_id") for r in manifest.get("repos") or []
               if isinstance(r, dict) and os.path.realpath(r.get("path") or "/nonexistent") == here]
        wanted = {"%s:%s" % (rid, rel) for rid in own} if own else None
        for e in mesh.get("edges") or []:
            t, s = str(e.get("target") or ""), str(e.get("source") or "")
            hit = t in wanted if wanted is not None else t.endswith(":" + rel)
            if hit and s.split(":", 1)[0] != t.split(":", 1)[0]:
                cross += 1
    return fan_in, layer, cross


def _target_of(tool, args):
    if not isinstance(args, dict):
        return ""
    if tool in SHELL_TOOLS:
        return str(args.get("command") or args.get("cmd") or "")
    for k in ("file_path", "path", "target_file", "notebook_path", "filePath", "target"):
        if args.get(k):
            return str(args[k])
    return ""


def classify(project, tool, args):
    """{"tier", "reasons", "tool", "target", ...}; never raises for bad input."""
    name = str(tool or "").strip()
    low = name.lower().replace(" ", "")
    target = _target_of(low, args)
    cfg = config(project)
    out = {"tool": name, "target": target[:500], "tier": 1, "reasons": []}
    if low in READ_TOOLS:
        out.update(tier=0, reasons=["read-only tool"])
        return out
    if low in SHELL_TOOLS:
        lowered = target.lower()
        if "agent-spec-risk" in lowered and re.search(r"\b(approve|deny)\b", lowered):
            out.update(tier=3, protected=True, reasons=["approves or denies a gated action; only a person can"])
            return out
        if any(h in lowered for h in PROTECTED_HINTS) and SHELL_WRITE.search(_without_harmless(target)):
            out.update(tier=3, protected=True, reasons=["changes the risk gate's own config, approvals or code"])
            return out
        if DESTRUCTIVE.search(target):
            out.update(tier=3, reasons=["destructive shell command"])
        elif VERIFY.search(target):
            out.update(tier=0, reasons=["test, build or read-only git command"])
        else:
            out["reasons"].append("shell command")
        # A shell write to a file is an edit of that file: same tiers as the edit tools.
        for path in shell_paths(target)[:20]:
            sub = classify(project, "Write", {"file_path": path})
            if sub.get("protected"):
                return dict(out, tier=3, protected=True, file=sub.get("file"),
                            reasons=["changes the risk gate's own config, approvals or code"])
            if sub["tier"] > out["tier"]:
                out.update(tier=sub["tier"], file=sub.get("file"), fan_in=sub.get("fan_in"),
                           cross_repo_callers=sub.get("cross_repo_callers"),
                           reasons=["shell write to %s" % sub.get("file")] + sub["reasons"][1:])
        return out
    if low not in EDIT_TOOLS:
        out["reasons"].append("unclassified tool")
        return out
    rel = _rel(project, target)
    out["file"] = rel
    if is_protected(rel):
        out.update(tier=3, protected=True, reasons=["changes the risk gate's own config, approvals or code"])
        return out
    fan_in, layer, cross = graph_facts(project, rel)
    out.update(fan_in=fan_in, layer=layer, cross_repo_callers=cross)
    tier, reasons = 1, ["edit"]
    if any(fnmatch.fnmatch(rel, g) for g in cfg["migration_globs"]):
        tier, reasons = 3, reasons + ["database migration"]
    if cross:
        tier, reasons = 3, reasons + ["%d caller(s) in other repos" % cross]
    if fan_in >= cfg["tier3_fan_in"]:
        tier, reasons = 3, reasons + ["%d files depend on it (tier 3 at %d)" % (fan_in, cfg["tier3_fan_in"])]
    elif fan_in >= cfg["tier2_fan_in"]:
        tier, reasons = max(tier, 2), reasons + ["%d files depend on it (tier 2 at %d)" % (fan_in, cfg["tier2_fan_in"])]
    if layer and layer in cfg["core_layers"]:
        tier, reasons = max(tier, 2), reasons + ["core layer %s" % layer]
    if any(fnmatch.fnmatch(rel, g) for g in cfg["core_globs"]):
        tier, reasons = 3, reasons + ["matches a core path in risk.json"]
    out.update(tier=tier, reasons=reasons)
    return out


# ---- approvals --------------------------------------------------------------------------------

def action_key(result):
    """Same tool family + same target -> same key, so an approval covers the agent's retry."""
    family = "shell" if result["tool"].lower() in SHELL_TOOLS else "edit"
    basis = "%s\0%s" % (family, result.get("file") or result.get("target") or "")
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def _store(project):
    return os.path.join(spec_dir(project), "risk", "approvals.json")


def _locked(project, fn):
    path = _store(project)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".lock", "a+") as lock:
        try:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass  # Windows: best effort, the window is one hook call wide
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("pending", {})
        data.setdefault("approved", {})
        result, changed = fn(data)
        if changed:
            with open(path + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=1)
            os.replace(path + ".tmp", path)
        return result


def _audit(project, row):
    metrics = os.path.join(spec_dir(project), "metrics")
    try:
        os.makedirs(metrics, exist_ok=True)
        row = dict({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, **row)
        with open(os.path.join(metrics, "risk.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    except OSError:
        pass


def consume_approval(project, result, session=None):
    """True once per approval: the approved retry goes through, the next identical one waits."""
    key = action_key(result)
    now = time.time()

    def take(data):
        entry = data["approved"].pop(key, None)
        if entry and entry.get("expires", 0) >= now:
            return True, True
        return False, entry is not None  # an expired approval is dropped
    ok = _locked(project, take)
    if ok:
        _audit(project, {"event": "used", "key": key, "tier": result["tier"], "tool": result["tool"],
                         "target": result.get("file") or result.get("target"), "session": session})
    return ok


def record_blocked(project, result, session=None):
    key = action_key(result)

    def put(data):
        prev = data["pending"].get(key) or {}
        data["pending"][key] = dict(result, key=key, session=session, first_blocked=prev.get("first_blocked") or
                                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                    attempts=int(prev.get("attempts") or 0) + 1)
        return key, True
    _locked(project, put)
    _audit(project, {"event": "blocked", "key": key, "tier": result["tier"], "tool": result["tool"],
                     "target": result.get("file") or result.get("target"), "reasons": result.get("reasons"),
                     "session": session})
    return key


def decide(project, key, approve, by="dashboard"):
    ttl = int(config(project).get("approval_ttl_s") or 1800)

    def move(data):
        entry = data["pending"].pop(key, None)
        if entry is None:
            return None, False
        if approve:
            data["approved"][key] = dict(entry, approved_by=by, expires=time.time() + ttl)
        return entry, True
    entry = _locked(project, move)
    if entry is None:
        raise KeyError(key)
    _audit(project, {"event": "approved" if approve else "denied", "key": key, "tier": entry.get("tier"),
                     "tool": entry.get("tool"), "target": entry.get("file") or entry.get("target"), "by": by})
    return entry


def pending(project):
    return _locked(project, lambda data: (sorted(data["pending"].values(),
                                                 key=lambda e: e.get("first_blocked") or ""), False))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", default=os.getcwd())
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("classify")
    p.add_argument("--tool", required=True)
    p.add_argument("--target", default="")
    sub.add_parser("pending")
    for name in ("approve", "deny"):
        sub.add_parser(name).add_argument("key")
    args = ap.parse_args(argv)
    if args.cmd == "classify":
        key = "command" if args.tool.lower() in SHELL_TOOLS else "file_path"
        print(json.dumps(classify(args.project, args.tool, {key: args.target}), indent=2))
    elif args.cmd == "pending":
        print(json.dumps(pending(args.project), indent=2))
    else:
        # The agent the gate constrains can run shell commands, so the CLI asks a person at a
        # real terminal to retype the key. Without a TTY, use the dashboard.
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            print("refused: %s needs a person at an interactive terminal; use the dashboard "
                  "(Project > Risk)" % args.cmd, file=sys.stderr)
            return 2
        try:
            typed = input("Type the key to %s it: " % args.cmd).strip()
        except EOFError:
            typed = ""
        if typed != args.key:
            print("refused: key did not match", file=sys.stderr)
            return 2
        try:
            print(json.dumps(decide(args.project, args.key, args.cmd == "approve", by="cli"), indent=2))
        except KeyError:
            print("no pending action %s" % args.key, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
