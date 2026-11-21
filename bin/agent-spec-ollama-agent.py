#!/usr/bin/env python3
"""A local stand-in for `cursor-agent` that runs on Ollama, so the harness can be exercised
end to end without a Cursor subscription.

It accepts the `cursor-agent -p` arguments the dashboard's Agent Console sends, runs a small
read-only tool loop (Read, Grep, graphify context) against a local Ollama model, and fires the
project's registered Cursor hooks from `.cursor/hooks.json` with Cursor-shaped payloads:
sessionStart (the digest becomes the system prompt), beforeSubmitPrompt, preToolUse (a deny is
honoured), postToolUse, afterAgentResponse with Ollama's measured token counts, and stop. The
requests it produces therefore land in events.jsonl and the dashboard exactly as a Cursor chat
would, tagged with the model name `ollama:<model>`.

    agent-spec-ollama-agent.py -p --workspace <dir> "<prompt>"
    agent-spec-ollama-agent.py -p --bare ...    the same agent with the harness off: no digest,
                                                no graph tool, no preToolUse guard (A/B baseline)
    AGENT_SPEC_FAKE_CURSOR_AGENT=<this file> AGENT_SPEC_CONSOLE=1 agent-spec-platform.py serve

Settings: AGENT_SPEC_OLLAMA_URL (default: loopback, then the Windows host under WSL; see
aspec_platform/ollama.py), AGENT_SPEC_OLLAMA_MODEL or --model (default qwen2.5-coder:7b when installed).

A model named `groq:<name>` (e.g. groq:openai/gpt-oss-120b) runs the same loop on Groq's
OpenAI-compatible API instead, with Groq's measured token counts. That sends the prompt and every
file the agent reads to Groq, so it needs AGENT_SPEC_ALLOW_REMOTE_MODELS=1, plus a key in
GROQ_API_KEY or in ~/.config/agent-spec/groq_api_key (owner-only). AGENT_SPEC_GROQ_URL overrides
the endpoint. A rate-limit reply (HTTP 429) is waited out, up to RETRY_WAIT_CAP seconds per call.
Stdlib only.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aspec_platform import ollama, redact  # noqa: E402

MAX_STEPS = 6
READ_CAP = 12000
TOOL_OUT_CAP = 6000
GREP_LINES, GREP_LINE_CHARS = 60, 240
DEFAULT_MODEL = "qwen2.5-coder:7b"
# Token budget (measured with step_usage): every step re-sends the system prompt, the tool schema
# and all earlier tool results, so each is kept as small as the answer quality allows.
SEARCH_HITS, SNIPPET_CHARS, PURPOSE_CHARS = 5, 110, 90
SEARCH_KINDS = ("code", "doc", "memory")
OLD_RESULT_CHARS = 280            # tool results older than the latest one shrink to this
READ_DEFAULT_LINES = 80           # a Read without a range returns this many lines, never the whole file
DIGEST_KEEP = ("stack:",)         # digest header lines a local model can use; the rest is Cursor-session state
REPEAT_NOTE = "You already made this exact call; its result is above. Make a different call or answer now."
HARNESS_SYSTEM = ("You are a coding assistant working in %s. For any 'where is / which file' question, call "
                  "search_project first, then graphify_context or a ranged Read to confirm. For 'who imports X', "
                  "'what does X import' or 'what breaks if X changes', call graphify_file on X and answer only from "
                  "its lists. Never read a whole large file. Answer every part of the question, naming each file path. No preamble.\n%s")
BARE_SYSTEM = "You are a coding assistant working in %s. Use the tools to look at the code. Answer the question."
CHAT_DIR = os.path.join(os.path.expanduser("~"), ".cache", "agent-spec", "ollama-chats")
VERSION = "ollama-agent/1.0"  # traces.py tags any version naming ollama as origin "local"
# Remote OpenAI-compatible providers, chosen by a model prefix: name -> (url env, default url, key env).
PROVIDERS = {"groq": ("AGENT_SPEC_GROQ_URL", "https://api.groq.com/openai/v1", "GROQ_API_KEY")}
KEY_DIR = os.path.join(os.path.expanduser("~"), ".config", "agent-spec")
RETRY_WAIT_CAP = 120

TOOLS = [
    {"type": "function", "function": {
        "name": "Read", "description": "Read lines of a file (offset, limit).",
        "parameters": {"type": "object", "required": ["file_path"], "properties": {
            "file_path": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}}}}},
    {"type": "function", "function": {
        "name": "Grep", "description": "Regex search; returns path:line matches.",
        "parameters": {"type": "object", "required": ["pattern"], "properties": {
            "pattern": {"type": "string"}, "path": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "graphify_context",
        "description": "Files the dependency graph links to a task.",
        "parameters": {"type": "object", "required": ["task"], "properties": {"task": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "graphify_file",
        "description": "Exact import graph of one file: what it imports and every file that imports it (blast radius).",
        "parameters": {"type": "object", "required": ["file"], "properties": {"file": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "search_project",
        "description": "Ranked file:line hits from the project index (code, docs, memory). Use first.",
        "parameters": {"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}}}}},
]
HARNESS_TOOLS = ("graphify_context", "graphify_file", "search_project")
LOGGED_AS = {"graphify_context": "Shell", "graphify_file": "Shell", "search_project": "codebase_search"}


SKILL_PROMPT = re.compile(r"^/(agent-spec-[\w-]+)")


def skill_body(prompt: str) -> tuple:
    """A prompt that opens with /agent-spec-<name> loads that installed skill, as Cursor does."""
    m = SKILL_PROMPT.match(prompt.strip())
    if not m:
        return None, ""
    path = os.path.join(os.path.expanduser("~"), ".cursor", "skills", m.group(1), "SKILL.md")
    try:
        with open(path, encoding="utf-8") as fh:
            return m.group(1), fh.read()
    except OSError:
        return m.group(1), ""


def emit(obj: dict) -> None:
    print(json.dumps(obj), flush=True)


def parse_args(argv: list) -> dict:
    out = {"workspace": os.getcwd(), "resume": None, "mode": "ask", "prompt": "", "bare": "--bare" in argv}
    i, rest = 0, []
    while i < len(argv):
        a = argv[i]
        if a in ("--workspace", "--resume", "--mode", "--output-format", "--model"):
            if i + 1 < len(argv):
                out[a[2:].replace("-", "_")] = argv[i + 1]
            i += 2
            continue
        if not a.startswith("-"):
            rest.append(a)
        i += 1
    out["prompt"] = " ".join(rest).strip()
    return out


def pick_model(requested: str | None, models: list) -> str:
    names = [m["name"] for m in ollama.chat_models(models)]
    for want in (requested, os.environ.get("AGENT_SPEC_OLLAMA_MODEL"), DEFAULT_MODEL):
        if want and want in names:
            return want
    if requested:
        raise SystemExit("model %s is not installed in Ollama (have: %s)" % (requested, ", ".join(names) or "none"))
    if not names:
        raise SystemExit("no chat model installed in Ollama; run: ollama pull " + DEFAULT_MODEL)
    return names[0]


NUDGE = "No tool call is possible here. Answer the question in plain text from what you already have."


class ProviderError(Exception):
    """A remote provider refused the call; `code` is the agent's exit code."""

    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


