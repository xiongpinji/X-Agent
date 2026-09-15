"""P1-4「可观测性自足」— 饱和度（saturation）真信号证明性测试。

缺陷背景（修复前实测）：
1. ``MetricsCollector.set_resource_metrics`` 使用 ``if cpu_percent > 0`` /
   ``if memory_bytes > 0`` 守卫 —— **合法的 0 值被静默丢弃**。空闲 CPU 或已释放的
   内存读数永远写不进 gauge，仪表盘会持续显示旧值（"假信号"）。
   判别式就是 ``> 0`` 与 ``is not None`` 的差别。
2. ``backend/app/monitoring/resource_monitor.py`` 的 ``ResourceMonitor.start()``
   是阻塞 ``while True`` 循环，且**全仓无任何调用点** → ``xagent_cpu_usage_percent`` /
   ``xagent_memory_usage_bytes`` 从未被写入。
3. 采集逻辑只在 ``disk_usage`` 非空时才调用 ``set_resource_metrics``，把
   CPU / 内存一起拖下水（磁盘枚举失败 → 饱和度整体丢失）。

测试设计要点（为什么用"哨兵 + 断言被覆盖"）：
Prometheus 的 gauge 是**进程级全局对象**，且 NewGauge 初始值为 0。若直接断言
``== 0.0``，在"方法根本没写"时也会通过（初始值同为 0）—— 这是典型的假通过。
因此每个用例先用 ``_prime()`` 直写一个哨兵值（绕过被测方法），再断言哨兵被
**替换**，从而让断言对"是否真的写入"具备区分度。

覆盖的验收标准：
1. 0 值必须真的覆盖旧值落到 gauge（核心回归鉴别式）。
2. 非 0 值正常落位（防"顺手把功能删了"）。
3. 局部更新不得清空未提供的字段。
4. ``collect_once()`` 必须真正写入 saturation（非阻塞、可反复调用）。
5. app 上真实挂载的 ``/metrics`` 路由处理器在 scrape 时必须刷新 saturation。
"""

from __future__ import annotations

import pytest
from prometheus_client import REGISTRY

from backend.app.core.metrics import MetricsCollector, metrics_collector

# 真实系统内存占用远高于该值；用它区分"哨兵残留"与"真实采集"。
_REAL_MEM_FLOOR = 1_000_000  # 1 MB


def _sample(name: str) -> float | None:
    return REGISTRY.get_sample_value(name)


def _prime(cpu: float, mem: int) -> None:
    """直写 gauge 构造确定初值（绕过被测方法，避免依赖测试顺序）。"""
    metrics_collector.cpu_usage_percent.set(cpu)
    metrics_collector.memory_usage_bytes.set(mem)


# ─── 1~3：set_resource_metrics 契约（回归鉴别式）────────────────────────────


def test_zero_saturation_values_are_actually_published() -> None:
    """0 值必须覆盖旧值 —— 修复前 `> 0` 守卫会把它静默丢弃。"""
    _prime(88.0, 5_000_000_000)
    MetricsCollector(enabled=True).set_resource_metrics(cpu_percent=0.0, memory_bytes=0)
    assert _sample("xagent_cpu_usage_percent") == 0.0, "CPU 0 值被静默丢弃（假信号）"
    assert _sample("xagent_memory_usage_bytes") == 0, "内存 0 值被静默丢弃（假信号）"


def test_nonzero_saturation_values_are_published() -> None:
    """非 0 值正常落位。"""
    _prime(0.0, 0)
    MetricsCollector(enabled=True).set_resource_metrics(
        cpu_percent=42.5, memory_bytes=1_234_567_890
    )
    assert _sample("xagent_cpu_usage_percent") == 42.5
    assert _sample("xagent_memory_usage_bytes") == 1_234_567_890


def test_partial_update_does_not_clobber_untouched_fields() -> None:
    """只更新 CPU 时不得把内存清零（可选参数语义）。"""
    _prime(0.0, 0)
    collector = MetricsCollector(enabled=True)
    collector.set_resource_metrics(cpu_percent=7.0, memory_bytes=999)
    collector.set_resource_metrics(cpu_percent=8.0)
    assert _sample("xagent_cpu_usage_percent") == 8.0
    assert _sample("xagent_memory_usage_bytes") == 999


def test_missing_args_are_true_noops() -> None:
    """完全不传参数时不应写入任何值（保持可选语义）。"""
    _prime(3.0, 77)
    MetricsCollector(enabled=True).set_resource_metrics()
    assert _sample("xagent_cpu_usage_percent") == 3.0
    assert _sample("xagent_memory_usage_bytes") == 77


