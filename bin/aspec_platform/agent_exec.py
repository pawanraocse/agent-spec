"""Thin Cursor CLI job runner for the Agent Console (DEC-14). Stdlib only."""
from __future__ import annotations

import json
import os
import queue
import re
import signal
import shutil
import subprocess
import sys
import threading
import time

from . import common, db, redact

MAX_JOBS = 2
JOB_TIMEOUT_S = 15 * 60
STDERR_CAP = 64 * 1024


def _cli_argv(cli: str, argv: list[str]) -> list[str]:
    if cli.endswith(".py"):
        return [sys.executable, cli] + list(argv)
    return [cli] + list(argv)


def _resolve_cli() -> str | None:
    fake = os.environ.get("AGENT_SPEC_FAKE_CURSOR_AGENT")
    if fake and os.path.isfile(fake):
        return fake
    for name in ("cursor-agent", "agent"):
        path = shutil.which(name)
        if not path:
            continue
        try:
            out = subprocess.check_output([path, "--version"], text=True, stderr=subprocess.STDOUT, timeout=5)
        except (subprocess.SubprocessError, OSError):
            continue
        if re.match(r"^\d{4}\.\d{2}\.\d{2}-", out.strip()):
            return path
    return None


class Job:
    __slots__ = (
        "job_id", "argv", "cwd", "proc", "started", "ended", "exit_code", "events",
        "stderr", "_lock", "stdout_queue", "_stdout_closed",
    )

    def __init__(self, job_id: str, argv: list[str], cwd: str):
        self.job_id = job_id
        self.argv = argv
        self.cwd = cwd
        self.proc = None
        self.started = common.utc_now()
        self.ended = None
        self.exit_code = None
        self.events: list[dict] = []
        self.stderr = ""
        self._lock = threading.Lock()
        self.stdout_queue: queue.Queue[str | None] = queue.Queue()
        self._stdout_closed = False

    def append_event(self, kind: str, payload: dict):
        with self._lock:
            self.events.append({"ts": common.utc_now(), "type": kind, **payload})


