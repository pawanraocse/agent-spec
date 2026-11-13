"""Local dashboard server (D-020, S-003): stdlib `http.server`, read-only JSON from platform.db.

Guards, in order, on every request: `Host` header must be loopback (DNS rebinding) -> 403;
non-GET method -> 405; per-launch token (cookie or `X-Agent-Spec-Token` header; `?token=` only on
`/` to seed the cookie) -> 401. The server binds 127.0.0.1 only and serves the v1 or v2 UI bundle
file, so there is no filesystem path to traverse. Nothing here writes to the database.
"""
from __future__ import annotations

import hmac
import html
import mimetypes
import json
import os
import re
import secrets
import sqlite3
import sys
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

from . import agent_exec, common, db, demo_seed, insights, observe, platform_data, savings, cursor_sessions, traces

HERE = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(HERE, "ui")
UI_DIST = os.path.join(UI_DIR, "dist")
UI_DIST_INDEX = os.path.join(UI_DIST, "index.html")
COOKIE = "aspec_token"
TOKEN_HEADER = "X-Agent-Spec-Token"
LOOPBACK_HOSTS = ("127.0.0.1", "localhost")
CSP_V2 = ("default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
          "connect-src 'self'; img-src 'self' data: blob:; worker-src 'self' blob:; "
          "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
TABLES = ("requests", "steps", "subagent_runs", "events", "gate_events", "tasks", "memory_facts",
          "fact_injections", "experiences", "graph_stats", "quarantine_events")
MAX_LIMIT = 500
RUN_ID = re.compile(r"^/api/runs/([^/]+)$")
SESSION_ID = re.compile(r"^/api/sessions/([^/]+)$")

GRAPH_BLAST = re.compile(r"^/api/graph/blast$")
RUN_EVENTS = re.compile(r"^/api/runs/([^/]+)/events$")
AGENT_STREAM = re.compile(r"^/api/agent/jobs/([^/]+)/stream$")
AGENT_CANCEL = re.compile(r"^/api/agent/jobs/([^/]+)/cancel$")
AGENT_MSG = re.compile(r"^/api/agent/sessions/([^/]+)/messages$")
WF_START = re.compile(r"^/api/workflows/([^/]+)/start$")
POST_MAX_BODY = 65536
PROMPT_MAX = 16384
CURSOR_SESSION_ID = re.compile(r"^/api/cursor/session/([^/]+)$")
REQUEST_ID = re.compile(r"^/api/requests/([^/]{1,400})$")
LIVE_POLL_S = 0.5
LIVE_MAX_S = 600  # a stream closes after this; EventSource reconnects from Last-Event-ID
LIVE_BATCH = 200


def _filters(params):
    return {k: _first(params, k) for k in ("session", "status", "skill", "source", "workspace", "since", "until", "q")
            if _first(params, k)}


def _offset(params) -> int:
    try:
        return max(0, int(_first(params, "offset") or 0))
    except (TypeError, ValueError):
        return 0


# DV-012/DV-041/DV-050/DV-056: read routes that need the project as well as the connection.
PROJECT_ROUTES = {
    "/api/requests": lambda project, conn, q: traces.list_requests(project, conn, _filters(q), _limit(q, 50), _offset(q)),
    "/api/coach/lag": lambda project, conn, q: traces.lag(project, conn, _first(q, "since")),
    "/api/coach/issues": lambda project, conn, q: observe.coach_issues(project, conn),
    "/api/learning": lambda project, conn, q: observe.learning(project, conn, _limit(q, 10)),
    "/api/panels": lambda project, conn, q: observe.panels(project),
    "/api/catalog": lambda project, conn, q: observe.catalog(project, conn),
}


def _use_v2_ui() -> bool:
    return True


def _csp() -> str:
    return CSP_V2



def _safe_dist_file(url_path: str):
    """Resolve a URL path under UI_DIST; None if outside the bundle or missing."""
    if not url_path.startswith("/"):
        return None
    rel = url_path.lstrip("/")
    if not rel or rel.startswith("..") or "/.." in rel:
        return None
    root = os.path.realpath(UI_DIST)
    full = os.path.realpath(os.path.join(UI_DIST, rel))
    if full != root and not full.startswith(root + os.sep):
        return None
    if os.path.isfile(full):
        return full
    return None


def _inject_token_meta(body: bytes, tok: str) -> bytes:
    text = body.decode("utf-8", errors="replace")
    tag = '<meta name="aspec-token" content="%s">' % html.escape(tok, quote=True)
    if "</head>" in text:
        text = text.replace("</head>", tag + "\n</head>", 1)
    else:
        text = tag + text
    return text.encode("utf-8")

class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _limit(params, default: int = 100) -> int:
    try:
        value = int(params.get("limit", [default])[0])
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, MAX_LIMIT))


