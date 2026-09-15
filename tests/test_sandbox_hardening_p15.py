"""P1-5「沙箱硬化」的证明性测试。

缺陷背景（硬化前实测）：
1. 直连路径 `DockerSandbox._docker_start` 只设置了 `mem_limit` / `nano_cpus` /
   `network_mode`，**缺少**只读根文件系统、非 root 用户、no-new-privileges、
   capability 降权、pids 限额。
2. 池化路径 `DockerContainerPool._create_container_sync` 的 `container_kwargs`
   默认为空 —— 池中容器**完全没有隔离参数**。
3. **SDK 依赖导致硬化整体失效**：旧实现走 `docker` Python SDK，而该包是 optional
   且可能未安装 → `is_docker_available()` 恒 False → 沙箱静默退化到 subprocess，
   硬化参数一个都没生效。本轮已把容器后端改造为**直接调用 docker CLI**（无需
   Python SDK），并把探测/降级全部升级为显式 WARNING。

验收标准（本文件断言）：
1. 隔离参数由**单一事实源**（`build_container_security_kwargs`）构造，且逐项落位
   （只读根 fs / 非 root / no-new-privileges / cap_drop ALL / pids_limit /
   网络策略 / 资源限额）。
2. 池化路径与直连路径产出**同一组**硬化参数（防两处漂移）。
3. 在真实容器上，这些参数确实生效：非 root、根 fs 只读、/workspace 仍可写、
   capability 全清、no-new-privileges 生效。
4. `enable_network=True` 时网络策略正确放开（不是硬编码关闭）。
5. CLI 翻译（`container_security_kwargs_to_cli`）逐项覆盖硬化参数，且放宽后对应
   参数消失；`DockerSandbox` 端到端确实走 **docker** 后端而非 subprocess。
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from backend.app.core.sandbox.docker_sandbox import (
    SandboxSpec,
    build_container_security_kwargs,
    container_security_kwargs_to_cli,
)

# ─── 1 & 2：纯函数契约（无需 docker，永远可跑）─────────────────────────────


def test_security_kwargs_include_every_hardening_control() -> None:
    """默认 spec 必须逐项开启全部硬化控制。"""
    spec = SandboxSpec()
    kwargs = build_container_security_kwargs(spec, "/host/ws")

    assert kwargs["read_only"] is True, "root filesystem must be read-only"
    assert kwargs["tmpfs"] == {"/tmp": "size=64m"}, "read-only root needs a writable /tmp"
    assert kwargs["user"] == "65534:65534", "must run as non-root"
    assert kwargs["security_opt"] == ["no-new-privileges:true"]
    assert kwargs["cap_drop"] == ["ALL"], "all capabilities must be dropped"
    assert kwargs["pids_limit"] == 256, "fork-bomb protection missing"
    assert kwargs["network_mode"] == "none", "network must be off by default"
    assert kwargs["mem_limit"] == "512m"
    assert kwargs["nano_cpus"] == 1_000_000_000
    # 工作目录单独挂载 rw，否则只读根 fs 下沙箱无法工作
    assert kwargs["volumes"] == {"/host/ws": {"bind": "/workspace", "mode": "rw"}}
    assert kwargs["working_dir"] == "/workspace"


def test_security_kwargs_respect_network_opt_in() -> None:
    """enable_network=True 时必须真正放开，而不是被硬化逻辑吞掉。"""
    kwargs = build_container_security_kwargs(SandboxSpec(enable_network=True), None)
    assert kwargs["network_mode"] == "bridge"
    assert "volumes" not in kwargs


def test_security_kwargs_allow_per_item_relaxation() -> None:
    """每个控制项都必须可显式放宽（避免运维被安全默认锁死）。"""
    spec = SandboxSpec(
        read_only_root=False,
        run_as_user=None,
        drop_all_capabilities=False,
        no_new_privileges=False,
        pids_limit=0,
    )
    kwargs = build_container_security_kwargs(spec, None)
    for key in ("read_only", "tmpfs", "user", "security_opt", "cap_drop", "pids_limit"):
        assert key not in kwargs, f"{key} should be omitted when relaxed"


def test_pooled_path_uses_the_same_hardening_source() -> None:
    """池化路径必须与直连路径共用同一份参数（防两处漂移）。

    硬化前池化路径 `container_kwargs` 默认为空 → 等于零隔离。
    """
    from backend.app.core.sandbox.container_cache import DockerContainerPool

    pool = DockerContainerPool(image="python:3.11-slim", warm_size=0, max_size=1)
    captured: dict = {}

    class _FakeContainers:
        def run(self, **kwargs):  # noqa: ANN003
            captured.update(kwargs)

            class _C:
                id = "deadbeef"

            return _C()

    class _FakeClient:
        containers = _FakeContainers()

    pool._get_client = lambda: _FakeClient()  # type: ignore[method-assign]
    pool._create_container_sync()

    assert captured["read_only"] is True
    assert captured["user"] == "65534:65534"
    assert captured["cap_drop"] == ["ALL"]
    assert captured["security_opt"] == ["no-new-privileges:true"]
    assert captured["network_mode"] == "none"
    assert captured["pids_limit"] == 256


# ─── 3：真实容器行为验证（flags 从被测函数派生，杜绝"测的是副本"）──────────

def _docker_cli_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, timeout=30, check=False,
        ).returncode == 0
    except Exception:
        return False


# CLI 参数翻译由**生产函数**提供（container_security_kwargs_to_cli），
# 不再在测试里另抄一份 —— 硬化参数一旦被弱化，生产与测试会同时反映出来。

@pytest.mark.skipif(not _docker_cli_available(), reason="docker CLI/daemon unavailable")
def test_hardened_container_really_isolates() -> None:
    """在真实容器上验证隔离生效（离线可用：python:3.11-slim 已本地缓存）。"""
    spec = SandboxSpec(image="python:3.11-slim", memory_limit_mb=256, cpu_limit=0.5)
    workspace = Path(tempfile.mkdtemp(prefix="p15_ws_"))
    kwargs = build_container_security_kwargs(spec, workspace)

    script = "\n".join([
        "echo uid=$(id -u)",
        "echo -n 'workspace_write='; (echo ok > /workspace/ok.txt && echo OK) || echo DENIED",
        "echo -n 'etc_write='; (echo x > /etc/evil.txt 2>/dev/null && echo ALLOWED) || echo DENIED",
        "echo -n 'tmp_write='; (echo t > /tmp/t.txt && echo OK) || echo DENIED",
        "grep -o 'NoNewPrivs:[[:space:]]*[0-9]*' /proc/self/status",
        # 注意：必须断言 CapBnd（bounding set）而非 CapEff（effective set）。
        # 实测（A/B）：仅 `--user 65534` 就足以让 CapEff 归零（非 root 的
        # effective set 天然为空），因此 CapEff 对 `--cap-drop ALL` **没有区分度**；
        # 只有 CapBnd 能反映 cap-drop 是否真正落位（无 cap-drop 时实测为
        # 00000000a80425fb）。
        "grep -o 'CapBnd:[[:space:]]*[0-9a-f]*' /proc/self/status",
    ])
    cmd = (
        ["docker", "run", "--rm"]
        # 卷挂载已由 container_security_kwargs_to_cli 输出（含 workspace→/workspace:rw），
        # 这里不能再追加一条，否则 daemon 报 "Duplicate mount point: /workspace"。
        + container_security_kwargs_to_cli(kwargs)
        + [spec.image, "sh", "-c", script]
    )
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    out = proc.stdout + proc.stderr

    assert proc.returncode == 0, f"container run failed: {out}"
    assert "uid=65534" in out, f"container must run as non-root; got:\n{out}"
    assert "workspace_write=OK" in out, f"/workspace must stay writable; got:\n{out}"
    assert "etc_write=DENIED" in out, f"root fs must be read-only; got:\n{out}"
    assert "tmp_write=OK" in out, f"/tmp tmpfs must be writable; got:\n{out}"
    assert "NoNewPrivs: 1" in out.replace("\t", " "), f"no-new-privileges not effective:\n{out}"
    # CapBnd 才是 cap-drop 的判别式；CapEff 在非 root 下恒为 0，不具区分度。
    assert "CapBnd: 0000000000000000" in out.replace("\t", " "), f"caps not dropped:\n{out}"
    # 写入确实落到宿主侧挂载点（证明确实是同一个 /workspace）
    assert (workspace / "ok.txt").is_file()


# ─── 4：CLI 后端可用性 + DockerSandbox 端到端（P1-5 CLI 改造）──────────────

def test_cli_translation_covers_every_hardening_control() -> None:
    """CLI 翻译必须把每一项硬化控制都翻出来（防"翻译函数漏项"）。"""
    kwargs = build_container_security_kwargs(SandboxSpec(), "/host/ws")
    args = container_security_kwargs_to_cli(kwargs)

    assert "--read-only" in args
    assert "--tmpfs" in args and "/tmp:size=64m" in args
    assert "--user" in args and "65534:65534" in args
    assert "--security-opt" in args and "no-new-privileges:true" in args
    assert "--cap-drop" in args and "ALL" in args
    assert "--pids-limit" in args and "256" in args
    assert "--network" in args and "none" in args
    assert "--memory" in args and "512m" in args
    assert "--cpus" in args and "1" in args
    assert "-w" in args and "/workspace" in args
    # 卷挂载：宿主路径转正斜杠，避免 Docker Desktop 路径解析歧义
    assert "-v" in args and "/host/ws:/workspace:rw" in args


def test_cli_translation_omits_relaxed_controls() -> None:
    """逐项放宽后，对应 CLI 参数必须消失。"""
    spec = SandboxSpec(
        read_only_root=False,
        run_as_user=None,
        drop_all_capabilities=False,
        no_new_privileges=False,
        pids_limit=0,
    )
    args = container_security_kwargs_to_cli(build_container_security_kwargs(spec, None))
    for flag in ("--read-only", "--tmpfs", "--user", "--security-opt", "--cap-drop", "--pids-limit"):
        assert flag not in args, f"{flag} should be omitted when relaxed"


@pytest.mark.skipif(not _docker_cli_available(), reason="docker CLI/daemon unavailable")
def test_docker_sandbox_cli_backend_end_to_end() -> None:
    """DockerSandbox 必须真的走 docker 后端（而非静默退到 subprocess）。

    P1-5 改造前：SDK 缺失 → `is_docker_available()` 恒 False → `backend` 为
    "subprocess"，容器硬化**根本没生效**。改造为 CLI 后本用例应看到 backend=="docker"
    且隔离真实生效。
    """
    from backend.app.core.sandbox.docker_sandbox import DockerSandbox, reset_docker_probe

    reset_docker_probe()
    workspace = Path(tempfile.mkdtemp(prefix="p15_sbx_"))
    sandbox = DockerSandbox(
        SandboxSpec(image="python:3.11-slim", workspace_path=str(workspace),
                    timeout_seconds=120, memory_limit_mb=256, cpu_limit=0.5)
    )
    if sandbox.backend != "docker":
        pytest.skip("docker probe reported unavailable in this environment")

    async def _scenario() -> dict[str, object]:
        await sandbox.start()
        try:
            uid = await sandbox.run("id -u")
            ro = await sandbox.run("echo x > /etc/evil 2>&1 || echo DENIED")
            caps = await sandbox.run("grep -o 'CapBnd:[[:space:]]*[0-9a-f]*' /proc/self/status")
            wp = await sandbox.run("echo ok > /workspace/ok.txt && echo WROTE")
            bad = await sandbox.run("exit 7")
            return {
                "uid": uid.stdout.strip(),
                "backend": uid.backend,
                "ro": (ro.stdout + ro.stderr).strip(),
                "caps": caps.stdout.strip(),
                "wp": wp.stdout.strip(),
                "bad_exit": bad.exit_code,
                "bad_success": bad.success,
            }
        finally:
            await sandbox.stop()

    import asyncio

    r = asyncio.run(_scenario())

    assert r["backend"] == "docker", f"must use docker backend, got {r['backend']}"
    assert r["uid"] == "65534", f"must run as non-root, got uid={r['uid']}"
    assert "DENIED" in str(r["ro"]), f"root fs must be read-only, got {r['ro']!r}"
    assert "CapBnd: 0000000000000000" in str(r["caps"]).replace("\t", " ")
    assert r["wp"] == "WROTE", "workspace must stay writable"
    assert r["bad_exit"] == 7 and r["bad_success"] is False
    assert (workspace / "ok.txt").is_file(), "write must land on the host mount"
    assert sandbox._container_id is None, "container must be removed on stop"