class JobRegistry:
    def __init__(self, project: str):
        self.project = project
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.ended is None)

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def launch(self, job_id: str, argv: list[str], cwd: str) -> dict:
        cli = _resolve_cli()
        if not cli:
            return {
                "ok": False,
                "error": "cli_missing",
                "install_hint": "curl https://cursor.com/install -fsS | bash",
            }
        cwd = os.path.realpath(cwd)
        root = os.path.realpath(self.project)
        if cwd != root:
            return {"ok": False, "error": "cwd_forbidden"}
        with self._lock:
            active = sum(1 for j in self._jobs.values() if j.ended is None)
            if active >= MAX_JOBS:
                return {"ok": False, "error": "too_many_jobs"}
            job = Job(job_id, _cli_argv(cli, argv), cwd)
            self._jobs[job_id] = job
        try:
            proc = subprocess.Popen(
                job.argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                cwd=cwd,
                start_new_session=True,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            with self._lock:
                self._jobs.pop(job_id, None)
            return {"ok": False, "error": "spawn_failed", "detail": str(exc)}
        job.proc = proc
        job.append_event("start", {"argv_len": len(job.argv)})

        def _read_stderr():
            assert proc.stderr
            chunks = []
            for line in proc.stderr:
                chunks.append(line)
                if sum(len(c) for c in chunks) > STDERR_CAP:
                    break
            job.stderr = "".join(chunks)[-STDERR_CAP:]

        threading.Thread(target=_read_stderr, daemon=True).start()

        def _read_stdout():
            assert proc.stdout
            try:
                for line in proc.stdout:
                    job.stdout_queue.put(line)
                    job.append_event("line", {"text": line[:200]})
            finally:
                job._stdout_closed = True
                job.stdout_queue.put(None)

        threading.Thread(target=_read_stdout, daemon=True).start()

        def _wait():
            try:
                code = proc.wait(timeout=JOB_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except OSError:
                    proc.kill()
                code = -9
            job.exit_code = code
            job.ended = common.utc_now()
            job.append_event("end", {"exit_code": code})
            self._write_db_event(job)

        threading.Thread(target=_wait, daemon=True).start()
        return {"ok": True, "job_id": job_id}

    def cancel(self, job_id: str) -> dict:
        job = self.get(job_id)
        if not job or not job.proc or job.ended:
            return {"ok": False, "error": "not_running"}
        try:
            os.killpg(os.getpgid(job.proc.pid), signal.SIGTERM)
        except OSError:
            job.proc.kill()
        return {"ok": True}

    def _write_db_event(self, job: Job):
        try:
            conn = db.open_ready(db.db_path(self.project))
            conn.execute(
                "INSERT INTO events (event_id, run_id, ts, type, payload_json) VALUES (?, ?, ?, ?, ?)",
                (common.ulid(), job.job_id, job.ended or common.utc_now(), "agent_job",
                 json.dumps({"exit_code": job.exit_code})),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def iter_sse(self, job_id: str):
        job = self.get(job_id)
        if not job:
            yield "event: error\ndata: {\"error\":\"not_found\"}\n\n"
            return
        stdout_done_at = None
        deadline = time.time() + JOB_TIMEOUT_S + 30
        while time.time() < deadline:
            try:
                line = job.stdout_queue.get(timeout=0.05)
            except queue.Empty:
                line = "__empty__"
            if line is None:
                if stdout_done_at is None:
                    stdout_done_at = time.time()
            elif line != "__empty__":
                frame = self._frame_from_ndjson(line, job)
                if frame:
                    yield frame
            if stdout_done_at is None and job._stdout_closed:
                stdout_done_at = time.time()
            proc = job.proc
            if stdout_done_at and job.ended is None and proc is not None:
                code = proc.poll()
                if code is not None:
                    for _ in range(20):
                        if job.ended is not None:
                            break
                        time.sleep(0.025)
                    if job.ended is None:
                        job.exit_code = code
                        job.ended = common.utc_now()
                        job.append_event("end", {"exit_code": code})
            if stdout_done_at and job.ended is not None:
                while True:
                    try:
                        extra = job.stdout_queue.get_nowait()
                    except queue.Empty:
                        break
                    if extra is None:
                        continue
                    frame = self._frame_from_ndjson(extra, job)
                    if frame:
                        yield frame
                yield "event: done\ndata: {\"exit_code\": %d}\n\n" % (job.exit_code or -1)
                return
            if stdout_done_at and (time.time() - stdout_done_at) > 30 and job.ended is None:
                break
        yield "event: error\ndata: {\"error\":\"timeout\"}\n\n"

    def _frame_from_ndjson(self, line: str, job: Job) -> str:
        line = line.strip()
        if not line:
            return ""
        try:
            obj = json.loads(line)
        except ValueError:
            text = redact.redact(line)
            return "event: message\ndata: %s\n\n" % json.dumps({"chunk": text})
        typ = obj.get("type") or obj.get("event") or "message"
        if typ == "result":
            text = redact.redact(obj.get("result") or obj.get("text") or "")
            return "event: done\ndata: %s\n\n" % json.dumps({"chunk": text, "exit_code": 0})
        if "tool" in typ:
            name = obj.get("name") or (obj.get("tool") or {}).get("name") or "tool"
            call_id = obj.get("call_id") or obj.get("id") or ""
            args = obj.get("args") or obj.get("arguments") or obj.get("writeToolCall", {}).get("args") or {}
            status = "completed" if "completed" in typ else obj.get("status", "running")
            tool_payload = {
                "name": name,
                "call_id": call_id,
                "status": status,
                "args": args,
            }
            return "event: tool\ndata: %s\n\n" % json.dumps(tool_payload)
        chunk = obj.get("text") or obj.get("message") or obj.get("delta") or ""
        if isinstance(chunk, dict):
            chunk = chunk.get("text", "")
        chunk = redact.redact(str(chunk))
        if chunk:
            return "event: message\ndata: %s\n\n" % json.dumps({"chunk": chunk})
        return ""
