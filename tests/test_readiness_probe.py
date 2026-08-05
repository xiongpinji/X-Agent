"""P1-16：根级 /ready 深探针的回归测试。

背景：部署清单（helm/canary/rollout）的 readinessProbe 全部指向根级 /ready；
main.py 的根级 /ready 处理器为唯一 live 实现（components 深查本地存储 +
integrations 只读连通性）。api/health.py 的 extended_router 上另有一份
未挂载的 /ready 实现（C2 保留，不生效）。本测试锁定根级探针语义防回归。
"""

from __future__ import annotations

from starlette.testclient import TestClient

from backend.app.main import app


def test_ready_probe_returns_component_checks() -> None:
    with TestClient(app) as client:
        resp = client.get("/ready")

    # 本地存储故障时可为 503，但绝不 404，且必须带 components 明细
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert body["status"] in ("ready", "not_ready", "draining")
    components = body.get("components") or {}
    assert {"memory", "trace", "runs", "workflows", "audit"} <= set(components)
    assert all(v in ("ok", "error", "degraded") for v in components.values())


def test_ready_probe_public_no_auth() -> None:
    """探针必须公开（无 API key 也可达，供 kubelet 探测）。"""
    with TestClient(app) as client:
        assert client.get("/ready").status_code in (200, 503)
        assert client.get("/health").status_code == 200
