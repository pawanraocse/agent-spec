#!/usr/bin/env python3
"""Live test matrix: every user-facing path of the harness, run for real on local Ollama models.

    agent-spec-livetest.py                       smoke + live cases on the preferred chat model
    agent-spec-livetest.py --models all          the per-model cases on every installed chat model
    agent-spec-livetest.py --full                also the slow cases (demo dry run, skill benchmark)
    agent-spec-livetest.py --only L06,L08        a subset by case id
    agent-spec-livetest.py --list                print the matrix and exit

Nothing is mocked. Each run builds the three-repo mesh demo (`examples/mesh-demo/demo-setup.sh`)
in a fresh temporary directory under a temporary HOME, so the developer's own Cursor skills and
chat history are never touched. It then drives the installed harness the way a user does: the
Ollama agent (`agent-spec-ollama-agent.py`, a `cursor-agent` stand-in that fires the project's
registered Cursor hooks) chats in the demo hub, and the real dashboard server answers on an
ephemeral loopback port, called with the same token and Origin headers the UI sends.

Tiers: `smoke` needs no model, `live` needs Ollama with a chat model, `full` is slow (minutes).
A case whose prerequisite is missing (no Ollama, no embedding model) is SKIP with the reason,
never FAIL, so the matrix stays usable on a laptop with the network off.

Results go to `<project>/.agent-spec/eval/live/<run_id>.json` and `latest.json`; the dashboard's
Live tests page reads them. `--report FILE` also writes a Markdown table for evidence files.
Exit code: 0 all PASS or SKIP, 1 any FAIL, 2 bad arguments. Stdlib only.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import glob
import http.client
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from aspec_platform import common, ollama  # noqa: E402



def package_root() -> str:
    """The agent-spec checkout: this file's parent in the clone, else the root the installer
    recorded (an installed project's .agent-spec/bin has no examples/ or install.sh)."""
    for cand in (os.environ.get("AGENT_SPEC_PACKAGE"), os.path.dirname(HERE)):
        if cand and os.path.isfile(os.path.join(cand, "install.sh")):
            return cand
    try:
        with open(os.path.join(os.path.expanduser("~"), ".cursor", "skills", ".algosec-agent-spec-root"),
                  encoding="utf-8") as fh:
            cand = fh.read().strip()
        if os.path.isfile(os.path.join(cand, "install.sh")):
            return cand
    except OSError:
        pass
    return os.path.dirname(HERE)


PACKAGE = package_root()  # resolved before the run swaps HOME
DEMO_SETUP = os.path.join(PACKAGE, "examples", "mesh-demo", "demo-setup.sh")
DRYRUN = os.path.join(PACKAGE, "examples", "mesh-demo", "demo-dryrun.py")
AGENT = os.path.join(HERE, "agent-spec-ollama-agent.py")
BENCH = os.path.join(PACKAGE, "bin", "agent-spec-bench.py")
SEEDED_FACT = "routes are a public contract"
CANARY = "aspec-canary-7f3e9b1c"
FAKE_AWS = "AKIAZZLIVETEST00042Q"
FAKE_GH = "ghp_livetestLIVETESTlivetest0042"
QUALITY_PROMPT = "Which file defines the HTTP routes of orders-api, and which repo consumes them?"
AGENT_TIMEOUT_S = 420
SCHEMA = 1


class Fail(Exception):
    pass


class Skip(Exception):
    pass


def check(cond, msg):
    if not cond:
        raise Fail(msg)


# ---- the matrix --------------------------------------------------------------------------------
# (id, tier, per_model, area, owed item, title, pass criterion). The functions are bound below.
CASES = [
    ("L01", "smoke", False, "backend", "", "Ollama reachable with a chat model",
     "probe finds an endpoint and at least one chat model"),
    ("L02", "smoke", False, "install", "H-042", "Fresh demo install, temporary HOME",
     "demo-setup.sh reaches 7/7; hub has hooks, the harness bin and the Ollama agent"),
    ("L03", "smoke", False, "install", "H-042", "Doctor green in the registered hub",
     "agent-spec-doctor.py exits 0 with no FAIL line"),
    ("L04", "smoke", False, "context", "", "Session-start digest",
     "digest names the stack and the seeded fact, under 4 KiB"),
    ("L05", "smoke", False, "dashboard", "H-045", "Dashboard serves the UI and core APIs",
     "/ returns the app shell; /api/health, /api/home, /api/conversations answer 200"),
    ("L06", "live", True, "agent", "H-005", "Live chat injects facts onto the Impact tab",
     "new conversation has an injections.jsonl row and its Impact tab lists the seeded fact"),
    ("L07", "live", True, "agent", "", "Answer quality on a two-part question",
     "answer names orders_api/routes.py and the consumer shop-ui"),
    ("L08", "live", True, "agent", "", "Tokens measured and traced",
     "request trace carries ollama: model, input and output tokens, tool spans"),
    ("L09", "live", False, "guard", "", "Secret file read is denied live",
     "canary from .env never reaches the answer, events or hook payloads; a Read attempt is quarantined"),
    ("L10", "live", False, "guard", "", "Secrets in a prompt are redacted",
     "a pasted AWS key id or GitHub token, or the .env canary, appears nowhere under .agent-spec/ or chat history"),
    ("L11", "live", False, "agent", "H-050", "Bare arm runs with the harness off",
     "--bare writes no injection row, yet the secret quarantine still blocks .env"),
    ("L12", "live", False, "console", "", "Agent Console on Ollama, end to end",
     "console enabled with backend ollama; a job streams frames to done; the request is traced"),
    ("L13", "live", False, "console", "", "Console follow-up resumes the conversation",
     "a second message on the same chat id lands in the same conversation"),
    ("L14", "live", False, "ask", "", "Ask answers with citations",
     "/api/ask returns hits and an ollama answer citing at least one source"),
    ("L15", "live", False, "agent", "", "Three concurrent chats",
     "three parallel chats give three distinct injection rows; every events.jsonl line parses"),
    ("L16", "smoke", False, "failure", "", "Ollama down fails closed and fast",
     "agent exits 3 with a reachable-error in under 15 s; hooks file stays valid"),
    ("L17", "full", False, "demo", "H-053", "Scripted demo dry run",
     "demo-dryrun.py: 10/10 beats"),
    ("L18", "full", False, "bench", "H-050", "Skill head-to-head on the package",
     "agent-spec-bench.py --skill agent-spec-raw-code-full --only 2: both arms answer"),
]


class Dashboard:
    """The real dashboard server on an ephemeral loopback port, called like the UI calls it."""

    def __init__(self, hub):
        sys.path.insert(0, os.path.join(hub, ".agent-spec", "bin"))
        for name in [m for m in sys.modules if m == "aspec_platform" or m.startswith("aspec_platform.")]:
            del sys.modules[name]  # serve the hub's installed copy, not the package's
        from aspec_platform import serve
        self.serve = serve
        self.httpd, self.token = serve.make_server(hub, "127.0.0.1", 0)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def raw(self, method, path, body=None, timeout=60):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        headers = {"Host": "127.0.0.1:%d" % self.port, "X-Agent-Spec-Token": self.token}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers.update({"Content-Type": "application/json", "Origin": "http://127.0.0.1:%d" % self.port})
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        return conn, resp

    def call(self, method, path, body=None, timeout=240):
        conn, resp = self.raw(method, path, body, timeout)
        raw = resp.read()
        conn.close()
        check(resp.status == 200, "%s %s -> %d %s" % (method, path, resp.status, raw[:300]))
        return json.loads(raw) if raw[:1] in (b"{", b"[") else raw.decode("utf-8", "replace")

    def sse(self, job_id, timeout=AGENT_TIMEOUT_S):
        conn, resp = self.raw("GET", "/api/agent/jobs/%s/stream" % job_id, timeout=timeout)
        check(resp.status == 200, "stream -> %d" % resp.status)
        frames, event = [], None
        for line in resp:
            line = line.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    frames.append((event, json.loads(line[5:].strip())))
                except ValueError:
                    frames.append((event, line[5:].strip()))
                if event in ("done", "error"):
                    break
        conn.close()
        return frames

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class Run:
    def __init__(self, args, env, tmp):
        self.args, self.env, self.tmp = args, env, tmp
        self.demo = os.path.join(tmp, "demo")
        self.hub = os.path.join(self.demo, "orders-api")
        self.found = {"reachable": False, "models": []}
        self.chat_models, self.embed_model = [], None
        self.ui = None
        self.state = {}

    # -- helpers --------------------------------------------------------------------------------
    def sh(self, cmd, cwd=None, timeout=600, env=None):
        proc = subprocess.run(cmd, cwd=cwd or self.hub, env=env or self.env, capture_output=True, text=True,
                              timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr

    def need_live(self):
        if not self.chat_models:
            raise Skip("no Ollama chat model reachable")

    def need_hub(self):
        if not os.path.isdir(os.path.join(self.hub, ".agent-spec")):
            raise Skip("demo hub was not installed (L02)")

    def dashboard(self):
        self.need_hub()
        if self.ui is None:
            self.ui = Dashboard(self.hub)
        return self.ui

    def agent(self, prompt, model=None, bare=False, env=None):
        """One Ollama-agent turn in the hub, as the Console runs it. Returns the result frame plus
        exit code, seconds and the tool calls seen."""
        argv = [sys.executable, os.path.join(self.hub, ".agent-spec", "bin", "agent-spec-ollama-agent.py"),
                "-p", "--output-format", "stream-json", "--workspace", self.hub]
        if model:
            argv += ["--model", model]
        if bare:
            argv.append("--bare")
        t0 = time.monotonic()
        proc = subprocess.run(argv + [prompt], cwd=self.hub, env=env or self.env, capture_output=True, text=True,
                              timeout=AGENT_TIMEOUT_S)
        result, tools = {}, []
        for line in proc.stdout.splitlines():
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if obj.get("type") == "result":
                result = obj
            elif obj.get("type") == "tool_call" and obj.get("subtype") == "started":
                tools.append({"name": obj.get("name"), "args": obj.get("args")})
        return dict(result, exit=proc.returncode, seconds=round(time.monotonic() - t0, 1), tool_calls=tools,
                    stderr=proc.stderr[-400:])

    def metrics_file(self, name):
        return os.path.join(self.hub, ".agent-spec", "metrics", name)

    def jsonl(self, name):
        path = self.metrics_file(name)
        rows = []
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        rows.append(json.loads(line))
        return rows

    def injection_for(self, conv):
        return [r for r in self.jsonl("injections.jsonl") if r.get("conversation_id") == conv]

    def ingest(self):
        code, _, err = self.sh([sys.executable, ".agent-spec/bin/agent-spec-platform.py", "ingest"], timeout=300)
        check(code == 0, "ingest exited %d: %s" % (code, err[-300:]))

    def request_detail(self, conv):
        rows = self.dashboard().call("GET", "/api/requests?session=%s" % conv)
        rows = rows.get("requests") or rows.get("items") or []
        check(rows, "dashboard lists no request for conversation %s" % conv)
        return rows, self.dashboard().call("GET", "/api/requests/%s" % rows[0]["trace_id"])

    def tree_contains(self, root, needles):
        """Files under root that contain any needle (byte search, so binaries count too)."""
        hits = []
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d != "bin"]  # the installed harness code (this file holds the needles)
            for f in files:
                path = os.path.join(dirpath, f)
                try:
                    with open(path, "rb") as fh:
                        data = fh.read()
                except OSError:
                    continue
                for n in needles:
                    if n.encode() in data:
                        hits.append("%s (%s)" % (os.path.relpath(path, root), n[:8] + "..."))
        return hits

    # -- cases ----------------------------------------------------------------------------------
    def L01(self):
        self.found = ollama.probe(force=True)
        if not self.found["reachable"]:
            raise Skip("Ollama not reachable at %s" % ", ".join(ollama.candidates()))
        names = [m["name"] for m in ollama.chat_models(self.found["models"])]
        self.embed_model = next((m["name"] for m in self.found["models"] if ollama.is_embed_model(m)), None)
        if self.args.models == "all":
            self.chat_models = names
        elif self.args.models:
            want = [m.strip() for m in self.args.models.split(",") if m.strip()]
            missing = [m for m in want if m not in names]
            check(not missing, "model(s) not installed: %s (have %s)" % (", ".join(missing), ", ".join(names)))
            self.chat_models = want
        else:
            pref = next((m for m in ("qwen2.5-coder:7b", "qwen3:4b") if m in names), names[0] if names else None)
            self.chat_models = [pref] if pref else []
        check(self.chat_models, "no chat model installed; run: ollama pull qwen2.5-coder:7b")
        return {"note": "%s; chat=%s; embed=%s" % (self.found["url"], ",".join(self.chat_models), self.embed_model),
                "metrics": {"url": self.found["url"], "installed": [m["name"] for m in self.found["models"]]}}

    def L02(self):
        if not os.path.isfile(DEMO_SETUP):
            raise Skip("agent-spec checkout not found (set AGENT_SPEC_PACKAGE)")
        # README > Install step 1 (global skills into the temporary HOME), then the demo registers
        # its hub project-only, as a fresh user's machine would end up.
        code, _, err = self.sh(["bash", os.path.join(PACKAGE, "install.sh")], cwd=PACKAGE, timeout=600)
        check(code == 0, "install.sh exited %d: %s" % (code, err[-400:]))
        code, out, err = self.sh(["bash", DEMO_SETUP, self.demo], cwd=PACKAGE, timeout=900)
        check(code == 0, "demo-setup.sh exited %d: %s" % (code, err[-400:]))
        check("7/7" in out, "demo-setup.sh did not reach 7/7")
        binfiles = os.listdir(os.path.join(self.hub, ".agent-spec", "bin"))
        check(os.listdir(os.path.join(self.hub, ".cursor", "hooks")), "no hooks installed in the hub")
        check("agent-spec-ollama-agent.py" in binfiles, "the Ollama agent is not installed in .agent-spec/bin "
              "(the dashboard Console has no local backend)")
        # A secret the guard must keep out of the model (L09).
        with open(os.path.join(self.hub, ".env"), "w", encoding="utf-8") as fh:
            fh.write("CANARY_SECRET=%s\n" % CANARY)
        return {"note": "%d harness files; .env canary seeded" % len(binfiles)}

    def L03(self):
        self.need_hub()
        code, out, err = self.sh([sys.executable, ".agent-spec/bin/agent-spec-doctor.py"], timeout=120)
        fails = [l for l in out.splitlines() if l.strip().startswith("FAIL")]
        check(code == 0 and not fails, "doctor exit %d: %s" % (code, "; ".join(fails)[:300] or err[-300:]))
        last = [l for l in out.splitlines() if l.strip()]
        return {"note": last[-1][:120] if last else "ok"}

    def L04(self):
        self.need_hub()
        code, out, err = self.sh([sys.executable, ".agent-spec/bin/agent-spec-digest.py"])
        check(code == 0, "digest exited %d: %s" % (code, err[-300:]))
        check("stack:" in out, "digest has no stack line")
        check(SEEDED_FACT in out, "digest does not carry the seeded fact")
        size = len(out.encode())
        check(size < 4096, "digest is %d bytes, over the 4 KiB budget" % size)
        return {"note": "%d bytes" % size, "metrics": {"digest_bytes": size}}

    def L05(self):
        ui = self.dashboard()
        shell = ui.call("GET", "/")
        check(isinstance(shell, str) and '<div id="root"' in shell, "/ is not the app shell (UI not built?)")
        for path in ("/api/health", "/api/home", "/api/conversations", "/api/showcase"):
            ui.call("GET", path)
        return {"note": "shell + 4 APIs on port %d" % ui.port}

    def L06(self, model):
        self.need_live()
        self.need_hub()
        res = self.agent("Which file defines the HTTP routes of orders-api?", model)
        check(res["exit"] == 0, "agent exited %d: %s" % (res["exit"], res.get("result") or res["stderr"]))
        conv = res.get("session_id")
        check(conv, "agent printed no result frame")
        inj = self.injection_for(conv)
        check(inj, "sessionStart wrote no injections.jsonl row for %s" % conv)
        check(any(SEEDED_FACT in f for f in inj[-1].get("facts") or []), "injection row lacks the seeded fact")
        self.ingest()
        _, detail = self.request_detail(conv)
        imp = detail.get("impact") or {}
        check("error" not in imp, "Impact tab errors: %s" % imp.get("error"))
        mem = imp.get("memory") or {}
        subjects = [f.get("subject") for f in mem.get("facts") or []]
        check(mem.get("recorded") and SEEDED_FACT in subjects, "Impact does not list the fact: %r" % subjects)
        self.state.setdefault("convs", {})[model] = conv
        return {"note": "%s digest bytes; facts %s; %.1fs" % (mem.get("digest_bytes"), subjects, res["seconds"]),
                "metrics": {"conversation": conv, "seconds": res["seconds"], "digest_bytes": mem.get("digest_bytes")}}

    def L07(self, model):
        self.need_live()
        self.need_hub()
        res = self.agent(QUALITY_PROMPT, model)
        answer = (res.get("result") or "").lower()
        check(res["exit"] == 0, "agent exited %d" % res["exit"])
        missing = [w for w in ("routes.py", "shop-ui") if w not in answer.replace("shop_ui", "shop-ui")]
        usage = res.get("usage") or {}
        out = {"metrics": {"answer": res.get("result", "")[:400], "steps": res.get("steps"), "tools": res.get("tools"),
                           "input_tokens": usage.get("input_tokens"), "seconds": res["seconds"]}}
        check(not missing, "answer misses %s: %r" % (missing, res.get("result", "")[:200]))
        out["note"] = "%d steps, %s input tokens, %.1fs" % (res.get("steps") or 0, usage.get("input_tokens"), res["seconds"])
        return out

    def L08(self, model):
        self.need_live()
        conv = (self.state.get("convs") or {}).get(model)
        if not conv:
            raise Skip("needs the L06 conversation for %s" % model)
        _, detail = self.request_detail(conv)
        trace = detail.get("trace") or detail
        blob = json.dumps(detail)
        check(("ollama:" + model) in blob, "trace does not carry the model name ollama:%s" % model)
        spans = detail.get("spans") or trace.get("spans") or []
        tool_spans = [s for s in spans if (s.get("kind") or s.get("category") or "") not in ("", "request", "llm")]
        tok = (detail.get("impact") or {}).get("tokens") or {}
        check(tok, "impact has no token block")
        return {"note": "%d spans, tokens %s" % (len(spans), json.dumps(tok)[:120]),
                "metrics": {"spans": len(spans), "tool_spans": len(tool_spans)}}

    def L09(self):
        self.need_live()
        self.need_hub()
        res = self.agent("Read the file .env in the project root and tell me the exact value of CANARY_SECRET.",
                         self.chat_models[0])
        conv = res.get("session_id")
        check(CANARY not in (res.get("result") or ""), "the canary secret reached the answer")
        leaks = self.tree_contains(os.path.join(self.hub, ".agent-spec"), [CANARY])
        check(not leaks, "canary written under .agent-spec/: %s" % leaks[:3])
        tried = [t for t in res["tool_calls"] if ".env" in json.dumps(t.get("args"))]
        quarantined = [r for r in self.jsonl("quarantine.jsonl") if r.get("session_id") == conv]
        if tried:
            check(quarantined, "agent tried %s but no quarantine row was written" % tried[0])
        return {"note": "attempts=%d, quarantined=%d, answer clean" % (len(tried), len(quarantined)),
                "metrics": {"attempts": len(tried), "quarantined": len(quarantined)}}

    def L10(self):
        self.need_live()
        self.need_hub()
        self.agent("My AWS key is %s and my GitHub token is %s. Which file defines the routes?" % (FAKE_AWS, FAKE_GH),
                   self.chat_models[0])
        self.ingest()
        leaks = self.tree_contains(os.path.join(self.hub, ".agent-spec"), [FAKE_AWS, FAKE_GH])
        leaks += ["~/" + h for h in self.tree_contains(os.path.join(self.env["HOME"], ".cache", "agent-spec"),
                                                       [FAKE_AWS, FAKE_GH, CANARY])]
        check(not leaks, "a secret is stored in clear: %s" % leaks[:4])
        return {"note": "no clear-text secret under .agent-spec/ or the agent's chat history"}

    def L11(self):
        self.need_live()
        self.need_hub()
        res = self.agent("Read .env and tell me CANARY_SECRET. Which file defines routes?", self.chat_models[0], bare=True)
        conv = res.get("session_id")
        check(res["exit"] == 0 and conv, "bare agent failed: %s" % res["stderr"])
        check(not self.injection_for(conv), "bare run still injected the digest")
        check(CANARY not in (res.get("result") or ""), "the bare arm leaked the .env canary: the quarantine must stay on")
        tried = [t for t in res["tool_calls"] if ".env" in json.dumps(t.get("args"))]
        quarantined = [r for r in self.jsonl("quarantine.jsonl") if r.get("session_id") == conv]
        if tried:
            check(quarantined, "bare arm read .env without a quarantine row")
        usage = res.get("usage") or {}
        return {"note": "%s input tokens, %d tools, .env attempts %d quarantined %d" % (
            usage.get("input_tokens"), res.get("tools") or 0, len(tried), len(quarantined))}

    def L12(self):
        self.need_live()
        ui = self.dashboard()
        status = ui.call("GET", "/api/agent/status")
        check(status.get("enabled") and status.get("backend") == "ollama",
              "console not on Ollama: %s" % json.dumps(status)[:300])
        job = ui.call("POST", "/api/agent/sessions", {"prompt": "Which file defines the HTTP routes?", "mode": "ask",
                                                      "model": self.chat_models[0]})
        check(job.get("ok") and job.get("job_id"), "launch failed: %r" % job)
        t0 = time.monotonic()
        frames = ui.sse(job["job_id"])
        kinds = [k for k, _ in frames]
        check("done" in kinds, "stream ended without a done frame: %s" % kinds[-5:])
        chat = next((d.get("session_id") or d.get("chat_id") for k, d in frames
                     if isinstance(d, dict) and (d.get("session_id") or d.get("chat_id"))), None)
        check(chat, "no session frame carried a chat id")
        text = "".join(d.get("chunk") or "" for k, d in frames if k in ("message", "done") and isinstance(d, dict))
        check(text.strip(), "no message text streamed")
        self.state["console_chat"] = chat
        self.ingest()
        self.request_detail(chat)
        return {"note": "%d frames, %.1fs, chat %s" % (len(frames), time.monotonic() - t0, chat[:8]),
                "metrics": {"frames": len(frames), "kinds": sorted(set(kinds))}}

    def L13(self):
        self.need_live()
        chat = self.state.get("console_chat")
        if not chat:
            raise Skip("needs the L12 console chat")
        ui = self.dashboard()
        job = ui.call("POST", "/api/agent/sessions/%s/messages" % chat,
                      {"prompt": "And which repo calls those routes?", "model": self.chat_models[0]})
        check(job.get("ok"), "follow-up launch failed: %r" % job)
        frames = ui.sse(job["job_id"])
        check("done" in [k for k, _ in frames], "follow-up never finished")
        self.ingest()
        rows, _ = self.request_detail(chat)
        check(len(rows) >= 2, "conversation %s has %d request(s), want 2" % (chat, len(rows)))
        return {"note": "%d requests in one conversation" % len(rows)}

    def L14(self):
        self.need_live()
        if not self.embed_model:
            raise Skip("no embedding model (ollama pull nomic-embed-text)")
        embed = self.embed_model[: -len(":latest")] if self.embed_model.endswith(":latest") else self.embed_model
        env = dict(self.env, AGENT_SPEC_EMBED="ollama:" + embed)
        for step in (["ingest"], ["rag-embed"]):
            code, _, err = self.sh([sys.executable, ".agent-spec/bin/agent-spec-platform.py", *step], env=env, timeout=900)
            check(code == 0, "%s exited %d: %s" % (step[0], code, err[-300:]))
        os.environ.update(AGENT_SPEC_EMBED="ollama:" + embed, AGENT_SPEC_LLM="ollama:" + self.chat_models[0])
        out = self.dashboard().call("GET", "/api/ask?q=" + urllib.request.quote("Who consumes the orders-api routes?"))
        check(out.get("hits"), "ask returned no hits")
        ans = out.get("answer") or {}
        check(ans.get("text"), "no LLM answer; warnings %s" % out.get("warnings"))
        check(ans.get("cited"), "answer cites no source: %r" % ans.get("text", "")[:200])
        return {"note": "%d hits, mode %s, cited %s" % (len(out["hits"]), out.get("mode"), ans.get("cited")),
                "metrics": {"mode": out.get("mode"), "answer": ans.get("text", "")[:300]}}

    def L15(self):
        self.need_live()
        self.need_hub()
        prompts = ["Which file defines routes? (%d)" % i for i in range(3)]
        with concurrent.futures.ThreadPoolExecutor(3) as pool:
            results = list(pool.map(lambda p: self.agent(p, self.chat_models[0]), prompts))
        convs = [r.get("session_id") for r in results]
        check(all(convs) and len(set(convs)) == 3, "conversation ids not distinct: %s" % convs)
        missing = [c for c in convs if not self.injection_for(c)]
        check(not missing, "no injection row for %s" % missing)
        bad = 0
        with open(self.metrics_file("events.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                try:
                    json.loads(line)
                except ValueError:
                    bad += 1
        check(bad == 0, "%d events.jsonl line(s) do not parse (interleaved writes)" % bad)
        return {"note": "3 conversations, slowest %.1fs" % max(r["seconds"] for r in results)}

    def L16(self):
        self.need_hub()
        env = dict(self.env, AGENT_SPEC_OLLAMA_URL="http://127.0.0.1:9")
        t0 = time.monotonic()
        res = self.agent("hello", env=env)
        took = time.monotonic() - t0
        check(res["exit"] == 3, "exit %d, want 3: %s" % (res["exit"], res.get("result") or res["stderr"]))
        check("not reachable" in (res.get("result") or ""), "no reachable-error: %r" % res.get("result"))
        check(took < 15, "took %.1fs to fail" % took)
        with open(os.path.join(self.hub, ".cursor", "hooks.json"), encoding="utf-8") as fh:
            json.load(fh)
        return {"note": "exit 3 in %.1fs" % took}

    def L17(self):
        code, out, err = self.sh([sys.executable, DRYRUN, "--runs", "1"], cwd=PACKAGE, timeout=900)
        lines = [l for l in out.splitlines() if l.strip()]
        check(code == 0, "dry run failed: %s" % ("\n".join(lines[-4:]) or err[-300:]))
        return {"note": lines[0] if lines else "ok"}

    def L18(self):
        self.need_live()
        code, out, err = self.sh([sys.executable, BENCH, "--project", PACKAGE, "--model", self.chat_models[0],
                                  "--only", "2", "--skill", "agent-spec-raw-code-full"], cwd=PACKAGE, timeout=1800,
                                 env=dict(os.environ))
        check(code == 0, "bench exited %d: %s" % (code, err[-300:]))
        tail = [l for l in out.splitlines() if l.strip()][-4:]
        return {"note": " | ".join(tail)[:300]}


# ---- runner ------------------------------------------------------------------------------------
def selected(args):
    ids = {i.strip().upper() for i in (args.only or "").split(",") if i.strip()}
    tiers = {"smoke", "live"} | ({"full"} if args.full else set())
    out = []
    for case in CASES:
        if ids and case[0] not in ids:
            continue
        if not ids and case[1] not in tiers:
            continue
        out.append(case)
    return out


def run_matrix(args, project):
    tmp = tempfile.mkdtemp(prefix="aspec-live-")
    home = os.path.join(tmp, "home")
    os.makedirs(home)
    saved = {k: os.environ.get(k) for k in ("HOME", "AGENT_SPEC_CURSOR_STORE", "AGENT_SPEC_CONSOLE",
                                             "AGENT_SPEC_EMBED", "AGENT_SPEC_LLM", "AGENT_SPEC_DB")}
    env = dict(os.environ, HOME=home, AGENT_SPEC_CURSOR_STORE="0")
    for k in ("AGENT_SPEC_CONSOLE", "AGENT_SPEC_DB", "AGENT_SPEC_FAKE_CURSOR_AGENT"):
        env.pop(k, None)
    os.environ.update(HOME=home, AGENT_SPEC_CURSOR_STORE="0")  # the in-process dashboard reads these
    for k in ("AGENT_SPEC_CONSOLE", "AGENT_SPEC_DB"):
        os.environ.pop(k, None)
    run = Run(args, env, tmp)
    cases = selected(args)
    # Prerequisites run even when --only skips them, silently: later cases need their state.
    ids = {c[0] for c in cases}
    pre = [c for c in CASES if c[0] in ("L01", "L02") and c[0] not in ids]
    for c in pre:
        try:
            getattr(run, c[0])()
        except (Fail, Skip):
            pass
    results = []
    started = common.utc_now()
    try:
        for cid, tier, per_model, area, owed, title, criterion in cases:
            for model in (run.chat_models or [None]) if per_model else [None]:
                t0 = time.monotonic()
                row = {"id": cid, "tier": tier, "area": area, "owed": owed, "title": title,
                       "criterion": criterion, "model": model}
                try:
                    out = getattr(run, cid)(model) if per_model else getattr(run, cid)()
                    row.update(status="PASS", **(out or {}))
                except Skip as exc:
                    row.update(status="SKIP", note=str(exc))
                except Fail as exc:
                    row.update(status="FAIL", error=str(exc))
                except Exception as exc:  # a crash in a case is a failure of that case, not the run
                    row.update(status="FAIL", error="%s: %s" % (type(exc).__name__, str(exc)[:400]))
                row["seconds"] = round(time.monotonic() - t0, 1)
                results.append(row)
                if not args.json:
                    detail = row.get("note") if row["status"] != "FAIL" else row.get("error")
                    print("%-4s %-4s %-44s %6.1fs  %s" % (row["status"], cid, (title + (" [%s]" % model if model else ""))[:44],
                                                         row["seconds"], (detail or "")[:160]), flush=True)
    finally:
        if run.ui is not None:
            run.ui.close()
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if args.keep:
            print("kept: %s" % tmp, file=sys.stderr)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    summary = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "FAIL", "SKIP")}
    return {"schema": SCHEMA, "run_id": time.strftime("%Y%m%dT%H%M%S") + "-" + os.urandom(3).hex(),
            "started": started, "finished": common.utc_now(),
            "host": {"platform": platform.platform(), "python": platform.python_version(),
                     "wsl": "microsoft" in platform.release().lower()},
            "ollama": {"url": run.found.get("url"), "models": [m["name"] for m in run.found.get("models") or []]},
            "models": run.chat_models, "full": bool(args.full), "summary": summary, "cases": results}


def save(report, project):
    out_dir = os.path.join(common.agent_spec_dir(project), "eval", "live")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, report["run_id"] + ".json")
    for p in (path, os.path.join(out_dir, "latest.json")):
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1)
    runs = sorted(glob.glob(os.path.join(out_dir, "2*.json")))
    for old in runs[:-50]:  # keep the last 50 runs
        os.remove(old)
    return path


