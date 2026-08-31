#!/usr/bin/env python3
"""agent-spec-lint-refs.py — fail when the framework's own prose points at nothing.

Four separate defects of one kind reached main before this existed: CLAUDE.md named
two skills the installer prunes, AGENTS.md and GEMINI.md promised a SessionStart hook
that only Claude Code has, GEMINI.md linked a snapshot template at a path that never
existed, and two files still named a skill by its pre-rename directory. Each was found
by accident, and each fix was written for the one file where it was noticed.

The cost of that class of defect is unusual: an instruction the model cannot follow is
charged on every turn like any other, and then wastes a tool call proving itself wrong.

So this walks every file an agent is given and checks two things — that each repository
path it names exists, and that each /agent-spec-<skill> it names has a directory.

Runtime paths under .agent-spec/ are deliberately not checked: they belong to whatever
project the framework is installed into, not to this repository. CHANGELOG.md is not
checked either, because a changelog is supposed to name things that have since gone.

Usage: agent-spec-lint-refs.py [repo-root]
"""
import os
import re
import sys

TOP = ("bin", "docs", "skills", "agents", "hooks", "personas", "benchmarks",
       "coding-standards", "output-styles", "templates", "core", "rules", "sdlc",
       "memory", "pipeline", "context", "anti-hallucination")

# Both patterns demand a left boundary. Without one, "skillsdirectory.com/skills/x"
# matches as a repository path and "bin/agent-spec-gate.py" matches as a skill name.
BOUNDARY = r"(?<![A-Za-z0-9_./-])"
PATH_RE = re.compile(
    BOUNDARY + r"(?:%s)/[A-Za-z0-9_.*<>-]+(?:/[A-Za-z0-9_.*<>-]+)*" % "|".join(TOP))
SKILL_RE = re.compile(BOUNDARY + r"/(agent-spec(?:-[a-z0-9]+)*)(?![A-Za-z0-9_./-])")

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".agent-spec"}
SKIP_FILES = {"CHANGELOG.md"}


def scan_files(root):
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            if name.endswith(".md") and name not in SKIP_FILES:
                yield os.path.join(base, name)


def check(root):
    problems = []
    skills_dir = os.path.join(root, "skills", "claude")
    known_skills = set(os.listdir(skills_dir)) if os.path.isdir(skills_dir) else set()

    for path in sorted(scan_files(root)):
        rel = os.path.relpath(path, root)
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue

        for raw in set(PATH_RE.findall(text)):
            # A placeholder or a glob names a shape, not a file.
            if any(ch in raw for ch in "*<>"):
                continue
            # Prose that trails off mid-path ("skills/claude/agent-spec-") is not a claim.
            if raw.endswith(("-", "/", ".")):
                continue
            if not os.path.exists(os.path.join(root, raw.rstrip(".,;:)"))):
                problems.append("%s names %s, which does not exist" % (rel, raw))

        for name in set(SKILL_RE.findall(text)):
            if name in ("agent-spec",) and "skills/claude/agent-spec" not in text:
                pass
            if known_skills and name not in known_skills:
                problems.append("%s names the skill /%s, which is not installed" % (rel, name))

    return problems


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    problems = check(root)
    for p in problems:
        print(p)
    if problems:
        print("%d dangling reference(s)" % len(problems))
        return 1
    print("every path and skill name resolves")
    return 0


if __name__ == "__main__":
    sys.exit(main())