def test_disabled_collector_writes_nothing() -> None:
    """enabled=False 时是 no-op。"""
    _prime(11.0, 22)
    MetricsCollector(enabled=False).set_resource_metrics(cpu_percent=123.0, memory_bytes=456)
    assert _sample("xagent_cpu_usage_percent") == 11.0
    assert _sample("xagent_memory_usage_bytes") == 22


# ─── 4：采集器真正写入 saturation（修复前 start() 无调用点）────────────────


def test_collect_once_publishes_saturation() -> None:
    """collect_once() 必须把 CPU / 内存真正写进 gauge。"""
    from backend.app.monitoring.resource_monitor import ResourceMonitor

    _prime(0.0, 1)  # 哨兵：1 字节，真实系统不可能这么低
    monitor = ResourceMonitor(interval=30)
    monitor.collect_once()  # prime：psutil.cpu_percent 首个非阻塞样本
    snapshot = monitor.collect_once()

    assert "cpu_percent" in snapshot, "collect_once 应返回采集快照"
    assert _sample("xagent_cpu_usage_percent") is not None, "CPU 饱和度未写入"
    mem = _sample("xagent_memory_usage_bytes")
    assert mem is not None and mem > _REAL_MEM_FLOOR, f"内存饱和度仍是哨兵值(={mem})"


def test_collect_once_does_not_gate_on_disk_enumeration() -> None:
    """即使磁盘枚举为空，CPU / 内存也必须写入（修复前被 `if disk_usage` 拖死）。"""
    from backend.app.monitoring import resource_monitor as rm

    _prime(0.0, 1)
    monitor = rm.ResourceMonitor(interval=30)

    class _Psutil:
        class virtual_memory:  # noqa: N801
            used = 4_000_000_000
            percent = 50.0

        @staticmethod
        def cpu_percent(interval=None):  # noqa: ANN001, ANN205
            return 12.0

        @staticmethod
        def disk_partitions():
            return []  # 磁盘枚举为空

    import sys
    import types

    fake = types.ModuleType("psutil")
    fake.cpu_percent = _Psutil.cpu_percent
    fake.virtual_memory = _Psutil.virtual_memory
    fake.disk_partitions = _Psutil.disk_partitions
    monkey = pytest.MonkeyPatch()
    monkey.setitem(sys.modules, "psutil", fake)
    try:
        monitor.collect_once()
    finally:
        monkey.undo()

    assert _sample("xagent_cpu_usage_percent") == 12.0, "磁盘为空时 CPU 被一起丢弃"
    assert _sample("xagent_memory_usage_bytes") == 4_000_000_000


# ─── 5：路由级集成 —— 真实挂载的 /metrics 处理器会刷新 saturation ──────────


def _metrics_endpoint():
    """取出 app 上真实挂载的 /metrics 精确路径路由处理器。"""
    from backend.app.main import app

    for route in app.routes:
        if getattr(route, "path", None) == "/metrics" and hasattr(route, "endpoint"):
            return route.endpoint
    return None


def test_metrics_endpoint_refreshes_saturation_on_scrape() -> None:
    """scrape /metrics 时必须刷新出真实 saturation。

    修复前：无人采集，哨兵值不会被覆盖。
    修复后：处理器刷新 → 内存读数为真实值（> 1MB）。

    说明：这里**直接调用路由处理器**，而不走 ``TestClient`` 的完整 lifespan。
    原因：TestClient 启动会触发 app lifespan，而本仓库存在一个**预存在的顺序相关
    flake**（lifespan 后台任务未清理 + 跨测试共享事件循环 → 批跑时
    ``concurrent.futures._base.CancelledError``）。路由处理器正是本改动所在的
    单元，直接调用它既覆盖了真正的改动点，又不会引入新的 flake 面。
    完整 lifespan 下的端到端观测由人工探针验证（见交付报告）。
    """
    import asyncio

    from prometheus_client import CONTENT_TYPE_LATEST

    endpoint = _metrics_endpoint()
    assert endpoint is not None, "app 上未找到 /metrics 精确路径路由"

    _prime(0.0, 1)  # 哨兵

    resp = asyncio.run(endpoint())
    assert resp.media_type == CONTENT_TYPE_LATEST

    body = resp.body.decode("utf-8")
    assert "xagent_cpu_usage_percent" in body, "CPU 饱和度指标未暴露"
    assert "xagent_memory_usage_bytes" in body, "内存饱和度指标未暴露"

    mem = _sample("xagent_memory_usage_bytes")
    assert mem is not None and mem > _REAL_MEM_FLOOR, f"内存饱和度是假信号（={mem}）"