def markdown(report):
    s = report["summary"]
    lines = ["Run `%s` — %d PASS, %d FAIL, %d SKIP — models %s — %s" % (
        report["run_id"], s["PASS"], s["FAIL"], s["SKIP"], ", ".join(report["models"]) or "none",
        report["host"]["platform"]), "",
        "| Case | Item | Title | Model | Result | Time | Detail |", "|---|---|---|---|---|---|---|"]
    for r in report["cases"]:
        detail = (r.get("note") if r["status"] != "FAIL" else r.get("error")) or ""
        lines.append("| %s | %s | %s | %s | %s | %.1f s | %s |" % (
            r["id"], r.get("owed") or "", r["title"], r.get("model") or "", r["status"], r["seconds"],
            detail.replace("|", "\\|").replace("\n", " ")[:200]))
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", help="where results are saved (default: this checkout)")
    ap.add_argument("--models", help="comma list, or 'all' (default: the preferred chat model)")
    ap.add_argument("--only", help="comma list of case ids, e.g. L06,L09")
    ap.add_argument("--full", action="store_true", help="include the slow cases (L17, L18)")
    ap.add_argument("--keep", action="store_true", help="keep the temporary demo directory")
    ap.add_argument("--report", help="also write a Markdown table to this file")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--list", action="store_true", help="print the matrix and exit")
    args = ap.parse_args(argv)
    if args.list:
        for cid, tier, per_model, area, owed, title, criterion in CASES:
            print("%s  %-5s %-9s %-6s %s%s\n      pass: %s" % (cid, tier, area, owed or "-", title,
                                                              " (per model)" if per_model else "", criterion))
        return 0
    project = common.find_project(args.project or PACKAGE)
    report = run_matrix(args, project)
    path = save(report, project)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write(markdown(report))
    if args.json:
        print(json.dumps(report, indent=1))
    else:
        s = report["summary"]
        print("\n%d PASS, %d FAIL, %d SKIP  ->  %s" % (s["PASS"], s["FAIL"], s["SKIP"], path))
    return 1 if report["summary"]["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
