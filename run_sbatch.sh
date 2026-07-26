#!/usr/bin/env bash
# Run one small batch: bash run_sbatch.sh <index> [workers]
set -u
i=$(printf "%02d" "$1")
files=$(tr -d '\r' < ".regression_batches/s_${i}.txt" | grep . | tr '\n' ' ')
log=".regression_batches/run_s_${i}.log"
start=$(date +%s)
COVERAGE_FILE=.coverage_reg_${i} XAGENT_PERF_PORT=$((59900 + 10#$i)) ./venv/Scripts/python.exe -m pytest $files \
  -q --no-cov -p no:cacheprovider -n "${2:-6}" --timeout=120 --max-worker-restart=10 -rf --tb=no \
  --junitxml=".regression_batches/s_${i}.xml" > "$log" 2>&1
rc=$?
end=$(date +%s)
grep -E "passed|failed|error" "$log" | tail -1
echo "BATCH s_${i} rc=${rc} dur=$((end-start))s"
