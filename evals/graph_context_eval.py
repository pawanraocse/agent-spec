#!/usr/bin/env python3
"""Recall of `graphify-cli.py context` against this repository's own git history.

Each recent commit is one case: its subject (conventional-commit prefix stripped) is the
task, and the files it changed that are still in the graph are the answer. A ranking that
puts those files in the first k results would have saved the agent the search.

    python3 evals/graph_context_eval.py            # from the project root, after a graph build
    python3 evals/graph_context_eval.py --commits 500 --cli path/to/graphify-cli.py

Prints hit@k (any changed file in the top k) and recall@k (share of changed files found).
Tune the weights in graphify-cli.py against this, not against a single hand-picked task.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_cli(path):
    spec = importlib.util.spec_from_file_location("graphify_cli", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cases(graph, commits):
    ids = {n["id"] for n in graph["nodes"]}
    log = subprocess.run(["git", "log", "-%d" % commits, "--no-merges", "--name-only", "--format=@@%s"],
                         capture_output=True, text=True, check=True).stdout
    out = []
    for block in log.split("@@")[1:]:
        lines = [l for l in block.strip().splitlines() if l]
        if not lines:
            continue
        subject = re.sub(r"^\w+(\([^)]*\))?!?:\s*", "", lines[0])
        files = {f for f in lines[1:] if f in ids}
        # One to eight files: a commit touching thirty is a sweep, not a task a ranking answers.
        if 1 <= len(files) <= 8 and not subject.lower().startswith(("merge", "session")):
            out.append((subject, files))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cli", default=os.path.join(ROOT, "bin", "graphify-cli.py"))
    ap.add_argument("--graph", default=os.path.join(".agent-spec", "graph", "knowledge-graph.json"))
    ap.add_argument("--commits", type=int, default=300)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    cli = load_cli(args.cli)
    with open(args.graph, encoding="utf-8") as fh:
        graph = json.load(fh)
    fan_in = {}
    for e in graph.get("edges", []):
        fan_in[e["target"]] = fan_in.get(e["target"], 0) + 1

    rows = cases(graph, args.commits)
    if not rows:
        print("no usable commits (need history that touches files still in the graph)", file=sys.stderr)
        return 1
    result = {"cases": len(rows)}
    for k in (4, 12):
        hit = recall = 0.0
        for subject, gold in rows:
            words = []
            for w in cli._id_words(subject):
                if w not in cli._STOP and w not in words:
                    words.append(w)
            got = set(cli._rank(cli._score_files(graph, words), fan_in, subject)[:k])
            found = len(got & gold)
            hit += found > 0
            recall += found / len(gold)
        result["hit@%d" % k] = round(hit / len(rows), 4)
        result["recall@%d" % k] = round(recall / len(rows), 4)
    if args.json:
        print(json.dumps(result))
    else:
        print("%d cases  hit@4=%.0f%%  recall@4=%.0f%%  hit@12=%.0f%%  recall@12=%.0f%%" % (
            result["cases"], result["hit@4"] * 100, result["recall@4"] * 100,
            result["hit@12"] * 100, result["recall@12"] * 100))
    return 0


if __name__ == "__main__":
    sys.exit(main())
