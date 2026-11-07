#!/usr/bin/env python3
"""R1 import guard (P2.3): the core harness must never depend on the platform extra (DEC-03).

Core = every bin/*.py and hooks/*.py outside the platform packages. They may not import the
platform packages or any PyPI extra. Also guards the `platform` shadowing trap: no directory
named `platform` may sit in bin/.

Run: python3 tests/test_platform_guard.py
"""
import ast
import glob
import os
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORBIDDEN = {"aspec_platform", "hub", "fastapi", "uvicorn", "pydantic", "yaml", "httpx", "starlette"}


def imports_of(path):
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), path)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return found


class GuardTest(unittest.TestCase):
    def test_core_scripts_do_not_import_the_extra(self):
        core = glob.glob(os.path.join(REPO_DIR, "bin", "*.py")) + \
            glob.glob(os.path.join(REPO_DIR, "hooks", "*.py"))
        self.assertTrue(core)
        for path in core:
            if os.path.basename(path) == "agent-spec-platform.py":
                continue  # the extra's own entry point (imports lazily, stdlib-only data layer)
            if os.path.basename(path).startswith("agent-spec-run"):
                continue  # orchestrator entry point (P2.37+) imports bin/hub on purpose
            bad = imports_of(path) & FORBIDDEN
            self.assertFalse(bad, "%s imports %s" % (os.path.relpath(path, REPO_DIR), sorted(bad)))

    def test_no_platform_directory_shadowing_stdlib(self):
        self.assertFalse(os.path.exists(os.path.join(REPO_DIR, "bin", "platform")),
                         "bin/platform would shadow the stdlib `platform` module")
        self.assertFalse(os.path.exists(os.path.join(REPO_DIR, "bin", "platform.py")))

    def test_data_layer_is_stdlib_only(self):
        """aspec_platform modules other than api/serve/security may not import PyPI packages."""
        allowed_extra = {"api.py", "serve.py", "security.py", "sse.py"}
        for path in glob.glob(os.path.join(REPO_DIR, "bin", "aspec_platform", "*.py")):
            if os.path.basename(path) in allowed_extra:
                continue
            bad = imports_of(path) & {"fastapi", "uvicorn", "pydantic", "yaml", "httpx", "starlette"}
            self.assertFalse(bad, "%s imports %s" % (os.path.basename(path), sorted(bad)))


if __name__ == "__main__":
    unittest.main(verbosity=1)
