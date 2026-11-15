#!/usr/bin/env python3
"""Per-request impact: tool categories, the token counterfactual, rule checks, injected facts."""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(REPO, "bin"))
from aspec_platform import impact, ingest, traces  # noqa: E402


def span(sid, kind, name, parent="t#root", **attrs):
    return {"span_id": sid, "trace_id": "t", "parent_span_id": parent, "kind": kind, "name": name, "attributes": attrs}


class ToolCategoryTest(unittest.TestCase):
    def test_graphify_shell_is_named_after_the_query(self):
        self.assertEqual(traces.tool_category("Shell", "./.agent-spec/bin/graphify-cli.py context --task x"),
                         ("graph", "graphify context"))
        self.assertEqual(traces.tool_category("Shell", "python3 .agent-spec/bin/agent-spec-memory.py search foo"),
                         ("memory", "memory search"))

    def test_edit_and_lint_tools_are_not_searches_or_reads(self):
        self.assertEqual(traces.tool_category("search_replace", "a.py"), ("edit", None))
        self.assertEqual(traces.tool_category("Write", "a.py"), ("edit", None))
        self.assertEqual(traces.tool_category("ReadLints", "a.py"), ("other", None))
        self.assertEqual(traces.tool_category("read_file", "a.py"), ("read", None))

    def test_plain_tools_keep_their_name(self):
        self.assertEqual(traces.tool_category("Shell", "git log"), ("shell", None))
        self.assertEqual(traces.tool_category("Shell", "grep -n x y"), ("search", None))
        self.assertEqual(traces.tool_category("Grep", "x"), ("search", None))
        self.assertEqual(traces.tool_category("Read", "f"), ("read", None))


class ImpactTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".agent-spec", "graph"))
        for name, size in (("a.py", 1000), ("b.py", 3000), ("c.py", 5000)):
            with open(os.path.join(self.root, name), "w") as fh:
                fh.write("x" * size)
        with open(os.path.join(self.root, ".agent-spec", "graph", "knowledge-graph.json"), "w") as fh:
            json.dump({"nodes": [{"path": "a.py"}, {"path": "b.py"}, {"path": "c.py"}]}, fh)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def spans(self):
        return [
            span("g", "tool", "graphify context", category="graph", bytes_out=400),
            span("s", "tool", "Grep", category="search", bytes_out=200),
            span("r", "tool", "Read", category="read", target=os.path.join(self.root, "c.py"), ranged=True, read_chars=1000),
            span("w", "tool", "Read", category="read", target=os.path.join(self.root, "a.py"), ranged=False, read_chars=1000),
            span("sub", "subagent", "agent-spec-search"),
            span("sr", "tool", "Read", parent="sub", category="read", target=os.path.join(self.root, "b.py"), ranged=False, read_chars=3000),
        ]

    def test_counterfactual_counts_graph_ranged_and_subagent(self):
        out = impact.for_request(self.root, sqlite3.connect(":memory:"), {"trace_id": "t", "session_id": "c"}, self.spans())
        self.assertEqual(out["median_file_bytes"], 3000)
        # graph: 3000 - 400; ranged: 5000 - 1000; subagent: 3000 kept in the child context
        self.assertEqual(out["tokens"]["avoided_by"], {"graph": 650, "ranged_reads": 1000, "subagents": 750})
        # main context: graph 400 + grep 200 + ranged 1000 + whole 1000
        self.assertEqual(out["tokens"]["context_in"], 650)
        self.assertEqual(out["tokens"]["plain_cursor"], 650 + 650 + 1000 + 750)
        self.assertEqual(out["tools"]["read_whole"], 1)
        self.assertEqual(out["tools"]["in_subagents"], 1)

    def test_edit_kind_wins_over_a_stored_category(self):
        spans = [span("e", "edit", "Write", category="other", target="a.py")]
        out = impact.for_request(self.root, None, {"trace_id": "t", "session_id": "c"}, spans)
        self.assertEqual(out["tools"]["edit"], 1)

    def test_unknown_range_is_neither_whole_nor_ranged(self):
        spans = [span("r", "tool", "Read", target=os.path.join(self.root, "c.py"))]
        out = impact.for_request(self.root, None, {"trace_id": "t", "session_id": "c"}, spans)
        self.assertEqual((out["tools"]["read_whole"], out["tools"]["read_ranged"]), (0, 0))
        self.assertEqual(out["tokens"]["context_in"], 0)
        self.assertTrue(next(r for r in out["rules"] if r["rule"].startswith("No whole-file"))["pass"])

    def test_graph_rule_does_not_apply_without_a_search(self):
        spans = [span("e", "edit", "Write", target="a.py")]
        out = impact.for_request(self.root, None, {"trace_id": "t", "session_id": "c"}, spans)
        rules = {r["rule"]: r["pass"] for r in out["rules"]}
        self.assertIsNone(rules["Query the graph before searching"])
        self.assertNotIn("Guard rails held", rules)

    def test_injected_facts_are_read_live_from_the_hook_log(self):
        os.makedirs(os.path.join(self.root, ".agent-spec", "metrics"))
        with open(os.path.join(self.root, ".agent-spec", "metrics", "injections.jsonl"), "w") as fh:
            fh.write(json.dumps({"conversation_id": "other", "facts": ["- [decision] wrong: x"]}) + "\n")
            fh.write(json.dumps({"conversation_id": "c", "digest_bytes": 900,
                                 "facts": ["- [decision] known fact: body", "- [gotcha] not in db: body",
                                           "- (3 more facts)"]}) + "\n")
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE memory_facts (fact_id TEXT, type TEXT, subject TEXT)")
        conn.execute("INSERT INTO memory_facts VALUES ('f1', 'decision', 'known fact')")
        out = impact.for_request(self.root, conn, {"trace_id": "t", "session_id": "c"}, [])
        self.assertEqual(out["memory"]["digest_bytes"], 900)
        self.assertTrue(out["memory"]["recorded"])
        self.assertEqual([(f["fact_id"], f["subject"]) for f in out["memory"]["facts"]],
                         [("f1", "known fact"), ("digest:1", "not in db")])

    def test_rules_flag_the_whole_file_read(self):
        out = impact.for_request(self.root, sqlite3.connect(":memory:"), {"trace_id": "t", "session_id": "c"}, self.spans())
        rules = {r["rule"]: r["pass"] for r in out["rules"]}
        self.assertTrue(rules["Query the graph before searching"])
        self.assertFalse(rules["No whole-file reads in the main context"])


