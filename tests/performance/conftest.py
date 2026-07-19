"""
性能测试配置和夹具
"""
import pytest
import time
import psutil
import os
import socket
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime


# ---------------------------------------------------------------------------
# Live-server reachability guard
#
# 这些性能/压力/负载/瓶颈测试会用 aiohttp/asyncpg 对 localhost:8000 打真实流量
# （find_breaking_point、concurrent benchmark 等）。没有服务在跑时，连接持续失败、
# 在 nest_asyncio 事件循环里空转，Windows 上 pytest-timeout(thread 法) 触发时会
# 直接硬杀整个进程，导致 junit 文件都写不出来。
#
# 因此：收集期用 socket 探一次 127.0.0.1:8000，探不通就把本目录下所有用例标 skip，
# 让整套件能干净跑完（skip 不算红）。放在 conftest 的 collection hook 里，能在
# `-o addopts=""`（剥掉 marker 过滤）时依然生效——与 #121 给 qdrant 加的可达性
# skip 同一套路。需要跑真实性能基线时，先起服务再单独 `pytest tests/performance`。
# ---------------------------------------------------------------------------
_PERF_SERVER_HOST = os.environ.get("XAGENT_PERF_HOST", "127.0.0.1")
_PERF_SERVER_PORT = int(os.environ.get("XAGENT_PERF_PORT", "8000"))


def _perf_server_reachable(host: str, port: int, timeout: float = 0.5) -> bool:
    """Best-effort TCP probe; True only if something is actually listening."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(config, items):
    """Skip live-infra perf tests in THIS directory when no server is up."""
    if _perf_server_reachable(_PERF_SERVER_HOST, _PERF_SERVER_PORT):
        return  # server present -> run for real

    conftest_dir = Path(__file__).resolve().parent
    skip_marker = pytest.mark.skip(
        reason=(
            f"perf/load tests need a live server at "
            f"{_PERF_SERVER_HOST}:{_PERF_SERVER_PORT} (set XAGENT_PERF_HOST/PORT "
            f"or start the API, then run `pytest tests/performance`)"
        )
    )
    for item in items:
        try:
            item_path = Path(str(item.fspath)).resolve()
        except Exception:
            continue
        if conftest_dir in item_path.parents:
            item.add_marker(skip_marker)


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    test_name: str
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    response_times: List[float] = field(default_factory=list)
    errors: int = 0
    success_count: int = 0
    cpu_usage: List[float] = field(default_factory=list)
    memory_usage: List[float] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time if self.end_time else 0.0

    @property
    def avg_response_time(self) -> float:
        return sum(self.response_times) / len(self.response_times) if self.response_times else 0.0

    @property
    def p95_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[idx]

    @property
    def p99_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.99)
        return sorted_times[idx]

    @property
    def throughput(self) -> float:
        """吞吐量 (请求/秒)"""
        return self.success_count / self.duration if self.duration > 0 else 0.0

    @property
    def error_rate(self) -> float:
        """错误率 (%)"""
        total = self.success_count + self.errors
        return (self.errors / total * 100) if total > 0 else 0.0

    @property
    def avg_cpu_usage(self) -> float:
        return sum(self.cpu_usage) / len(self.cpu_usage) if self.cpu_usage else 0.0

    @property
    def avg_memory_usage(self) -> float:
        return sum(self.memory_usage) / len(self.memory_usage) if self.memory_usage else 0.0

    @property
    def max_memory_usage(self) -> float:
        return max(self.memory_usage) if self.memory_usage else 0.0


class ResourceMonitor:
    """资源监控器"""

    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.start_time = None
        self.metrics = []

    def start(self):
        self.start_time = time.time()
        self.metrics = []

    def record(self):
        """记录当前资源使用情况"""
        try:
            cpu_percent = self.process.cpu_percent(interval=0.1)
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024

            self.metrics.append({
                'timestamp': time.time(),
                'cpu_percent': cpu_percent,
                'memory_mb': memory_mb
            })
        except Exception as e:
            print(f"Error recording metrics: {e}")

    def get_summary(self) -> Dict[str, float]:
        """获取资源使用摘要"""
        if not self.metrics:
            return {}

        cpu_values = [m['cpu_percent'] for m in self.metrics]
        memory_values = [m['memory_mb'] for m in self.metrics]

        return {
            'avg_cpu': sum(cpu_values) / len(cpu_values),
            'max_cpu': max(cpu_values),
            'avg_memory_mb': sum(memory_values) / len(memory_values),
            'max_memory_mb': max(memory_values),
            'min_memory_mb': min(memory_values),
        }


@pytest.fixture
def performance_metrics():
    """性能指标夹具"""
    return PerformanceMetrics(test_name="test")


@pytest.fixture
def resource_monitor():
    """资源监控器夹具"""
    monitor = ResourceMonitor()
    monitor.start()
    yield monitor


@pytest.fixture
def timer():
    """计时器夹具"""
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def __enter__(self):
            self.start_time = time.time()
            return self

        def __exit__(self, *args):
            self.end_time = time.time()

        @property
        def elapsed(self) -> float:
            if self.end_time is None:
                return time.time() - self.start_time
            return self.end_time - self.start_time

    return Timer()
