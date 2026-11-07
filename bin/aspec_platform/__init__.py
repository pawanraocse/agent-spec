"""algosec-agent-spec platform extra (Phase 2): data layer, ingest, retrieval, dashboard API.

Named `aspec_platform` (not `platform`) so it can never shadow the stdlib `platform` module when
`bin/` is on sys.path. Core harness scripts do not import this package (DEC-03).
"""
