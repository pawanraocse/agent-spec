#!/usr/bin/env python3
"""Manage Git lifecycle hooks for algosec-agent-spec automated Graphify indexing.

Actions:
  install <project_root>   - Idempotently install or update post-checkout, post-merge and
                             post-rewrite hooks (rewrite = rebase/amend)
  uninstall <project_root> - Remove algosec-agent-spec hook blocks from git hooks
  check <project_root>     - Verify git hooks exist and are executable

Features:
- Preserves existing custom hooks by wrapping commands in identifiable marker blocks.
- Non-blocking: background detachment with `&` ensures 0ms Git command overhead.
- Branch-only filter: post-checkout only triggers when $3 == 1 (branch switch, not file checkout).
- Fail-open: all background execution errors are redirected to /dev/null so Git never fails.
"""
import os
import re
import stat
import subprocess
import sys

MARKER_START = "# >>> algosec-agent-spec auto-index >>>"
MARKER_END = "# <<< algosec-agent-spec auto-index <<<"

POST_CHECKOUT_BLOCK = """# >>> algosec-agent-spec auto-index >>>
# Background re-indexing on branch switch ($3 == 1)
if [ "${3:-}" = "1" ]; then
  ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
  ( cd "${ROOT_DIR}" && {
    if [ -x "./.agent-spec/bin/agent-spec-index" ]; then
      ./.agent-spec/bin/agent-spec-index --quiet >/dev/null 2>&1 &
    elif [ -f "./.agent-spec/bin/graphify-build.py" ]; then
      python3 ./.agent-spec/bin/graphify-build.py --quiet >/dev/null 2>&1 &
    fi
  } )
fi
# <<< algosec-agent-spec auto-index <<<"""

POST_MERGE_BLOCK = """# >>> algosec-agent-spec auto-index >>>
# Background re-indexing on merge/pull
ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
( cd "${ROOT_DIR}" && {
  if [ -x "./.agent-spec/bin/agent-spec-index" ]; then
    ./.agent-spec/bin/agent-spec-index --quiet >/dev/null 2>&1 &
  elif [ -f "./.agent-spec/bin/graphify-build.py" ]; then
    python3 ./.agent-spec/bin/graphify-build.py --quiet >/dev/null 2>&1 &
  fi
} )
# <<< algosec-agent-spec auto-index <<<"""

POST_REWRITE_BLOCK = """# >>> algosec-agent-spec auto-index >>>
# Background re-indexing on rebase/amend
ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
( cd "${ROOT_DIR}" && {
  if [ -x "./.agent-spec/bin/agent-spec-index" ]; then
    ./.agent-spec/bin/agent-spec-index --quiet >/dev/null 2>&1 &
  elif [ -f "./.agent-spec/bin/graphify-build.py" ]; then
    python3 ./.agent-spec/bin/graphify-build.py --quiet >/dev/null 2>&1 &
  fi
} )
# <<< algosec-agent-spec auto-index <<<"""

HOOK_BLOCKS = {
    "post-checkout": POST_CHECKOUT_BLOCK,
    "post-merge": POST_MERGE_BLOCK,
    "post-rewrite": POST_REWRITE_BLOCK,
}


