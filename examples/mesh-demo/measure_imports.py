#!/usr/bin/env python3
"""P3-001: precision and recall of cross-repo `imports` edges against the Java import statements.

Usage: measure_imports.py HUB ROOT  (HUB holds .agent-spec/graph/mesh-graph.json; each member is ROOT/<repo_id>)
Ground truth: every `import [static] a.b.C;` or `import a.b.*;` in a member that names a class file in another member.
"""
import json, os, re, sys
hub, root = sys.argv[1], sys.argv[2]
g = json.load(open(os.path.join(hub, ".agent-spec/graph/mesh-graph.json")))
members = [r.get("repo_id") or r.get("id") if isinstance(r, dict) else r for r in g["repos"]]
fqn = {}  # fqn -> member:path
pkgs = {}
for m in members:
    base = os.path.join(root, m)
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if d not in ("target", "build", "node_modules", ".git")]
        for f in fn:
            if f.endswith(".java"):
                p = os.path.relpath(os.path.join(dp, f), base)
                mm = re.search(r"src/(?:main|test)/java/(.+)\.java$", p)
                if mm:
                    q = mm.group(1).replace("/", ".")
                    fqn[q] = (m, p)
                    pkgs.setdefault(q.rsplit(".", 1)[0], []).append((m, p))
truth = set()
for q, (m, p) in fqn.items():
    text = open(os.path.join(root, m, p), encoding="utf-8", errors="replace").read()
    for imp in re.findall(r"^\s*import\s+(?:static\s+)?([\w.]+(?:\.\*)?)\s*;", text, re.M):
        targets = []
        if imp.endswith(".*"):
            targets = pkgs.get(imp[:-2], [])
        else:
            parts = imp.split(".")
            for i in range(len(parts), 1, -1):
                if ".".join(parts[:i]) in fqn:
                    targets = [fqn[".".join(parts[:i])]]; break
        for tm, tp in targets:
            if tm != m:
                truth.add(("%s:%s" % (m, p), "%s:%s" % (tm, tp)))
found = {(e["source"], e["target"]) for e in g["edges"] if e.get("cross_repo") and e["type"] == "imports"}
tp = found & truth
print(json.dumps({"members": members, "found": len(found), "truth": len(truth), "correct": len(tp),
                  "precision": round(len(tp) / len(found), 3) if found else None,
                  "recall": round(len(tp) / len(truth), 3) if truth else None,
                  "false_positives": sorted(found - truth)[:10], "missed": sorted(truth - found)[:10]}, indent=1))
