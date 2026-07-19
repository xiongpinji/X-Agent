"""Wave A (P1-18) 真实负载基准: 本地 uvicorn + 异步 HTTP 客户端.

对核心端点做真实负载测量并输出机器可读的 JSON 结果。

测量设计 (与后端实际限流策略对齐, 见 backend/app/main.py rate_limit_middleware):
  - 限流硬编码: login 10/min/IP, register 5/min/IP, 其余 /api/* 合计 100/min/IP;
    /health 不限流。
  - Phase A "配额内延迟": 在冷配额下以低并发测量各核心端点的真实服务延迟
    (api 桶总消耗 90 < 100, login 桶 8 < 10), 样本仅统计 status<400 的响应。
  - Phase B "health 洪泛": /health 不限流, 做 2000 请求基准 + 并发扫描
    (c=10/50/100), 测量吞吐与延迟随并发的变化。
  - Phase C "限流验证": 等待 61s 让 api 桶窗口滑过后, 以 150 请求冲击
    /api/v1/agents, 验证 100/min 限流的实际执行 (预期 ~100 个 200 后转 429)。

用法:
    ./venv/Scripts/python.exe benchmarks/wave_a_load_benchmark.py [--port 8123]

脚本自行启动 uvicorn 子进程, 测量完成后无条件终止该子进程并校验端口释放,
不会留下后台进程。结果写入 benchmarks/results/wave_a_benchmark_<timestamp>.json
及 wave_a_benchmark_latest.json。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

try:
    import psutil
except ImportError:  # pragma: no cover - 防御性降级
    psutil = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "benchmarks" / "results"


def _percentile(samples: list[float], pct: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] + (ordered[high] - ordered[low]) * frac


def _env_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "machine": platform.machine(),
        "python_version": sys.version.split()[0],
        "cpu_count_logical": os.cpu_count(),
        "llm_mode": "mock (settings.llm_backend 默认值 'mock', 未配置真实 LLM API key)",
        "app_mode": "development (XAGENT_APP_MODE)",
        "date_utc": datetime.now(timezone.utc).isoformat(),
    }
    if psutil is not None:
        info["cpu_model"] = platform.processor() or "unknown"
        info["memory_total_gb"] = round(psutil.virtual_memory().total / (1024**3), 2)
    return info


class LoadRunner:
    """有界并发负载执行器, 复用单个 AsyncClient。"""

    def __init__(self, base_url: str, timeout: float = 180.0) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.token: str | None = None

    def _headers(self, auth: bool) -> dict[str, str]:
        if auth and self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    async def run_scenario(
        self,
        name: str,
        method: str,
        path: str,
        *,
        num_requests: int,
        concurrency: int,
        json_body: dict[str, Any] | None = None,
        auth: bool = False,
    ) -> dict[str, Any]:
        """执行一个测量场景。

        延迟样本只统计 status<400 的响应 (端点真实服务时间);
        429 计入 rejected_429, 5xx/网络异常计入 errors。
        """
        url = self.base_url + path
        samples: list[float] = []  # seconds
        status_codes: dict[str, int] = {}
        errors = 0
        semaphore = asyncio.Semaphore(concurrency)

        limits = httpx.Limits(
            max_connections=max(concurrency * 2, 20),
            max_keepalive_connections=max(concurrency, 10),
        )
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout, limits=limits) as client:
            async def one_request() -> None:
                nonlocal errors
                async with semaphore:
                    t0 = time.perf_counter()
                    try:
                        resp = await client.request(
                            method, url,
                            json=json_body if json_body is not None else None,
                            headers=self._headers(auth),
                        )
                        elapsed = time.perf_counter() - t0
                        code = str(resp.status_code)
                        status_codes[code] = status_codes.get(code, 0) + 1
                        if resp.status_code >= 500:
                            errors += 1
                        elif resp.status_code < 400:
                            samples.append(elapsed)
                    except Exception:
                        errors += 1

            await asyncio.gather(*(one_request() for _ in range(num_requests)))
        wall = time.perf_counter() - started

        rejected_429 = status_codes.get("429", 0)
        accepted = len(samples)
        samples_ms = [s * 1000.0 for s in samples]
        result = {
            "scenario": name,
            "method": method,
            "path": path,
            "auth": auth,
            "num_requests": num_requests,
            "concurrency": concurrency,
            "accepted_requests": accepted,
            "rejected_429": rejected_429,
            "errors_5xx_or_network": errors,
            "error_rate": errors / num_requests if num_requests else 0.0,
            "rejection_rate_429": rejected_429 / num_requests if num_requests else 0.0,
            "status_codes": status_codes,
            "wall_time_s": round(wall, 3),
            "throughput_rps": round(num_requests / wall, 2) if wall > 0 else 0.0,
            "latency_ms": {
                "min": round(min(samples_ms), 2) if samples_ms else None,
                "max": round(max(samples_ms), 2) if samples_ms else None,
                "mean": round(statistics.mean(samples_ms), 2) if samples_ms else None,
                "p50": round(_percentile(samples_ms, 50), 2),
                "p95": round(_percentile(samples_ms, 95), 2),
                "p99": round(_percentile(samples_ms, 99), 2),
                "sample_count": accepted,
            },
        }
        lat = result["latency_ms"]
        print(
            f"  [{name}] {method} {path} n={num_requests} c={concurrency} "
            f"p50={lat['p50']}ms p95={lat['p95']}ms p99={lat['p99']}ms "
            f"rps={result['throughput_rps']} 429={rejected_429} err={errors} "
            f"status={status_codes}"
        )
        return result


async def _wait_for_server(base_url: str, timeout_s: float = 90.0) -> None:
    deadline = time.time() + timeout_s
    async with httpx.AsyncClient(timeout=5.0) as client:
        while time.time() < deadline:
            try:
                resp = await client.get(base_url + "/health")
                if resp.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(1.0)
    raise RuntimeError(f"服务器在 {timeout_s}s 内未就绪: {base_url}")


def _start_server(port: int) -> subprocess.Popen:
    python = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
    if not python.exists():
        python = Path(sys.executable)
    env = os.environ.copy()
    env.setdefault("XAGENT_APP_MODE", "development")
    log_path = RESULTS_DIR / "uvicorn_benchmark_server.log"
    log_file = open(log_path, "w", encoding="utf-8")  # noqa: SIM115 - 生命周期与进程一致
    proc = subprocess.Popen(
        [
            str(python), "-m", "uvicorn",
            "backend.app.main:app",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "warning",
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    proc._log_file = log_file  # type: ignore[attr-defined]
    return proc


def _stop_server(proc: subprocess.Popen, port: int) -> None:
    """终止服务器子进程并确认端口已释放。"""
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
    log_file = getattr(proc, "_log_file", None)
    if log_file is not None:
        log_file.close()
    # 校验端口释放, 防止遗留后台进程
    if psutil is not None:
        deadline = time.time() + 15
        while time.time() < deadline:
            listeners = [
                c for c in psutil.net_connections(kind="tcp")
                if c.laddr and c.laddr.port == port and c.status == "LISTEN"
            ]
            if not listeners:
                return
            time.sleep(0.5)
        raise RuntimeError(f"端口 {port} 仍被监听, 服务器可能未完全退出")


async def run_benchmarks(port: int, phases: set[str]) -> dict[str, Any]:
    base_url = f"http://127.0.0.1:{port}"
    runner = LoadRunner(base_url)

    # 0) 注册独立基准用户并登录取 token
    stamp = int(time.time())
    email = f"perf_{stamp}@example.com"
    password = "PerfBench1234"
    async with httpx.AsyncClient(timeout=30.0) as client:
        reg = await client.post(
            base_url + "/api/v1/auth/register",
            json={"email": email, "password": password},
        )
        if reg.status_code not in (200, 201, 409):
            raise RuntimeError(f"注册基准用户失败: {reg.status_code} {reg.text[:200]}")
        login = await client.post(
            base_url + "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        login.raise_for_status()
        data = login.json()
        runner.token = data.get("access_token") or data.get("token")
        if not runner.token:
            raise RuntimeError(f"登录未返回 token: {data}")
    print(f"基准用户 {email} 注册并登录成功 (role=developer)")

    report: dict[str, Any] = {
        "benchmark": "wave_a_load",
        "environment": _env_info(),
        "base_url": base_url,
        "phases_executed": sorted(phases),
        "rate_limits_in_code": {
            "source": "backend/app/main.py rate_limit_middleware",
            "login": "10 req/min/IP",
            "register": "5 req/min/IP",
            "api_other": "100 req/min/IP (合计)",
            "health": "不限流",
        },
    }

    if "a" in phases:
        # Phase A: 配额内真实延迟 (api 桶合计 44 < 100/min, login 桶 8 < 10/min)
        print("\n== Phase A: 配额内端点真实延迟 (低并发, 样本仅含 status<400) ==")
        phase_a: list[dict[str, Any]] = []
        phase_a.append(await runner.run_scenario(
            "auth_login", "POST", "/api/v1/auth/login",
            json_body={"email": email, "password": password},
            num_requests=8, concurrency=2))
        phase_a.append(await runner.run_scenario(
            "agents_list", "GET", "/api/v1/agents",
            num_requests=15, concurrency=5, auth=True))
        phase_a.append(await runner.run_scenario(
            "agent_run_mock", "POST", "/api/v1/agents/run",
            json_body={"task": "用一句话回答: 1+1 等于几?"},
            num_requests=3, concurrency=2, auth=True))
        phase_a.append(await runner.run_scenario(
            "memory_store", "POST", "/api/v1/memory",
            json_body={"content": "Wave A 性能基准写入样本: X-Agent benchmark payload.",
                       "layer": 3, "importance": 0.5, "tags": ["benchmark"]},
            num_requests=20, concurrency=5, auth=True))
        phase_a.append(await runner.run_scenario(
            "memory_search", "POST", "/api/v1/memory/search",
            json_body={"query": "性能基准", "top_k": 5},
            num_requests=20, concurrency=5, auth=True))
        phase_a.append(await runner.run_scenario(
            "memory_count", "GET", "/api/v1/memory/count",
            num_requests=10, concurrency=5, auth=True))
        report["phase_a_within_quota_latency"] = phase_a

    if "b" in phases:
        # Phase B: /health 洪泛 + 并发扫描 (health 不限流)
        print("\n== Phase B: /health 洪泛与并发扫描 ==")
        phase_b: list[dict[str, Any]] = []
        phase_b.append(await runner.run_scenario(
            "health_flood", "GET", "/health", num_requests=2000, concurrency=50))
        for conc in (10, 50, 100):
            phase_b.append(await runner.run_scenario(
                f"health_c{conc}", "GET", "/health",
                num_requests=1000, concurrency=conc))
        report["phase_b_health_flood"] = phase_b

    if "c" in phases:
        # Phase C: 限流验证 (等 61s 滑窗后以 150 请求冲击 api 桶, 预期 ~100 个 200 后转 429)
        print("\n== Phase C: api 限流 (100/min/IP) 验证, 等待 61s 滑窗 ==")
        await asyncio.sleep(61)
        report["phase_c_rate_limit_verification"] = await runner.run_scenario(
            "rate_limit_verify", "GET", "/api/v1/agents",
            num_requests=150, concurrency=10, auth=True)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Wave A 真实负载基准 (P1-18)")
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument(
        "--phases", default="abc",
        help="要执行的阶段子集, 如 'ab' / 'c'。分段执行后再用 merge 模式合并结果。")
    parser.add_argument(
        "--merge", nargs="*", default=None, metavar="JSON",
        help="合并模式: 合并若干阶段结果 JSON, 不写服务器。输出到 --out 指定文件。")
    parser.add_argument("--out", default=None, help="合并模式输出路径")
    args = parser.parse_args()

    if args.merge is not None:
        merged: dict[str, Any] | None = None
        for path_str in args.merge:
            part = json.loads(Path(path_str).read_text(encoding="utf-8"))
            if merged is None:
                merged = part
                continue
            for key, value in part.items():
                if key.startswith("phase_"):
                    merged[key] = value
            merged["phases_executed"] = sorted(
                set(merged.get("phases_executed", [])) | set(part.get("phases_executed", [])))
        if merged is None:
            raise SystemExit("merge 模式至少需要一个 JSON 文件")
        out = Path(args.out) if args.out else RESULTS_DIR / "wave_a_benchmark_merged.json"
        out.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        latest = RESULTS_DIR / "wave_a_benchmark_latest.json"
        latest.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"合并结果已写入: {out}")
        print(f"最新结果副本: {latest}")
        return 0

    phases = set(args.phases.lower())
    if not phases <= set("abc"):
        raise SystemExit("--phases 只能包含 a/b/c")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    proc = _start_server(args.port)
    print(f"uvicorn 子进程已启动 pid={proc.pid} port={args.port} (XAGENT_APP_MODE=development)")
    report: dict[str, Any] | None = None
    try:
        asyncio.run(_wait_for_server(f"http://127.0.0.1:{args.port}"))
        print("服务器就绪, 开始测量\n")
        report = asyncio.run(run_benchmarks(args.port, phases))
    finally:
        _stop_server(proc, args.port)
        print(f"\nuvicorn 子进程已终止, 端口 {args.port} 已释放")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = "".join(sorted(phases))
    out_path = RESULTS_DIR / f"wave_a_benchmark_{tag}_{ts}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = RESULTS_DIR / f"wave_a_benchmark_{tag}_latest.json"
    latest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结果已写入: {out_path}")
    print(f"最新结果副本: {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
