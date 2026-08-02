"""验证 test-fix 闭环：Agent 写代码 → 跑测试 → 失败 → 自动修复"""
import asyncio
import httpx
import json
import sys
import os

BASE = "http://127.0.0.1:18000"
HEADERS = {"X-API-Key": "xagent-dev-key-2024", "Content-Type": "application/json"}

# 用 venv Python 确保 pytest 可运行
VENV_PY = os.path.join(os.path.dirname(__file__), "venv", "Scripts", "python.exe")

# 任务：故意写一个有 bug 的函数，让测试失败，触发自动修复
TASK = f"""Do the following steps in order:
1. Create file _tf_calc.py with this EXACT content (has a bug - subtract uses + instead of -):
   def add(a, b): return a + b
   def subtract(a, b): return a + b
2. Create file _tf_test_calc.py with pytest tests:
   from _tf_calc import add, subtract
   def test_add(): assert add(2, 3) == 5
   def test_subtract(): assert subtract(5, 3) == 2
3. Run tests: {VENV_PY} -m pytest _tf_test_calc.py -v
4. If tests fail, fix the bug in _tf_calc.py and re-run tests until they pass."""


async def main():
    print("=" * 60)
    print("TEST-FIX LOOP VERIFICATION")
    print("=" * 60)
    print(f"\nTask: {TASK[:100]}...")
    print("\nSending to Agent...\n")

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{BASE}/api/v1/agents/run",
            headers=HEADERS,
            json={"task": TASK, "agent_id": "default"},
        )

        if resp.status_code != 200:
            print(f"ERROR: HTTP {resp.status_code}")
            print(resp.text[:500])
            sys.exit(1)

        data = resp.json()

    # 分析结果
    status = data.get("status", "unknown")
    answer = data.get("answer", "")
    iterations = data.get("iterations", 0)
    tool_calls = data.get("tool_calls", [])
    events = data.get("events", [])
    exec_summary = data.get("execution_summary", {})

    print(f"Status: {status}")
    print(f"Iterations: {iterations}")
    print(f"Tool calls: {len(tool_calls)}")
    print(f"Events: {len(events)}")

    # 检查是否有 test_failure.repair_injected 事件
    repair_events = [e for e in events if "repair" in str(e.get("event", "")).lower()
                     or "test_failure" in str(e.get("event", "")).lower()]
    auto_verify = [e for e in events if "auto_verify" in str(e.get("event", "")).lower()]

    # 也检查 execution_summary 中的修复轮次
    repair_round = exec_summary.get("_test_repair_round", 0)

    print(f"\nRepair events (in response): {len(repair_events)}")
    print(f"Auto-verify events (in response): {len(auto_verify)}")
    print(f"Repair rounds (from exec_summary): {repair_round}")

    # 显示工具调用
    print("\n--- Tool Calls ---")
    for tc in tool_calls:
        name = tc.get("tool_name", tc.get("name", "?"))
        success = tc.get("success", "?")
        print(f"  {name} -> success={success}")

    # 显示答案
    print("\n--- Answer ---")
    print(answer[:1500] if answer else "(no answer)")

    # 判定
    print("\n" + "=" * 60)
    has_repair = repair_round > 0 or len(repair_events) > 0
    if status == "completed" and len(tool_calls) >= 2:
        print("RESULT: PASS - Agent executed tools and completed task")
        if has_repair:
            print(f"  + Test-failure-repair loop TRIGGERED (rounds={repair_round})")
        if auto_verify:
            print("  + Auto-verify (run tests after write) TRIGGERED")
        if not has_repair:
            print("  ! Repair loop NOT triggered - checking if tests passed first try")
    else:
        print(f"RESULT: NEEDS REVIEW - status={status}, tools={len(tool_calls)}")
    print("=" * 60)

    # 检查文件是否最终正确
    print("\n--- Final File Check ---")
    calc_path = os.path.join(os.path.dirname(__file__), "_tf_calc.py")
    if os.path.exists(calc_path):
        content = open(calc_path).read()
        print(f"_tf_calc.py content:\n{content}")
        if "a - b" in content:
            print("  >>> BUG FIXED: subtract now uses '-' operator")
        else:
            print("  >>> BUG STILL PRESENT: subtract still uses '+'")
    else:
        print("_tf_calc.py not found")


if __name__ == "__main__":
    asyncio.run(main())
