"""Cursor Workspaces & Session Intelligence layer.

Provides read-only inspection, conversation extraction, and automated session evaluation
for all Cursor workspaces and composer sessions.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time

import glob
import sys
from urllib.parse import unquote

# DV-003: Cursor's local store is unofficial and per-OS. Override with AGENT_SPEC_CURSOR_USER_DIR
# (the `.../Cursor/User` directory). Every row read from here is labelled "Cursor local store
# (unofficial)" by the API; hook events are the primary source.
USER_DIR_ENV = "AGENT_SPEC_CURSOR_USER_DIR"


def _is_wsl(env) -> bool:
    if env.get("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/version", encoding="utf-8") as fh:
            return "microsoft" in fh.read().lower()
    except OSError:
        return False


def user_dir_candidates(env=None, platform=None, home=None, wsl=None) -> list:
    """Ordered candidate `Cursor/User` directories for this machine (existence not checked)."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    home = home or os.path.expanduser("~")
    out = []
    if env.get(USER_DIR_ENV):
        out.append(env[USER_DIR_ENV])
    if platform == "darwin":
        out.append(os.path.join(home, "Library", "Application Support", "Cursor", "User"))
    elif platform.startswith("win"):
        appdata = env.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
        out.append(os.path.join(appdata, "Cursor", "User"))
    else:
        out.append(os.path.join(env.get("XDG_CONFIG_HOME") or os.path.join(home, ".config"), "Cursor", "User"))
        if _is_wsl(env) if wsl is None else wsl:
            user = env.get("USER") or os.path.basename(home)
            mine = "/mnt/c/Users/%s/AppData/Roaming/Cursor/User" % user
            out.append(mine)
            out.extend(p for p in sorted(glob.glob("/mnt/c/Users/*/AppData/Roaming/Cursor/User")) if p != mine)
    return out


def cursor_user_dir(env=None, platform=None, home=None, wsl=None):
    """First candidate holding `globalStorage/state.vscdb`, else None."""
    for cand in user_dir_candidates(env, platform, home, wsl):
        if os.path.isfile(os.path.join(cand, "globalStorage", "state.vscdb")):
            return cand
    return None


def _store_path(*parts):
    base = cursor_user_dir()
    return os.path.join(base, *parts) if base else os.path.join("/nonexistent-cursor-store", *parts)


def global_vscdb():
    return _store_path("globalStorage", "state.vscdb")


def search_db():
    return _store_path("globalStorage", "conversation-search.db")


def ws_storage():
    return _store_path("workspaceStorage")


def folder_path(uri: str) -> str:
    """workspace.json folder URI -> local path: file://, vscode-remote://wsl+<distro>/, Windows drives."""
    uri = unquote(uri or "")
    m = re.match(r"^vscode-remote://wsl\+[^/]+(/.*)$", uri)
    if m:
        return m.group(1)
    if uri.startswith("file://"):
        uri = uri[len("file://"):]
        m = re.match(r"^/?wsl(?:\.localhost|\$)/[^/]+(/.*)?$", uri, re.I)
        if m:
            return m.group(1) or "/"
    m = re.match(r"^/?([A-Za-z]):[/\\](.*)$", uri)
    if m:
        drive, rest = m.group(1).lower(), m.group(2).replace("\\", "/")
        return "/mnt/%s/%s" % (drive, rest) if (sys.platform.startswith("linux")) else "%s:/%s" % (drive.upper(), rest)
    return uri


