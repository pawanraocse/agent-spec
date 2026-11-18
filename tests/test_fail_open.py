#!/usr/bin/env python3
"""H-046 fail-open proof: no hook may stop Cursor. Each hook runs with its helpers deleted,
with a corrupt graph, and with a full disk; every run must exit 0, and preToolUse must
answer allow for an ordinary edit.

Run: python3 tests/test_fail_open.py
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = {name: os.path.join(REPO, "hooks", name) for name in (
    "cursor-session-start.py", "cursor-pre-tool-use.py", "cursor-event.py", "cursor-session-end.py")}
PAYLOADS = {
    "cursor-session-start.py": {"hook_event_name": "sessionStart", "conversation_id": "c1"},
    "cursor-pre-tool-use.py": {"hook_event_name": "preToolUse", "conversation_id": "c1", "tool_name": "Write",
                               "tool_input": {"file_path": "app.py", "content": "x = 1\n"}},
    "cursor-event.py": {"hook_event_name": "postToolUse", "conversation_id": "c1", "generation_id": "g1",
                        "tool_name": "Write", "tool_input": {"file_path": "app.py"}},
    "cursor-session-end.py": {"hook_event_name": "sessionEnd", "conversation_id": "c1"},
}


def project(with_bin=True):
    t = tempfile.mkdtemp()
    spec = os.path.join(t, ".agent-spec")
    for d in ("graph", "metrics", "memory"):
        os.makedirs(os.path.join(spec, d))
    with open(os.path.join(t, "app.py"), "w") as fh:
        fh.write("x = 0\n")
    if with_bin:
        shutil.copytree(os.path.join(REPO, "bin"), os.path.join(spec, "bin"),
                        ignore=shutil.ignore_patterns("__pycache__", "ui"))
    return t


class FailOpenTest(unittest.TestCase):
    def run_hook(self, root, name, extra_env=None):
        env = dict(os.environ, HOME=root, AGENT_SPEC_BUILD_TIMEOUT="5", AGENT_SPEC_CURSOR_STORE="0",
                   TMPDIR=root, **(extra_env or {}))
        res = subprocess.run([sys.executable, HOOKS[name]], input=json.dumps(PAYLOADS[name]), cwd=root,
                             capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(res.returncode, 0, "%s exited %d: %s" % (name, res.returncode, res.stderr[-400:]))
        if name == "cursor-pre-tool-use.py":
            self.assertEqual(json.loads(res.stdout)["permission"], "allow", res.stdout)
        return res

    def each_hook(self, root, **kw):
        for name in HOOKS:
            with self.subTest(hook=name):
                self.run_hook(root, name, **kw)

    def test_helpers_deleted(self):
        root = project(with_bin=False)
        try:
            self.each_hook(root)
        finally:
            shutil.rmtree(root)

    def test_corrupt_graph_and_status(self):
        root = project()
        try:
            gdir = os.path.join(root, ".agent-spec", "graph")
            for name, body in (("knowledge-graph.json", "{not json"), (".status.json", "[]"),
                               ("mesh-graph.json", "null")):
                with open(os.path.join(gdir, name), "w") as fh:
                    fh.write(body)
            with open(os.path.join(root, ".agent-spec", "risk.json"), "w") as fh:
                fh.write("{broken")
            self.each_hook(root)
        finally:
            shutil.rmtree(root)

    @unittest.skipUnless(os.path.exists("/dev/full"), "needs /dev/full (Linux)")
    def test_full_disk(self):
        root = project()
        try:
            metrics = os.path.join(root, ".agent-spec", "metrics")
            for name in ("events.jsonl", "automation.jsonl", "injections.jsonl", "risk.jsonl", "guard.jsonl"):
                os.symlink("/dev/full", os.path.join(metrics, name))  # every append fails with ENOSPC
            self.each_hook(root)
        finally:
            shutil.rmtree(root)

    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0, "permission bits do not bind here")
    def test_read_only_harness_dir(self):
        root = project()
        spec = os.path.join(root, ".agent-spec")
        try:
            for dirpath, dirs, _ in os.walk(spec):
                for d in dirs:
                    os.chmod(os.path.join(dirpath, d), stat.S_IRUSR | stat.S_IXUSR)
            os.chmod(spec, stat.S_IRUSR | stat.S_IXUSR)
            self.each_hook(root)
        finally:
            for dirpath, dirs, _ in os.walk(spec):
                os.chmod(dirpath, stat.S_IRWXU)
                for d in dirs:
                    os.chmod(os.path.join(dirpath, d), stat.S_IRWXU)
            shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main(verbosity=1)
