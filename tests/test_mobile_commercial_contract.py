from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from backend.app.api import mobile
from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.api.mobile import MobileRunManager, TriggerRequest
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal


def _principal(tenant: str, user: str) -> Principal:
    return Principal(
        tenant_id=tenant,
        user_id=user,
        role="user",
        scopes=["agent:read", "agent:run"],
        authenticated=True,
    )


def _request(operation_id: str = "mobile-operation-1") -> TriggerRequest:
    return TriggerRequest(task="Generate a report", operation_id=operation_id)


@pytest.mark.parametrize(
    "payload",
    [
        {"task": "Generate", "operation_id": "   "},
        {
            "task": "Generate",
            "operation_id": "bounded-metadata",
            "metadata": {"blob": "x" * 65_536},
        },
        {
            "task": "Generate",
            "operation_id": "typed-device",
            "metadata": {"device_id": {"nested": True}},
        },
    ],
)
def test_mobile_trigger_rejects_unbounded_or_ambiguous_input(payload: dict) -> None:
    with pytest.raises(ValidationError):
        TriggerRequest.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"device_id": "device-1", "platform": "unknown", "push_token": "token"},
        {"device_id": "device-1", "platform": "ios", "push_token": "x" * 4_097},
        {
            "device_id": "device-1",
            "platform": "ios",
            "push_token": "token",
            "topics": [f"topic-{index}" for index in range(33)],
        },
    ],
)
def test_mobile_push_registration_has_resource_bounds(payload: dict) -> None:
    with pytest.raises(ValidationError):
        mobile.PushRegisterRequest.model_validate(payload)


def test_mobile_runs_and_push_tokens_are_owner_scoped() -> None:
    manager = MobileRunManager()
    owner = _principal("tenant-a", "user-a")
    foreign_user = _principal("tenant-a", "user-b")
    foreign_tenant = _principal("tenant-b", "user-a")

    record = manager.create_run(_request(), owner)

    assert manager.get_run(record.run_id, owner) == record
    assert manager.get_run(record.run_id, foreign_user) is None
    assert manager.get_run(record.run_id, foreign_tenant) is None
    assert manager.list_runs(owner) == [record]
    assert manager.list_runs(foreign_user) == []

    push = mobile.PushRegisterRequest(
        device_id="device-1",
        platform="ios",
        push_token="push-token",
    )
    manager.register_push(push, owner)
    assert manager.unregister_push("device-1", foreign_user) is False
    assert manager.unregister_push("device-1", owner) is True


@pytest.mark.asyncio
async def test_mobile_cancel_stops_the_owned_execution_task() -> None:
    manager = MobileRunManager()
    owner = _principal("tenant-a", "user-a")
    record = manager.create_run(_request(), owner)
    started = asyncio.Event()

    async def wait_forever() -> None:
        started.set()
        await asyncio.Event().wait()

    execution = asyncio.create_task(wait_forever())
    manager.attach_execution(record.run_id, execution)
    await started.wait()

    assert await manager.cancel_execution(record.run_id, owner) is True
    assert execution.cancelled()
    assert record.status == "cancelled"


@pytest.mark.asyncio
async def test_mobile_execution_binds_operation_owner_and_safe_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = MobileRunManager()
    owner = _principal("tenant-a", "user-a")
    success = manager.create_run(_request("operation-success"), owner)
    failure = manager.create_run(_request("operation-failure"), owner)
    captured = []

    class FakeAgent:
        async def run(self, *, task, context):
            captured.append((task, context))
            if context.operation_id == "operation-failure":
                raise RuntimeError("PRIVATE_MOBILE_PROVIDER_SECRET")
            return SimpleNamespace(answer="real answer")

    monkeypatch.setattr(mobile, "get_mobile_manager", lambda: manager)
    monkeypatch.setattr(mobile, "get_agent", lambda: FakeAgent())

    await mobile._execute_mobile_run(success, owner)
    with caplog.at_level(logging.ERROR):
        await mobile._execute_mobile_run(failure, owner)

    _, context = captured[0]
    assert context.operation_id == "operation-success"
    assert context.request_id == success.run_id
    assert context.tenant_id == "tenant-a"
    assert context.user_id == "user-a"
    assert success.status == "completed"
    assert success.result_summary == "real answer"
    assert failure.status == "failed"
    assert failure.error == "Agent execution failed."
    assert failure.error_code == "agent_execution_failed"
    assert "PRIVATE_MOBILE_PROVIDER_SECRET" not in caplog.text


@pytest.mark.asyncio
async def test_mobile_http_surface_enforces_owner_and_hides_owner_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = MobileRunManager()
    app = FastAPI()
    app.include_router(mobile.router)
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)

    def principal_from_header(request: Request) -> Principal:
        return _principal(
            request.headers.get("x-test-tenant", "tenant-a"),
            request.headers.get("x-test-user", "user-a"),
        )

    async def complete_without_provider(record, principal) -> None:
        manager.update_status(record.run_id, "completed", result_summary="done")
        manager.detach_execution(record.run_id)

    app.dependency_overrides[get_current_principal] = principal_from_header
    monkeypatch.setattr(mobile, "get_mobile_manager", lambda: manager)
    monkeypatch.setattr(mobile, "_execute_mobile_run", complete_without_provider)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/api/v1/mobile/trigger",
            json={"task": "Generate", "operation_id": "mobile-http-op"},
        )
        assert created.status_code == 200
        run_id = created.json()["run_id"]

        owner_runs = await client.get("/api/v1/mobile/runs")
        assert owner_runs.status_code == 200
        assert len(owner_runs.json()) == 1
        assert "tenant_id" not in owner_runs.json()[0]
        assert "user_id" not in owner_runs.json()[0]

        foreign = await client.get(
            f"/api/v1/mobile/runs/{run_id}/status",
            headers={"x-test-user": "user-b"},
        )
        assert foreign.status_code == 404
        foreign_runs = await client.get(
            "/api/v1/mobile/runs",
            headers={"x-test-user": "user-b"},
        )
        assert foreign_runs.json() == []
