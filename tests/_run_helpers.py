"""Shared helpers for the agent-spec-run tests (stdlib only, Python 3.9+)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_PY = os.path.join(REPO_DIR, "bin", "agent-spec-run.py")
EXAMPLE_WF = os.path.join(REPO_DIR, "skills", "agent-spec-wf-example", "SKILL.md")


def workflow_text(name="agent-spec-wf-t", steps=None, extra=""):
    """A workflow skill with the given steps (default: a -> b -> c)."""
    if steps is None:
        steps = [("a", []), ("b", ["a"]), ("c", ["b"])]
    lines = []
    for sid, needs in steps:
        lines.append("- id: %s" % sid)
        lines.append("  needs: [%s]" % ", ".join(needs))
        lines.append("  ai: true")
    return ("---\nname: \"%s\"\ndescription: >-\n  Test workflow.\n---\n\n# t\n\n```steps\n%s\n```\n%s"
            % (name, "\n".join(lines), extra))


class Sandbox(object):
    """Temp workspace with an `.agent-spec/` dir; runs the script with that cwd."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="aspec-run-")
        os.makedirs(os.path.join(self.root, ".agent-spec"))
        self.wf = os.path.join(self.root, "wf", "SKILL.md")
        self.write_workflow(workflow_text())

    def write_workflow(self, text):
        os.makedirs(os.path.dirname(self.wf), exist_ok=True)
        with open(self.wf, "w", encoding="utf-8") as fh:
            fh.write(text)

    def run(self, *args):
        """Return (exit_code, parsed_json_or_None, stderr)."""
        proc = subprocess.run([sys.executable, RUN_PY] + [str(a) for a in args], cwd=self.root,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        out = None
        if proc.stdout.strip():
            out = json.loads(proc.stdout)
        return proc.returncode, out, proc.stderr

    def start(self, request="do the thing", wf=None, *extra):
        code, out, err = self.run("start", "--workflow", "t", "--request", request,
                                  "--workflow-file", wf or self.wf, *extra)
        assert code == 0, (code, out, err)
        return out["run_id"]

    def run_dir(self, run_id):
        return os.path.join(self.root, ".agent-spec", "runs", run_id)

    def events(self, run_id):
        with open(os.path.join(self.run_dir(run_id), "events.jsonl"), encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()