def _fmt_relative_time(ts_ms):
    if not ts_ms:
        return "recently"
    now_ms = time.time() * 1000
    diff_sec = max(0, (now_ms - ts_ms) / 1000)
    if diff_sec < 60:
        return "just now"
    if diff_sec < 3600:
        return f"{int(diff_sec // 60)}m ago"
    if diff_sec < 86400:
        return f"{int(diff_sec // 3600)}h ago"
    days = int(diff_sec // 86400)
    return f"{days}d ago"


_SNAPSHOT_LOCK = threading.Lock()
_LEGACY_SNAPSHOT_SWEPT = False


def _cache_dir():
    """A per-user 0700 directory for store copies: they hold every chat Cursor recorded, so
    they must never sit in a shared, world-readable temp directory."""
    global _LEGACY_SNAPSHOT_SWEPT
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    cache = os.path.join(base, "agent-spec", "cursor-snapshot")
    os.makedirs(cache, mode=0o700, exist_ok=True)
    os.chmod(cache, 0o700)
    if not _LEGACY_SNAPSHOT_SWEPT:  # earlier builds copied into /tmp with the default umask
        import shutil
        import tempfile
        shutil.rmtree(os.path.join(tempfile.gettempdir(), "agent-spec-cursor-snapshot"), ignore_errors=True)
        _LEGACY_SNAPSHOT_SWEPT = True
    return cache


def _snapshot(path):
    """Copy a live WAL database (and its -wal file) to a private cache and return the copy.

    Cursor keeps state.vscdb in WAL mode. On a WSL drvfs mount (/mnt/c) SQLite cannot take
    the shared-memory lock, so even a read-only open fails with "disk I/O error". A copy
    of the main file plus the WAL reads consistently, including the newest sessions that
    `immutable=1` would miss. The copy is refreshed only when either source file changes.

    The copy is built under a unique temporary name, its WAL folded into the main file
    (journal_mode=DELETE), and only then renamed over the previous copy. A reader therefore
    always opens one complete, self-contained file, whether the copy is being rebuilt by
    another thread (the server's backfill loop) or another process (the stop hook).
    """
    import shutil

    with _SNAPSHOT_LOCK:
        cache = _cache_dir()
        tag = re.sub(r"[^A-Za-z0-9]+", "_", path)[-120:]
        dst = os.path.join(cache, tag + ".vscdb")
        stamp = []
        for suffix in ("", "-wal"):
            try:
                st = os.stat(path + suffix)
                stamp.append(f"{st.st_mtime_ns}:{st.st_size}")
            except OSError:
                stamp.append("-")
        stamp_file = dst + ".stamp"
        try:
            with open(stamp_file, encoding="utf-8") as fh:
                fresh = fh.read() == "|".join(stamp)
        except OSError:
            fresh = False
        if fresh and os.path.isfile(dst):
            return dst
        tmp = "%s.%d.%d.tmp" % (dst, os.getpid(), threading.get_ident())
        try:
            shutil.copyfile(path, tmp)
            os.chmod(tmp, 0o600)
            if os.path.isfile(path + "-wal"):
                shutil.copyfile(path + "-wal", tmp + "-wal")
                os.chmod(tmp + "-wal", 0o600)
            conn = sqlite3.connect(tmp)
            try:
                conn.execute("PRAGMA journal_mode=DELETE").fetchall()  # checkpoints the WAL in
            finally:
                conn.close()
            os.replace(tmp, dst)
        finally:
            for leftover in (tmp, tmp + "-wal", tmp + "-shm", tmp + "-journal"):
                try:
                    os.remove(leftover)
                except OSError:
                    pass
        for suffix in ("-wal", "-shm"):  # a copy made by an earlier build kept its WAL beside it
            try:
                os.remove(dst + suffix)
            except OSError:
                pass
        with open(stamp_file, "w", encoding="utf-8") as fh:
            fh.write("|".join(stamp))
        return dst


def _connect_ro(path):
    """Open one of Cursor's databases without ever writing to it. None when unreadable."""
    if not os.path.isfile(path):
        return None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()
        return conn
    except sqlite3.Error:
        pass
    try:
        conn = sqlite3.connect(_snapshot(path))
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()
        return conn
    except (sqlite3.Error, OSError):
        return None


def _workspace_composers(ws_ids) -> dict:
    """composerId -> workspaceStorage id, from each workspace's `composer.composerData` item."""
    out = {}
    for wid in ws_ids:
        wconn = _connect_ro(os.path.join(ws_storage(), wid, "state.vscdb"))
        if not wconn:
            continue
        try:
            row = wconn.execute("SELECT value FROM ItemTable WHERE key = 'composer.composerData'").fetchone()
            data = json.loads(row[0]) if row and row[0] else {}
            for item in data.get("allComposers") or []:
                if isinstance(item, dict) and item.get("composerId"):
                    out[item["composerId"]] = wid
        except Exception:
            pass
        finally:
            wconn.close()
    return out


def _unc_to_path(path: str) -> str:
    """`\\\\wsl.localhost\\<distro>\\home\\x` or `\\\\wsl$\\...` -> `/home/x`; other paths via folder_path."""
    m = re.match(r"^[\\/]{2}wsl(?:\.localhost|\$)[\\/][^\\/]+(.*)$", path or "")
    if m:
        return m.group(1).replace("\\", "/") or "/"
    return folder_path(path)


def _rows_from_kv(conn, ws_map) -> list:
    """Stores without `composerHeaders` keep one `composerData:<id>` JSON per session in
    `cursorDiskKV`. Returns rows shaped like the composerHeaders query; the workspace comes
    from the workspace's composer list, else from the session's tracked git repo path."""
    owner = _workspace_composers(list(ws_map))
    by_path = {w["path"].rstrip("/"): wid for wid, w in ws_map.items() if w.get("path")}
    rows, children = [], {}
    for key, val in conn.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%'"):
        try:
            v = json.loads(val)
        except Exception:
            continue
        if not isinstance(v, dict):
            continue
        cid = v.get("composerId") or key.split(":", 1)[1]
        for sub in (v.get("subagentComposerIds") or []) + (v.get("subComposerIds") or []):
            children[sub] = v.get("subagentTypeName") or "subagent"
        v.setdefault("contextTokensUsed", v.get("contextTokensUsed") or 0)
        wid = owner.get(cid)
        if wid is None:
            for repo in v.get("trackedGitRepos") or []:
                wid = by_path.get(_unc_to_path(str((repo or {}).get("repoPath") or "")).rstrip("/"))
                if wid:
                    break
        rows.append([cid, wid, v.get("createdAt"), v.get("lastUpdatedAt") or v.get("createdAt"),
                     0, 0, "", json.dumps({k: v.get(k) for k in ("name", "contextTokensUsed", "totalLinesAdded",
                                                                     "totalLinesRemoved")})])
    for r in rows:
        if r[0] in children:
            r[5], r[6] = 1, children[r[0]]
    rows.sort(key=lambda r: -(r[3] or 0))
    return [tuple(r) for r in rows]


def get_cursor_workspaces():
    """Discover all workspaces and their composer sessions from Cursor local databases."""
    ws_map = {}
    ws_root = ws_storage()
    if os.path.isdir(ws_root):
        for d in os.listdir(ws_root):
            wp = os.path.join(ws_root, d, "workspace.json")
            if os.path.isfile(wp):
                try:
                    with open(wp, "r", encoding="utf-8") as fh:
                        dt = json.load(fh)
                        folder = dt.get("folder") or dt.get("workspace") or ""
                        folder = folder_path(folder)
                        name = os.path.basename(folder)
                        if name.endswith(".code-workspace"):
                            name = name[:-15]
                        ws_map[d] = {"id": d, "name": name or d, "path": folder, "sessions": []}
                except Exception:
                    pass

    conn = _connect_ro(global_vscdb())
    if not conn:
        return {"workspaces": list(ws_map.values()), "total_sessions": 0}

    try:
        c = conn.cursor()
        try:
            c.execute("""
                SELECT composerId, workspaceId, createdAt, lastUpdatedAt, isArchived, isSubagent, subagentTypeName, value
                FROM composerHeaders
                WHERE isArchived = 0
                ORDER BY lastUpdatedAt DESC
            """)
            rows = c.fetchall()
        except sqlite3.OperationalError:
            rows = _rows_from_kv(conn, ws_map)

        other_ws = {"id": "other", "name": "Global / Miscellaneous", "path": "", "sessions": []}

        for r in rows:
            cid, wid, created, updated, archived, is_sub, sub_type, val_str = r
            name = "Untitled Session"
            tokens = 0
            lines_added = 0
            lines_removed = 0
            if val_str:
                try:
                    v = json.loads(val_str)
                    name = v.get("name") or name
                    tokens = v.get("contextTokensUsed") or 0
                    lines_added = v.get("totalLinesAdded") or 0
                    lines_removed = v.get("totalLinesRemoved") or 0
                except Exception:
                    pass

            session_item = {
                "composerId": cid,
                "workspaceId": wid,
                "name": name,
                "createdAt": created,
                "lastUpdatedAt": updated,
                "relativeTime": _fmt_relative_time(updated),
                "isSubagent": bool(is_sub),
                "subagentTypeName": sub_type or "",
                "tokens": tokens,
                "linesAdded": lines_added,
                "linesRemoved": lines_removed
            }

            if wid in ws_map:
                ws_map[wid]["sessions"].append(session_item)
            else:
                other_ws["sessions"].append(session_item)

        result_workspaces = []
        # Current repo workspace first
        cwd = os.getcwd()
        sorted_ws = sorted(ws_map.values(), key=lambda w: (
            0 if w["path"] == cwd else (1 if len(w["sessions"]) > 0 else 2),
            -((w["sessions"][0].get("lastUpdatedAt") or 0) if w["sessions"] else 0)
        ))

        for w in sorted_ws:
            w["session_count"] = len(w["sessions"])
            if w["session_count"] > 0:
                result_workspaces.append(w)

        if other_ws["sessions"]:
            other_ws["session_count"] = len(other_ws["sessions"])
            result_workspaces.append(other_ws)

        return {
            "workspaces": result_workspaces,
            "total_sessions": len(rows),
            "current_workspace": cwd
        }
    finally:
        conn.close()


def load_session_review(composer_id: str, project: str | None = None) -> dict | None:
    """Load AI-judged review from .agent-spec/metrics/reviews/{composer_id}.json.
    Returns None if not reviewed (DEC-15 honest by construction).
    """
    proj = project or os.getcwd()
    rev_dir = os.path.join(proj, ".agent-spec", "metrics", "reviews")
    if not os.path.isdir(rev_dir):
        return None
    rev_path = os.path.join(rev_dir, f"{composer_id}.json")
    if os.path.isfile(rev_path):
        try:
            with open(rev_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return None
    return None


def _messages_from_bubbles(c, composer_id, comp_data, limit=300, cap=4000):
    """Stores without the conversation-search index: one `bubbleId:<composer>:<bubble>` JSON per
    message, ordered by `fullConversationHeadersOnly`. Returns (messages, tool calls), redacted."""
    try:
        from .redact import redact
    except Exception:  # pragma: no cover - package import always works in the harness
        redact = str
    messages, tools, turn = [], [], 0
    for head in (comp_data.get("fullConversationHeadersOnly") or [])[:limit]:
        bid = (head or {}).get("bubbleId")
        if not bid:
            continue
        row = c.execute("SELECT value FROM cursorDiskKV WHERE key = ?", (f"bubbleId:{composer_id}:{bid}",)).fetchone()
        try:
            b = json.loads(row[0]) if row and row[0] else {}
        except Exception:
            continue
        tool = b.get("toolFormerData") or {}
        if isinstance(tool, dict) and tool.get("name"):
            params = tool.get("params") or tool.get("rawArgs") or ""
            tools.append({"case": tool.get("name"), "status": tool.get("status") or "completed",
                          "path": redact(str(params))[:160]})
        text = (b.get("text") or "").strip()
        if not text:
            continue
        role = "user" if b.get("type") == 1 else "assistant"
        if role == "user":
            turn += 1
        messages.append({"role": role, "text": redact(text)[:cap], "turn": max(turn, 1)})
    return messages, tools


def _header_row(c, composer_id):
    """composerHeaders row, or the same shape built from `composerData:<id>` on stores without it."""
    try:
        c.execute("""
            SELECT composerId, workspaceId, createdAt, lastUpdatedAt, isArchived, isSubagent, subagentTypeName, value
            FROM composerHeaders
            WHERE composerId = ?
        """, (composer_id,))
        return c.fetchone()
    except sqlite3.OperationalError:
        pass
    c.execute("SELECT value FROM cursorDiskKV WHERE key = ?", (f"composerData:{composer_id}",))
    row = c.fetchone()
    try:
        v = json.loads(row[0]) if row and row[0] else None
    except Exception:
        v = None
    if not isinstance(v, dict):
        return None
    return (composer_id, None, v.get("createdAt"), v.get("lastUpdatedAt") or v.get("createdAt"), 0,
            1 if v.get("subagentTypeName") else 0, v.get("subagentTypeName") or "",
            json.dumps({k: v.get(k) for k in ("name", "status", "contextTokensUsed", "totalLinesAdded",
                                                "totalLinesRemoved", "lastUpdatedAt")}))


def get_cursor_session_detail(composer_id):
    """Retrieve full structured dialogue, subagents, and automated evaluation for a session."""
    conn = _connect_ro(global_vscdb())
    if not conn:
        return None

    try:
        c = conn.cursor()

        # 1. Header info
        h_row = _header_row(c, composer_id)
        if not h_row:
            return None

        cid, wid, created, updated, archived, is_sub, sub_type, val_str = h_row
        name = "Untitled Session"
        val_json = {}
        if val_str:
            try:
                val_json = json.loads(val_str)
                name = val_json.get("name") or name
            except Exception:
                pass

        # 2. composerData from cursorDiskKV
        c.execute("SELECT value FROM cursorDiskKV WHERE key = ?", (f"composerData:{composer_id}",))
        kv_row = c.fetchone()
        comp_data = json.loads(kv_row[0]) if kv_row and kv_row[0] else {}

        # 3. Subagents with rich prompts and responses
        sub_ids = comp_data.get("subagentComposerIds") or []
        subagents = []
        if sub_ids:
            sub_rows = [r for r in (_header_row(c, sid) for sid in sub_ids) if r]
            for sr in [(r[0], r[6], r[7]) for r in sub_rows]:
                sub_cid = sr[0]
                s_val = json.loads(sr[2]) if sr[2] else {}
                
                # Extract subagent prompt and response from cursorDiskKV
                c.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE ? AND value LIKE \"%text%\"", (f"bubbleId:{sub_cid}:%",))
                s_prompt = ""
                s_response = ""
                for bk, bv in c.fetchall():
                    try:
                        bd = json.loads(bv)
                        if bd.get("type") == 1 and not s_prompt:
                            s_prompt = bd.get("text", "")
                        elif bd.get("type") == 2:
                            txt = (bd.get("text") or "").strip()
                            if txt and len(txt) > len(s_response):
                                s_response = txt
                    except Exception:
                        pass

                subagents.append({
                    "id": sub_cid,
                    "type": sr[1] or "subagent",
                    "name": s_val.get("name") or "Subagent",
                    "status": s_val.get("status") or "completed",
                    "prompt": s_prompt,
                    "response": s_response,
                    "lastUpdatedAt": s_val.get("lastUpdatedAt") or 0
                })

        # 4. Tool calls summary
        c.execute("SELECT value FROM cursorDiskKV WHERE key = ?", (f"composerConvHeaders:{composer_id}:000000",))
        conv_row = c.fetchone()
        tools_executed = []
        if not (conv_row and conv_row[0]) and comp_data.get("fullConversationHeadersOnly"):
            conv_row = (json.dumps(comp_data["fullConversationHeadersOnly"]),)
        if conv_row and conv_row[0]:
            try:
                headers = json.loads(conv_row[0])
                for item in headers:
                    grp = item.get("grouping", {})
                    if grp.get("toolCallCase"):
                        tools_executed.append({
                            "case": grp.get("toolCallCase"),
                            "status": grp.get("toolFormerStatus", "completed"),
                            "path": grp.get("toolDisplayPath", "")
                        })
            except Exception:
                pass

        # 5. Conversation Body
        body_text = ""
        s_conn = _connect_ro(search_db())
        if s_conn:
            try:
                sc = s_conn.cursor()
                sc.execute("""
                    SELECT fts.body
                    FROM conversations c
                    JOIN conversation_fts fts ON fts.rowid = c.fts_rowid
                    WHERE c.id = ?
                """, (composer_id,))
                sb_row = sc.fetchone()
                if sb_row and sb_row[0]:
                    body_text = sb_row[0]
            finally:
                s_conn.close()

        # Parse messages into conversational turns
        messages = []
        if body_text:
            raw_turns = body_text.split("Algosec Cursor AI\n")
            for idx, turn_chunk in enumerate(raw_turns):
                chunk = turn_chunk.strip()
                if not chunk:
                    continue

                if idx == 0:
                    # First turn: user prompt starts it
                    lines = chunk.split("\n", 1)
                    user_text = lines[0].strip()
                    ai_text = lines[1].strip() if len(lines) > 1 else ""
                    if user_text:
                        messages.append({"role": "user", "text": user_text, "turn": 1})
                    if ai_text:
                        messages.append({"role": "assistant", "text": ai_text, "turn": 1})
                else:
                    # Subsequent turns: first line is usually user prompt, remainder is assistant
                    lines = chunk.split("\n", 1)
                    user_text = lines[0].strip()
                    ai_text = lines[1].strip() if len(lines) > 1 else ""

                    if user_text and not user_text.startswith("<system_notification>"):
                        messages.append({"role": "user", "text": user_text, "turn": idx + 1})
                    if ai_text:
                        messages.append({"role": "assistant", "text": ai_text, "turn": idx + 1})

        if not messages:
            messages, bubble_tools = _messages_from_bubbles(c, composer_id, comp_data)
            tools_executed = tools_executed or bubble_tools

        # Load AI-judged review if available (honest by construction; None if unreviewed)
        evaluation = load_session_review(composer_id)

        return {
            "composerId": composer_id,
            "workspaceId": wid,
            "name": name,
            "createdAt": created,
            "lastUpdatedAt": updated,
            "relativeTime": _fmt_relative_time(updated),
            "isSubagent": bool(is_sub),
            "subagentTypeName": sub_type or "",
            "contextTokensUsed": comp_data.get("contextTokensUsed") or 0,
            "contextTokenLimit": comp_data.get("contextTokenLimit") or 200000,
            "contextUsagePercent": comp_data.get("contextUsagePercent") or 0.0,
            "totalLinesAdded": comp_data.get("totalLinesAdded") or 0,
            "totalLinesRemoved": comp_data.get("totalLinesRemoved") or 0,
            "subagents": subagents,
            "tools": tools_executed,
            "evaluation": evaluation,
            "messages": messages,
            "messageCount": len(messages)
        }
    finally:
        conn.close()


def _iso_ms(value):
    """Bubble `createdAt` (ISO string or epoch ms) -> epoch ms, or None."""
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value:
        try:
            from datetime import datetime
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
        except ValueError:
            return None
    return None


def context_usage(path=None) -> dict:
    """Cursor's own context counters for every top-level chat (context budget, exact).

    Returns {"by_id": {composer_id: {"used", "limit", "percent", "name", "updated",
    "breakdown"}}, "floor": int | None} where breakdown is Cursor's own `promptTokenBreakdown`
    ({category id: tokens}, Cursor labels them estimated) and
    floor is the smallest non-zero `contextTokensUsed` of any top-level chat: the measured
    size of a fresh chat. Subagent composers are excluded (they start from a task, not the
    rules). json_extract keeps the read to three fields per row. {} when unreadable.
    """
    conn = _connect_ro(path or global_vscdb())
    if not conn:
        return {}
    try:
        rows = conn.execute(
            "SELECT substr(key, 14), json_extract(value, '$.contextTokensUsed'), "
            "json_extract(value, '$.contextTokenLimit'), json_extract(value, '$.contextUsagePercent'), "
            "json_extract(value, '$.subagentComposerIds'), json_extract(value, '$.name'), "
            "json_extract(value, '$.lastUpdatedAt'), json_extract(value, '$.promptTokenBreakdown.categories') "
            "FROM cursorDiskKV "
            "WHERE key LIKE 'composerData:%' AND json_valid(value)").fetchall()
    except sqlite3.Error:
        return {}
    finally:
        conn.close()
    children = set()
    for row in rows:
        try:
            children.update(json.loads(row[4]) if row[4] else [])
        except (ValueError, TypeError):
            continue
    by_id = {}
    for cid, used, limit, pct, _subs, name, updated, cats in rows:
        if cid in children or not isinstance(used, int) or used <= 0:
            continue
        breakdown = {}
        try:
            for c in json.loads(cats) if cats else []:
                if isinstance(c, dict) and isinstance(c.get("estimatedTokens"), int):
                    breakdown[str(c.get("id") or c.get("label"))] = c["estimatedTokens"]
        except (ValueError, TypeError):
            breakdown = {}
        by_id[cid] = {"used": used, "limit": limit if isinstance(limit, int) else None,
                      "percent": round(pct, 1) if isinstance(pct, (int, float)) else None,
                      "name": name if isinstance(name, str) else None,
                      "updated": _iso_ms(updated) if isinstance(updated, (int, float)) else None,
                      "breakdown": breakdown or None}
    return {"by_id": by_id, "floor": min((v["used"] for v in by_id.values()), default=None)}


def store_conversations(limit: int = 200, bubble_cap: int = 600) -> list:
    """Every recent composer in Cursor's local store (unofficial, DV-010 history source).

    Returns dicts: {composer_id, name, workspace, model, mode, status, created, updated,
    subagent_ids, subagent_type, bubbles: [{type, created, text, tool}]}; text is redacted and
    capped. Read-only; returns [] when no store is found or its schema is unknown.
    """
    from .redact import redact
    conn = _connect_ro(global_vscdb())
    if not conn:
        return []
    ws_map = {}
    root = ws_storage()
    if os.path.isdir(root):
        for d in os.listdir(root):
            try:
                with open(os.path.join(root, d, "workspace.json"), encoding="utf-8") as fh:
                    dt = json.load(fh)
                ws_map[d] = {"path": folder_path(dt.get("folder") or dt.get("workspace") or "")}
            except (OSError, ValueError):
                continue
    try:
        try:
            heads = _rows_from_kv(conn, ws_map)
        except sqlite3.OperationalError:
            return []
        out = []
        for cid, wid, created, updated, _arch, _sub, sub_type, _val in heads[:limit]:
            row = conn.execute("SELECT value FROM cursorDiskKV WHERE key = ?", (f"composerData:{cid}",)).fetchone()
            try:
                comp = json.loads(row[0]) if row and row[0] else {}
            except ValueError:
                comp = {}
            bubbles = []
            for head in (comp.get("fullConversationHeadersOnly") or [])[:bubble_cap]:
                bid = (head or {}).get("bubbleId")
                if not bid:
                    continue
                b_row = conn.execute("SELECT value FROM cursorDiskKV WHERE key = ?",
                                     (f"bubbleId:{cid}:{bid}",)).fetchone()
                try:
                    b = json.loads(b_row[0]) if b_row and b_row[0] else None
                except ValueError:
                    b = None
                if not isinstance(b, dict):
                    continue
                tf = b.get("toolFormerData") if isinstance(b.get("toolFormerData"), dict) else {}
                tool = None
                if tf.get("name"):
                    params = tf.get("params") or tf.get("rawArgs") or ""
                    result = tf.get("result")
                    tool = {"name": str(tf["name"])[:64], "status": str(tf.get("status") or "completed")[:32],
                            "params": redact(str(params))[:300],
                            "params_bytes": len(str(params)), "result_bytes": len(str(result or "")),
                            "tool_call_id": tf.get("toolCallId")}
                bubbles.append({"type": b.get("type"), "created": _iso_ms(b.get("createdAt")),
                                "text": redact((b.get("text") or "").strip())[:2000],
                                "text_chars": len(b.get("text") or ""),
                                "thinking_ms": b.get("thinkingDurationMs"), "tool": tool})
            model = (comp.get("modelConfig") or {}).get("modelName") if isinstance(comp.get("modelConfig"), dict) else None
            out.append({"composer_id": cid, "name": comp.get("name") or "Untitled session",
                        "workspace": (ws_map.get(wid) or {}).get("path") if wid else None,
                        "model": model, "mode": comp.get("unifiedMode") or comp.get("forceMode"),
                        "status": comp.get("status"), "created": created, "updated": updated,
                        "subagent_ids": list(comp.get("subagentComposerIds") or []),
                        "subagent_type": sub_type or comp.get("subagentTypeName") or "",
                        "context_tokens": comp.get("contextTokensUsed"),
                        "lines_added": comp.get("totalLinesAdded"), "lines_removed": comp.get("totalLinesRemoved"),
                        "bubbles": bubbles})
        return out
    finally:
        conn.close()
