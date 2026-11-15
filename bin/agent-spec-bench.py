#!/usr/bin/env python3
"""Harness A/B benchmark on a free local model: the same prompts, the same Ollama model, run
once with the agent-spec harness (digest, graph tool, input-discipline guard) and once bare.

    agent-spec-bench.py [--model qwen2.5-coder:7b] [--only N] [--project DIR]

Cases come from `.agent-spec/eval/agent-bench.jsonl`, one `{"prompt", "expect": [..]}` per line;
an answer is correct when it mentions every `expect` string (case-insensitive), so accuracy is
a measured check, not a judgment. Each run appends one row per prompt and arm to
`.agent-spec/eval/agent-bench-results.jsonl` with Ollama's measured token counts, the tool
calls, wall time and the request id, which links to the full trace in the dashboard. Both arms
are traced through the project's hooks, so the dashboard shows them like any other request.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.join(HERE, "agent-spec-ollama-agent.py")
sys.path.insert(0, HERE)
from aspec_platform import common  # noqa: E402

TIMEOUT_S = 600


def eval_dir(project: str) -> str:
    return os.path.join(common.agent_spec_dir(project), "eval")


def load_cases(project: str) -> list:
    path = os.path.join(eval_dir(project), "agent-bench.jsonl")
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                row = json.loads(line)
                if row.get("prompt") and isinstance(row.get("expect"), list):
                    out.append(row)
    return out


def run_arm(project: str, prompt: str, model: str | None, bare: bool) -> dict:
    argv = [sys.executable, AGENT, "-p", "--output-format", "stream-json", "--workspace", project]
    if model:
        argv += ["--model", model]
    if bare:
        argv.append("--bare")
    started = time.time()
    proc = subprocess.run(argv + [prompt], capture_output=True, text=True, timeout=TIMEOUT_S)
    result = {}
    for line in proc.stdout.splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("type") == "result":
            result = obj
    usage = result.get("usage") or {}
    return {"answer": result.get("result") or proc.stderr[-300:], "request_id": result.get("request_id"),
            "model": result.get("model"), "tokens_in": usage.get("input_tokens"), "tokens_out": usage.get("output_tokens"),
            "tools": result.get("tools"), "steps": result.get("steps"), "ms": int((time.time() - started) * 1000),
            "exit": proc.returncode}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project")
    ap.add_argument("--model")
    ap.add_argument("--only", type=int, help="first N cases")
    args = ap.parse_args(argv)
    project = common.find_project(args.project)
    cases = load_cases(project)[: args.only or None]
    run_id = time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    out_path = os.path.join(eval_dir(project), "agent-bench-results.jsonl")
    rows = []
    for i, case in enumerate(cases, 1):
        for arm in ("harness", "bare"):
            r = run_arm(project, case["prompt"], args.model, arm == "bare")
            text = (r["answer"] or "").lower()
            r.update(run_id=run_id, ts=common.utc_now(), case=i, arm=arm, prompt=case["prompt"], expect=case["expect"],
                     correct=r["exit"] == 0 and all(e.lower() in text for e in case["expect"]))
            r["answer"] = (r["answer"] or "")[:600]
            rows.append(r)
            with open(out_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(r) + "\n")
            print("case %d %-7s correct=%-5s in=%-6s out=%-5s tools=%-2s %5.1fs" % (
                i, arm, r["correct"], r["tokens_in"], r["tokens_out"], r["tools"], r["ms"] / 1000), flush=True)
    for arm in ("harness", "bare"):
        rs = [r for r in rows if r["arm"] == arm]
        if rs:
            print("%-7s accuracy=%d/%d tokens_in=%d tools=%d time=%.0fs" % (
                arm, sum(r["correct"] for r in rs), len(rs), sum(r["tokens_in"] or 0 for r in rs),
                sum(r["tools"] or 0 for r in rs), sum(r["ms"] for r in rs) / 1000))
    print("results -> %s (run %s)" % (out_path, run_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
