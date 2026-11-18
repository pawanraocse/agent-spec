#!/usr/bin/env python3
"""H-011 branch-aware graph and H-021 build-failure status.

Run: python3 tests/test_graph_git.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(REPO_DIR, "bin")


def git(root, *args):
    subprocess.run(["git", "-C", root, "-c", "user.email=t@example.invalid", "-c", "user.name=t"] + list(args),
                   check=True, capture_output=True)


def make_repo():
    t = tempfile.mkdtemp()
    os.makedirs(os.path.join(t, ".agent-spec", "graph"))
    with open(os.path.join(t, "a.py"), "w") as fh:
        fh.write("import b\n")
    with open(os.path.join(t, "b.py"), "w") as fh:
        fh.write("X = 1\n")
    git(t, "init", "-q", "-b", "main")
    git(t, "add", "-A")
    git(t, "commit", "-q", "-m", "init")
    return t


def build(root):
    subprocess.run([sys.executable, os.path.join(BIN, "graphify-build.py"), "--quiet"], cwd=root,
                   check=True, capture_output=True)
    with open(os.path.join(root, ".agent-spec", "graph", "knowledge-graph.json")) as fh:
        return json.load(fh)


def digest_module(root):
    spec = importlib.util.spec_from_file_location("digest_under_test", os.path.join(BIN, "agent-spec-digest.py"))
    mod = importlib.util.module_from_spec(spec)
    cwd = os.getcwd()
    os.chdir(root)
    try:
        spec.loader.exec_module(mod)
    finally:
        os.chdir(cwd)
    mod.ROOT = root
    mod.SPEC = os.path.join(root, ".agent-spec")
    return mod


def test_graph_records_branch_and_sha():
    t = make_repo()
    try:
        g = build(t)["git"]
        head = subprocess.run(["git", "-C", t, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        assert g["branch"] == "main" and g["head_sha"] == head, g
        assert g["dirty"] is False and g["operation"] is None and g["conflicts"] == 0, g
    finally:
        shutil.rmtree(t)


def test_digest_flags_a_branch_switch():
    t = make_repo()
    try:
        build(t)
        git(t, "checkout", "-q", "-b", "feature")
        with open(os.path.join(t, "c.py"), "w") as fh:
            fh.write("import a\n")
        git(t, "add", "-A")
        git(t, "commit", "-q", "-m", "c")
        d = digest_module(t)
        line = d.graph_line()
        assert "graph reflects: main @" in line, line
        assert "HEAD is now" in line, line
        g = build(t)["git"]
        assert g["branch"] == "feature", g
        assert "HEAD is now" not in d.graph_line()
    finally:
        shutil.rmtree(t)


def test_merge_in_progress_is_labelled():
    t = make_repo()
    try:
        git(t, "checkout", "-q", "-b", "other")
        with open(os.path.join(t, "b.py"), "w") as fh:
            fh.write("X = 2\n")
        git(t, "commit", "-qam", "other")
        git(t, "checkout", "-q", "main")
        with open(os.path.join(t, "b.py"), "w") as fh:
            fh.write("X = 3\n")
        git(t, "commit", "-qam", "main")
        subprocess.run(["git", "-C", t, "-c", "user.email=t@example.invalid", "-c", "user.name=t",
                        "merge", "other"], capture_output=True)  # conflicts on purpose
        g = build(t)["git"]
        assert g["operation"] == "merge" and g["conflicts"] == 1, g
        label = digest_module(t).git_label(g)
        assert "built during a merge with 1 conflicted file(s)" in label, label
    finally:
        shutil.rmtree(t)


def test_failed_build_is_recorded_and_kept():
    t = tempfile.mkdtemp()
    try:
        spec = importlib.util.spec_from_file_location("gb", os.path.join(BIN, "graphify-build.py"))
        gb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gb)
        gb.OUTPUT_DIR = t
        gb.write_status({"state": "failed", "finished": "2026-11-18T10:00:00", "error": "ValueError: boom"})
        gb.write_status({"state": "ok", "finished": "2026-11-18T10:05:00", "files": 2})
        with open(os.path.join(t, ".status.json")) as fh:
            status = json.load(fh)
        assert status["state"] == "ok"
        assert status["last_failure"]["error"] == "ValueError: boom", status
    finally:
        shutil.rmtree(t)


def test_crash_writes_failed_status():
    t = make_repo()
    try:
        # A graph dir that is a file makes the build crash after argument parsing.
        graph = os.path.join(t, ".agent-spec", "graph")
        shutil.rmtree(graph)
        out = os.path.join(t, "out")
        os.makedirs(out)
        os.makedirs(os.path.join(out, "knowledge-graph.json"))  # a directory where the file goes
        res = subprocess.run([sys.executable, os.path.join(BIN, "graphify-build.py"), "--quiet", "--out", out],
                             cwd=t, capture_output=True, text=True)
        assert res.returncode != 0
        with open(os.path.join(out, ".status.json")) as fh:
            status = json.load(fh)
        assert status["state"] == "failed" and status["error"], status
    finally:
        shutil.rmtree(t)



def test_unchanged_tree_takes_the_fast_path():
    """H-043: a second build with nothing changed leaves the graph alone; a change, or a new
    commit, does the real build."""
    t = make_repo()
    try:
        build(t)
        graph = os.path.join(t, ".agent-spec", "graph", "knowledge-graph.json")
        before = os.path.getmtime(graph)
        build(t)
        with open(os.path.join(t, ".agent-spec", "graph", ".status.json")) as fh:
            assert json.load(fh).get("noop") is True
        assert os.path.getmtime(graph) == before
        with open(os.path.join(t, "b.py"), "a") as fh:
            fh.write("Y = 2\n")
        build(t)
        with open(os.path.join(t, ".agent-spec", "graph", ".status.json")) as fh:
            status = json.load(fh)
        assert not status.get("noop") and status["reparsed"] == 1, status
    finally:
        shutil.rmtree(t)

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("  ok", fn.__name__)
    print("%d graph git tests passed" % len(tests))