def remote(model: str | None):
    """(provider, base url, provider model name) for a `<provider>:<name>` model, else None.
    Ollama names have a colon too (qwen2.5-coder:7b); only a known provider prefix counts."""
    head, _, name = (model or "").partition(":")
    if head not in PROVIDERS or not name:
        return None
    url_env, default, _ = PROVIDERS[head]
    return head, (os.environ.get(url_env) or default).rstrip("/"), name


def api_key(provider: str) -> str:
    var = PROVIDERS[provider][2]
    key = (os.environ.get(var) or "").strip()
    path = os.path.join(KEY_DIR, var.lower())
    if not key and os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            key = fh.read().strip()
    return key


def openai_messages(messages: list) -> list:
    """The loop's Ollama-shaped history as OpenAI chat messages: tool calls get ids, arguments
    become JSON strings, and each tool result answers the oldest unanswered call."""
    out, pending, n = [], [], 0

    def close_pending():
        while pending:  # every call must be answered before the next non-tool message
            out.append({"role": "tool", "tool_call_id": pending.pop(0), "content": "(no result)"})

    for m in messages:
        role = m["role"]
        if role == "tool":
            if pending:
                out.append({"role": "tool", "tool_call_id": pending.pop(0), "content": m.get("content") or ""})
            else:
                out.append({"role": "user", "content": m.get("content") or ""})
            continue
        close_pending()
        if role == "assistant" and m.get("tool_calls"):
            calls = []
            for c in m["tool_calls"]:
                fn = c.get("function") or {}
                args = fn.get("arguments")
                n += 1
                pending.append("call_%d" % n)
                calls.append({"id": pending[-1], "type": "function", "function": {
                    "name": fn.get("name", ""), "arguments": args if isinstance(args, str) else json.dumps(args or {})}})
            out.append({"role": "assistant", "content": m.get("content") or None, "tool_calls": calls})
        else:
            out.append({"role": role, "content": m.get("content") or ""})
    close_pending()
    return out


