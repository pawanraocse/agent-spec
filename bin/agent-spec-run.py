#!/usr/bin/env python3
"""agent-spec-run.py — deterministic run-state plumbing for Cursor-native workflows (DEC-12).

There is no workflow runner here. The AI steps are Cursor Task subagents driven by the
`agent-spec-hub-runner` skill; this script only records what happened so a run is observable,
resumable and idempotent:

  .agent-spec/runs/<ULID>/
    run.json  events.jsonl (append-only)  checkpoint.json (atomic)  steps/<id>/output.json  result.json

Every subcommand prints ONE JSON object on stdout. Exit 0 ok, 2 usage, 3 refused.

  start --workflow ID --request TEXT [--workflow-file PATH] [--budget-usd N]
  step-start RUN STEP [--needs a,b] [--writes p1,p2] [--agent N] [--model T] [--skill N] [--inputs-json J]
  step-end   RUN STEP --status success|failed|skipped [--output-file F | --output-json J]
             [--tokens-in N --tokens-out N] [--cost-usd N] [--error MSG]
  event RUN TYPE [--payload-json J] [--step ID]
  status RUN | finish RUN [--force] | resume RUN [--accept-drift] | list | compact --days N
  validate FILE        check a workflow skill (skills/agent-spec-wf-<name>/SKILL.md)

Stdlib only; Python 3.9+. Events follow docs/IMPLEMENTATION-GUIDE.md §4.2.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
import time

try:
    import fcntl
except ImportError:  # non-POSIX: run without cross-process locking
    fcntl = None

SCHEMA = 1
ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
RUN_ID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
STEP_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
USER_EVENT_TYPES = {"decision", "retry", "gate.requested", "gate.resolved", "memory.retrieved",
                    "error", "budget.exceeded", "heartbeat", "tool.called", "tool.result",
                    "experience.written"}
STEP_STATUSES = ("success", "failed", "skipped")
SATISFIED = ("success", "skipped")


class Usage(Exception):
    """Exit 2."""


class Refused(Exception):
    """Exit 3."""


# ---------------------------------------------------------------- time, ids, json

def now_ms():
    return int(time.time() * 1000)


def iso_from_ms(ms):
    dt = datetime.datetime.fromtimestamp(ms / 1000.0, datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (dt.microsecond // 1000)


def parse_iso(value):
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=datetime.timezone.utc)
    except (TypeError, ValueError):
        return None


def ulid_encode(value):
    out = []
    for _ in range(26):
        out.append(ULID_ALPHABET[value & 31])
        value >>= 5
    return "".join(reversed(out))


def ulid_decode(text):
    value = 0
    for ch in text:
        value = (value << 5) | ULID_ALPHABET.index(ch)
    return value


def new_ulid(after=None):
    """Sortable id (48-bit ms + 80-bit random). With `after`, guaranteed to sort after it."""
    ulid = ulid_encode((now_ms() << 80) | secrets.randbits(80))
    if after and RUN_ID_RE.match(after) and ulid <= after:
        ulid = ulid_encode(ulid_decode(after) + 1)
    return ulid


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json_atomic(path, obj):
    """Write via a temp file in the same directory, fsync, then os.replace."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# ---------------------------------------------------------------- redaction (same module as ingest/dashboard — loaded by path, no platform import)

