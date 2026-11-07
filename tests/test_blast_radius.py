#!/usr/bin/env python3
"""Tests for bin/agent-spec-blast-radius (S-001) against a tiny temp project.

Run: python3 tests/test_blast_radius.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(REPO, "bin")
WRAPPER = os.path.join(BIN, "agent-spec-blast-radius")
FILES = {"core.py": "def a():\n    return 1\n", "mid.py": "import core\n",
         "other.py": "import core\n", "top.py": "import mid\n"}


class BlastRadiusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proj = tempfile.mkdtemp()
        for name, body in FILES.items():
            with open(os.path.join(cls.proj, name), "w") as fh:
                fh.write(body)
        os.makedirs(os.path.join(cls.proj, ".agent-spec", "graph"))
        res = subprocess.run([sys.executable, os.path.join(BIN, "graphify-build.py"), "--quiet"],
                             cwd=cls.proj, capture_output=True, text=True)
        assert res.returncode == 0, res.stderr

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.proj)

    def run_wrapper(self, *args, **env):
        e = {k: v for k, v in os.environ.items() if k != "NO_COLOR"}
        e.update(env)
        return subprocess.run([sys.executable, WRAPPER] + list(args), cwd=self.proj,
                              capture_output=True, text=True, env=e)

    def test_groups_direct_and_transitive(self):
        res = self.run_wrapper("--file", "core.py")
        self.assertEqual(res.returncode, 0, res.stderr)
        out = res.stdout
        self.assertIn("Direct dependents (2)", out)
        self.assertIn("Transitive dependents (1)", out)
        self.assertIn("Total: 3", out)
        direct, trans = out.split("Transitive dependents")
        self.assertIn("mid.py", direct)
        self.assertIn("other.py", direct)
        self.assertIn("top.py", trans)
        self.assertNotIn("top.py", direct)

    def test_no_color_when_not_tty(self):
        self.assertNotIn("\033[", self.run_wrapper("--file", "core.py").stdout)

    def test_ansi_when_tty(self):
        try:
            import pty
        except ImportError:
            self.skipTest("no pty")
        try:
            for fd in pty.openpty():
                os.close(fd)
        except OSError:
            self.skipTest("no pty devices")
        for extra, env in (([], {}), (["--no-color"], {}), ([], {"NO_COLOR": "1"})):
            master, slave = pty.openpty()
            e = {k: v for k, v in os.environ.items() if k != "NO_COLOR"}
            e.update(env)
            p = subprocess.Popen([sys.executable, WRAPPER, "--file", "core.py"] + extra,
                                 cwd=self.proj, stdout=slave, env=e)
            os.close(slave)
            data = b""
            while True:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                data += chunk
            p.wait()
            os.close(master)
            self.assertEqual(p.returncode, 0)
            self.assertEqual(b"\033[" in data, not extra and not env, (extra, env))

    def test_unknown_file_exits_2(self):
        res = self.run_wrapper("--file", "nope.py")
        self.assertEqual(res.returncode, 2)
        self.assertIn("nope.py", res.stderr)

    def test_leaf_file_has_no_dependents(self):
        res = self.run_wrapper("--file", "top.py")
        self.assertEqual(res.returncode, 0)
        self.assertIn("Total: 0", res.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
