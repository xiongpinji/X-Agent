"""验证 test-fix 闭环：Agent 写代码 → 跑测试 → 失败 → 自动修复"""
import asyncio
import httpx
import json
import sys

BASE = "http://127.0.0.1:18000"
HEADERS = {"X-API-Key": "xagent-dev-key-2024", "Content-Type": "application/json"}

# 任务：让 Agent 写一个有 bug 的函数，然后跑测试，触发自动修复
TASK = """Create a file called _test_fix_demo.py with a function `add_numbers(a, b)` that returns a + b.
Then create a test file _test_fix_demo_test.py with pytest tests for add_numbers.
Then run the tests with: python -m pytest _test_fix_demo_test.py -v
Make sure the tests pass."""


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

    print(f"\nRepair events: {len(repair_events)}")
    print(f"Auto-verify events: {len(auto_verify)}")

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
    if status == "completed" and len(tool_calls) >= 2:
        print("RESULT: PASS - Agent executed tools and completed task")
        if repair_events:
            print("  + Test-failure-repair loop TRIGGERED")
        if auto_verify:
            print("  + Auto-verify (run tests after write) TRIGGERED")
    else:
        print(f"RESULT: NEEDS REVIEW - status={status}, tools={len(tool_calls)}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
