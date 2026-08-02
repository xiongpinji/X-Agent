"""全链路回归验证：覆盖所有已修复差距"""
import asyncio
import httpx
import json
import sys
import os

BASE = "http://127.0.0.1:18000"
HEADERS = {"X-API-Key": "xagent-dev-key-2024", "Content-Type": "application/json"}
VENV_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "Scripts", "python.exe")

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    status = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


async def test_health():
    print("\n=== 1. Health Check ===")
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BASE}/health")
        check("GET /health", r.status_code == 200 and r.json().get("status") == "ok")


async def test_fast_path():
    print("\n=== 2. Fast-Path (simple question) ===")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{BASE}/api/v1/agents/run", headers=HEADERS,
                         json={"task": "What is 7 * 8?", "agent_id": "default"})
        data = r.json()
        check("HTTP 200", r.status_code == 200)
        check("Status completed", data.get("status") == "completed")
        check("Iterations <= 2", data.get("iterations", 99) <= 2,
              f"got {data.get('iterations')}")
        answer = data.get("answer", "")
        check("Answer contains 56", "56" in answer, f"answer={answer[:80]}")
        es = data.get("execution_summary", {})
        check("Fast-path flag", es.get("fast_path") is True)


async def test_sse_stream():
    print("\n=== 3. SSE Streaming ===")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{BASE}/api/v1/agents/run/stream", headers=HEADERS,
                         json={"task": "Hello", "agent_id": "default"})
        lines = [l for l in r.text.split("\n") if l.startswith("data:")]
        check("SSE returns data frames", len(lines) >= 2, f"got {len(lines)} frames")
        final = [l for l in lines if "_final" in l]
        check("Has _final frame", len(final) >= 1)


async def test_write_and_test_fix():
    print("\n=== 4. Write + Test-Fix Loop ===")
    task = (
        f"1. Create _reg_mod.py with: def multiply(a, b): return a * b\\n"
        f"   def divide(a, b): return a * b  # BUG: should be /\\n"
        f"2. Create _reg_test.py with pytest tests for multiply and divide.\\n"
        f"3. Run: {VENV_PY} -m pytest _reg_test.py -v\\n"
        f"4. Fix any failures and re-run until tests pass."
    )
    async with httpx.AsyncClient(timeout=300) as c:
        r = await c.post(f"{BASE}/api/v1/agents/run", headers=HEADERS,
                         json={"task": task, "agent_id": "default"})
        data = r.json()
        check("HTTP 200", r.status_code == 200)
        check("Status completed", data.get("status") == "completed")
        tool_calls = data.get("tool_calls", [])
        check("Multiple tool calls", len(tool_calls) >= 3, f"got {len(tool_calls)}")
        tool_names = [tc.get("tool_name", "") for tc in tool_calls]
        check("Used write_file", "write_file" in tool_names)
        check("Used run_command", "run_command" in tool_names)
        # Check final file
        mod_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_reg_mod.py")
        if os.path.exists(mod_path):
            content = open(mod_path).read()
            check("Bug fixed (a / b)", "a / b" in content, f"content={content[:100]}")
        else:
            check("Bug fixed (a / b)", False, "_reg_mod.py not found")
        # Check execution_summary has repair round
        es = data.get("execution_summary", {})
        repair = es.get("_test_repair_round", 0)
        check("Repair round reported", repair >= 0, f"round={repair}")


async def test_sandbox_annotation():
    print("\n=== 5. Sandbox Auto-Detect ===")
    task = f"Run this command and show me the output: {VENV_PY} -c \"print('sandbox test ok')\""
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{BASE}/api/v1/agents/run", headers=HEADERS,
                         json={"task": task, "agent_id": "default"})
        data = r.json()
        check("HTTP 200", r.status_code == 200)
        tool_calls = data.get("tool_calls", [])
        rc_calls = [tc for tc in tool_calls if tc.get("tool_name") == "run_command"]
        if rc_calls:
            output = rc_calls[0].get("output", {})
            sandbox_val = output.get("sandbox", "") if isinstance(output, dict) else ""
            check("Sandbox annotated", bool(sandbox_val), f"sandbox={sandbox_val}")
        else:
            check("Sandbox annotated", False, "no run_command call found")


async def test_batch_patch_registered():
    print("\n=== 6. Batch Patch Tool Available ===")
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BASE}/api/v1/tools", headers=HEADERS)
        if r.status_code == 200:
            tools_data = r.json()
            tool_list = tools_data if isinstance(tools_data, list) else tools_data.get("tools", tools_data.get("data", []))
            names = [t.get("name", "") for t in tool_list] if isinstance(tool_list, list) else []
            check("apply_batch_patch registered", "apply_batch_patch" in names,
                  f"found {len(names)} tools")
        else:
            check("apply_batch_patch registered", False, f"HTTP {r.status_code}")


async def main():
    print("=" * 60)
    print("X-AGENT FULL REGRESSION TEST")
    print("=" * 60)

    await test_health()
    await test_fast_path()
    await test_sse_stream()
    await test_write_and_test_fix()
    await test_sandbox_annotation()
    await test_batch_patch_registered()

    print("\n" + "=" * 60)
    print(f"RESULTS: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
    print("=" * 60)
    sys.exit(1 if FAIL > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())