def _load_redact():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aspec_platform", "redact.py")
    spec = importlib.util.spec_from_file_location("aspec_redact_for_run", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.redact_obj


redact = _load_redact()


# ---------------------------------------------------------------- workflow parsing (YAML subset)

LEGACY_RE = re.compile(r"^(pipeline|sub_agents):", re.M)
FENCE_RE = re.compile(r"^```steps[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
KEY_ITEM_RE = re.compile(r"^-\s+([A-Za-z_][\w-]*):\s*(.*)$")
KEY_LINE_RE = re.compile(r"^\s+([A-Za-z_][\w-]*):\s*(.*)$")
STEP_KEYS = ("id", "needs", "ai", "agent", "model", "skill", "writes", "gate", "when", "retries", "timeout_s")
LEGACY_MSG = ("legacy template format (pipeline:/sub_agents: keys) is not supported; migrate to a skill "
              "skills/agent-spec-wf-<name>/SKILL.md with name/description frontmatter and a ```steps block "
              "(see skills/agent-spec-wf-example/SKILL.md)")


def _scalar(raw):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [_scalar(p) for p in inner.split(",")] if inner else []
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    if re.match(r"^-?\d+$", raw):
        return int(raw)
    return raw


def _frontmatter(text):
    """Return ({key: raw value}, error). Only top-level `key: value` lines are read."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, "missing frontmatter (file must start with a --- block with name and description)"
    meta = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return meta, None
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            meta[m.group(1)] = m.group(2).strip()
    return None, "frontmatter is not closed with ---"


def parse_workflow(path):
    """Parse and validate a workflow skill. Returns (info, errors); errors are bare messages."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        return None, ["cannot read file: %s" % exc]
    if LEGACY_RE.search(text):
        return None, [LEGACY_MSG]
    errors = []
    meta, err = _frontmatter(text)
    if err:
        errors.append(err)
        meta = {}
    name = (meta.get("name") or "").strip("\"'")
    if meta and not name:
        errors.append("frontmatter is missing name")
    elif name and not name.startswith("agent-spec-wf-"):
        errors.append("name '%s' must start with agent-spec-wf-" % name)
    if meta and "description" not in meta:
        errors.append("frontmatter is missing description")

    fence = FENCE_RE.search(text)
    if not fence:
        errors.append("missing ```steps block")
        return None, errors
    steps, step_errors = _parse_steps(fence.group(1))
    errors.extend(step_errors)
    if not steps and not step_errors:
        errors.append("steps block has no steps")
    errors.extend(_check_graph(steps))
    if errors:
        return None, errors
    return {"name": name, "version": (meta.get("version") or "").strip("\"'"), "steps": steps}, []


def _parse_steps(block):
    items, errors, current = [], [], None
    for lineno, line in enumerate(block.split("\n"), 1):
        if not line.strip() or line.strip().startswith("#"):
            continue
        m_item, m_line = KEY_ITEM_RE.match(line), KEY_LINE_RE.match(line)
        if m_item:
            current = {"_n": len(items) + 1, "_keys": {}}
            items.append(current)
            key, raw = m_item.group(1), m_item.group(2)
        elif m_line and current is not None:
            key, raw = m_line.group(1), m_line.group(2)
        else:
            errors.append("steps line %d is not 'key: value' or '- key: value': %s" % (lineno, line.strip()))
            continue
        if key in current["_keys"]:
            errors.append("step %d: duplicate key '%s'" % (current["_n"], key))
        current["_keys"][key] = _scalar(raw)
    steps = []
    for item in items:
        keys, label = item["_keys"], "step %d" % item["_n"]
        if "id" in keys and isinstance(keys["id"], str) and keys["id"]:
            label = "step '%s'" % keys["id"]
        for key in keys:
            if key not in STEP_KEYS:
                errors.append("%s: unknown key '%s'" % (label, key))
        sid = keys.get("id")
        if not isinstance(sid, str) or not sid:
            errors.append("%s: missing id" % label)
            continue
        if not STEP_ID_RE.match(sid):
            errors.append("%s: id must match [A-Za-z0-9_.-]" % label)
        for list_key in ("needs", "writes"):
            if list_key in keys and not (isinstance(keys[list_key], list)
                                         and all(isinstance(v, str) and v for v in keys[list_key])):
                errors.append("%s: %s must be a list like [a, b]" % (label, list_key))
        if "ai" in keys and not isinstance(keys["ai"], bool):
            errors.append("%s: ai must be true or false" % label)
        for str_key in ("agent", "model", "skill", "when"):
            if str_key in keys and not isinstance(keys[str_key], str):
                errors.append("%s: %s must be text" % (label, str_key))
        if "gate" in keys and keys["gate"] != "human":
            errors.append("%s: gate must be 'human' (got %r)" % (label, keys["gate"]))
        if "retries" in keys:
            r = keys["retries"]
            if isinstance(r, bool) or not isinstance(r, int) or not 0 <= r <= 3:
                errors.append("%s: retries must be an integer 0-3" % label)
        if "timeout_s" in keys:
            t = keys["timeout_s"]
            if isinstance(t, bool) or not isinstance(t, int) or t <= 0:
                errors.append("%s: timeout_s must be a positive integer" % label)
        steps.append({
            "id": sid,
            "needs": keys["needs"] if isinstance(keys.get("needs"), list) else [],
            "ai": keys["ai"] if isinstance(keys.get("ai"), bool) else False,
            "agent": keys.get("agent") if isinstance(keys.get("agent"), str) else None,
            "model": keys.get("model") if isinstance(keys.get("model"), str) else None,
            "skill": keys.get("skill") if isinstance(keys.get("skill"), str) else None,
            "writes": keys["writes"] if isinstance(keys.get("writes"), list) else [],
            "gate": keys.get("gate") if keys.get("gate") == "human" else None,
            "when": keys.get("when") if isinstance(keys.get("when"), str) else None,
            "retries": keys["retries"] if isinstance(keys.get("retries"), int)
            and not isinstance(keys.get("retries"), bool) else 0,
            "timeout_s": keys["timeout_s"] if isinstance(keys.get("timeout_s"), int)
            and not isinstance(keys.get("timeout_s"), bool) else None,
        })
    return steps, errors


def _check_graph(steps):
    errors, seen = [], set()
    for step in steps:
        if step["id"] in seen:
            errors.append("duplicate step id '%s'" % step["id"])
        seen.add(step["id"])
    for step in steps:
        for need in step["needs"]:
            if need not in seen:
                errors.append("step '%s' needs unknown step '%s'" % (step["id"], need))
    if errors:
        return errors
    graph = {s["id"]: s["needs"] for s in steps}
    state = {}

    def visit(node, trail):
        state[node] = 1
        for need in graph[node]:
            if state.get(need) == 1:
                return trail[trail.index(need):] + [need] if need in trail else [node, need]
            if need not in state:
                found = visit(need, trail + [need])
                if found:
                    return found
        state[node] = 2
        return None

    for sid in graph:
        if sid not in state:
            cycle = visit(sid, [sid])
            if cycle:
                return ["cycle: %s" % " -> ".join(cycle)]
    return []


# ---------------------------------------------------------------- locations and locking

def find_root():
    env = os.environ.get("AGENT_SPEC_ROOT")
    if env:
        return os.path.abspath(env)
    cur = os.path.abspath(os.getcwd())
    while True:
        if os.path.isdir(os.path.join(cur, ".agent-spec")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.abspath(os.getcwd())
        cur = parent


def runs_dir():
    return os.path.join(find_root(), ".agent-spec", "runs")


def run_path(run_id):
    if not RUN_ID_RE.match(run_id or "") or not os.path.isfile(os.path.join(runs_dir(), run_id, "run.json")):
        raise Refused("unknown run '%s' (see: agent-spec-run.py list)" % run_id)
    return os.path.join(runs_dir(), run_id)


class RunLock(object):
    """Exclusive flock on runs/<id>/.lock so parallel Task calls cannot interleave updates."""

    def __init__(self, rd):
        self.path = os.path.join(rd, ".lock")
        self.fh = None

    def __enter__(self):
        self.fh = open(self.path, "a")
        if fcntl is not None:
            fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if self.fh:
            if fcntl is not None:
                fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
            self.fh.close()
        return False


def find_workflow_file(workflow_id, explicit):
    if explicit:
        if not os.path.isfile(explicit):
            raise Refused("workflow file not found: %s" % explicit)
        return os.path.abspath(explicit)
    name = workflow_id if workflow_id.startswith("agent-spec-wf-") else "agent-spec-wf-" + workflow_id
    candidates = [
        os.path.join(find_root(), ".cursor", "skills", name, "SKILL.md"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", name, "SKILL.md"),
        os.path.join(os.path.expanduser("~"), ".cursor", "skills", name, "SKILL.md"),
    ]
    for cand in candidates:
        if os.path.isfile(cand):
            return cand
    raise Refused("workflow '%s' not found (looked for %s/SKILL.md); pass --workflow-file" % (workflow_id, name))


def file_sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# ---------------------------------------------------------------- events

def last_event_id(path):
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 8192))
            lines = [ln for ln in fh.read().split(b"\n") if ln.strip()]
        return json.loads(lines[-1].decode("utf-8")).get("event_id") if lines else None
    except (OSError, ValueError):
        return None


def emit(rd, run, etype, step_id=None, actor=None, payload=None, tokens=None, cost_usd=0.0,
         duration_ms=0, span_id=None):
    """Append one redacted event as a single write + fsync. Caller holds the run lock."""
    path = os.path.join(rd, "events.jsonl")
    root_span = run["root_span_id"]
    event = {
        "schema": SCHEMA,
        "event_id": new_ulid(last_event_id(path)),
        "ts": iso_from_ms(now_ms()),
        "run_id": run["run_id"],
        "trace_id": run["trace_id"],
        "span_id": span_id or root_span,
        "parent_span_id": root_span if span_id and span_id != root_span else None,
        "source": "ide",
        "type": etype,
        "actor": actor or {"role": None, "agent": None, "model": None, "skill": None},
        "step_id": step_id,
        "payload": redact(payload or {}),
        "tokens": tokens or {"input": 0, "output": 0, "cache_read": 0, "estimated": True},
        "cost_usd": float(cost_usd or 0.0),
        "duration_ms": int(duration_ms or 0),
    }
    data = (json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    return event


# ---------------------------------------------------------------- state helpers

def load_run(rd):
    return read_json(os.path.join(rd, "run.json"))


def load_checkpoint(rd):
    path = os.path.join(rd, "checkpoint.json")
    return read_json(path) if os.path.isfile(path) else {}


def save_checkpoint(rd, checkpoint):
    write_json_atomic(os.path.join(rd, "checkpoint.json"), checkpoint)


def plan_ids(run):
    return [s["id"] for s in run.get("plan", [])]


def plan_step(run, step_id):
    for s in run.get("plan", []):
        if s["id"] == step_id:
            return s
    return None


def csv(value):
    return [p.strip() for p in (value or "").split(",") if p.strip()]


def parse_json_arg(raw, what):
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise Usage("%s is not valid JSON: %s" % (what, exc))


def require_running(run):
    if run.get("status") != "running":
        raise Refused("run %s is already %s" % (run["run_id"], run.get("status")))


def check_step_id(step_id):
    if not STEP_ID_RE.match(step_id or ""):
        raise Usage("invalid step id '%s'" % step_id)


def derive_status(success, total):
    """O-017: success = every planned step succeeded; failed = none did; else partial."""
    if total == 0 or success == 0:
        return "failed"
    return "success" if success == total else "partial"


def summarize(run, checkpoint):
    counts = {"success": 0, "failed": 0, "skipped": 0, "running": 0, "pending": 0}
    steps = {}
    ids = plan_ids(run) + [s for s in checkpoint if s not in plan_ids(run)]
    for sid in ids:
        entry = checkpoint.get(sid)
        status = entry["status"] if entry else "pending"
        counts[status] += 1
        steps[sid] = {"status": status, "attempts": entry.get("attempts", 0) if entry else 0}
        if entry and entry.get("error"):
            steps[sid]["error"] = entry["error"]
    tokens = {"input": sum(e.get("tokens", {}).get("input", 0) for e in checkpoint.values()),
              "output": sum(e.get("tokens", {}).get("output", 0) for e in checkpoint.values())}
    cost = round(sum(e.get("cost_usd", 0.0) for e in checkpoint.values()), 6)
    return counts, steps, tokens, cost


def ready_steps(run, checkpoint, candidates):
    out = []
    for sid in candidates:
        needs = (plan_step(run, sid) or {}).get("needs", [])
        if all(checkpoint.get(n, {}).get("status") in SATISFIED for n in needs):
            out.append(sid)
    return out


def over_budget(run, cost):
    limit = (run.get("budgets") or {}).get("max_cost_usd")
    return limit is not None and cost > limit


# ---------------------------------------------------------------- commands

def cmd_start(args):
    wf_file = find_workflow_file(args.workflow, args.workflow_file)
    info, errors = parse_workflow(wf_file)
    if errors:
        raise Refused("; ".join("%s: %s" % (wf_file, e) for e in errors))
    run_id = new_ulid()
    rd = os.path.join(runs_dir(), run_id)
    os.makedirs(os.path.join(rd, "steps"))
    sha = file_sha(wf_file)
    run = {
        "run_id": run_id,
        "trace_id": new_ulid(),
        "root_span_id": "s-" + secrets.token_hex(6),
        "workflow_id": args.workflow,
        "workflow_version": info["version"] or "sha:" + sha[:12],
        "workflow_sha": sha,
        "workflow_file": wf_file,
        "request": redact(args.request),
        "status": "running",
        "source": "ide",
        "budgets": {"max_cost_usd": args.budget_usd},
        "plan": info["steps"],
        "drift_accepted": [],
        "started": iso_from_ms(now_ms()),
    }
    write_json_atomic(os.path.join(rd, "run.json"), run)
    with RunLock(rd):
        open(os.path.join(rd, "events.jsonl"), "a").close()
        emit(rd, run, "run.received", payload={"workflow_id": args.workflow, "workflow_sha": sha,
                                               "request": run["request"], "steps": plan_ids(run)})
    return {"ok": True, "run_id": run_id, "trace_id": run["trace_id"], "dir": rd,
            "workflow_sha": sha, "steps": plan_ids(run)}


def cmd_step_start(args):
    check_step_id(args.step)
    rd = run_path(args.run)
    with RunLock(rd):
        run, checkpoint = load_run(rd), load_checkpoint(rd)
        require_running(run)
        planned = plan_step(run, args.step)
        if run.get("plan") and planned is None:
            raise Refused("step '%s' is not in the workflow (steps: %s)" % (args.step, ", ".join(plan_ids(run))))
        needs = list(dict.fromkeys((planned["needs"] if planned else []) + csv(args.needs)))
        blocked = ["%s (%s)" % (n, checkpoint.get(n, {}).get("status", "not started"))
                   for n in needs if checkpoint.get(n, {}).get("status") not in SATISFIED]
        if blocked:
            raise Refused("step '%s' needs unfinished step(s): %s" % (args.step, ", ".join(blocked)))
        inputs = parse_json_arg(args.inputs_json, "--inputs-json")
        upstream = {n: checkpoint[n].get("output_sha", "") for n in sorted(needs)}
        key = sha256(canonical({"workflow_sha": run["workflow_sha"], "step_id": args.step,
                                "inputs": inputs, "upstream": upstream}))
        prior = checkpoint.get(args.step)
        actor = {"role": None, "agent": args.agent, "model": args.model, "skill": args.skill}
        if prior and prior.get("status") == "success" and prior.get("key") == key:
            emit(rd, run, "decision", step_id=args.step, actor=actor,
                 payload={"choice": "reuse", "key": key, "reason": "idempotency key matches a success"})
            return {"ok": True, "step": args.step, "reuse": True, "key": key,
                    "output": os.path.join(rd, prior["output"])}
        span = "s-" + secrets.token_hex(6)
        attempts = (prior.get("attempts", 0) if prior else 0) + 1
        checkpoint[args.step] = {
            "status": "running", "key": key, "attempts": attempts, "span_id": span,
            "started": iso_from_ms(now_ms()), "started_ms": now_ms(), "needs": needs,
            "writes": csv(args.writes) or (planned["writes"] if planned else []),
            "agent": args.agent, "model": args.model, "skill": args.skill,
        }
        save_checkpoint(rd, checkpoint)
        emit(rd, run, "step.started", step_id=args.step, actor=actor, span_id=span,
             payload={"attempt": attempts, "key": key, "needs": needs,
                      "writes": checkpoint[args.step]["writes"]})
    return {"ok": True, "step": args.step, "reuse": False, "key": key, "attempt": attempts}


def read_output(args):
    if args.output_json is not None and args.output_file is not None:
        raise Usage("use --output-file or --output-json, not both")
    if args.output_json is not None:
        return parse_json_arg(args.output_json, "--output-json")
    if args.output_file is not None:
        try:
            with open(args.output_file, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            raise Usage("cannot read --output-file: %s" % exc)
        try:
            return json.loads(text)
        except ValueError:
            return {"text": text}
    return None


def sanitize_error(text, max_chars=1000):
    if not text:
        return text
    # Strip HTML tags
    stripped = re.sub(r"<[^>]+>", " ", text)
    stripped = re.sub(r"[ \t\r\f\v]+", " ", stripped)
    lines = [line.strip() for line in stripped.splitlines()]
    cleaned_lines = []
    prev_empty = False
    for line in lines:
        if not line:
            if not prev_empty:
                cleaned_lines.append("")
                prev_empty = True
        else:
            cleaned_lines.append(line)
            prev_empty = False
    stripped = "\n".join(cleaned_lines).strip()
    if len(stripped) <= max_chars:
        return stripped
    marker = "\n... [truncated %d chars] ...\n"
    overhead = len(marker % len(stripped))
    avail = max(0, max_chars - overhead)
    head_len = avail // 2
    tail_len = avail - head_len
    head = stripped[:head_len]
    tail = stripped[-tail_len:] if tail_len > 0 else ""
    truncated_count = len(stripped) - (head_len + tail_len)
    return head + (marker % truncated_count) + tail


def cmd_step_end(args):
    check_step_id(args.step)
    output = redact(read_output(args))
    rd = run_path(args.run)
    with RunLock(rd):
        run, checkpoint = load_run(rd), load_checkpoint(rd)
        require_running(run)
        if run.get("plan") and plan_step(run, args.step) is None:
            raise Refused("step '%s' is not in the workflow" % args.step)
        entry = checkpoint.get(args.step) or {"attempts": 1, "needs": [], "span_id": "s-" + secrets.token_hex(6),
                                              "started_ms": now_ms(), "started": iso_from_ms(now_ms())}
        out_sha = sha256(canonical(output))
        error = sanitize_error(redact(args.error)) if args.error else None
        finished_ms = now_ms()
        rel = os.path.join("steps", args.step, "output.json")
        write_json_atomic(os.path.join(rd, rel), {
            "step_id": args.step, "status": args.status, "attempt": entry["attempts"],
            "output": output, "output_sha": out_sha, "error": error, "finished": iso_from_ms(finished_ms)})
        given = args.tokens_in is not None or args.tokens_out is not None
        tokens = {"input": args.tokens_in or 0,
                  "output": args.tokens_out if args.tokens_out is not None else
                  (0 if output is None else (len(canonical(output)) + 3) // 4)}
        cost = args.cost_usd or 0.0
        duration = max(0, finished_ms - entry.get("started_ms", finished_ms))
        entry.update({"status": args.status, "output": rel, "output_sha": out_sha, "error": error,
                      "finished": iso_from_ms(finished_ms), "tokens": tokens, "cost_usd": cost})
        checkpoint[args.step] = entry
        save_checkpoint(rd, checkpoint)
        emit(rd, run, "step.finished", step_id=args.step,
             actor={"role": None, "agent": entry.get("agent"), "model": entry.get("model"),
                    "skill": entry.get("skill")},
             span_id=entry["span_id"], payload={"status": args.status, "attempt": entry["attempts"],
                                                "output_sha": out_sha, "error": error},
             tokens={"input": tokens["input"], "output": tokens["output"], "cache_read": 0,
                     "estimated": not given},
             cost_usd=cost, duration_ms=duration)
        total_cost = round(sum(e.get("cost_usd", 0.0) for e in checkpoint.values()), 6)
        exceeded = over_budget(run, total_cost)
        if exceeded:
            emit(rd, run, "budget.exceeded", step_id=args.step,
                 payload={"cost_usd": total_cost, "max_cost_usd": run["budgets"]["max_cost_usd"]})
    return {"ok": True, "step": args.step, "status": args.status, "output_sha": out_sha,
            "cost_usd": total_cost, "budget_exceeded": exceeded}


def cmd_event(args):
    if args.type not in USER_EVENT_TYPES:
        raise Usage("event type '%s' not allowed here; use one of: %s"
                    % (args.type, ", ".join(sorted(USER_EVENT_TYPES))))
    if args.step:
        check_step_id(args.step)
    payload = parse_json_arg(args.payload_json, "--payload-json") or {}
    if not isinstance(payload, dict):
        raise Usage("--payload-json must be a JSON object")
    rd = run_path(args.run)
    with RunLock(rd):
        run = load_run(rd)
        event = emit(rd, run, args.type, step_id=args.step, payload=payload)
    return {"ok": True, "event_id": event["event_id"], "type": args.type}


def cmd_status(args):
    rd = run_path(args.run)
    run, checkpoint = load_run(rd), load_checkpoint(rd)
    counts, steps, tokens, cost = summarize(run, checkpoint)
    pending = [s for s in steps if steps[s]["status"] == "pending"]
    return {"ok": True, "run_id": run["run_id"], "workflow_id": run["workflow_id"], "status": run["status"],
            "derived": derive_status(counts["success"], sum(counts.values())), "counts": counts,
            "steps": steps, "ready": ready_steps(run, checkpoint, pending), "tokens": tokens,
            "cost_usd": cost, "budget_usd": run["budgets"]["max_cost_usd"],
            "budget_exceeded": over_budget(run, cost), "started": run["started"],
            "finished": run.get("finished")}


def append_experience(rd, run, status, tokens, steps):
    """L-001: one line per finished workflow in `.agent-spec/experience.jsonl`. Fail-open: never blocks finish."""
    line = {"schema": 1, "exp_id": "workflow:" + run["run_id"], "kind": "workflow", "ts": iso_from_ms(now_ms()),
            "task": run.get("request"), "status": status, "workflow_id": run.get("workflow_id"),
            "run_id": run["run_id"], "tokens": {"input": tokens["input"], "output": tokens["output"], "cache_read": 0},
            "retries": sum(max(0, s.get("attempts", 0) - 1) for s in steps.values()),
            "gates": [sid for sid, s in steps.items() if s["status"] == "success"
                      and (plan_step(run, sid) or {}).get("gate")],
            "corrections": 0, "facts_injected": None}
    try:
        path = os.path.join(os.path.dirname(os.path.dirname(rd)), "experience.jsonl")
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, (json.dumps(redact(line), sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
        finally:
            os.close(fd)
    except OSError:
        pass


def cmd_finish(args):
    rd = run_path(args.run)
    with RunLock(rd):
        run, checkpoint = load_run(rd), load_checkpoint(rd)
        require_running(run)
        running = [s for s, e in checkpoint.items() if e["status"] == "running"]
        if running and not args.force:
            raise Refused("step(s) still running: %s (step-end them, resume, or finish --force)"
                          % ", ".join(running))
        for sid in running:
            checkpoint[sid].update({"status": "failed", "error": "unfinished at finish --force"})
        if running:
            save_checkpoint(rd, checkpoint)
        counts, steps, tokens, cost = summarize(run, checkpoint)
        status = derive_status(counts["success"], sum(counts.values()))
        finished = iso_from_ms(now_ms())
        for sid, info in steps.items():
            entry = checkpoint.get(sid)
            if entry and entry.get("output") and os.path.isfile(os.path.join(rd, entry["output"])):
                info["output"] = read_json(os.path.join(rd, entry["output"])).get("output")
                info["output_sha"] = entry.get("output_sha")
        started = parse_iso(run["started"])
        duration = int((parse_iso(finished) - started).total_seconds() * 1000) if started else 0
        result = {"run_id": run["run_id"], "trace_id": run["trace_id"], "workflow_id": run["workflow_id"],
                  "status": status, "counts": counts, "steps": steps, "tokens": tokens, "cost_usd": cost,
                  "started": run["started"], "finished": finished, "duration_ms": duration}
        write_json_atomic(os.path.join(rd, "result.json"), result)
        run.update({"status": status, "finished": finished})
        write_json_atomic(os.path.join(rd, "run.json"), run)
        emit(rd, run, "run.status", payload={"status": status, "counts": counts},
             cost_usd=cost, duration_ms=duration)
        append_experience(rd, run, status, tokens, steps)
    return {"ok": True, "run_id": run["run_id"], "status": status, "counts": counts,
            "result": os.path.join(rd, "result.json")}


def cmd_resume(args):
    rd = run_path(args.run)
    with RunLock(rd):
        run, checkpoint = load_run(rd), load_checkpoint(rd)
        require_running(run)
        wf_file = run.get("workflow_file")
        if not wf_file or not os.path.isfile(wf_file):
            raise Refused("workflow file is missing: %s" % wf_file)
        current = file_sha(wf_file)
        drift = current != run["workflow_sha"]
        if drift and current not in run.get("drift_accepted", []):
            if not args.accept_drift:
                raise Refused("workflow_sha drifted since start (%s -> %s); the workflow changed mid-run. "
                              "Re-run with --accept-drift to continue on the original plan, or start a new run."
                              % (run["workflow_sha"][:12], current[:12]))
            run["drift_accepted"] = run.get("drift_accepted", []) + [current]
            write_json_atomic(os.path.join(rd, "run.json"), run)
            emit(rd, run, "decision", payload={"choice": "accept-drift", "from": run["workflow_sha"],
                                               "to": current, "reason": "--accept-drift"})
        ids = plan_ids(run)
        finished = [s for s in ids if checkpoint.get(s, {}).get("status") in SATISFIED]
        rerun = [s for s in ids if checkpoint.get(s, {}).get("status") == "running"]
        failed = [s for s in ids if checkpoint.get(s, {}).get("status") == "failed"]
        pending = [s for s in ids if s not in checkpoint]
    return {"ok": True, "run_id": run["run_id"], "workflow_id": run["workflow_id"], "finished": finished,
            "rerun": rerun, "failed": failed, "pending": pending,
            "ready": ready_steps(run, checkpoint, rerun + pending),
            "drift_accepted": bool(drift and args.accept_drift) or bool(run.get("drift_accepted"))}


def cmd_list(args):
    base, rows = runs_dir(), []
    names = sorted((n for n in os.listdir(base) if RUN_ID_RE.match(n)), reverse=True) if os.path.isdir(base) else []
    for name in names:
        try:
            run = read_json(os.path.join(base, name, "run.json"))
        except (OSError, ValueError):
            continue
        rows.append({"run_id": name, "workflow_id": run.get("workflow_id"), "status": run.get("status"),
                     "started": run.get("started"), "request": (run.get("request") or "")[:80]})
        if len(rows) >= args.limit:
            break
    return {"ok": True, "runs": rows}


def cmd_compact(args):
    base = runs_dir()
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=args.days)
    compacted, kept = [], 0
    names = sorted(n for n in os.listdir(base) if RUN_ID_RE.match(n)) if os.path.isdir(base) else []
    for name in names:
        rd = os.path.join(base, name)
        try:
            run = read_json(os.path.join(rd, "run.json"))
        except (OSError, ValueError):
            continue
        started = parse_iso(run.get("started"))
        doomed = [p for p in ("steps", "events.jsonl", "checkpoint.json", ".lock")
                  if os.path.exists(os.path.join(rd, p))]
        if run.get("status") == "running" or not started or started > cutoff or not doomed:
            kept += 1
            continue
        if not args.dry_run:
            for part in doomed:
                target = os.path.join(rd, part)
                shutil.rmtree(target) if os.path.isdir(target) else os.unlink(target)
        compacted.append(name)
    return {"ok": True, "dry_run": args.dry_run, "compacted": compacted, "kept": kept}


def cmd_validate(args):
    info, errors = parse_workflow(args.file)
    if errors:
        lines = ["%s: %s" % (args.file, e) for e in errors]
        for line in lines:
            sys.stderr.write(line + "\n")
        raise Refused_with(lines)
    return {"ok": True, "file": args.file, "name": info["name"], "steps": info["steps"]}


class Refused_with(Refused):
    """Refusal that carries a list of `file: message` lines."""

    def __init__(self, errors):
        Refused.__init__(self, "; ".join(errors))
        self.errors = errors


# ---------------------------------------------------------------- CLI

class JsonParser(argparse.ArgumentParser):
    def error(self, message):
        raise Usage(message)


def build_parser():
    parser = JsonParser(prog="agent-spec-run.py", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", parser_class=JsonParser)
    sub.required = True

    p = sub.add_parser("start")
    p.add_argument("--workflow", required=True)
    p.add_argument("--request", required=True)
    p.add_argument("--workflow-file")
    p.add_argument("--budget-usd", type=float)
    p.set_defaults(fn=cmd_start)

    p = sub.add_parser("step-start")
    p.add_argument("run")
    p.add_argument("step")
    p.add_argument("--needs")
    p.add_argument("--writes")
    p.add_argument("--agent")
    p.add_argument("--model")
    p.add_argument("--skill")
    p.add_argument("--inputs-json")
    p.set_defaults(fn=cmd_step_start)

    p = sub.add_parser("step-end")
    p.add_argument("run")
    p.add_argument("step")
    p.add_argument("--status", required=True, choices=STEP_STATUSES)
    p.add_argument("--output-file")
    p.add_argument("--output-json")
    p.add_argument("--tokens-in", type=int)
    p.add_argument("--tokens-out", type=int)
    p.add_argument("--cost-usd", type=float)
    p.add_argument("--error")
    p.set_defaults(fn=cmd_step_end)

    p = sub.add_parser("event")
    p.add_argument("run")
    p.add_argument("type")
    p.add_argument("--payload-json")
    p.add_argument("--step")
    p.set_defaults(fn=cmd_event)

    for name, fn in (("status", cmd_status), ("finish", cmd_finish), ("resume", cmd_resume)):
        p = sub.add_parser(name)
        p.add_argument("run")
        if name == "finish":
            p.add_argument("--force", action="store_true")
        if name == "resume":
            p.add_argument("--accept-drift", action="store_true")
        p.set_defaults(fn=fn)

    p = sub.add_parser("list")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("compact")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_compact)

    p = sub.add_parser("validate")
    p.add_argument("file")
    p.set_defaults(fn=cmd_validate)
    return parser


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
        result = args.fn(args)
        code = 0
    except Usage as exc:
        result, code = {"ok": False, "error": str(exc)}, 2
    except Refused_with as exc:
        result, code = {"ok": False, "error": str(exc), "errors": exc.errors}, 3
    except Refused as exc:
        result, code = {"ok": False, "error": str(exc)}, 3
    if code == 3 and "errors" in result:
        result["file"] = getattr(args, "file", None)
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
