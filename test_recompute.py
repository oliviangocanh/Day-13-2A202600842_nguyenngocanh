import json, sys
sys.path.insert(0, ".")
from solution.wrapper import _recompute

cases = [
    ("trace_dbg-coupon.json", "Mua 2 iPad voi coupon VIP20 giao Ha Noi - tong cong bao nhieu VND?", "total 28835000"),
    ("trace_dbg-plain.json",  "Mua 3 iPhone giao Hai Phong tinh tong tien giup minh.",                "total 66030500"),
    ("trace_dbg-oos.json",    "Mua 1 AirPods giao Ha Noi?",                                            "refuse"),
    ("trace_dbg-city.json",   "Mua 1 iPhone giao Da Lat?",                                             "refuse"),
]
ok = True
for f, q, expect in cases:
    r = json.load(open(f, encoding="utf-8"))
    v = _recompute(q, r.get("trace"))
    got = ("%s %s" % (v[0], v[1])) if v and v[0] == "total" else (v[0] if v else "None")
    agent = r.get("answer", "")[:40]
    flag = "OK " if got.startswith(expect) else "XX "
    if not got.startswith(expect):
        ok = False
    print("%s %-22s expect=%-18s got=%-18s | agent said: %s" % (flag, f.replace("trace_dbg-", "").replace(".json", ""), expect, got, agent))
print("ALL PASS" if ok else "SOME FAILED")
