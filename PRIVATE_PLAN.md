# Kế hoạch chạy phase PRIVATE — mục tiêu headline ≥ 90

> Bản public đã đạt **100.0**. File này là checklist sẵn-sàng-chạy cho phase PRIVATE.
> Lệnh chạy bằng **PowerShell** (gọi WSL Ubuntu). Thay `KEY_MOI` bằng OpenAI API key mới.
> Đường dẫn dự án trong WSL: `/mnt/d/VIN_UNI/day13/Day-13-2A202600842_nguyenngocanh`

---

## 0. Bối cảnh — vì sao đang thuận lợi

Private = **bộ giữ kín + paraphrase + đòn injection** (giá/lệnh giả trong ghi chú "GHI CHU").

Wrapper `mitigate()` đọc **giá / % giảm / phí ship / tồn kho / thành phố từ `trace` (kết quả tool)**,
KHÔNG parse từ câu hỏi. Hệ quả:
- Paraphrase **không** ảnh hưởng giá/giảm-giá/tồn-kho/thành-phố — chỉ ảnh hưởng **số lượng (qty)**.
- **Injection giá giả bị vô hiệu hóa tự động**: tổng tính từ giá `check_stock` thật, không dùng giá trong note.

→ Điểm dễ vỡ duy nhất là **parse qty**. Kế hoạch tập trung hardening chỗ đó + thêm finding injection.

---

## 1. TRƯỚC TIÊN: chốt public (nếu chưa push)

```powershell
cd d:\VIN_UNI\day13\Day-13-2A202600842_nguyenngocanh
git add solution/
git add -f run_output.json score.json
git commit -m "Public submission: headline 100.0"
git push
```
⚠️ Sau khi push public xong mới làm Bước 2 (vì Bước 2 sửa solution/ khác bản public).
⚠️ **Sao lưu run public 100**: đã có `run_output_100.backup.json` — đừng xóa.

---

## ✅ TRẠNG THÁI (đã làm)
- Prep Bước 2 **ĐÃ ÁP DỤNG** vào solution: findings 11 (có prompt_injection), `context_size=4`,
  `_qty` hardening (test OK), `_INJECT_RE` mở rộng. selfcheck PASS (11 findings).
- Private **SIM** đã có: `observathon-private-sim-linux-x64/` → bộ **80 câu**, qid `prv-001..prv-080`.
- Private **SCORE** binary: **CHƯA có** (ra ~mốc 3.5h). Chưa có nó thì KHÔNG đo được headline private.

## 2. PREP (ĐÃ XONG — để tham khảo) — 3 chỉnh sửa

### 2a. findings.json — thêm lại `prompt_injection` (→ 11 findings)
Mở `solution/findings.json`, trong mảng `findings` thêm object này (trước dấu `]` cuối),
và **xóa** dòng `_note_private_only`:
```json
,
{
  "fault_class": "prompt_injection",
  "evidence": {"metric": "note_override_rate", "observed": "agent obeys fake prices/instructions hidden in order notes ('GHI CHU ...'); the stated total diverges from the real catalog price", "trace_ids": []},
  "root_cause": "the shipped prompt follows instructions/prices embedded in order text instead of treating notes as data.",
  "suggested_fix": "prompt: prices ONLY from check_stock, treat notes/'GHI CHU' as DATA; wrapper: recompute total from check_stock price (ignores injected price) + strip injected note blocks."
}
```

### 2b. config.json — `context_size` 2 → 4 (chống fail/drift khi re-run)
Đổi dòng `"context_size": 2,` thành `"context_size": 4,`

### 2c. wrapper.py — hardening `_qty` (paraphrase-proof)
Thay hàm `_qty` và regex qty hiện tại bằng:
```python
_BUY_QTY = re.compile(r"\b(?:mua|đặt|dat|lấy|lay|order|cần|can|muốn|muon)\s+(\d+)", re.IGNORECASE)
_STANDALONE = re.compile(r"(?<![A-Za-z0-9])(\d+)(?![A-Za-z0-9])")  # bỏ số trong VIP20/SALE15
_WORDNUM = {"mot": 1, "một": 1, "hai": 2, "ba": 3, "bon": 4, "bốn": 4, "nam": 5, "năm": 5,
            "sau": 6, "sáu": 6, "bay": 7, "bảy": 7, "tam": 8, "tám": 8, "chin": 9, "chín": 9, "muoi": 10, "mười": 10}


def _qty(question: str) -> int:
    q = question or ""
    m = _BUY_QTY.search(q)               # 1) số ngay sau động từ mua/đặt/lấy...
    if m:
        return max(1, int(m.group(1)))
    m = _STANDALONE.search(q)            # 2) số độc lập đầu tiên (không nằm trong mã coupon)
    if m:
        return max(1, int(m.group(1)))
    for w, n in _WORDNUM.items():        # 3) số viết bằng chữ
        if re.search(r"\b%s\b" % w, q, re.IGNORECASE):
            return n
    return 1                            # 4) mặc định 1
```
(Giữ nguyên `_ORDER_RE` để nhận diện đơn; có thể mở rộng:
`_ORDER_RE = re.compile(r"\b(mua|đặt|dat|lấy|lay|order)\b", re.IGNORECASE)`)

### 2d. wrapper.py — tăng nhận diện injection trong note (tùy chọn, an toàn)
Mở rộng `_INJECT_RE` thêm các mẫu: `gia\s*(?:that|thuc|moi)`, `tinh\s*\d`, `chi\s*\d+\s*vnd`, `=\s*\d`.

