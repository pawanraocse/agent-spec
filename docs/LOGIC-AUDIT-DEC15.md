# Logic Audit — AI-First Realignment (DEC-15 / AF-007)

> **Document type:** Architecture & Implementation Audit  
> **Authority:** DEC-15 (MASTER-PLAN v3.1.0 §AI-first principle)  
> **Rule:** Code is permitted only for: *Security*, *Exact computation*, *Per-call latency*, or *Plumbing*.

---

## 1. Summary Matrix

| File / Component | Primary Function | Current LOC | Allowed Reason | Verdict & Recommendation |
|---|---|---|---|---|
| `bin/agent-spec-tokens.py` | Transcript parsing & token accounting | ~1,200 | Exact computation & plumbing | **Shrink & Keep:** Keep exact token counting, transcript extraction, and A/B delta calculation. Strip subjective grading/heuristics. |
| `bin/agent-spec-memory.py` | Fact storage, indexing, linting, dedup | ~724 | Plumbing (storage) vs AI (dedup) | **Shrink:** Keep file storage, `INDEX.md` formatting, and schema validation (plumbing). Move duplicate/conflict detection to `/agent-spec-remember` skill prompt. |
| `bin/agent-spec-receipt.py` | Session receipt generation & daily rollup | ~350 | Exact computation & plumbing | **Keep:** Deterministic counting of tool turns, duration, and tokens. Zero subjective guesswork. |
| `bin/aspec_platform/savings.py` | Context savings formula calculation | ~180 | Exact computation | **Keep:** Pure mathematical model: $(Tokens_{naive} - Tokens_{graph})$. Essential for proof pack. |
| `bin/aspec_platform/cursor_sessions.py` | Cursor DB scraper & `evaluate_session` | ~560 | None for evaluation; Plumbing for scraper | **Shrink:** Retire `evaluate_session` (invented base score 82). Replace with `.agent-spec/metrics/reviews/*.json` from `agent-spec-session-review` skill. |
| `hooks/cursor-pre-tool-use.py` | Quarantine & token cap guards | ~525 | Security floor & per-call latency | **Keep:** Synchronous hook requiring <5ms latency. Prevents secrets leakage and prompt runaway without network roundtrips. |
| `bin/graphify-build.py` | AST parsing & graph topology building | ~850 | Exact computation | **Keep:** Deterministic symbol extraction and import dependency graph building. |

---

## 2. Detailed Findings

### 2.1 `cursor_sessions.evaluate_session`
- **Current State:** Starts every session at score 82, deducts points based on hardcoded arbitrary rules, and injects fake praise like "0 credential leaks detected" without verification.
- **DEC-15 Action:** Deprecate in favor of the `agent-spec-session-review` skill and `agent-spec-reviewer` subagent. The dashboard now renders the `AI-judged` badge or `"Not reviewed"`.

### 2.2 `agent-spec-memory.py`
- **Current State:** Hand-coded text-matching heuristics attempt to flag contradictory facts.
- **DEC-15 Action:** Let the LLM judge contradiction and deduplication during the interactive `/agent-spec-remember` turn. The Python script remains purely for atomic writing, linting schema versions, and updating `INDEX.md`.

### 2.3 `insights.gaps`
- **Current State:** Mixed verifiable facts (`step_failed`, `secret_path_blocked`) with speculative heuristics (`token_spike`, `whole_file_no_graph`).
- **DEC-15 Action:** Split completed in AF-006: deterministic facts remain in SQL; speculative gaps become model-evaluated findings in session reviews.
