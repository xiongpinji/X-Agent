from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.core.backup_scheduler import BackupConfig, BackupScheduler
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

ROOT = Path(__file__).resolve().parents[1]
API_MODULE = "backend.app.api.backup_scheduler_api"
API_FILE = ROOT / "backend" / "app" / "api" / "backup_scheduler_api.py"


def _load_api():
    assert API_FILE.is_file(), "secured backup scheduler API is missing"
    return importlib.import_module(API_MODULE)


def _admin_principal() -> Principal:
    return Principal(
        user_id="admin-user",
        tenant_id="default",
        role="admin",
        authenticated=True,
        scopes=["backup:read", "backup:write"],
        permission_scope=["backup:read", "backup:write"],
    )


def _app(router, *, authenticated: bool) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.include_router(router)
    if authenticated:
        app.dependency_overrides[get_current_principal] = _admin_principal
    return app


def _scheduler(tmp_path: Path) -> BackupScheduler:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "tenant-store.json").write_text(
        json.dumps({"tenants": [{"id": "default"}]}),
        encoding="utf-8",
    )
    return BackupScheduler(
        BackupConfig(
            backup_dir=str(tmp_path / "backups"),
            pg_enabled=False,
            qdrant_enabled=False,
            file_store_dirs=[str(data_dir)],
            file_patterns=["*.json"],
        )
    )


def test_backup_scheduler_route_requires_authentication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    api = _load_api()
    monkeypatch.setattr(api, "_get_scheduler", lambda: _scheduler(tmp_path))
    monkeypatch.setattr(api, "_check_enabled", lambda: None)

    with TestClient(_app(api.router, authenticated=False), raise_server_exceptions=False) as client:
        response = client.post("/api/v1/backup/scheduler/run")

    assert response.status_code == 401


def test_backup_scheduler_api_writes_and_verifies_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    api = _load_api()
    scheduler = _scheduler(tmp_path)
    monkeypatch.setattr(api, "_get_scheduler", lambda: scheduler)
    monkeypatch.setattr(api, "_check_enabled", lambda: None)

    with TestClient(_app(api.router, authenticated=True)) as client:
        run_response = client.post("/api/v1/backup/scheduler/run")
        assert run_response.status_code == 200, run_response.text
        run_payload = run_response.json()

        manifest = tmp_path / "backups" / run_payload["backup_id"] / "manifest.json"
        assert manifest.is_file()
        assert json.loads(manifest.read_text(encoding="utf-8"))["success"] is True

        list_response = client.get("/api/v1/backup/scheduler/list")
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1

        verify_response = client.post(
            f"/api/v1/backup/scheduler/verify/{run_payload['backup_id']}"
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["valid"] is True

        status_response = client.get("/api/v1/backup/scheduler/status")
        assert status_response.status_code == 200
        assert status_response.json()["last_backup_id"] == run_payload["backup_id"]
