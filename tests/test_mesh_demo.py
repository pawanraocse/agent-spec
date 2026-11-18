#!/usr/bin/env python3
"""H-010: examples/mesh-demo builds into a mesh with imports, http and message edges across
repos, and every cross-repo edge is one the fixture really has (P3-001 precision).

Run: python3 tests/test_mesh_demo.py
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(REPO, "examples", "mesh-demo")

# Ground truth: (source repo, target repo, type) the fixture's code actually contains.
EXPECTED = {("orders-api", "acme-common", "imports"), ("orders-worker", "acme-common", "imports"),
            ("shop-ui", "orders-api", "http"), ("orders-api", "orders-worker", "message")}


class MeshDemoTest(unittest.TestCase):
    def test_demo_mesh_has_every_edge_type_and_no_false_edges(self):
        hub = tempfile.mkdtemp()
        try:
            res = subprocess.run(["bash", os.path.join(DEMO, "build.sh"), hub], capture_output=True, text=True, timeout=180)
            self.assertEqual(res.returncode, 0, res.stderr + res.stdout)
            with open(os.path.join(hub, ".agent-spec", "graph", "mesh-graph.json")) as fh:
                edges = [e for e in json.load(fh)["edges"] if e.get("cross_repo")]
            found = {(e["source"].split(":", 1)[0], e["target"].split(":", 1)[0], e["type"]) for e in edges}
            self.assertEqual(found, EXPECTED, "precision and recall are both 100% on the fixture")
        finally:
            shutil.rmtree(hub)


if __name__ == "__main__":
    unittest.main(verbosity=1)