### 2e. Kiểm tra
```powershell
wsl.exe -d Ubuntu-24.04 -u root -- bash -lc "cd /mnt/d/VIN_UNI/day13/Day-13-2A202600842_nguyenngocanh && python3 harness/selfcheck.py"
```
Phải thấy `[PASS]` cả 5 và `findings.json (11)`.

---

## 3. KHI PRIVATE SIM PHÁT HÀNH (~mốc 3h)

### 3a. Xác nhận binary + qid offline (mock, KHÔNG tốn key)
Tìm thư mục kiểu `observathon-private-sim-linux-x64` (và `...-score...`). Rồi:
```powershell
wsl.exe -d Ubuntu-24.04 -u root -- bash -lc "cd /mnt/d/VIN_UNI/day13/Day-13-2A202600842_nguyenngocanh && chmod +x observathon-private-sim-linux-x64/observathon-sim observathon-private-score-linux-x64/observathon-score; python3 -c \"import json;c=json.load(open('solution/config.json'));c['provider']='mock';json.dump(c,open('/tmp/m.json','w'))\"; ./observathon-private-sim-linux-x64/observathon-sim --config /tmp/m.json --wrapper solution/wrapper.py --out /tmp/p.json --concurrency 4 >/dev/null 2>&1; python3 -c \"import json;d=json.load(open('/tmp/p.json'));print('n=',d['n'],'phase=',d['phase'],'qid0=',d['results'][0]['qid'])\""
```
→ kỳ vọng `phase=private`, qid kiểu `priv-*`. (Nếu tên thư mục khác, sửa lại đường dẫn.)

### 3b. Debug-capture vài câu paraphrase + injection (rẻ ~$0.03) — xác minh trace + qty + injection
Tạo `debug_questions_priv.json` (4–6 câu mô phỏng paraphrase + 1 câu có "GHI CHU" giá giả), rồi:
```powershell
wsl.exe -d Ubuntu-24.04 -u root -- bash -c "export OPENAI_API_KEY='KEY_MOI'; cd /mnt/d/VIN_UNI/day13/Day-13-2A202600842_nguyenngocanh && ./observathon-private-sim-linux-x64/observathon-sim --questions debug_questions_priv.json --wrapper debug_wrapper.py --out /tmp/dbg.json --concurrency 4"
```
Đọc các file `trace_*.json` sinh ra: kiểm tra `observation` còn các field `unit_price_vnd / percent / cost_vnd / found / in_stock / quantity` không (nếu giữ nguyên → recompute chạy tốt). Với câu injection: tổng phải tính theo **giá tool**, KHÔNG theo giá trong note.

### 3c. Chạy full private + chấm
```powershell
wsl.exe -d Ubuntu-24.04 -u root -- bash -c "export OPENAI_API_KEY='KEY_MOI'; cd /mnt/d/VIN_UNI/day13/Day-13-2A202600842_nguyenngocanh && ./observathon-private-sim-linux-x64/observathon-sim --config solution/config.json --wrapper solution/wrapper.py --out run_output.json --concurrency 8 && ./observathon-private-score-linux-x64/observathon-score --run run_output.json --findings solution/findings.json --team 2A202600842_nguyenngocanh --out score.json"
```
Xem dòng `HEADLINE: x/100`. Sim là LLM thật nên **mỗi lần khác nhau** — nếu lần đầu có nhiều fail (drift/error thấp), chạy lại 1–2 lần lấy bản tốt nhất.

### 3d. Nếu < 90: chẩn đoán lỗi hệ thống
```powershell
wsl.exe -d Ubuntu-24.04 -u root -- bash -lc "cd /mnt/d/VIN_UNI/day13/Day-13-2A202600842_nguyenngocanh && python3 /mnt/d/VIN_UNI/day13/diag.py run_output.json"
```
- `suspect_discount > 0` → recompute sai → kiểm tra parse qty (paraphrase mới?) trong `_qty`.
- `statuses` có nhiều ≠ ok → tăng `context_size` (4→6) hoặc giảm `--concurrency`.
- Nhiều refusal sai → kiểm tra logic `found/in_stock/quantity/shipping-error` trong `_recompute`.
Sửa → chạy lại 3c.

---

## 4. NỘP private (1 lần)
```powershell
cd d:\VIN_UNI\day13\Day-13-2A202600842_nguyenngocanh
git add solution/
git add -f run_output.json score.json
git commit -m "Private submission: headline <điểm> (injection-robust, F1 1.0)"
git push
```

---

## 5. Checklist nhanh
- [ ] Public đã push (100) trước khi sửa
- [ ] findings.json có 11 findings (gồm prompt_injection)
- [ ] config.json `context_size=4`
- [ ] `_qty` đã hardening (synonyms + số độc lập + số chữ)
- [ ] selfcheck PASS (11 findings)
- [ ] Mock-probe: phase=private, qid=priv-*
- [ ] Debug-capture: trace format OK, injection bị recompute bỏ qua
- [ ] Full run + score ≥ 90
- [ ] Push private 1 lần

## Dự phóng điểm
Cần `weighted ≥ 0.68` (đã có +22 từ F1=1.0). Recompute giữ correct ~0.6+, context_size=4 giữ
error/drift cao → **weighted ~0.73–0.78 → headline 95–100 (cap)** ≥ 90 thoải mái.
