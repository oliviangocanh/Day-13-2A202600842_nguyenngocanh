#!/usr/bin/env bash
# Chay PRIVATE sim (REAL LLM) -> run_output.json, roi cham diem -> score.json.
# Goi voi OPENAI_API_KEY trong moi truong.
set -eu
cd /mnt/d/VIN_UNI/day13/Day-13-2A202600842_nguyenngocanh
SIM=./observathon-private-sim-linux-x64/observathon-sim
SCORE=./observathon-private-score-linux-x64/observathon-score
TEAM=2A202600842_nguyenngocanh
chmod +x "$SIM" "$SCORE" 2>/dev/null || true
if [ -z "${OPENAI_API_KEY:-}" ]; then echo "!! Chua co OPENAI_API_KEY"; exit 1; fi

echo ">> [1/2] Chay private sim (80 cau, concurrency 8)..."
"$SIM" --config solution/config.json --wrapper solution/wrapper.py \
       --out run_output.json --concurrency 8

echo ">> [2/2] Cham diem..."
"$SCORE" --run run_output.json --findings solution/findings.json \
         --team "$TEAM" --out score.json
echo ">> Xong."
