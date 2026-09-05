#!/bin/bash
# 单文件测试 runner（供 xargs 并行调用）
cd "/d/AI编程库/项目库/进行中的项目/X-Agent" || exit 1
export XAGENT_ENVIRONMENT=development XAGENT_LLM_BACKEND=mock
f="$1"
result=$(timeout 150 venv/Scripts/python.exe -m pytest "$f" -q -o addopts= -p no:cov -p no:cacheprovider --tb=no 2>&1 | tail -1)
code=$?
if [ $code -eq 124 ]; then
  echo "HANG $f"
else
  echo "DONE($code) $f :: $result"
fi
