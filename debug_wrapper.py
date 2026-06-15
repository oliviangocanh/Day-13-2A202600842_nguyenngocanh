"""TEMP debug wrapper: dump each full result (incl. trace) so we can see the
trace/tool-result format, then build deterministic arithmetic in wrapper.py.
Not for scoring. Run on a tiny --questions set."""
import json


def mitigate(call_next, question, config, context):
    r = call_next(question, config)
    try:
        qid = (context or {}).get("qid", "x")
        with open("trace_%s.json" % qid, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2, default=str)
    except Exception:
        pass
    return r
