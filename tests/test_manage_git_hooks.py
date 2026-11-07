#!/usr/bin/env python3
"""Automated test suite for algosec-agent-spec Git lifecycle hook management.

Tests:
1. Non-git directory handling (fail-open graceful exit).
2. Clean installation into .git/hooks/ (post-checkout, post-merge, post-rewrite).
3. Verification of hook contents, shell syntax (sh -n), and executable permissions.
4. Idempotent re-installation (no duplicate marker blocks).
5. Preservation of existing custom developer hooks on install and uninstall.
6. Clean uninstallation of harness-created hook files.
"""
import os
import stat
import subprocess
import sys
import tempfile

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANAGE_SCRIPT = os.path.join(REPO_DIR, "hooks", "manage-git-hooks.py")


def run_manage(action, project_root):
    return subprocess.run(
        [sys.executable, MANAGE_SCRIPT, action, project_root],
        capture_output=True,
        text=True,
    )


def test_git_hooks_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        # --- Test 1: Non-git directory ---
        res = run_manage("install", tmpdir)
        assert res.returncode == 0, "install on non-git dir must return 0"
        res = run_manage("check", tmpdir)
        assert res.returncode == 0, "check on non-git dir must return 0"
        res = run_manage("uninstall", tmpdir)
        assert res.returncode == 0, "uninstall on non-git dir must return 0"

        # --- Test 2: Clean Git repo install ---
        hooks_dir = os.path.join(tmpdir, ".git", "hooks")
        os.makedirs(hooks_dir, exist_ok=True)

        res = run_manage("install", tmpdir)
        assert res.returncode == 0, "install on git dir failed: " + res.stderr

        res = run_manage("check", tmpdir)
        assert res.returncode == 0, "check should pass after install: " + res.stdout + res.stderr

        for hook in ("post-checkout", "post-merge", "post-rewrite"):
            hook_file = os.path.join(hooks_dir, hook)
            assert os.path.isfile(hook_file), f"{hook} was not created"
            assert os.access(hook_file, os.X_OK), f"{hook} is not executable"

            with open(hook_file, "r", encoding="utf-8") as f:
                content = f.read()
            assert "# >>> algosec-agent-spec auto-index >>>" in content
            assert "# <<< algosec-agent-spec auto-index <<<" in content
            assert "git rev-parse --show-toplevel" in content

            # Verify shell syntax
            sh_syntax = subprocess.run(["sh", "-n", hook_file], capture_output=True, text=True)
            assert sh_syntax.returncode == 0, f"Shell syntax error in {hook}: " + sh_syntax.stderr

        # Branch-only filter test on post-checkout
        with open(os.path.join(hooks_dir, "post-checkout")) as f:
            chk_content = f.read()
        assert '[ "${3:-}" = "1" ]' in chk_content

        # --- Test 3: Idempotent re-install ---
        res = run_manage("install", tmpdir)
        assert res.returncode == 0
        for hook in ("post-checkout", "post-merge", "post-rewrite"):
            hook_file = os.path.join(hooks_dir, hook)
            with open(hook_file) as f:
                content = f.read()
            assert content.count("# >>> algosec-agent-spec auto-index >>>") == 1, (
                f"Duplicate marker block in {hook}"
            )

        # --- Test 4: Clean uninstall of harness-created hooks ---
        res = run_manage("uninstall", tmpdir)
        assert res.returncode == 0
        for hook in ("post-checkout", "post-merge", "post-rewrite"):
            hook_file = os.path.join(hooks_dir, hook)
            assert not os.path.exists(hook_file), f"{hook} should be removed when harness-created"

        # --- Test 5: Custom hook preservation ---
        custom_hook = os.path.join(hooks_dir, "post-checkout")
        custom_code = '#!/bin/sh\n# Developer custom script\necho "Running linter"\n'
        with open(custom_hook, "w", encoding="utf-8") as f:
            f.write(custom_code)
        os.chmod(custom_hook, 0o755)

        # Install should append marker block
        res = run_manage("install", tmpdir)
        assert res.returncode == 0
        with open(custom_hook) as f:
            merged_content = f.read()
        assert 'echo "Running linter"' in merged_content
        assert "# >>> algosec-agent-spec auto-index >>>" in merged_content

        # Uninstall should restore custom script and remove only marker block
        res = run_manage("uninstall", tmpdir)
        assert res.returncode == 0
        assert os.path.exists(custom_hook), "Custom hook must be preserved"
        with open(custom_hook) as f:
            restored_content = f.read()
        assert 'echo "Running linter"' in restored_content
        assert "# >>> algosec-agent-spec auto-index >>>" not in restored_content

    print("ALL GIT HOOK LIFECYCLE TESTS PASSED.")


if __name__ == "__main__":
    test_git_hooks_lifecycle()
