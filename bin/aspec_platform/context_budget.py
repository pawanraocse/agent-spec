"""Measured context budget for one conversation (exact computation: token arithmetic).

Why this exists: cache reads were 69.5% of the weighted bill across 413 local sessions
(`agent-spec-tokens.py --claude corpus`), and the context at the last turn averaged 4.7x the
first. Every model call re-sends the whole context, so a long chat is paid for again on
every call until it is reset.

Two measured inputs, both from Cursor itself:
- `used`: Cursor's `contextTokensUsed` for the chat (its local store, also shown in the
  chat's context meter). This is the context one model call sends now.
- `floor`: what a reset cannot remove. Preferably the chat's own fixed part from Cursor's
  `promptTokenBreakdown` (every category except the conversation: system prompt, tools,
  rules, skills, MCP, subagent definitions). Otherwise the smallest `contextTokensUsed` of
  any top-level chat on this machine. They are close: on 2026-11-13 the largest chat's
  fixed part was 22,660 tokens and the smallest chat 18,489.

`afterAgentResponse` token counts are per *request* (every call in the agent loop summed:
a trivial "hi" cost 36,176 and a request with two subagents 157,633), so they are shown as
the billed trend and never used as the context size.

Standalone on purpose: the stop hook loads it by path without importing the package, so it
must not import anything outside the standard library.
"""

# Same defaults as agent-spec-tokens.py: cache read 0.1x, cache write 1.25x input price.
READ_WEIGHT = 0.1
WRITE_WEIGHT = 1.25
# agent-spec-tokens.py advises a reset when it pays for itself in under five model calls.
RESET_BREAKEVEN_CALLS = 5.0
MAX_POINTS = 120


def _int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def request_tokens(row):
    """Input tokens billed for one request (all calls in its agent loop), or None.

    Cursor reports `input_tokens` with `cache_read_tokens` inside it (recorded: input 157,633,
    cache_read 134,144); if a harness reports them disjoint (cache_read above input), add them.
    """
    inp = _int(row.get("input_tokens"))
    if inp is None:
        return None
    read = _int(row.get("cache_read_tokens")) or 0
    write = _int(row.get("cache_write_tokens")) or 0
    return inp if inp >= read else inp + read + write


def request_series(rows, conversation_id):
    """Per-request billed tokens for one conversation from events.jsonl rows, oldest first.
    Deduplicated: the hook and Cursor's own hook log record the same generation twice."""
    seen, out = set(), []
    for row in rows:
        if row.get("event") != "afterAgentResponse" or row.get("conversation_id") != conversation_id:
            continue
        tokens = request_tokens(row)
        if tokens is None:
            continue
        key = (row.get("generation_id"), tokens, row.get("output_tokens"))
        if key in seen:
            continue
        seen.add(key)
        out.append({"ts": row.get("ts"), "generation_id": row.get("generation_id"), "input": tokens,
                    "cache_read": _int(row.get("cache_read_tokens")) or 0,
                    "output": _int(row.get("output_tokens")) or 0})
    out.sort(key=lambda p: p.get("ts") or "")
    return out


def series_summary(points):
    """Totals for a request series: billed input, cache-read share, values for a sparkline."""
    vals = [p["input"] for p in points if isinstance(p.get("input"), int)]
    if not vals:
        return None
    total = sum(vals)
    reads = sum(p.get("cache_read") or 0 for p in points)
    step = max(1, -(-len(vals) // MAX_POINTS))
    return {"requests": len(vals), "input_total": total,
            "output_total": sum(p.get("output") or 0 for p in points),
            "cache_read_share": round(reads / total, 3) if total else None, "points": vals[::step]}


CONVERSATION = ("conversation", "summarized_conversation")


def fixed_tokens(breakdown):
    """The part of a chat's context a reset keeps: every category but the conversation."""
    if not isinstance(breakdown, dict) or not breakdown:
        return None
    return sum(v for k, v in breakdown.items() if k not in CONVERSATION and isinstance(v, int))


def machine_floor(usage):
    """The smallest measured fresh-chat size: the smallest chat, or any chat's fixed part."""
    by_id = (usage or {}).get("by_id") or {}
    cands = [v.get("used") for v in by_id.values()] + [fixed_tokens(v.get("breakdown")) for v in by_id.values()]
    cands = [c for c in cands if isinstance(c, int) and c > 0]
    return min(cands) if cands else None


def budget(used, floor, limit=None):
    """The reset arithmetic for a chat whose context is `used` tokens, or None without data.

    carry      = used x read weight              cost of each further model call as things are
    reset_once = floor x write weight            a new chat writes its base once
    after      = floor x read weight             cost of each call after the reset
    break-even = reset_once / (carry - after)    model calls until the reset has paid for itself
    """
    used, floor = _int(used), _int(floor)
    if not used:
        return None
    floor = floor if floor and floor <= used else used
    carry = used * READ_WEIGHT
    reset_once = floor * WRITE_WEIGHT
    after = floor * READ_WEIGHT
    saving = carry - after
    breakeven = round(reset_once / saving, 1) if saving > 0 else None
    if breakeven is None:
        verdict = "fresh"
    elif breakeven < RESET_BREAKEVEN_CALLS:
        verdict = "reset"
    else:
        verdict = "carry"
    limit = _int(limit)
    return {
        "used": used,
        "floor": floor,
        "limit": limit,
        "percent": round(100.0 * used / limit, 1) if limit else None,
        "growth": round(used / floor, 2) if floor else None,
        "carried_tokens": used - floor,
        "carry_per_call": round(carry),
        "reset_once": round(reset_once),
        "saving_per_call": round(saving) if saving > 0 else 0,
        "breakeven_calls": breakeven,
        "verdict": verdict,
        "reset_threshold_calls": RESET_BREAKEVEN_CALLS,
        "weights": {"read": READ_WEIGHT, "write": WRITE_WEIGHT},
        # used/floor/limit are Cursor's counters; every weighted figure (carry, reset,
        # saving, break-even) also depends on the configured price ratios above.
        "provenance": "measured",
        "weighted_provenance": "estimated",
    }


def nudge_text(b):
    """The stop-hook follow-up for a `reset` verdict: numbers first, then the one command."""
    return ("Agent-Spec context check (Cursor's own counter): this chat re-sends {used:,} tokens on every "
            "model call, {growth}x a fresh chat ({floor:,}). A new chat pays for itself in {be} calls and "
            "saves ~{save:,} weighted tokens per call after that. Run `/agent-spec-compact` to write the "
            "state to disk, then tell me to continue in a new chat.").format(
        used=b["used"], growth=b["growth"], floor=b["floor"], be=b["breakeven_calls"], save=b["saving_per_call"])