class IngestOrderTest(unittest.TestCase):
    def test_traces_are_ingested_before_memory(self):
        """memory joins injected facts to traces, so traces must be current first."""
        self.assertLess(ingest.ALL.index("traces"), ingest.ALL.index("memory"))


class InjectionTest(unittest.TestCase):
    def test_digest_lines_match_the_longest_subject(self):
        facts = {"f1": ("constraint", "index"), "f2": ("constraint", "index is per-workspace"), "f3": ("decision", "x")}
        lines = ["- [constraint] index is per-workspace: body", "- [decision] x: y", "- [gotcha] unknown: z"]
        self.assertEqual(ingest.match_facts(lines, facts), ["f2", "f3"])

    def test_session_start_hook_records_injected_facts(self):
        root = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(root, ".agent-spec", "metrics"))
            os.makedirs(os.path.join(root, ".agent-spec", "bin"))
            with open(os.path.join(root, ".agent-spec", "bin", "agent-spec-digest.py"), "w") as fh:
                fh.write("def build_digest():\n    return 'stack: x\\nremembered:\\n- [constraint] a: b\\n- [decision] c: d\\nDo NOT open'\n")
            out = subprocess.run([sys.executable, os.path.join(REPO, "hooks", "cursor-session-start.py")], cwd=root,
                                 input=json.dumps({"conversation_id": "conv-1"}), capture_output=True, text=True, timeout=10)
            self.assertIn("additional_context", json.loads(out.stdout))
            with open(os.path.join(root, ".agent-spec", "metrics", "injections.jsonl")) as fh:
                row = json.loads(fh.readline())
            self.assertEqual(row["conversation_id"], "conv-1")
            self.assertEqual(row["facts"], ["- [constraint] a: b", "- [decision] c: d"])
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