def openai_chat(provider: str, url: str, model: str, messages: list, on_delta, tools: list) -> dict:
    """One /chat/completions call, shaped like chat()'s return so the loop is unchanged."""
    body = {"model": model, "messages": openai_messages(messages), "temperature": 0}
    if tools:
        body["tools"] = tools
    data, waited, nudged = None, 0.0, 0
    while data is None:
        req = urllib.request.Request(url + "/chat/completions", data=json.dumps(body).encode(), headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + api_key(provider),
            # Groq sits behind Cloudflare, which refuses urllib's default "Python-urllib" agent (1010).
            "User-Agent": "agent-spec-local-agent/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310 — ollama.allowed() checked
                data = json.load(resp)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                err = json.loads(raw).get("error") or {}
            except ValueError:
                err = {}
            if exc.code == 429:
                try:
                    wait = max(1.0, float(exc.headers.get("retry-after") or 5))
                except ValueError:
                    wait = 5.0
                if waited + wait <= RETRY_WAIT_CAP:
                    time.sleep(wait)
                    waited += wait
                    continue
                # A wait past the cap is a quota (Groq's free tier also caps tokens per day): the
                # caller cannot run now, so exit 3 and let a benchmark stop instead of recording zeros.
                msg = redact.redact(str(err.get("message") or raw)[:300])
                raise ProviderError("%s HTTP 429: %s" % (provider, msg), 3)
            if exc.code == 400 and err.get("code") == "tool_use_failed":
                # The model wrote a malformed call; its raw text goes to the text-call parser, as
                # a small Ollama model's JSON-in-prose does.
                text = str(err.get("failed_generation") or "")
                if (not tools or not text_tool_calls(text)) and nudged < 2:
                    # Nothing to run (no tools offered, or no parseable call): ask again for prose
                    # rather than recording an empty answer.
                    nudged += 1
                    body["messages"] = body["messages"] + [{"role": "user", "content": NUDGE}]
                    continue
                on_delta(text)
                return {"message": {"content": text, "tool_calls": []}, "prompt_eval_count": None, "eval_count": None}
            msg = redact.redact(str(err.get("message") or raw)[:300])
            raise ProviderError("%s HTTP %d: %s" % (provider, exc.code, msg), 3 if exc.code in (401, 403, 404) else 1)
        except (urllib.error.URLError, OSError) as exc:
            raise ProviderError("%s unreachable: %s" % (provider, exc), 3)
    msg = ((data.get("choices") or [{}])[0].get("message")) or {}
    content = msg.get("content") or ""
    if content:
        on_delta(content)
    calls = [{"function": {"name": (c.get("function") or {}).get("name", ""),
                           "arguments": (c.get("function") or {}).get("arguments") or "{}"}}
             for c in msg.get("tool_calls") or []]
    usage = data.get("usage") or {}
    return {"message": {"content": content, "tool_calls": calls}, "prompt_eval_count": usage.get("prompt_tokens"),
            "eval_count": usage.get("completion_tokens"),
            "cached_tokens": (usage.get("prompt_tokens_details") or {}).get("cached_tokens")}


def chat(url: str, model: str, messages: list, think: bool, on_delta, tools=None) -> dict:
    """Streams one /api/chat turn; text deltas go to on_delta. Returns the assembled message
    plus Ollama's measured prompt_eval_count / eval_count. A `groq:` model goes to openai_chat."""
    r = remote(model)
    if r:
        return openai_chat(r[0], r[1], r[2], messages, on_delta, TOOLS if tools is None else tools)
    body = {"model": model, "messages": messages, "tools": TOOLS if tools is None else tools, "stream": True,
            "options": {"temperature": 0}}
    if think:
        body["think"] = False  # only sent to models that support it; others reject the field
    req = urllib.request.Request(url + "/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    content, calls, final = [], [], {}
    with urllib.request.urlopen(req, timeout=600) as resp:  # noqa: S310 — ollama.allowed() checked
        for raw in resp:
            if not raw.strip():
                continue
            part = json.loads(raw)
            msg = part.get("message") or {}
            if msg.get("content"):
                content.append(msg["content"])
                on_delta(msg["content"])
            calls.extend(msg.get("tool_calls") or [])
            if part.get("done"):
                final = part
    return {"message": {"content": "".join(content), "tool_calls": calls},
            "prompt_eval_count": final.get("prompt_eval_count"), "eval_count": final.get("eval_count")}


class Hooks:
    """Runs the commands registered in <workspace>/.cursor/hooks.json, as Cursor does."""

    # The harness's own behaviour (digest injection, the input-discipline guard). --bare skips
    # these and keeps only the observers, so the baseline is traced the same way. The secret
    # quarantine is the exception: --bare still fires preToolUse and honours a quarantine deny,
    # because a benchmark baseline must never send .env or a private key to the model.
    HARNESS_EVENTS = ("sessionStart",)
    BARE_DENY = "quarantine:"

    def __init__(self, workspace: str, base: dict, bare: bool = False):
        self.workspace, self.base, self.bare = workspace, base, bare
        try:
            with open(os.path.join(workspace, ".cursor", "hooks.json"), encoding="utf-8") as fh:
                self.table = json.load(fh).get("hooks") or {}
        except (OSError, ValueError):
            self.table = {}

    def fire(self, event: str, extra: dict | None = None) -> list:
        payload = dict(self.base, hook_event_name=event, **(extra or {}))
        outputs = []
        if self.bare and event in self.HARNESS_EVENTS:
            return outputs
        for hook in self.table.get(event) or []:
            try:
                proc = subprocess.run(hook["command"], shell=True, cwd=self.workspace, input=json.dumps(payload),
                                      capture_output=True, text=True, timeout=hook.get("timeout", 5) + 5,
                                      env=dict(os.environ, CURSOR_PROJECT_DIR=self.workspace))
                out = proc.stdout.strip()
                outputs.append(json.loads(out) if out.startswith("{") else {})
            except (OSError, subprocess.SubprocessError, ValueError, KeyError):
                outputs.append({})
        if self.bare and event == "preToolUse":  # keep only the secret quarantine's denies
            outputs = [o for o in outputs if self.BARE_DENY in str(o.get("agent_message") or "")]
        return outputs


def _inside(workspace: str, path: str) -> str | None:
    full = os.path.realpath(os.path.join(workspace, path))
    root = os.path.realpath(workspace)
    return full if full == root or full.startswith(root + os.sep) else None


def run_tool(workspace: str, name: str, args: dict) -> tuple:
    """-> (cursor tool name, tool_input as logged, output text, ok)."""
    if name == "Read":
        path = _inside(workspace, str(args.get("file_path") or ""))
        if not path or not os.path.isfile(path):
            return "Read", args, "error: no such file in the workspace", False
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        start = max(int(args.get("offset") or 1) - 1, 0)
        lines = lines[start:start + min(int(args.get("limit") or READ_DEFAULT_LINES), 200)]
        text = "".join(lines)
        return "Read", dict(args, file_path=path), text[:READ_CAP], True
    if name == "Grep":
        path = _inside(workspace, str(args.get("path") or ".")) or workspace
        proc = subprocess.run(["grep", "-rnI", "-E", "--exclude-dir=.git", "--exclude-dir=node_modules",
                               "--exclude-dir=dist", "--exclude-dir=__pycache__", "--exclude=*.min.js",
                               str(args.get("pattern") or ""), path], capture_output=True, text=True, timeout=20)
        root = os.path.realpath(workspace) + os.sep
        lines = [ln.replace(root, "")[:GREP_LINE_CHARS] for ln in proc.stdout.splitlines()[:GREP_LINES]]
        return "Grep", args, "\n".join(lines) or "no matches", proc.returncode in (0, 1)
    if name in ("graphify_context", "graphify_file"):
        # argv, never a shell string: the task text is model output, and a file the agent read can
        # steer it, so `$(...)` or backticks in it must stay text.
        cli = os.path.join(workspace, ".agent-spec", "bin", "graphify-cli.py")
        if name == "graphify_context":
            argv = [sys.executable, cli, "context", "--task", str(args.get("task") or "")]
        else:
            target = str(args.get("file") or "")
            full = _inside(workspace, target)
            argv = [sys.executable, cli, "query", "--file", os.path.relpath(full, workspace) if full else target]
        proc = subprocess.run(argv, cwd=workspace, capture_output=True, text=True, timeout=30)
        cmd = " ".join(shlex.quote(a) for a in ["python3"] + argv[1:])
        return "Shell", {"command": cmd}, (proc.stdout or proc.stderr)[:TOOL_OUT_CAP], proc.returncode == 0
    if name == "search_project":
        return "codebase_search", args, project_search(workspace, str(args.get("query") or ""), args.get("kind")), True
    return name, args, "error: unknown tool", False


def project_search(workspace: str, query: str, kind) -> str:
    """The dashboard's own retrieval (BM25 + tuned embedding fusion) over the local index."""
    from aspec_platform import db, rag_eval, retrieval
    path = db.db_path(workspace)
    if not query.strip() or not os.path.isfile(path):
        return "no project index; run: agent-spec-platform.py ingest"
    conn = db.open_ready(path, readonly=True)
    try:
        # Past requests and reviews are excluded: they hold earlier answers to the same question,
        # which would leak into an A/B run and point the model at a request id instead of a file.
        filters = {"kinds": [kind] if kind in SEARCH_KINDS else list(SEARCH_KINDS)}
        res = retrieval.search(conn, query, filters, SEARCH_HITS * 3)
        # One line per file, described by what the file says it is for (its docstring or heading),
        # not by the keyword snippet: a small model picks the right file from purposes, not matches.
        lines, seen = [], set()
        skip_tests = "test" not in query.lower()   # "which file implements X" is rarely answered by a test
        for h in res["hits"]:
            if h["source"] in seen or (skip_tests and h["source"].startswith(("tests/", "test/"))):
                continue
            seen.add(h["source"])
            head = conn.execute("SELECT body FROM chunks WHERE kind = ? AND source = ? ORDER BY start_line LIMIT 1",
                                (h["kind"], h["source"])).fetchone()
            purpose = (rag_eval._first_sentence(head[0]) if head else "")[:PURPOSE_CHARS]
            snip = re.sub(r"\s+", " ", (h.get("snippet") or "").replace("[[", "").replace("]]", "")).strip(" …")
            lines.append("[%d] %s (%s) %s | %s" % (len(lines) + 1, h["ref"], h["kind"], purpose, snip[:SNIPPET_CHARS]))
            if len(lines) == SEARCH_HITS:
                break
    finally:
        conn.close()
    return "\n".join(lines) if lines else "no matches"


def slim_digest(context: str, prompt: str) -> str:
    """The digest re-sent on every step, cut to what helps this question: the stack line and the
    remembered facts that share at least two words with the prompt. Cursor-session state (last
    session, open items, doctor, file-loading instructions) is dropped; the full digest is still
    what the sessionStart hook recorded."""
    words = {w for w in re.findall(r"[a-z][a-z0-9_]{3,}", prompt.lower())}
    keep = []
    for line in context.splitlines():
        s = line.strip()
        if s.startswith(DIGEST_KEEP):
            keep.append(s)
        elif s.startswith("- [") and len(words & set(re.findall(r"[a-z][a-z0-9_]{3,}", s.lower()))) >= 2:
            keep.append(s[:240])
    return "\n".join(keep)


def compact_history(messages: list) -> None:
    """Shrink every tool result but the latest to OLD_RESULT_CHARS: the model has already acted on
    it, and re-sending it in full on every later step is the largest token cost of a tool loop."""
    tools = [m for m in messages if m["role"] == "tool"]
    for m in tools[:-1]:
        if len(m["content"]) > OLD_RESULT_CHARS:
            m["content"] = m["content"][:OLD_RESULT_CHARS] + " …[%d chars elided]" % (len(m["content"]) - OLD_RESULT_CHARS)


def final_answer(url: str, model: str, think: bool, prompt: str, results: list, on_delta) -> dict:
    """Out of tool budget: answer from the collected results in a fresh, tool-free prompt, so a
    model that keeps emitting call JSON still has to produce prose."""
    notes = "\n\n".join(results)[-7000:]
    msgs = [{"role": "system", "content": "Answer the question using only these tool results. Name the files. Be brief."},
            {"role": "user", "content": "Question: %s\n\nTool results:\n%s" % (prompt, notes)}]
    return chat(url, model, msgs, think, on_delta, [])


TEXT_TOOLS = ("Read", "Grep", "graphify_context", "graphify_file", "search_project")
TEXT_NAMES = {n.lower(): n for n in TEXT_TOOLS}


def text_tool_calls(content: str) -> list:
    """Small models sometimes write calls as JSON text instead of tool_calls entries, and
    qwen2.5-coder:14b writes several, one per line (live test L07). Every object naming a known
    tool becomes a call; prose around them is ignored."""
    calls, dec, text, i = [], json.JSONDecoder(), content or "", 0
    while True:
        i = text.find("{", i)
        if i < 0:
            return calls
        try:
            obj, end = dec.raw_decode(text, i)
        except ValueError:
            i += 1
            continue
        name = TEXT_NAMES.get(str(obj.get("name") or "").lower()) if isinstance(obj, dict) else None
        if name:  # gpt-oss on Groq writes "grep" for Grep
            args = obj.get("arguments") or obj.get("parameters") or {}
            calls.append({"function": {"name": name, "arguments": args}})
        i = end


def save_history(store: str, messages: list) -> None:
    """Persist the chat for --resume, redacted and owner-only: prompts and tool output can carry
    secrets (a pasted key, a file the --bare arm read without the guard)."""
    fd = os.open(store, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(redact.redact_obj(messages), fh)
    os.chmod(store, 0o600)


def main(argv: list) -> int:
    if "--version" in argv:
        print(VERSION)
        return 0
    opts = parse_args(argv)
    workspace = os.path.realpath(opts["workspace"])
    if not opts["prompt"]:
        emit({"type": "result", "result": "error: no prompt"})
        return 2
    requested = opts.get("model") or os.environ.get("AGENT_SPEC_OLLAMA_MODEL")
    rem = remote(requested)
    if rem:
        provider, url, _ = rem
        if not ollama.allowed(url):
            emit({"type": "result", "result": "error: %s is a remote model; it receives the prompt and every file the "
                  "agent reads. Set AGENT_SPEC_ALLOW_REMOTE_MODELS=1 to allow it." % requested})
            return 3
        if not api_key(provider):
            var = PROVIDERS[provider][2]
            emit({"type": "result", "result": "error: no %s key: set %s or write it to %s" % (
                provider, var, os.path.join(KEY_DIR, var.lower()))})
            return 3
        model, think, tag = requested, False, requested
    else:
        found = ollama.probe(force=True)
        if not found["reachable"]:
            emit({"type": "result", "result": "error: Ollama is not reachable at " + ", ".join(ollama.candidates())})
            return 3
        url, model = found["url"], pick_model(opts.get("model"), found["models"])
        think = ollama.supports(found["models"], model, "thinking")
        tag = "ollama:" + model
    conv = opts["resume"] or str(uuid.uuid4())
    gen = str(uuid.uuid4())
    bare = opts["bare"]
    base = {"conversation_id": conv, "generation_id": gen, "model": tag,
            "cursor_version": VERSION + ("+bare" if bare else ""), "workspace_roots": [workspace], "cwd": workspace}
    hooks = Hooks(workspace, base, bare)
    tools = [t for t in TOOLS if t["function"]["name"] not in HARNESS_TOOLS] if bare else TOOLS
    os.makedirs(CHAT_DIR, mode=0o700, exist_ok=True)
    store = os.path.join(CHAT_DIR, re.sub(r"[^\w-]", "_", conv) + ".json")

    messages = []
    if opts["resume"] and os.path.isfile(store):
        with open(store, encoding="utf-8") as fh:
            messages = json.load(fh)
    else:
        context = "".join(o.get("additional_context", "") for o in hooks.fire("sessionStart", {"source": "startup"}))
        messages.append({"role": "system", "content": BARE_SYSTEM % workspace if bare else HARNESS_SYSTEM % (
            workspace, slim_digest(context, opts["prompt"]))})
        name, body = (None, "") if bare else skill_body(opts["prompt"])
        if body:  # re-sent on every step like the rest of the system prompt, so its cost is measured too
            messages[0]["content"] += "\n\n<skill name=\"%s\">\n%s\n</skill>" % (name, body)
    hooks.fire("beforeSubmitPrompt", {"prompt": opts["prompt"], "attachments": []})
    messages.append({"role": "user", "content": opts["prompt"]})
    emit({"type": "system", "subtype": "init", "session_id": conv, "request_id": gen, "model": tag})

    tokens_in = tokens_out = tool_calls = 0
    step_usage = []
    answer, loops = "", 0
    seen_calls, results = set(), []
    looping = False
    for loops in range(1, MAX_STEPS + 1):
        last = loops == MAX_STEPS or looping
        compact_history(messages)
        delta = lambda d: emit({"type": "assistant", "delta": d})  # noqa: E731
        if last:  # out of tool budget: the model answers from what it has instead of stopping empty
            reply = final_answer(url, model, think, opts["prompt"], results, delta)
        else:
            reply = chat(url, model, messages, think, delta, tools)
        tokens_in += int(reply.get("prompt_eval_count") or 0)
        tokens_out += int(reply.get("eval_count") or 0)
        step_usage.append({"step": loops, "prompt_tokens": reply.get("prompt_eval_count"),
                           **({"cached_tokens": reply["cached_tokens"]} if reply.get("cached_tokens") is not None else {}),
                           "system_chars": len(messages[0]["content"]) if not last else 0,
                           "schema_chars": len(json.dumps(tools)) if not last else 0,
                           "tool_result_chars": sum(len(m["content"]) for m in messages if m["role"] == "tool") if not last else 0})
        msg = reply.get("message") or {}
        calls = [] if last else (msg.get("tool_calls") or text_tool_calls(msg.get("content")))
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls} if calls
                        else {"role": "assistant", "content": msg.get("content") or ""})
        if not calls:
            answer = re.sub(r"<think>.*?</think>", "", msg.get("content") or "", flags=re.S).strip()
            break
        for call in calls:
            fn = call.get("function") or {}
            name, args = fn.get("name", ""), fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            key = json.dumps([name, args], sort_keys=True)
            if key in seen_calls:  # a repeated call means the model is looping: answer from the notes now
                messages.append({"role": "tool", "tool_name": name, "content": REPEAT_NOTE})
                looping = True
                continue
            seen_calls.add(key)
            tool_use_id = "tu-" + uuid.uuid4().hex[:12]
            tool_calls += 1
            logged_name = LOGGED_AS.get(name, name)
            logged_input = ({"command": "graphify-cli.py context --task " + json.dumps(args.get("task", ""))}
                            if name == "graphify_context" else
                            {"command": "graphify-cli.py query --file " + json.dumps(args.get("file", ""))}
                            if name == "graphify_file" else args)
            verdicts = hooks.fire("preToolUse", {"tool_name": logged_name, "tool_input": logged_input,
                                                 "tool_use_id": tool_use_id})
            denied = next((v for v in verdicts if v.get("permission") == "deny"), None)
            emit({"type": "tool_call", "subtype": "started", "name": logged_name, "call_id": tool_use_id, "args": logged_input})
            started = time.time()
            if denied:
                out, ok, tool_input = "denied by harness: " + str(denied.get("agent_message") or ""), False, logged_input
            else:
                logged_name, tool_input, out, ok = run_tool(workspace, name, args)
            hooks.fire("postToolUse" if ok else "postToolUseFailure",
                       {"tool_name": logged_name, "tool_input": tool_input, "tool_output": out,
                        "tool_use_id": tool_use_id, "duration": int((time.time() - started) * 1000),
                        **({} if ok else {"error_message": out[:300]})})
            emit({"type": "tool_call", "subtype": "completed", "name": logged_name, "call_id": tool_use_id,
                  "status": "completed" if ok else "error"})
            messages.append({"role": "tool", "content": out[:TOOL_OUT_CAP], "tool_name": name})
            results.append("%s %s ->\n%s" % (name, json.dumps(args)[:200], out[:1500]))
        if last:
            break
    if not answer:
        answer = "(stopped after %d tool steps without a final answer)" % loops

    hooks.fire("afterAgentResponse", {"text": answer, "input_tokens": tokens_in, "output_tokens": tokens_out})
    hooks.fire("stop", {"status": "completed", "loop_count": loops})
    save_history(store, messages)
    emit({"type": "result", "result": answer, "session_id": conv, "request_id": gen, "model": tag,
          "steps": loops, "bare": bare, "tools": tool_calls, "step_usage": step_usage,
          "usage": {"input_tokens": tokens_in, "output_tokens": tokens_out}})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except ProviderError as exc:  # a refused remote call ends the turn with a readable result line
        emit({"type": "result", "result": "error: %s" % exc})
        sys.exit(exc.code)