def _first(params, key):
    values = params.get(key)
    return values[0] if values else None


def api_health(conn, params):
    rows = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in TABLES}
    return {"ok": True, "schema": db.schema_version(conn), "rows": rows}


def api_runs(conn, params):
    sql = ("SELECT r.request_id, r.session_id, r.ordinal, substr(r.prompt_redacted, 1, 200) AS prompt, "
           "r.status, r.source, r.started, r.finished, r.tokens_input, r.tokens_output, "
           "r.tokens_cache_read, r.tokens_estimated, r.cost_usd, r.workflow_id, "
           "(r.tokens_input + r.tokens_output + r.tokens_cache_read) AS tokens_total, "
           "(SELECT COUNT(*) FROM steps s WHERE s.request_id = r.request_id) AS step_count "
           "FROM requests r")
    args = []
    status = _first(params, "status")
    if status:
        sql += " WHERE r.status = ?"
        args.append(status)
    sql += " ORDER BY r.started DESC, r.request_id DESC LIMIT ?"
    args.append(_limit(params))
    return {"runs": [dict(r) for r in conn.execute(sql, args)]}


def api_run_detail(conn, run_id):
    detail = insights.run_detail(conn, run_id)
    if detail is None:
        raise ApiError(404, "run not found")
    return detail


def api_home(conn, params):
    return insights.home(conn)


def api_gaps(conn, params):
    return {"gaps": insights.gaps(conn, limit=_limit(params, 200))}


def api_tasks(conn, params):
    sql = "SELECT task_id, slice, title, status, effort, updated FROM tasks"
    args = []
    status = _first(params, "status")
    if status:
        sql += " WHERE status = ?"
        args.append(status)
    sql += " ORDER BY task_id LIMIT ?"
    args.append(_limit(params, MAX_LIMIT))
    return {"tasks": [dict(t) for t in conn.execute(sql, args)]}


def api_savings(conn, params):
    try:
        return savings.savings(conn, savings.parse_weights(params))
    except savings.InvalidWeight as exc:
        raise ApiError(400, str(exc))


def api_sessions(conn, params):
    return {"sessions": savings.sessions(conn, _limit(params))}


def api_session_detail(conn, session_id, project=None):
    detail = insights.session_detail(conn, session_id, project=project)
    if detail is None:
        raise ApiError(404, "session not found")
    return detail


def api_skills(conn, params, project):
    return insights.skills_catalog(conn, project)


def api_compare(conn, params):
    a, b = _first(params, "a"), _first(params, "b")
    if not a or not b:
        raise ApiError(400, "compare needs a and b (session ids)")
    try:
        return savings.compare(conn, a, b)
    except LookupError as exc:
        raise ApiError(404, str(exc))
    except RuntimeError as exc:
        raise ApiError(502, str(exc))


def api_cursor_workspaces(conn, params):
    return cursor_sessions.get_cursor_workspaces()


def api_cursor_session(conn, composer_id):
    detail = cursor_sessions.get_cursor_session_detail(composer_id)
    if not detail:
        raise ApiError(404, "cursor session not found")
    return detail


ROUTES = {"/api/health": api_health, "/api/runs": api_runs, "/api/tasks": api_tasks,
          "/api/savings": api_savings, "/api/sessions": api_sessions, "/api/compare": api_compare,
          "/api/home": api_home, "/api/gaps": api_gaps, "/api/skills": None,
          "/api/cursor/workspaces": api_cursor_workspaces}


