#!/usr/bin/env python3
"""One command to run the whole harness live on free local models, no Cursor plan needed.

    agent-spec-live.py [--project DIR] [--port 8765] [--bench] [--no-serve]

1. finds Ollama (loopback, or the Windows host under WSL) and picks a chat model;
2. pulls the embedding model when it is missing (nomic-embed-text, ~274 MB, once);
3. ingests traces, memory and the project index, then embeds every chunk;
4. scores retrieval (`rag-eval`, which also tunes the hybrid fusion weight) when no score exists;
5. with --bench, runs the harness-vs-bare A/B benchmark (bin/agent-spec-bench.py);
6. starts the dashboard with the Agent Console on the local model, and the Ask page answering
   with that model (AGENT_SPEC_LLM), and prints the URL.

Everything stays on the machine. Re-running is cheap: each step skips work already done.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from aspec_platform import common, ollama  # noqa: E402

EMBED_MODEL = "nomic-embed-text"
CHAT_PREFERENCE = ("qwen2.5-coder:7b", "qwen3:4b")


def step(msg: str) -> None:
    print("==> " + msg, flush=True)


def platform(*args, env) -> int:
    return subprocess.call([sys.executable, os.path.join(HERE, "agent-spec-platform.py"), *args], env=env)


def pull(url: str, model: str) -> None:
    req = urllib.request.Request(url + "/api/pull", data=json.dumps({"model": model, "stream": False}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as resp:  # noqa: S310 — ollama.allowed() endpoint
        print("    " + resp.read().decode()[:200])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--bench", action="store_true", help="run the harness A/B benchmark before serving")
    ap.add_argument("--no-serve", action="store_true")
    args = ap.parse_args(argv)
    project = common.find_project(args.project)

    step("Ollama")
    found = ollama.probe(force=True)
    if not found["reachable"]:
        print("error: Ollama is not reachable at %s. Start Ollama, then re-run." % ", ".join(ollama.candidates()), file=sys.stderr)
        return 2
    chat = [m["name"] for m in ollama.chat_models(found["models"])]
    model = next((m for m in CHAT_PREFERENCE if m in chat), chat[0] if chat else None)
    if not model:
        print("error: no chat model installed; run: ollama pull qwen2.5-coder:7b", file=sys.stderr)
        return 2
    print("    %s  chat=%s" % (found["url"], model))
    if not any(ollama.is_embed_model(m) for m in found["models"]):
        step("pulling %s (one time)" % EMBED_MODEL)
        pull(found["url"], EMBED_MODEL)
    embed = next((m["name"] for m in found["models"] if ollama.is_embed_model(m)), EMBED_MODEL)
    embed = embed[: -len(":latest")] if embed.endswith(":latest") else embed
    env = dict(os.environ, AGENT_SPEC_EMBED="ollama:" + embed, AGENT_SPEC_LLM="ollama:" + model,
               AGENT_SPEC_OLLAMA_MODEL=model)

    step("ingest + index")
    platform("ingest", "--project", project, env=env)
    step("embed index chunks (%s)" % env["AGENT_SPEC_EMBED"])
    platform("rag-embed", "--project", project, env=env)

    from aspec_platform import db, rag_eval
    conn = db.open_ready(db.db_path(project), readonly=True)
    try:
        scored = rag_eval.latest(conn)
    finally:
        conn.close()
    if not scored or scored.get("embedder") is None:
        step("RAG accuracy eval (tunes the fusion weight)")
        platform("rag-eval", "--project", project, "--no-refresh", "--label", "agent-spec-live", env=env)
    if args.bench:
        step("harness A/B benchmark on %s" % model)
        subprocess.call([sys.executable, os.path.join(HERE, "agent-spec-bench.py"), "--project", project, "--model", model], env=env)
        platform("ingest", "traces", "--project", project, env=env)
    if args.no_serve:
        return 0
    step("dashboard (Ctrl-C to stop): Showcase, Console, Ask all run on %s" % model)
    return platform("serve", "--project", project, "--port", str(args.port), env=env)


if __name__ == "__main__":
    sys.exit(main())
