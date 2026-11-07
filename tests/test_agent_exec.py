#!/usr/bin/env python3
"""Tests for agent_exec job runner (CP-010)."""
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "bin"))
FAKE = os.path.join(REPO, "tests", "fixtures", "fake_cursor_agent.py")

from aspec_platform import agent_exec  # noqa: E402


class AgentExecTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.project = os.path.join(self.tmp, "proj")
        os.makedirs(os.path.join(self.project, ".agent-spec"))
        self._env_cli = os.environ.get("AGENT_SPEC_FAKE_CURSOR_AGENT")
        os.environ["AGENT_SPEC_FAKE_CURSOR_AGENT"] = FAKE

    def _drain_jobs(self, reg):
        for j in list(getattr(reg, "_jobs", {}).values()):
            if j.proc and j.ended is None:
                try:
                    j.proc.wait(timeout=2)
                except Exception:
                    reg.cancel(j.job_id)

    def tearDown(self):
        if self._env_cli is None:
            os.environ.pop("AGENT_SPEC_FAKE_CURSOR_AGENT", None)
        else:
            os.environ["AGENT_SPEC_FAKE_CURSOR_AGENT"] = self._env_cli

    def test_launch_fake_cli(self):
        reg = agent_exec.JobRegistry(self.project)
        r = reg.launch("job1", ["-p", "hello"], self.project)
        self.assertTrue(r.get("ok"), r)
        job = reg.get(r["job_id"])
        self.assertIsNotNone(job)
        if job and job.proc:
            job.proc.wait(timeout=5)

    def test_iter_sse_drains_stdout_queue(self):
        lines = [
            json.dumps({"type": "assistant", "text": "a"}),
            json.dumps({"type": "assistant", "text": "b"}),
        ]
        transcript = tempfile.NamedTemporaryFile("w", suffix=".ndjson", delete=False, encoding="utf-8")
        for line in lines:
            transcript.write(line + "\n")
        transcript.close()
        self.addCleanup(os.unlink, transcript.name)
        prev = os.environ.get("AGENT_SPEC_FAKE_CLI_TRANSCRIPT")
        os.environ["AGENT_SPEC_FAKE_CLI_TRANSCRIPT"] = transcript.name
        if prev is None:
            self.addCleanup(os.environ.pop, "AGENT_SPEC_FAKE_CLI_TRANSCRIPT", None)
        else:
            self.addCleanup(os.environ.__setitem__, "AGENT_SPEC_FAKE_CLI_TRANSCRIPT", prev)

        reg = agent_exec.JobRegistry(self.project)
        launched = reg.launch("job-sse", ["-p", "stream"], self.project)
        self.assertTrue(launched.get("ok"), launched)
        job_id = launched["job_id"]
        chunks: list[str] = []
        for frame in reg.iter_sse(job_id):
            if "event: message" in frame or "event: done" in frame:
                chunks.append(frame)
        job = reg.get(job_id)
        self.assertIsNotNone(job)
        assert job is not None
        if job.proc:
            job.proc.wait(timeout=5)
        self.assertGreaterEqual(len(chunks), 2)
        line_events = [e for e in job.events if e.get("type") == "line"]
        self.assertGreaterEqual(len(line_events), len(lines))

    def test_too_many_jobs(self):
        os.environ["AGENT_SPEC_FAKE_CLI_SLEEP"] = "1"
        self.addCleanup(os.environ.pop, "AGENT_SPEC_FAKE_CLI_SLEEP", None)
        reg = agent_exec.JobRegistry(self.project)
        r1 = reg.launch("j1", ["-p", "one"], self.project)
        r2 = reg.launch("j2", ["-p", "two"], self.project)
        r3 = reg.launch("j3", ["-p", "three"], self.project)
        self.assertTrue(r1.get("ok"))
        self.assertTrue(r2.get("ok"))
        self.assertFalse(r3.get("ok"))
        self.assertEqual(r3.get("error"), "too_many_jobs")
        self._drain_jobs(reg)


if __name__ == "__main__":
    unittest.main()
