#!/usr/bin/env python3
"""Tests for graph symbols and callers (D-007): symbol nodes, `calls` edges, CLI `symbols` / `callers`.

Run: python3 tests/test_graph_symbols.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(REPO_DIR, "bin", "graphify-build.py")
CLI = os.path.join(REPO_DIR, "bin", "graphify-cli.py")

FILES = {
    "pkg/__init__.py": "",
    "pkg/util.py": "def helper(x):\n    return x\n\n\ndef shared():\n    return 1\n",
    "pkg/other.py": "def shared():\n    return 2\n",
    "pkg/app.py": (
        "from pkg import util\nfrom pkg.util import helper\n\n\n"
        "class Service:\n"
        "    def run(self):\n"
        "        return helper(1)\n\n"
        "    def again(self):\n"
        "        return self.run()\n\n\n"
        "def main():\n"
        "    return Service().run()\n"
    ),
    "pkg/amb.py": "from pkg.util import *\nfrom pkg.other import *\n\n\ndef go():\n    return shared()\n",
    "src/Repo.java": (
        "package x;\npublic class Repo {\n"
        "    public String load(String id) {\n        return fetch(id);\n    }\n"
        "    private String fetch(String id) {\n        return id;\n    }\n}\n"
    ),
}


class SymbolsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        os.makedirs(os.path.join(self.tmp, ".agent-spec"))
        for rel, body in FILES.items():
            path = os.path.join(self.tmp, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(body)
        self.build()

    def build(self, *extra):
        return subprocess.run([sys.executable, BUILD, "--quiet", *extra], cwd=self.tmp,
                              capture_output=True, text=True, check=True)

    def cli(self, *args):
        return subprocess.run([sys.executable, CLI, *args], cwd=self.tmp,
                              capture_output=True, text=True)

    def graph(self):
        with open(os.path.join(self.tmp, ".agent-spec", "graph", "knowledge-graph.json")) as fh:
            return json.load(fh)

    def test_symbol_nodes_have_kind_file_line(self):
        syms = {s["id"]: s for s in self.graph()["symbols"]}
        run = syms["pkg/app.py::Service.run"]
        self.assertEqual((run["type"], run["kind"], run["file"], run["line"]),
                         ("symbol", "method", "pkg/app.py", 6))
        self.assertEqual(syms["pkg/app.py::Service"]["kind"], "class")
        self.assertEqual(syms["pkg/app.py::main"]["kind"], "function")
        self.assertIn("src/Repo.java::Repo.load", syms)

    def test_file_nodes_and_edges_are_not_polluted(self):
        g = self.graph()
        self.assertTrue(all(n["type"] in ("file", "test") for n in g["nodes"]))
        self.assertTrue(all(e["type"] != "calls" for e in g["edges"]))

    def test_calls_edge_resolved_through_import(self):
        calls = {(c["source"], c["target"]): c for c in self.graph()["calls"]}
        edge = calls[("pkg/app.py::Service.run", "pkg/util.py::helper")]
        self.assertNotEqual(edge.get("confidence"), "low")

    def test_calls_within_same_file(self):
        calls = {(c["source"], c["target"]) for c in self.graph()["calls"]}
        self.assertIn(("pkg/app.py::Service.again", "pkg/app.py::Service.run"), calls)
        self.assertIn(("src/Repo.java::Repo.load", "src/Repo.java::Repo.fetch"), calls)

    def test_ambiguous_call_is_low_confidence(self):
        edges = [c for c in self.graph()["calls"] if c["source"] == "pkg/amb.py::go"]
        self.assertEqual({c["target"] for c in edges}, {"pkg/util.py::shared", "pkg/other.py::shared"})
        self.assertTrue(all(c["confidence"] == "low" for c in edges))

    def test_cli_symbols(self):
        out = self.cli("symbols", "--file", "pkg/app.py")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Service.run", out.stdout)
        self.assertIn("method", out.stdout)
        self.assertIn("pkg/app.py:6", out.stdout)

    def test_cli_callers(self):
        out = self.cli("callers", "--symbol", "helper")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("pkg/app.py::Service.run", out.stdout)
        self.assertNotIn("pkg/app.py::main", out.stdout)

    def test_cli_callers_unknown_symbol(self):
        out = self.cli("callers", "--symbol", "nope_nothing")
        self.assertEqual(out.returncode, 0)
        self.assertIn("No symbol", out.stdout)

    def test_incremental_build_keeps_symbols(self):
        before = self.graph()
        self.build()
        after = self.graph()
        self.assertEqual(before["symbols"], after["symbols"])
        self.assertEqual(before["calls"], after["calls"])

    def test_per_file_symbol_cap(self):
        body = "".join("def f%d():\n    pass\n" % i for i in range(260))
        with open(os.path.join(self.tmp, "big.py"), "w", encoding="utf-8") as fh:
            fh.write(body)
        self.build()
        n = sum(1 for s in self.graph()["symbols"] if s["file"] == "big.py")
        self.assertEqual(n, 200)

    def test_syntax_error_file_does_not_break_build(self):
        with open(os.path.join(self.tmp, "broken.py"), "w", encoding="utf-8") as fh:
            fh.write("def oops(:\n")
        self.build()
        self.assertIn("pkg/app.py::main", {s["id"] for s in self.graph()["symbols"]})

    def test_trend_line_counts_symbols(self):
        path = os.path.join(self.tmp, ".agent-spec", "graph", "stats-history.jsonl")
        with open(path, encoding="utf-8") as fh:
            last = json.loads(fh.readlines()[-1])
        self.assertEqual(last["symbols"], len(self.graph()["symbols"]))
        self.assertGreater(last["symbols"], 0)


if __name__ == "__main__":
    unittest.main()
