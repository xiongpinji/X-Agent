#!/usr/bin/env bash
# Run one regression batch: ./run_batch.sh <index>
set -u
i=$(printf "%02d" "$1")
files=$(tr -d '\r' < ".regression_batches/reg_${i}.txt" | grep . | tr '\n' ' ')
log=".regression_batches/run_reg_${i}.log"
start=$(date +%s)
COVERAGE_FILE=.coverage_reg XAGENT_PERF_PORT=59999 ./venv/Scripts/python.exe -m pytest $files \
  -q --no-cov -p no:cacheprovider -n "${2:-8}" --timeout=120 -rf --tb=no > "$log" 2>&1
rc=$?
end=$(date +%s)
tail -3 "$log" | grep -E "passed|failed|error" || tail -3 "$log"
echo "BATCH ${i} rc=${rc} dur=$((end-start))s"
