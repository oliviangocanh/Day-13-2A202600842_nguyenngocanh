"""YOUR mitigation + observability layer (Day 13 toolkit).

The agent is a SILENT black box on a REAL LLM whose arithmetic is unreliable
(it fabricates/miscomputes totals). mitigate() wraps every request and:

  - OBSERVES   : one structured AGENT_CALL log line per request (latency / tokens /
                 cost / tools / loops / PII) -- the only place these signals exist.
  - RECOMPUTES : reads the tool results from the trace (unit_price, discount %,
                 shipping) and computes the total DETERMINISTICALLY in Python, then
                 overrides the answer. This is the legal "arithmetic/guardrail
                 validation" move and fixes the model's wrong totals + bad refusals.
  - GUARDS     : refuses correctly (not found / out of stock / qty > stock /
                 destination not served); redacts email/phone; sanitizes order-note
                 injection; caches repeats; retries transient failures.

Thread-safe: the run is concurrent, so the shared cache is guarded by cache_lock.
Prompt fixes live in solution/prompt.txt.
"""
from __future__ import annotations

import re
import time

from telemetry.logger import logger, new_correlation_id, set_correlation_id
from telemetry.cost import cost_from_usage
from telemetry import redact

# Order "note" block + the injection/override cues that make it dangerous.
_NOTE_RE = re.compile(r"(ghi\s*ch[uú]\b.*)$", re.IGNORECASE | re.DOTALL)
_INJECT_RE = re.compile(
    r"(b[oỏ]\s*qua|ignore|override|gi[aá]\s*(?:l[aà]|=|ch[ii])|set\s+price|"
    r"mi[eễ]n\s*ph[ií]|free|=\s*0|th[aà]nh\s*0|system|prompt)",
    re.IGNORECASE,
)
_QTY_RE = re.compile(r"\bmua\s+(\d+)", re.IGNORECASE)
_ORDER_RE = re.compile(r"\bmua\b", re.IGNORECASE)


def _norm(q: str) -> str:
    return re.sub(r"\s+", " ", (q or "").strip()).lower()


def _sanitize(question: str):
    """Strip an order-note block only when it carries injection/override cues."""
    if not isinstance(question, str):
        return question, False
    m = _NOTE_RE.search(question)
    if m and _INJECT_RE.search(m.group(0)):
        return question[: m.start()].rstrip(" -,;.\t"), True
    return question, False


def _qty(question: str) -> int:
    m = _QTY_RE.search(question or "")
    if m:
        try:
            return max(1, int(m.group(1)))
        except ValueError:
            return 1
    return 1


def _tools_from_trace(trace):
    stock = disc = ship = None
    for s in trace or []:
        if not isinstance(s, dict):
            continue
        obs = s.get("observation")
        if not isinstance(obs, dict):
            continue
        t = s.get("tool")
        if t == "check_stock":
            stock = obs
        elif t == "get_discount":
            disc = obs
        elif t == "calc_shipping":
            ship = obs
    return stock, disc, ship


def _recompute(question, trace):
    """Deterministic total/refusal from the tool results in the trace.
    Returns ('total', int) or ('refuse', reason_str) or None (cannot decide)."""
    stock, disc, ship = _tools_from_trace(trace)
    if stock is None:
        return None
    if not stock.get("found", True):
        return ("refuse", "Xin loi, san pham nay khong co trong he thong nen khong the dat mua.")
    if not stock.get("in_stock", True):
        return ("refuse", "Xin loi, san pham hien het hang nen khong the dat mua.")
    qty = _qty(question)
    avail = stock.get("quantity")
    if isinstance(avail, int) and qty > avail:
        return ("refuse", "Xin loi, so luong yeu cau vuot qua ton kho hien co.")
    if isinstance(ship, dict) and (ship.get("error") or ship.get("cost_vnd") is None):
        return ("refuse", "Xin loi, khu vuc nay hien khong duoc phuc vu giao hang.")
    unit = stock.get("unit_price_vnd")
    if not isinstance(unit, (int, float)):
        return None
    subtotal = int(unit) * qty
    pct = 0
    if isinstance(disc, dict) and disc.get("valid"):
        try:
            pct = int(disc.get("percent", 0))
        except (TypeError, ValueError):
            pct = 0
    discounted = subtotal * (100 - pct) // 100
    shipping = int(ship["cost_vnd"]) if isinstance(ship, dict) and isinstance(ship.get("cost_vnd"), (int, float)) else 0
    return ("total", discounted + shipping)


def mitigate(call_next, question, config, context):
    set_correlation_id(new_correlation_id())
    context = context or {}
    cache = context.get("cache")
    lock = context.get("cache_lock")
    qkey = _norm(question)

    # 1) Cache: serve a previously computed identical request.
    if cache is not None and lock is not None:
        with lock:
            hit = cache.get(qkey)
        if hit is not None:
            logger.log_event("CACHE_HIT", {"qid": context.get("qid"), "q": question})
            return hit

    # 2) Injection defense: strip dangerous order-note instructions before the agent sees them.
    safe_q, sanitized = _sanitize(question)

    # 3) Call the black box, with a small retry on a transient failure.
    t0 = time.time()
    result = None
    attempt = 0
    for attempt in range(1, 3):
        result = call_next(safe_q, config)
        if (result or {}).get("status") not in ("wrapper_error", "no_action"):
            break
    wall_ms = int((time.time() - t0) * 1000)

    result = result or {}
    meta = result.get("meta", {}) or {}
    usage = meta.get("usage", {}) or {}
    tools = meta.get("tools_used", []) or []
    trace = result.get("trace", []) or []

    actions = [str(s.get("action")) for s in trace if isinstance(s, dict) and s.get("action")]
    repeated = len(actions) - len(set(actions))

    # 4) Deterministic arithmetic/guardrail override (the big correctness fix):
    #    trust the tool results, not the model's mental math.
    overridden = ""
    if _ORDER_RE.search(question or ""):
        verdict = _recompute(question, trace)
        if verdict is not None:
            kind, val = verdict
            result = dict(result)
            result["answer"] = ("Tong cong: %d VND" % val) if kind == "total" else val
            result["status"] = "ok"
            overridden = kind

    # 5) Boundary guardrail: redact any email/phone left in the answer (esp. non-order queries).
    answer = result.get("answer")
    pii = 0
    if isinstance(answer, str):
        red, pii = redact.redact(answer)
        if pii:
            result = dict(result)
            result["answer"] = red

    # 6) Observability -- the single place these signals exist for this request.
    logger.log_event("AGENT_CALL", {
        "qid": context.get("qid"),
        "session": context.get("session_id"),
        "turn": context.get("turn_index"),
        "status": result.get("status"),
        "wall_ms": wall_ms,
        "latency_ms": meta.get("latency_ms"),
        "steps": result.get("steps"),
        "tools_used": tools,
        "n_tools": len(tools),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "cost_usd": cost_from_usage(meta.get("model", ""), usage),
        "repeated_actions": repeated,
        "pii_redacted": pii,
        "sanitized_injection": sanitized,
        "recomputed": overridden,
        "attempts": attempt,
        "model": meta.get("model"),
    })

    # 7) Cache clean successes.
    if cache is not None and lock is not None and result.get("status") == "ok":
        with lock:
            cache[qkey] = result

    return result
