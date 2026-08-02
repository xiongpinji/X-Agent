"""Round 6 回归验证: Reasoning Trace + File Change Tracking + Multi-Turn Refinement"""
import httpx, sys

BASE = "http://127.0.0.1:18000"
H = {"X-API-Key": "xagent-dev-key-2024", "Content-Type": "application/json"}
results = []

def check(name: str, ok: bool, detail: str = ""):
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not ok else ""))

async def main():
    async with httpx.AsyncClient(base_url=BASE, headers=H, timeout=90) as c:
        # 先创建一个有 trace 的运行
        print("\n=== 0. 创建基础运行 ===")
        r = await c.post("/api/v1/agents/run", json={
            "task": "Create a hello world Python function and verify it",
            "extra_context": {"auto_commit": False}
        })
        check("创建基础运行", r.status_code == 200, f"HTTP {r.status_code}")
        trace_id = r.json().get("trace_id", "") if r.status_code == 200 else ""
        check("获得 trace_id", bool(trace_id), f"got: {trace_id[:20]}")

        # ─── 1. Reasoning Trace API ───
        print("\n=== 1. Reasoning Trace API ===")
        if trace_id:
            r = await c.get(f"/api/v1/agents/runs/{trace_id}/reasoning")
            check("reasoning 端点响应", r.status_code == 200, f"HTTP {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                check("返回 reasoning_steps", "reasoning_steps" in data)
                check("返回 tool_decisions", "tool_decisions" in data)
                check("返回 confidence_timeline", "confidence_timeline" in data)
                check("返回 summary", "summary" in data)
                s = data.get("summary", {})
                check("summary 含 total_reasoning_steps", "total_reasoning_steps" in s)
                check("summary 含 tool_decisions_made", "tool_decisions_made" in s)
                check("summary 含 replans", "replans" in s)
        else:
            check("reasoning 端点响应", False, "no trace_id")

        # 404 for nonexistent
        r = await c.get("/api/v1/agents/runs/fake-id-999/reasoning")
        check("reasoning 正确 404", r.status_code == 404, f"HTTP {r.status_code}")

        # ─── 2. File Change Tracking API ───
        print("\n=== 2. File Change Tracking ===")
        if trace_id:
            r = await c.get(f"/api/v1/agents/runs/{trace_id}/files-changed")
            check("files-changed 端点响应", r.status_code == 200, f"HTTP {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                check("返回 total_files_changed", "total_files_changed" in data)
                check("返回 files", "files" in data)
                check("返回 summary", "summary" in data)
                s = data.get("summary", {})
                check("summary 含 writes", "writes" in s)
                check("summary 含 verified", "verified" in s)
        else:
            check("files-changed 端点响应", False, "no trace_id")

        # 404 for nonexistent
        r = await c.get("/api/v1/agents/runs/fake-id-999/files-changed")
        check("files-changed 正确 404", r.status_code == 404, f"HTTP {r.status_code}")

        # ─── 3. Multi-Turn Refinement ───
        print("\n=== 3. Multi-Turn Refinement ===")
        if trace_id:
            r = await c.post(f"/api/v1/agents/runs/{trace_id}/refine", json={
                "instruction": "Now add type hints and a docstring to the function"
            })
            check("refine 端点响应", r.status_code == 200, f"HTTP {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                check("返回新 trace_id", "trace_id" in data and data["trace_id"] != trace_id)
                check("返回 refinement_of", data.get("refinement_of") == trace_id)
                check("返回 status", "status" in data)
                check("返回 instruction", "instruction" in data)
        else:
            check("refine 端点响应", False, "no trace_id")

        # 缺少 instruction 应 422
        if trace_id:
            r = await c.post(f"/api/v1/agents/runs/{trace_id}/refine", json={})
            check("refine 缺少 instruction 422", r.status_code == 422, f"HTTP {r.status_code}")

        # ─── 4. 核心端点回归 ───
        print("\n=== 4. 核心端点回归 ===")
        r = await c.get("/api/v1/agents")
        check("GET /agents", r.status_code == 200)

        r = await c.post("/api/v1/agents/run", json={"task": "echo test", "extra_context": {"auto_commit": False}})
        check("POST /agents/run", r.status_code == 200)

        r = await c.get("/health")
        check("GET /health", r.status_code == 200)

        if trace_id:
            r = await c.get(f"/api/v1/agents/runs/{trace_id}/plan")
            check("GET /runs/{id}/plan", r.status_code == 200, f"HTTP {r.status_code}")

            r = await c.get(f"/api/v1/agents/runs/{trace_id}/test-fix-loop")
            check("GET /runs/{id}/test-fix-loop", r.status_code == 200, f"HTTP {r.status_code}")

    # ─── 汇总 ───
    print("\n" + "=" * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"  Round 6 结果: {passed}/{total} 通过")
    if passed < total:
        print("  失败项:")
        for name, ok, detail in results:
            if not ok:
                print(f"    ✗ {name}: {detail}")
    print("=" * 60)
    return passed == total

if __name__ == "__main__":
    import asyncio
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
