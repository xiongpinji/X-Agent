#!/bin/bash
# 审计: 逐文件硬超时跑顶层测试, 记录每文件结果
cd "/d/AI编程库/项目库/进行中的项目/X-Agent" || exit 1
export XAGENT_ENVIRONMENT=development XAGENT_LLM_BACKEND=mock
OUT=_audit_perfile_results.txt
: > "$OUT"
for f in tests/test_*.py; do
  [ "$f" = "tests/test_payment.py" ] && { echo "SKIP_BROKEN_COLLECT $f" >> "$OUT"; continue; }
  result=$(timeout 150 venv/Scripts/python.exe -m pytest "$f" -q -o addopts= -p no:cov -p no:cacheprovider --tb=no 2>&1 | tail -1)
  code=$?
  if [ $code -eq 124 ]; then
    echo "HANG $f" >> "$OUT"
  else
    echo "DONE($code) $f :: $result" >> "$OUT"
  fi
done
echo "ALL_FINISHED" >> "$OUT"
