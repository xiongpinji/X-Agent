from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "frontend" / "src" / "services"

AUTH_CLIENTS = (
    "api.ts",
    "adminOps.ts",
    "automationOps.ts",
    "complianceOps.ts",
    "evolutionOps.ts",
    "feedback.ts",
    "governanceOps.ts",
    "mcpOps.ts",
    "observabilityOps.ts",
    "sandboxOps.ts",
    "securityOps.ts",
    "syncOps.ts",
    "workflowOps.ts",
)


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_custom_api_clients_share_api_key_auth() -> None:
    helper = SERVICES / "authHeaders.ts"
    assert helper.is_file(), "shared Axios auth helper is missing"
    helper_source = helper.read_text(encoding="utf-8")
    assert "localStorage.getItem('auth_token')" in helper_source
    assert "localStorage.getItem('api_key')" in helper_source
    assert "config.headers['x-api-key'] = apiKey" in helper_source

    for filename in AUTH_CLIENTS:
        source = (SERVICES / filename).read_text(encoding="utf-8")
        assert "applyStoredAuth" in source, f"{filename} does not use shared auth"


def test_health_prefetch_uses_mounted_liveness_route() -> None:
    source = _read("frontend/src/main.tsx")
    assert "link.href = '/api/v1/health/live'" in source
    assert "link.href = '/api/health'" not in source
    assert "/fonts/inter.woff2" not in source
    assert 'rel="icon" href="data:image/svg+xml' in _read("frontend/index.html")


def test_api_key_login_is_validated_before_authentication() -> None:
    source = _read("frontend/src/pages/LoginPage.tsx")
    api_source = _read("frontend/src/services/api.ts")
    assert "await apiClient.getCurrentPrincipal()" in source
    assert "localStorage.removeItem('api_key')" in source
    assert "window.location.pathname !== '/login'" in api_source


def test_backup_client_uses_real_scheduler_contract() -> None:
    source = _read("frontend/src/services/governanceOps.ts")
    for path in (
        "/backup/scheduler/run",
        "/backup/scheduler/list",
        "/backup/scheduler/status",
        "/backup/scheduler/restore/",
        "/backup/scheduler/verify/",
        "/backup/scheduler/cleanup",
    ):
        assert path in source


def test_tenants_initial_effect_does_not_call_unavailable_domains() -> None:
    source = _read("frontend/src/pages/TenantsBillingPage.tsx")
    initial_effect = re.search(
        r"useEffect\(\(\) => \{(?P<body>.*?)\}, \[(?P<deps>.*?)\]\)",
        source,
        flags=re.DOTALL,
    )
    assert initial_effect is not None
    assert initial_effect.group("body").strip() == "loadTenants()"
    assert initial_effect.group("deps").strip() == "loadTenants"
    assert "disabled: true" in source
    assert "window.confirm" in source


def test_mobile_sidebar_is_closed_and_not_persisted() -> None:
    source = _read("frontend/src/store/appStore.ts")
    assert "sidebarOpen: false" in source
    persisted = source.split("partialize:", 1)[1]
    assert "sidebarOpen: state.sidebarOpen" not in persisted
    assert "merge: (persistedState, currentState)" in source


def test_backend_mounts_scheduler_and_tenant_crud_contracts() -> None:
    source = _read("backend/app/main.py")
    assert '"backup_scheduler_api"' in source
    assert "tenants_extended_router" in source


def test_api_key_guard_allows_spa_login_but_protects_api(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from backend.app import main

    (tmp_path / "index.html").write_text("<h1>SPA login shell</h1>", encoding="utf-8")
    monkeypatch.setattr(main, "frontend_dist_dir", tmp_path)
    monkeypatch.setattr(main.settings, "require_api_key", True)

    with TestClient(main.app) as client:
        login = client.get("/login")
        status_response = client.get("/api-key/status")
        protected = client.get("/api/v1/overview")

    assert login.status_code == 200
    assert "SPA login shell" in login.text
    assert status_response.status_code == 200
    assert protected.status_code == 401

    route_paths = list(main.app.openapi()["paths"])
    assert route_paths.index("/api/v1/backup/scheduler/status") < route_paths.index(
        "/api/v1/backup/{backup_id}/status"
    )
