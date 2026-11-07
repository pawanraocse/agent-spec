"""Demo seed rows for empty dashboards (CP-005). All rows use source=demo_seed."""
from __future__ import annotations

import json

from . import common, db


def seed(project: str) -> dict:
    path = db.db_path(project)
    conn = db.open_ready(path)
    try:
        existing = conn.execute("SELECT COUNT(*) FROM requests WHERE source = 'demo_seed'").fetchone()[0]
        if existing:
            return {"ok": True, "action": "noop", "demo_rows": existing}
        now = common.utc_now()
        conn.executescript("""
        INSERT INTO requests (request_id, session_id, ordinal, source, prompt_redacted, status, started,
                              tokens_input, tokens_output, tokens_cache_read, workflow_id)
          VALUES ('demo-seed-r1', 'demo-s1', 1, 'demo_seed', '«demo» example harness run', 'success',
                  '%s', 1200, 400, 50, 'agent-spec-wf-example');
        INSERT INTO steps (step_id, request_id, ordinal, kind, name, tokens_input, status)
          VALUES ('demo-s1', 'demo-seed-r1', 1, 'skill', 'agent-spec-wf-example', 10, 'success'),
                 ('demo-s2', 'demo-seed-r1', 2, 'tool', 'Read', 30, 'success');
        INSERT INTO graph_stats (ts, files, edges, symbols, cycles, age_s, sha)
          VALUES ('%s', 42, 88, 120, 0, 3600, 'demo');
        INSERT INTO memory_facts (fact_id, type, subject, bytes, confidence, scope, updated)
          VALUES ('demo-fact-1', 'gotcha', 'demo seed', 120, 'HIGH', 'local', '%s');
        INSERT INTO experiences (exp_id, title, tier, confidence, uses, successes, created, record_json)
          VALUES ('demo-exp-1', 'Demo journey', 'candidate', 0.5, 1, 1, '%s', '{"task":"demo"}');
        """ % (now, now, now, now))
        conn.commit()
        return {"ok": True, "action": "seeded", "demo_rows": 1}
    finally:
        conn.close()


def remove(project: str) -> dict:
    path = db.db_path(project)
    conn = db.open_ready(path)
    try:
        conn.execute("DELETE FROM steps WHERE request_id IN (SELECT request_id FROM requests WHERE source='demo_seed')")
        n = conn.execute("DELETE FROM requests WHERE source = 'demo_seed'").rowcount
        conn.execute("DELETE FROM graph_stats WHERE sha = 'demo'")
        conn.execute("DELETE FROM memory_facts WHERE fact_id LIKE 'demo-%'")
        conn.execute("DELETE FROM experiences WHERE exp_id LIKE 'demo-%'")
        conn.commit()
        return {"ok": True, "action": "removed", "demo_rows": n}
    finally:
        conn.close()
