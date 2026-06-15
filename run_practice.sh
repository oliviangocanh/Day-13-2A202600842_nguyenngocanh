#!/usr/bin/env bash
# Chay sim practice (ban Linux) trong WSL Ubuntu.
# Key OPENAI_API_KEY lay tu moi truong (truyen vao khi goi).
set -eu
cd /mnt/d/VIN_UNI/day13/Day-13-2A202600842_nguyenngocanh
BIN="./observathon-practice-linux-x64/observathon-sim"
chmod +x "$BIN" 2>/dev/null || true

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "!! Chua co OPENAI_API_KEY. Dat key truoc khi chay."; exit 1
fi

echo ">> Dang chay practice sim (concurrency 8)..."
"$BIN" --config solution/config.json --wrapper solution/wrapper.py \
       --out run_output.json --concurrency 8

echo ">> Xong. Ket qua o run_output.json"
ls -l run_output.json