def get_git_hooks_dir(project_root):
    """Locate the git hooks directory for project_root, handling worktrees and submodules."""
    # 1. Try git rev-parse if git is available and project is a repo
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--git-path", "hooks"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0 and res.stdout.strip():
            raw_path = res.stdout.strip()
            if os.path.isabs(raw_path):
                return raw_path
            return os.path.normpath(os.path.join(project_root, raw_path))
    except Exception:
        pass

    # 2. Inspect filesystem directly
    git_entry = os.path.join(project_root, ".git")
    if os.path.isfile(git_entry):
        try:
            with open(git_entry, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content.startswith("gitdir:"):
                    ref = content.split(":", 1)[1].strip()
                    git_dir = ref if os.path.isabs(ref) else os.path.normpath(os.path.join(project_root, ref))
                    # Check for commondir in worktrees
                    commondir_file = os.path.join(git_dir, "commondir")
                    if os.path.isfile(commondir_file):
                        with open(commondir_file, "r", encoding="utf-8") as cf:
                            cdir = cf.read().strip()
                            common_git_dir = cdir if os.path.isabs(cdir) else os.path.normpath(os.path.join(git_dir, cdir))
                            return os.path.join(common_git_dir, "hooks")
                    return os.path.join(git_dir, "hooks")
        except Exception:
            pass
    elif os.path.isdir(git_entry):
        return os.path.join(git_entry, "hooks")

    return None


def make_executable(path):
    try:
        mode = os.stat(path).st_mode
        os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def install_hook(hook_path, block):
    os.makedirs(os.path.dirname(hook_path), exist_ok=True)
    if not os.path.exists(hook_path):
        content = "#!/bin/sh\n" + block + "\n"
        with open(hook_path, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        with open(hook_path, "r", encoding="utf-8") as f:
            content = f.read()

        if MARKER_START in content and MARKER_END in content:
            pattern = re.compile(
                re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
                re.DOTALL,
            )
            content = pattern.sub(block, content)
        else:
            if not content.endswith("\n"):
                content += "\n"
            content += block + "\n"

        with open(hook_path, "w", encoding="utf-8") as f:
            f.write(content)

    make_executable(hook_path)


def uninstall_hook(hook_path):
    if not os.path.isfile(hook_path):
        return
    try:
        with open(hook_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return

    if MARKER_START not in content:
        return

    pattern = re.compile(
        r"\n?" + re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END) + r"\n?",
        re.DOTALL,
    )
    new_content = pattern.sub("\n", content).strip()

    # If the file only contained our hook (or empty shebang), remove it completely
    if not new_content or new_content in ("#!/bin/sh", "#!/bin/bash"):
        try:
            os.remove(hook_path)
        except OSError:
            pass
    else:
        try:
            with open(hook_path, "w", encoding="utf-8") as f:
                f.write(new_content + "\n")
        except OSError:
            pass


def check_hook(hook_path):
    if not os.path.isfile(hook_path):
        return False
    if not os.access(hook_path, os.X_OK):
        return False
    try:
        with open(hook_path, "r", encoding="utf-8") as f:
            content = f.read()
        return MARKER_START in content and MARKER_END in content
    except OSError:
        return False


def main():
    if len(sys.argv) < 3:
        print("Usage: manage-git-hooks.py <install|uninstall|check> <project_root>", file=sys.stderr)
        return 1

    action = sys.argv[1].lower()
    project_root = os.path.abspath(sys.argv[2])

    hooks_dir = get_git_hooks_dir(project_root)

    if action == "install":
        if not hooks_dir:
            # Not a git repo — fail gracefully without error
            return 0
        for hook_name, block in HOOK_BLOCKS.items():
            hook_path = os.path.join(hooks_dir, hook_name)
            install_hook(hook_path, block)
        return 0

    elif action == "uninstall":
        if not hooks_dir:
            return 0
        for hook_name in HOOK_BLOCKS:
            hook_path = os.path.join(hooks_dir, hook_name)
            uninstall_hook(hook_path)
        return 0

    elif action == "check":
        if not hooks_dir:
            print("Not a git repository (skipped)")
            return 0
        all_ok = True
        for hook_name in HOOK_BLOCKS:
            hook_path = os.path.join(hooks_dir, hook_name)
            if not check_hook(hook_path):
                all_ok = False
                break
        if all_ok:
            print("OK: Git auto-indexing hooks active in %s" % hooks_dir)
            return 0
        else:
            print("MISSING/INVALID: Git auto-indexing hooks in %s" % hooks_dir)
            return 1

    else:
        print("Unknown action: %s" % action, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
