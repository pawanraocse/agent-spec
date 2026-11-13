// v2 Project-page fixtures for the honesty test (DV-005). Static payloads come from a live
// `serve` of this repository; sessions, runs, gaps and tasks are synthetic (the repo has none).
export const V2_ROUTES: Record<string, unknown> = {
 "/api/home": {
  "now": "2026-11-13T09:24:08.421Z",
  "today": {
   "runs": 2,
   "tokens": 15400
  },
  "last_7d": {
   "runs": 9,
   "tokens": 88000
  },
  "graph": {
   "ts": "2026-11-13T08:36:54.000Z",
   "files": 109,
   "edges": 108,
   "symbols": 1020,
   "cycles": 0,
   "age_s": 2834
  },
  "seeded": false,
  "demo_seed_count": 0,
  "saved_vs_baseline": {
   "estimate": true,
   "naive_tokens": 0,
   "graph_tokens": 0,
   "saved_tokens": 0,
   "saved_usd": 0.0
  },
  "learning": []
 },
 "/api/gates": {
  "current_gate": 0,
  "current_gate_name": "REQUIREMENTS",
  "feature": null,
  "gates": [
   {
    "gate": 0,
    "name": "REQUIREMENTS",
    "skill": "/agent-spec-requirements",
    "status": "missing",
    "artifact": "01-REQUIREMENTS.md"
   },
   {
    "gate": 1,
    "name": "TECH-SPEC",
    "skill": "/agent-spec-tech-spec",
    "status": "missing",
    "artifact": "02-TECH-SPEC.md"
   },
   {
    "gate": 2,
    "name": "PRD",
    "skill": "/agent-spec-prd",
    "status": "missing",
    "artifact": "03-PRD.md"
   },
   {
    "gate": 3,
    "name": "HLD",
    "skill": "/agent-spec-hld",
    "status": "missing",
    "artifact": "04-HLD.md"
   },
   {
    "gate": 4,
    "name": "LLD",
    "skill": "/agent-spec-lld",
    "status": "missing",
    "artifact": "05-LLD.md"
   },
   {
    "gate": 5,
    "name": "DEVELOPMENT",
    "skill": "/agent-spec-implement",
    "status": "ok",
    "artifact": null
   },
   {
    "gate": 6,
    "name": "REVIEW",
    "skill": "/agent-spec-review",
    "status": "missing",
    "artifact": "06-REVIEW.md"
   },
   {
    "gate": 7,
    "name": "TESTING",
    "skill": "/agent-spec-testing",
    "status": "missing",
    "artifact": "07-TEST-REPORT.md"
   },
   {
    "gate": 8,
    "name": "VALIDATION",
    "skill": "/agent-spec-validation",
    "status": "missing",
    "artifact": "08-VALIDATION.md"
   }
  ],
  "req_trace": []
 },
 "/api/savings": {
  "estimate": true,
  "weights": {
   "bytes_per_token": 4.0,
   "context_bytes": 152.0,
   "price_per_mtok": 3.0,
   "resend_turns": 1.0
  },
  "measured": {
   "whole_file_reads": 0,
   "whole_file_bytes": 0,
   "graph_queries": 0
  },
  "naive_tokens": 4000,
  "graph_tokens": 2800,
  "saved_tokens": 1200,
  "saved_usd": 0.0036
 },
 "/api/health/doctor": {
  "ok": true,
  "checks": [
   {
    "id": "project",
    "status": "OK",
    "message": "/home/pawan/personal/agent-spec has .agent-spec/",
    "fix": ""
   },
   {
    "id": "skills",
    "status": "WARN",
    "message": "10 package skill(s) not installed, e.g. agent-spec-ai-architect",
    "fix": "/home/pawan/personal/agent-spec/install.sh"
   },
   {
    "id": "hooks",
    "status": "OK",
    "message": "sessionStart + preToolUse + sessionEnd/stop registered, scripts present",
    "fix": ""
   },
   {
    "id": "graph",
    "status": "OK",
    "message": "graph built 0.0 days ago, 140 files",
    "fix": ""
   },
   {
    "id": "digest",
    "status": "OK",
    "message": "digest JSON valid (1864 B)",
    "fix": ""
   },
   {
    "id": "footprint",
    "status": "INFO",
    "message": "always-on ~1905 tokens/turn (rule 5756 B + digest 1864 B); under 5% of a turn once context exceeds ~38100 tokens",
    "fix": ""
   },
   {
    "id": "memory",
    "status": "OK",
    "message": "memory index 4903 B (limit 8000)",
    "fix": ""
   },
   {
    "id": "register",
    "status": "INFO",
    "message": "this is the algosec-agent-spec clone (refreshed by a bare ./install.sh)",
    "fix": ""
   },
   {
    "id": "version",
    "status": "OK",
    "message": "harness matches package 2.0.0",
    "fix": ""
   },
   {
    "id": "git-hooks",
    "status": "OK",
    "message": "post-checkout, post-merge, post-rewrite installed",
    "fix": ""
   },
   {
    "id": "team",
    "status": "INFO",
    "message": "no team.yaml (optional team defaults)",
    "fix": ""
   },
   {
    "id": "audit",
    "status": "OK",
    "message": "token audit: no findings",
    "fix": ""
   },
   {
    "id": "coexistence",
    "status": "OK",
    "message": "no stacked always-on style rule",
    "fix": ""
   },
   {
    "id": "mcp",
    "status": "OK",
    "message": "MCP tool schemas 6 tokens (limit 4000)",
    "fix": ""
   }
  ]
 },
 "/api/graph": {
  "nodes": [
   {
    "id": "bin/agent-spec-backlog.py",
    "type": "file",
    "lang": "python",
    "layer": "unknown",
    "in_degree": 0
   },
   {
    "id": "bin/agent-spec-digest.py",
    "type": "file",
    "lang": "python",
    "layer": "unknown",
    "in_degree": 0
   },
   {
    "id": "bin/agent-spec-doctor.py",
    "type": "file",
    "lang": "python",
    "layer": "unknown",
    "in_degree": 0
   },
   {
    "id": "bin/agent-spec-gate.py",
    "type": "file",
    "lang": "python",
    "layer": "unknown",
    "in_degree": 0
   },
   {
    "id": "bin/agent-spec-lint-refs.py",
    "type": "file",
    "lang": "python",
    "layer": "unknown",
    "in_degree": 0
   },
   {
    "id": "bin/agent-spec-mcp-filter.py",
    "type": "file",
    "lang": "python",
    "layer": "unknown",
    "in_degree": 0
   }
  ],
  "edges": [],
  "stats": {
   "files": 109,
   "internal_edges": 203,
   "integration_edges": 0,
   "external_packages": 94,
   "test_files": 48,
   "cycles": 0,
   "services": 2,
   "endpoints": 0,
   "topics": 0,
   "layer_violations": 0,
   "languages": {
    "python": 96,
    "typescript": 41,
    "javascript": 3
   },
   "layers": {
    "unknown": 79,
    "test": 48,
    "controller": 5,
    "config": 5,
    "util": 3
   },
   "most_depended": [
    [
     "ui-src/src/api/client.ts",
     16
    ],
    [
     "ui-src/src/lib/utils.ts",
     16
    ],
    [
     "bin/aspec_platform/__init__.py",
     13
    ],
    [
     "bin/aspec_platform/db.py",
     13
    ],
    [
     "bin/aspec_platform/common.py",
     11
    ],
    [
     "ui-src/src/api/traces.ts",
     9
    ],
    [
     "ui-src/src/components/Num.tsx",
     8
    ],
    [
     "bin/aspec_platform/ingest.py",
     7
    ],
    [
     "tests/_ingest_support.py",
     7
    ],
    [
     "tests/_api_support.py",
     6
    ]
   ],
   "top_external": [
    [
     "os",
     78
    ],
    [
     "sys",
     78
    ],
    [
     "json",
     69
    ],
    [
     "datetime",
     41
    ],
    [
     "subprocess",
     33
    ],
    [
     "__future__",
     32
    ],
    [
     "re",
     29
    ],
    [
     "tempfile",
     29
    ],
    [
     "unittest",
     29
    ],
    [
     "react",
     26
    ]
   ],
   "edges": 108,
   "age_s": 0,
   "ts": "2026-11-13T08:36:54.000Z"
  }
 },
 "/api/skills": {
  "skills": [
   {
    "id": "agent-spec-hub-runner",
    "name": "agent-spec-hub-runner",
    "description": "Run a workflow skill (agent-spec-wf-*) step by step with Cursor Task subagents, recording state through agent-spec-run.py. Resumable and idempotent.",
    "category": "Workflows & Orchestration",
    "tag": "workflow",
    "uses": 0,
    "is_workflow": true
   },
   {
    "id": "agent-spec-wf-eval",
    "name": "agent-spec-wf-eval",
    "description": "Golden-ticket eval for the RCA workflow: score each RCA result strict or directional against a golden CSV and gate on the BugBot baseline. Run via /agent-spec-hub-runner.",
    "category": "Workflows & Orchestration",
    "tag": "workflow",
    "uses": 0,
    "is_workflow": true
   },
   {
    "id": "agent-spec-wf-example",
    "name": "agent-spec-wf-example",
    "description": "Fixture workflow: gather -> analyze -> summarize, read-only. Run via /agent-spec-hub-runner to smoke-test run recording.",
    "category": "Workflows & Orchestration",
    "tag": "workflow",
    "uses": 0,
    "is_workflow": true
   }
  ],
  "usage": []
 },
 "/api/memory": {
  "facts": [
   {
    "fact_id": "20261113-agents-is-a-stale-copy-89bdca",
    "type": "gotcha",
    "subject": ".agents is a stale copy",
    "bytes": 288,
    "confidence": null,
    "scope": "local",
    "updated": "2026-11-13",
    "injections_count": 0
   },
   {
    "fact_id": "20261113-cursor-hook-payload-cont-8fe02e",
    "type": "reference",
    "subject": "cursor hook payload contract",
    "bytes": 481,
    "confidence": "HIGH",
    "scope": "local",
    "updated": "2026-11-13",
    "injections_count": 0
   },
   {
    "fact_id": "20261113-graphify-misreads-this-r-ea9b24",
    "type": "gotcha",
    "subject": "graphify misreads this repo",
    "bytes": 427,
    "confidence": "HIGH",
    "scope": "local",
    "updated": "2026-11-13",
    "injections_count": 0
   }
  ]
 },
 "/api/experiences": {
  "experiences": []
 },
 "/api/gaps": {
  "gaps": [
   {
    "rule": "step_failed",
    "request_id": "req-1",
    "ts": "2026-11-13T10:00:00.000Z",
    "detail": "step 2 exited 1"
   }
  ]
 },
 "/api/tasks": {
  "tasks": [
   {
    "task_id": "DV-057",
    "slice": "6d",
    "title": "Typed handoff display",
    "status": "open",
    "effort": "1d"
   }
  ]
 },
 "/api/runs": {
  "runs": [
   {
    "request_id": "req-1",
    "status": "failed",
    "tokens_total": 15400,
    "workflow_id": "agent-spec-wf-example",
    "started": "2026-11-13T10:00:00.000Z",
    "source": "hook"
   }
  ]
 },
 "/api/runs/req-1": {
  "run": {
   "request_id": "req-1",
   "status": "failed",
   "tokens_total": 15400,
   "workflow_id": "agent-spec-wf-example"
  },
  "steps": [
   {
    "step_id": "s1",
    "ordinal": 1,
    "kind": "tool",
    "name": "Read",
    "status": "ok",
    "duration_ms": 200,
    "tokens_input": 1200,
    "tokens_output": 300,
    "tokens_cache_read": 0,
    "bytes_in": 900
   },
   {
    "step_id": "s2",
    "ordinal": 2,
    "kind": "subagent",
    "name": "agent-spec-search",
    "status": "failed",
    "duration_ms": 2500,
    "tokens_input": 9000,
    "tokens_output": 4900,
    "tokens_cache_read": 0,
    "bytes_in": 12
   }
  ],
  "subagents": [
   {
    "agent": "agent-spec-search",
    "model": "claude-sonnet-4-5",
    "status": "failed",
    "latency_ms": 2500,
    "error": "exit 1"
   }
  ],
  "waterfall": [
   {
    "name": "Read",
    "kind": "tool",
    "ordinal": 1,
    "status": "ok",
    "duration_ms": 200,
    "tokens": 1500
   },
   {
    "name": "agent-spec-search",
    "kind": "subagent",
    "ordinal": 2,
    "status": "failed",
    "duration_ms": 2500,
    "tokens": 13900
   }
  ]
 },
 "/api/runs/req-1/events": {
  "events": []
 },
 "/api/sessions": {
  "sessions": [
   {
    "session_id": "conv-1",
    "runs": 2,
    "tokens": 15400,
    "workspace": "/p",
    "grade": "B",
    "started": "2026-11-13T10:00:00.000Z"
   },
   {
    "session_id": "conv-2",
    "runs": 1,
    "tokens": 4000,
    "started": "2026-11-12T10:00:00.000Z"
   }
  ]
 },
 "/api/sessions/conv-1": {
  "session_id": "conv-1",
  "story": [
   {
    "request_id": "req-1",
    "prompt": "why does login fail",
    "steps": [
     {
      "name": "Read",
      "kind": "tool"
     }
    ],
    "tokens_input": 10200,
    "tokens_output": 5200
   }
  ]
 },
 "/api/compare": {
  "a": {
   "session_id": "conv-1",
   "tokens": 15400,
   "runs": 2,
   "tools": 3
  },
  "b": {
   "session_id": "conv-2",
   "tokens": 4000,
   "runs": 1,
   "tools": 1
  },
  "delta_tokens": 11400,
  "delta_runs": 1
 }
};