def make_handler(project: str, token: str):
    job_registry = agent_exec.JobRegistry(project)
    class Handler(BaseHTTPRequestHandler):
        server_version = "agent-spec-dashboard"
        sys_version = ""

        def log_message(self, fmt, *args):  # request lines carry `?token=`; never log them
            return

        # ---- guards -------------------------------------------------------------------------
        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").strip().lower()
            name, _, port = host.partition(":")
            if name not in LOOPBACK_HOSTS:
                return False
            return not port or port == str(self.server.server_address[1])

        def _token_ok(self, allow_query: bool, query) -> bool:
            candidates = [self.headers.get(TOKEN_HEADER) or ""]
            jar = SimpleCookie()
            try:
                jar.load(self.headers.get("Cookie") or "")
            except Exception:
                pass
            if COOKIE in jar:
                candidates.append(jar[COOKIE].value)
            if allow_query:
                candidates.append(_first(query, "token") or "")
            return any(c and hmac.compare_digest(c.encode(), token.encode()) for c in candidates)

        # ---- responses ----------------------------------------------------------------------
        def _send(self, status, body: bytes, ctype, extra=None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", _csp())
            self.send_header("Referrer-Policy", "no-referrer")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        # ---- dispatch -----------------------------------------------------------------------
        def _reject_method(self):
            if not self._host_ok():
                return self._json(403, {"error": "forbidden host"})
            self.send_response(405)
            self.send_header("Allow", "GET")
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", _csp())
            self.end_headers()

        ALLOW_POST = frozenset(("/api/agent/sessions", "/api/seed"))

        def _read_body(self) -> bytes:
            length = int(self.headers.get("Content-Length") or "0")
            if length > POST_MAX_BODY:
                raise ApiError(413, "body too large")
            return self.rfile.read(length) if length else b""

        def _origin_ok(self) -> bool:
            origin = self.headers.get("Origin") or ""
            if not origin:
                return True
            port = self.server.server_address[1]
            allowed = "http://127.0.0.1:%d" % port
            return origin == allowed or origin == "http://localhost:%d" % port

        def do_POST(self):
            if not self._host_ok():
                return self._json(403, {"error": "forbidden host"})
            parts = urlsplit(self.path)
            path = parts.path
            if path not in self.ALLOW_POST and not AGENT_MSG.match(path) and not AGENT_CANCEL.match(path) and not WF_START.match(path):
                return self._reject_method()
            if not self._origin_ok():
                return self._json(403, {"error": "forbidden origin"})
            if not self.headers.get(TOKEN_HEADER):
                return self._json(401, {"error": "missing or invalid token"})
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                return self._json(415, {"error": "content-type must be application/json"})
            if not hmac.compare_digest((self.headers.get(TOKEN_HEADER) or "").encode(), token.encode()):
                return self._json(401, {"error": "missing or invalid token"})
            try:
                raw = self._read_body()
                body = json.loads(raw.decode("utf-8") or "{}")
            except (ValueError, ApiError) as exc:
                if isinstance(exc, ApiError):
                    return self._json(exc.status, {"error": exc.message})
                return self._json(400, {"error": "invalid json"})
            if path == "/api/seed":
                action = body.get("action", "seed")
                payload = demo_seed.remove(project) if action == "remove" else demo_seed.seed(project)
                return self._json(200, payload)
            if path == "/api/agent/sessions" or AGENT_MSG.match(path) or AGENT_CANCEL.match(path):
                if os.environ.get("AGENT_SPEC_CONSOLE") != "1":
                    return self._json(404, {"ok": False, "error": "console_frozen",
                                            "hint": "Cursor chat is the console (DEC-15). Set AGENT_SPEC_CONSOLE=1 to enable headless CLI."})
            if path == "/api/agent/sessions":
                prompt = str(body.get("prompt") or "")
                if len(prompt) > PROMPT_MAX:
                    return self._json(413, {"error": "prompt too large"})
                mode = body.get("mode", "ask")
                argv = ["-p", "--mode", mode, "--output-format", "stream-json", "--stream-partial-output",
                        "--trust", "--workspace", project, prompt] if mode in ("ask", "plan") else [
                    "-p", "--output-format", "stream-json", "--stream-partial-output", "--trust",
                    "--workspace", project, prompt]
                if mode == "agent" and not body.get("confirm"):
                    return self._json(400, {"error": "confirm required for agent mode"})
                job_id = common.ulid()
                result = job_registry.launch(job_id, argv, project)
                if not result.get("ok"):
                    status = 429 if result.get("error") == "too_many_jobs" else 503
                    return self._json(status, result)
                return self._json(200, result)
            if (m := AGENT_MSG.match(path)):
                chat_id = m.group(1)
                prompt = str(body.get("prompt") or "")
                argv = ["-p", "--resume", chat_id, "--output-format", "stream-json", "--stream-partial-output",
                        "--trust", "--workspace", project, prompt]
                job_id = common.ulid()
                result = job_registry.launch(job_id, argv, project)
                return self._json(200 if result.get("ok") else 503, result)
            if (c := AGENT_CANCEL.match(path)):
                return self._json(200, job_registry.cancel(c.group(1)))
            if (w := WF_START.match(path)):
                wf = w.group(1)
                inp = str(body.get("input") or "")
                prompt = "/agent-spec-hub-runner %s %s" % (wf, inp)
                argv = ["-p", "--approve-mcps", "--output-format", "stream-json", "--trust",
                        "--workspace", project, prompt]
                job_id = common.ulid()
                result = job_registry.launch(job_id, argv, project)
                return self._json(200 if result.get("ok") else 503, {"ok": result.get("ok"), "job_id": job_id,
                                                                  "copy_command": prompt, **result})
            return self._json(404, {"error": "not found"})

        do_PUT = do_DELETE = do_PATCH = _reject_method

        def do_GET(self):
            if not self._host_ok():
                return self._json(403, {"error": "forbidden host"})
            parts = urlsplit(self.path)
            query = parse_qs(parts.query)
            path = parts.path
            if re.search(r"(?:^|/)\.\.|%2e%2e", path, re.I):
                if not self._token_ok(False, query):
                    return self._json(401, {"error": "missing or invalid token"})
                return self._json(404, {"error": "not found"})
            if path in ("/", "/index.html"):
                return self._index(query)
            dist_file = _safe_dist_file(path)
            if dist_file is not None:
                if not self._token_ok(False, query):
                    return self._json(401, {"error": "missing or invalid token"})
                return self._dist_file(dist_file)
            if not path.startswith("/api/"):
                if not self._token_ok(False, query):
                    return self._json(401, {"error": "missing or invalid token"})
                return self._index(query)
            if not self._token_ok(False, query):
                return self._json(401, {"error": "missing or invalid token"})
            if path == "/api/live":
                return self._live_stream(query)
            if path in PROJECT_ROUTES or REQUEST_ID.match(path):
                try:
                    conn = self._open()
                except (sqlite3.Error, ApiError):
                    conn = None  # hook traces still come from events.jsonl
                try:
                    if path in PROJECT_ROUTES:
                        payload = PROJECT_ROUTES[path](project, conn, query)
                    else:
                        payload = traces.request_detail(project, conn, unquote(REQUEST_ID.match(path).group(1)))
                        if payload is None:
                            return self._json(404, {"error": "request not found"})
                finally:
                    if conn is not None:
                        conn.close()
                return self._json(200, payload)
            handler = ROUTES.get(path)
            run = RUN_ID.match(path)
            session = SESSION_ID.match(path)
            c_session = CURSOR_SESSION_ID.match(path)
            if (handler is None and run is None and session is None and c_session is None and path != "/api/skills"
                    and path not in ("/api/graph", "/api/memory", "/api/experiences", "/api/gates", "/api/pricing", "/api/health/doctor", "/api/status_bar")
                    and not GRAPH_BLAST.match(path) and not RUN_EVENTS.match(path)):
                return self._json(404, {"error": "not found"})
            try:
                conn = self._open()
                try:
                    if path == "/api/skills":
                        payload = api_skills(conn, query, project)
                    elif path == "/api/status_bar":
                        payload = platform_data.api_status_bar(project, conn, job_registry.active_count())
                    elif path == "/api/graph":
                        payload = platform_data.api_graph(project, conn)
                    elif GRAPH_BLAST.match(path):
                        file_arg = _first(query, "file") or ""
                        try:
                            depth = int(_first(query, "depth") or "2")
                        except (TypeError, ValueError):
                            depth = 2
                        payload = platform_data.api_graph_blast(project, file_arg, depth)
                    elif path == "/api/memory":
                        payload = platform_data.api_memory(conn)
                    elif path == "/api/experiences":
                        payload = platform_data.api_experiences(conn)
                    elif path == "/api/gates":
                        payload = platform_data.api_gates(project)
                    elif path == "/api/pricing":
                        payload = platform_data.api_pricing(project)
                    elif path == "/api/health/doctor":
                        payload = platform_data.api_doctor(project)
                    elif (rev := RUN_EVENTS.match(path)):
                        payload = platform_data.api_run_events(project, rev.group(1))
                    elif session is not None:
                        payload = api_session_detail(conn, session.group(1), project)
                    elif c_session is not None:
                        payload = api_cursor_session(conn, c_session.group(1))
                    elif path == "/api/gaps":
                        payload = {"gaps": insights.gaps(conn, limit=_limit(query, 200), project=project)}
                    elif handler is not None:
                        payload = handler(conn, query)
                    else:
                        payload = api_run_detail(conn, run.group(1))
                finally:
                    conn.close()
            except ApiError as exc:
                return self._json(exc.status, {"error": exc.message})
            except sqlite3.Error:
                return self._json(503, {"error": "database unavailable; run: agent-spec-platform.py ingest"})
            self._json(200, payload)

        def _live_stream(self, query):
            """DV-013: Server-Sent Events tail of events.jsonl. Loopback + token guards already ran.
            Resumes from `Last-Event-ID` or `?offset=`; default is the current end of file."""
            path = traces.events_path(project)
            resume = self.headers.get("Last-Event-ID") or _first(query, "offset")
            try:
                offset = int(resume) if resume is not None else os.path.getsize(path)
            except (TypeError, ValueError, OSError):
                offset = 0
            try:
                max_s = min(float(_first(query, "max_s") or LIVE_MAX_S), LIVE_MAX_S)
            except ValueError:
                max_s = LIVE_MAX_S
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", _csp())
            self.end_headers()
            import time as _time
            started = last_beat = _time.monotonic()
            try:
                self.wfile.write(b"retry: 2000\nevent: hello\ndata: {\"offset\": %d}\n\n" % offset)
                self.wfile.flush()
                while _time.monotonic() - started < max_s:
                    rows, new_offset = traces.read_events(path, offset)
                    if new_offset != offset or rows:
                        for i in range(0, len(rows), LIVE_BATCH) or [0]:
                            chunk = rows[i:i + LIVE_BATCH]
                            body = json.dumps({"rows": chunk, "offset": new_offset}, separators=(",", ":"))
                            self.wfile.write(("id: %d\nevent: rows\ndata: %s\n\n" % (new_offset, body)).encode())
                        self.wfile.flush()
                        offset = new_offset
                    elif _time.monotonic() - last_beat > 15:
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
                        last_beat = _time.monotonic()
                    _time.sleep(LIVE_POLL_S)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            self.close_connection = True

        def _open(self):
            path = db.db_path(project)
            if not os.path.isfile(path):
                raise ApiError(503, "no platform db; run: agent-spec-platform.py init")
            return db.connect(path, readonly=True)

        def _dist_file(self, path: str):
            try:
                with open(path, "rb") as fh:
                    body = fh.read()
            except OSError:
                return self._json(404, {"error": "asset missing"})
            ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
            self._send(200, body, ctype)

        def _index(self, query):
            if not self._token_ok(True, query):
                return self._json(401, {"error": "missing or invalid token"})
            try:
                with open(UI_DIST_INDEX, "rb") as fh:
                    body = fh.read()
            except OSError:
                return self._json(404, {"error": "ui missing; build with: (cd ui-src && npm run build)"})
            body = _inject_token_meta(body, token)
            cookie = "%s=%s; HttpOnly; SameSite=Strict; Path=/" % (COOKIE, token)
            self._send(200, body, "text/html; charset=utf-8", {"Set-Cookie": cookie})

    return Handler


def make_server(project: str, host: str = "127.0.0.1", port: int = 8765, token=None):
    """Return `(server, token)`. Refuses any bind address other than loopback."""
    if host not in LOOPBACK_HOSTS:
        raise ValueError("refusing to bind %r: the dashboard is loopback-only" % host)
    token = token or secrets.token_urlsafe(32)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(project, token))
    server.daemon_threads = True
    return server, token


def main(args) -> int:
    project = common.find_project(getattr(args, "project", None))
    token = getattr(args, "token", None) or os.environ.get("AGENT_SPEC_TOKEN")
    try:
        server, token = make_server(project, args.host, args.port, token=token)
    except (OSError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    url = "http://127.0.0.1:%d/?token=%s" % (server.server_address[1], token)
    print("agent-spec dashboard (read-only, loopback): %s  (Ctrl-C to stop)" % url, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
