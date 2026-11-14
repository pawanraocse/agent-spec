#!/usr/bin/env python3
"""graphify-mesh.py — multi-repo Graphify (P3-001).

  graphify-mesh.py add PATH [--id ID]   build PATH's graph into the hub and record it in mesh.json
  graphify-mesh.py remove ID            drop a member and its graph
  graphify-mesh.py build [--refresh]    merge member graphs into .agent-spec/graph/mesh-graph.json
  graphify-mesh.py stats [--json]       repos, cross-repo edges per pair, connected components
  graphify-mesh.py query --file REPO:PATH [--depth N] [--json]
                                        a file's cross-repo edges and cross-repo blast radius

The hub is the project in the current directory. Member graphs live at
`.agent-spec/mesh/<repo_id>/knowledge-graph.json` and are built with
`graphify-build.py --out`, so a member repo's working tree is never written to.

A cross-repo edge exists only where an import token in one repo equals the qualified name of a
file in another: the Java/Kotlin FQN after the source root, or the Python module path from the
topmost package. Suffixes are never matched across repos. A token that names files in two or
more other repos is recorded as `imports_ambiguous`.

Cross-repo `http` edges match a call's target to a repo by service identity (repo id, service
names, `.agent-spec/mesh-aliases.json`), then its path to that repo's routes; a call with no
identity matches by path alone and is only ever `http_ambiguous`. `message` edges join the
same topic string across repos. Design: docs/IMPLEMENTATION-GUIDE.md, "LLD addendum — P3-001"
and "LLD addendum — P3-002 step 3".

Allowed-code reason: exact computation (graph merge and name resolution). Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "graphify-build.py")
JVM_ROOTS = ("java", "kotlin", "scala", "groovy")
JVM_EXT = (".java", ".kt", ".scala", ".groovy")
LOOPBACK = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
CONFIDENT = ("imports", "http", "message")
MIN_GRAPH = (5, 3)              # first graph version with http_calls
MAX_PATH_ONLY_HITS = 10         # path-only matches per call; beyond that the path says nothing
_PARAM = re.compile(r"^(\{.*\}|:.+|<.+>)$")
_K8S_HOST = re.compile(r"^([a-z0-9-]+)\.[a-z0-9-]+\.svc(?:\.cluster\.local)?$")


def hub_paths(hub: str) -> dict:
    base = os.path.join(hub, ".agent-spec")
    return {"manifest": os.path.join(base, "mesh.json"), "members": os.path.join(base, "mesh"),
            "out": os.path.join(base, "graph", "mesh-graph.json")}


def load_manifest(hub: str) -> dict:
    try:
        with open(hub_paths(hub)["manifest"], encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("repos"), list):
            return data
    except (OSError, ValueError):
        pass
    return {"version": 1, "repos": []}


def load_aliases(hub: str) -> dict:
    """Optional `.agent-spec/mesh-aliases.json`: {called name: repo_id}. Missing or malformed -> {}."""
    try:
        with open(os.path.join(hub, ".agent-spec", "mesh-aliases.json"), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k).lower(): str(v) for k, v in data.items() if k and v}


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(path + ".tmp", path)


def repo_id_for(path: str, given: str | None) -> str:
    rid = (given or os.path.basename(os.path.abspath(path).rstrip("/"))).lower()
    rid = re.sub(r"[^a-z0-9-]+", "-", rid).strip("-")
    if not rid:
        raise SystemExit("error: cannot derive a repo id from %r; pass --id" % path)
    return rid


def build_member(hub: str, entry: dict) -> None:
    out = os.path.join(hub_paths(hub)["members"], entry["repo_id"])
    proc = subprocess.run([sys.executable, BUILD, "--quiet", "--out", out], cwd=entry["path"],
                          capture_output=True, text=True)
    graph = os.path.join(out, "knowledge-graph.json")
    if proc.returncode != 0 or not os.path.isfile(graph):
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ["no output"]
        raise SystemExit("error: graph build failed for %s: %s" % (entry["path"], tail[0]))
    with open(graph, "rb") as fh:
        entry["graph_sha"] = hashlib.sha1(fh.read()).hexdigest()
    entry["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def qualified_names(path: str, packages: set) -> list:
    """The dotted names another repo can import this file by (never bare suffixes)."""
    stem, ext = os.path.splitext(path)
    parts = stem.split("/")
    if ext in JVM_EXT:
        # The source root is the first java/kotlin/... directory, preferring one under
        # src/main or src/test: a package may itself contain a `java` segment.
        roots = [i for i, p in enumerate(parts[:-1]) if p in JVM_ROOTS]
        std = [i for i in roots if i > 0 and parts[i - 1] in ("main", "test", "src")]
        tail = parts[(std or roots)[0] + 1:] if roots else parts
        return [".".join(tail)] if len(tail) >= 2 else []
    if ext == ".py":
        if parts[-1] == "__init__":
            parts = parts[:-1]
            top = len(parts)
        else:
            top = len(parts) - 1
        while top > 0 and "/".join(parts[:top]) in packages:
            top -= 1
        tail = parts[top:]
        return [".".join(tail)] if len(tail) >= 2 else []
    return []


def graph_version(g: dict) -> tuple:
    try:
        return tuple(int(x) for x in str(g.get("version", "0")).split("."))
    except ValueError:
        return (0,)


def _segments(path: str) -> list:
    return [x for x in (path or "").split("/") if x]


def _literals(segs: list) -> int:
    return sum(1 for x in segs if not _PARAM.match(x) and "*" not in x)


def _seg_eq(a: str, b: str) -> bool:
    if a == b or _PARAM.match(a) or _PARAM.match(b):
        return True
    return b.startswith("*.") and a.endswith(b[1:])  # servlet extension mapping


def path_match(call: str, route: str) -> bool:
    """Whole-path match; `{x}`, `:x`, `<x>` match one segment, a trailing `/*` matches a prefix."""
    c, r = _segments(call), _segments(route)
    if r and r[-1] == "*":
        r = r[:-1]
        if len(c) < len(r):
            return False
        c = c[:len(r)]
    elif len(c) != len(r):
        return False
    return all(_seg_eq(a, b) for a, b in zip(c, r))


def suffix_match(call: str, route: str) -> bool:
    """The route is the tail of the call path: a gateway or context-root prefix sits in front."""
    c, r = _segments(call), _segments(route)
    if not r or r[-1] == "*" or _literals(r) < 1 or len(r) >= len(c):
        return False
    return all(_seg_eq(a, b) for a, b in zip(c[-len(r):], r))


def route_hits(verb: str, path: str, table: list, suffix: bool, min_literal: int = 0) -> list:
    ok = [(p, f) for v, p, f in table if verb == "ANY" or v in ("ANY", verb)]
    hits = sorted({f for p, f in ok if path_match(path, p) and _literals(_segments(p)) >= min_literal})
    if hits or not suffix:
        return hits
    return sorted({f for p, f in ok if suffix_match(path, p)})


def identity_map(graphs: dict, aliases: dict) -> dict:
    """Lowercased name -> set of repo ids that answer to it. An alias overrides derived names."""
    names = defaultdict(set)
    for rid, g in graphs.items():
        names[rid.lower()].add(rid)
        for n in g.get("nodes", []):
            if n.get("service"):
                names[str(n["service"]).lower()].add(rid)
    for alias, rid in aliases.items():
        if rid in graphs:  # an alias to an unknown repo is a typo, not an edge
            names[alias] = {rid}
    return names


def resolve_target(target: str, names: dict) -> set:
    if target in names:
        return names[target]
    m = _K8S_HOST.match(target)
    return names.get(m.group(1), set()) if m else set()


def wire_http(graphs: dict, aliases: dict) -> list:
    names = identity_map(graphs, aliases)
    routes = {rid: [(r.split(" ", 1)[0], r.split(" ", 1)[1], n["path"])
                    for n in g.get("nodes", []) for r in (n.get("routes") or []) if " " in r]
              for rid, g in graphs.items()}
    edges = []
    for rid, g in graphs.items():
        for n in g.get("nodes", []):
            for call in n.get("http_calls") or []:
                edges.extend(match_call(rid, n["path"], call, names, routes))
    return edges


def match_call(rid: str, src_path: str, call: dict, names: dict, routes: dict) -> list:
    target, verb, path = call.get("target") or "", call.get("verb") or "ANY", call.get("path") or "/"
    if target in LOOPBACK:
        return []
    base = {"source": "%s:%s" % (rid, src_path), "cross_repo": True,
            "detail": "%s %s" % (verb, path), "via": call.get("via")}
    owners = resolve_target(target, names)
    if owners:
        if rid in owners:  # a call to its own service is in-repo wiring
            return []
        kind = "http" if len(owners) == 1 else "http_ambiguous"
        out = []
        for b in sorted(owners):
            hits = route_hits(verb, path, routes[b], suffix=True)
            out += [dict(base, target="%s:%s" % (b, f), type=kind) for f in hits] or \
                [dict(base, target=b, type=kind, resolution="service")]
        for e in out if kind != "http" else []:
            e["confidence"] = "low"
        return out
    if target and not target.startswith("config:"):
        return []  # a named host outside the mesh: a third-party dependency
    if _literals(_segments(path)) < 2 or route_hits(verb, path, routes[rid], suffix=False):
        return []
    out = []
    for b in sorted(routes):
        if b != rid:
            out += [dict(base, target="%s:%s" % (b, f), type="http_ambiguous", confidence="low")
                    for f in route_hits(verb, path, routes[b], suffix=False, min_literal=2)]
    return out[:MAX_PATH_ONLY_HITS]


def wire_messages(graphs: dict) -> list:
    prod, cons = defaultdict(list), defaultdict(list)
    for rid, g in graphs.items():
        for n in g.get("nodes", []):
            for t in n.get("produces") or []:
                prod[t].append((rid, n["path"]))
            for t in n.get("consumes") or []:
                cons[t].append((rid, n["path"]))
    edges = []
    for topic in sorted(prod):
        if "${" in topic:
            continue
        for a, pa in prod[topic]:
            for b, pb in cons.get(topic, []):
                if a != b:
                    edges.append({"source": "%s:%s" % (a, pa), "target": "%s:%s" % (b, pb),
                                  "type": "message", "cross_repo": True, "detail": topic})
    return edges


def merge(hub: str, manifest: dict) -> dict:
    graphs = {}
    for entry in manifest["repos"]:
        path = os.path.join(hub_paths(hub)["members"], entry["repo_id"], "knowledge-graph.json")
        with open(path, encoding="utf-8") as fh:
            graphs[entry["repo_id"]] = json.load(fh)

    nodes, edges, provides = [], [], defaultdict(list)
    for rid, g in graphs.items():
        files = [n["path"] for n in g.get("nodes", [])]
        packages = {os.path.dirname(p) for p in files if p.endswith("/__init__.py")}
        for n in g.get("nodes", []):
            nodes.append(dict(n, id="%s:%s" % (rid, n["id"]), repo=rid))
            for name in qualified_names(n["path"], packages):
                provides[name].append((rid, n["path"]))
        for e in g.get("edges", []):
            edges.append(dict(e, source="%s:%s" % (rid, e["source"]), target="%s:%s" % (rid, e["target"])))

    missing = [rid for rid, g in graphs.items()
               if "unresolved_imports" not in g or graph_version(g) < MIN_GRAPH]
    cross = 0
    for rid, g in graphs.items():
        for token, sources in sorted((g.get("unresolved_imports") or {}).items()):
            hits = [(r, p) for r, p in provides.get(token.replace("::", "."), []) if r != rid]
            if not hits:
                continue
            kind = "imports" if len(hits) == 1 else "imports_ambiguous"
            for src in sources:
                for r, p in hits:
                    edge = {"source": "%s:%s" % (rid, src), "target": "%s:%s" % (r, p), "type": kind,
                            "cross_repo": True, "detail": token}
                    if kind != "imports":
                        edge["confidence"] = "low"
                    edges.append(edge)
                    cross += kind == "imports"

    seen = set()
    for e in wire_http(graphs, load_aliases(hub)) + wire_messages(graphs):
        key = (e["source"], e["target"], e["type"], e["detail"])
        if key not in seen:
            seen.add(key)
            edges.append(e)
            cross += e["type"] in CONFIDENT

    return {
        "version": "1.0",
        "generator": "graphify-mesh",
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repos": [{"repo_id": e["repo_id"], "graph_sha": e.get("graph_sha"),
                   "files": len(graphs[e["repo_id"]].get("nodes", []))} for e in manifest["repos"]],
        "stale_members": missing,
        "cross_repo_edges": cross,
        "nodes": nodes,
        "edges": edges,
        "note": ("Node ids are <repo_id>:<path>. Edges with cross_repo=true join two repos: "
                 "imports by an exact qualified name, http by service identity then path "
                 "(a bare <repo_id> target means the handler is unknown), message by topic. "
                 "*_ambiguous edges are low confidence and never count as connections."),
    }


def summarize(graph: dict) -> dict:
    repos = [r["repo_id"] for r in graph.get("repos", [])]
    pairs, adj, by_type = defaultdict(int), defaultdict(set), defaultdict(int)
    for e in graph.get("edges", []):
        if not e.get("cross_repo"):
            continue
        by_type[e["type"]] += 1
        if e["type"] in CONFIDENT:
            a, b = e["source"].split(":", 1)[0], e["target"].split(":", 1)[0]
            pairs["%s->%s" % (a, b)] += 1
            adj[a].add(b)
            adj[b].add(a)
    seen, components = set(), []
    for r in repos:
        if r in seen:
            continue
        stack, comp = [r], []
        seen.add(r)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nxt in adj[cur] - seen:
                seen.add(nxt)
                stack.append(nxt)
        components.append(sorted(comp))
    components.sort(key=lambda c: (-len(c), c))
    return {"repos": len(repos), "cross_repo_edges": sum(pairs.values()), "pairs": dict(sorted(pairs.items())),
            "by_type": dict(sorted(by_type.items())), "components": components, "largest_component": components[0] if components else [],
            "stale_members": graph.get("stale_members", [])}


def cmd_add(args, hub):
    path = os.path.abspath(args.path)
    if not os.path.isdir(path):
        raise SystemExit("error: not a directory: %s" % path)
    manifest = load_manifest(hub)
    rid = repo_id_for(path, args.id)
    if any(r["repo_id"] == rid for r in manifest["repos"]):
        raise SystemExit("error: %r is already in the mesh; pass --id to name this repo differently" % rid)
    entry = {"repo_id": rid, "path": path, "graph_sha": None, "updated": None}
    build_member(hub, entry)
    manifest["repos"].append(entry)
    save_json(hub_paths(hub)["manifest"], manifest)
    print("added %s (%s) graph %s" % (rid, path, entry["graph_sha"][:12]))
    return 0


def cmd_remove(args, hub):
    manifest = load_manifest(hub)
    keep = [r for r in manifest["repos"] if r["repo_id"] != args.id]
    if len(keep) == len(manifest["repos"]):
        raise SystemExit("error: %r is not in the mesh" % args.id)
    manifest["repos"] = keep
    save_json(hub_paths(hub)["manifest"], manifest)
    shutil.rmtree(os.path.join(hub_paths(hub)["members"], args.id), ignore_errors=True)
    print("removed %s" % args.id)
    return 0


def cmd_build(args, hub):
    manifest = load_manifest(hub)
    if not manifest["repos"]:
        raise SystemExit("error: the mesh is empty; run graphify-mesh.py add <path>")
    for entry in manifest["repos"]:
        graph = os.path.join(hub_paths(hub)["members"], entry["repo_id"], "knowledge-graph.json")
        if args.refresh or not os.path.isfile(graph):
            if not os.path.isdir(entry["path"]):
                raise SystemExit("error: %s: %s is gone; remove it or restore the path"
                                 % (entry["repo_id"], entry["path"]))
            build_member(hub, entry)
    save_json(hub_paths(hub)["manifest"], manifest)
    graph = merge(hub, manifest)
    save_json(hub_paths(hub)["out"], graph)
    s = summarize(graph)
    print("mesh: %d repos, %d nodes, %d cross-repo edges, largest component %d (%s)" % (
        s["repos"], len(graph["nodes"]), s["cross_repo_edges"], len(s["largest_component"]),
        ", ".join(s["largest_component"])))
    if s["stale_members"]:
        print("stale: %s predate graph 5.3; run graphify-mesh.py build --refresh" % ", ".join(s["stale_members"]))
    return 0


def cmd_stats(args, hub):
    s = summarize(load_mesh(hub))
    if args.json:
        print(json.dumps(s, indent=2))
        return 0
    print("%d repos, %d cross-repo edges (%s)" % (s["repos"], s["cross_repo_edges"], ", ".join(
        "%s %d" % kv for kv in s["by_type"].items()) or "none"))
    for pair, n in s["pairs"].items():
        print("  %-40s %d" % (pair, n))
    for comp in s["components"]:
        print("component: %s" % ", ".join(comp))
    return 0


def load_mesh(hub: str) -> dict:
    try:
        with open(hub_paths(hub)["out"], encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        raise SystemExit("error: no mesh graph; run graphify-mesh.py build")


def blast_radius(graph: dict, fid: str, depth: int) -> dict:
    """Files that reach `fid` over confident edges, walking dependents up to `depth` hops."""
    serves = {n["id"] for n in graph["nodes"] if n.get("routes")}
    rev, repo_level = defaultdict(list), defaultdict(list)
    for e in graph.get("edges", []):
        if e["type"] in CONFIDENT:
            (rev if ":" in e["target"] else repo_level)[e["target"]].append(e["source"])
    seen, frontier = {fid: 0}, [fid]
    for d in range(1, depth + 1):
        nxt = []
        for cur in frontier:
            srcs = rev[cur] + (repo_level[cur.split(":", 1)[0]] if cur in serves else [])
            for src in srcs:
                if src not in seen:
                    seen[src] = d
                    nxt.append(src)
        frontier = nxt
    return seen


def cmd_query(args, hub):
    graph = load_mesh(hub)
    nodes = {n["id"]: n for n in graph["nodes"]}
    fid = args.file
    if fid not in nodes:
        hits = [i for i, n in nodes.items() if n["path"] == fid]
        if len(hits) != 1:
            raise SystemExit("error: %s %s; pass --file <repo_id>:<path>" % (
                fid, "is in %s" % ", ".join(sorted(h.split(":", 1)[0] for h in hits)) if hits else "is not in the mesh"))
        fid = hits[0]
    rid = fid.split(":", 1)[0]
    serves = bool(nodes[fid].get("routes"))
    cross = [e for e in graph.get("edges", []) if e.get("cross_repo")]
    out_edges = [e for e in cross if e["source"] == fid]
    in_edges = [e for e in cross if e["target"] == fid or (serves and e["target"] == rid)]
    reach = blast_radius(graph, fid, args.depth)
    affected = sorted((d, s) for s, d in reach.items() if s.split(":", 1)[0] != rid)
    result = {"file": fid, "outgoing": out_edges, "incoming": in_edges, "depth": args.depth,
              "blast_radius": [{"file": s, "depth": d} for d, s in affected],
              "repos_affected": sorted({s.split(":", 1)[0] for _, s in affected})}
    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    def show(title, edges, end):
        print("%s (%d):" % (title, len(edges)))
        for e in edges[:args.limit]:
            low = " [low]" if e.get("confidence") == "low" else ""
            print("  %-15s %-40s %s%s" % (e["type"], e["detail"], e[end], low))
        if len(edges) > args.limit:
            print("  ... %d more (--json for all)" % (len(edges) - args.limit))

    print(fid)
    show("depends on, in other repos", out_edges, "target")
    show("depended on by, from other repos", in_edges, "source")
    print("cross-repo blast radius, depth %d: %d files in %d repos" % (
        args.depth, len(affected), len(result["repos_affected"])))
    for d, s in affected[:args.limit]:
        print("  %d  %s" % (d, s))
    if len(affected) > args.limit:
        print("  ... %d more (--json for all)" % (len(affected) - args.limit))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="graphify-mesh.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add", help="add a repo to the mesh and build its graph")
    p.add_argument("path")
    p.add_argument("--id")
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser("remove", help="drop a repo from the mesh")
    p.add_argument("id")
    p.set_defaults(fn=cmd_remove)
    p = sub.add_parser("build", help="merge member graphs into mesh-graph.json")
    p.add_argument("--refresh", action="store_true", help="rebuild every member graph first")
    p.set_defaults(fn=cmd_build)
    p = sub.add_parser("stats", help="cross-repo edges and connected components")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_stats)
    p = sub.add_parser("query", help="a file's cross-repo edges and cross-repo blast radius")
    p.add_argument("--file", required=True, help="<repo_id>:<path>, or a path unique across the mesh")
    p.add_argument("--depth", type=int, default=3)
    p.add_argument("--limit", type=int, default=50, help="lines per section in text output")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_query)
    args = ap.parse_args(argv)
    return args.fn(args, os.getcwd())


if __name__ == "__main__":
    sys.exit(main())
