from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.api.issue_to_pr import get_issue_to_pr_executor
from backend.app.main import app


def teardown_function() -> None:
    app.dependency_overrides.pop(get_issue_to_pr_executor, None)


def _csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/csrf-token")
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def test_issue_to_pr_dry_run_from_url_returns_plan() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})

    response = client.post(
        "/api/v1/issue-to-pr/dry-run",
        json={"issue_url": "https://github.com/acme/project/issues/42"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is True
    assert payload["execute_allowed"] is False
    assert payload["issue"]["repo_full_name"] == "acme/project"
    assert payload["issue"]["issue_number"] == 42
    assert payload["branch_name"] == "xagent/issue-42"
    assert payload["pr_title"].startswith("Fix #42:")
    assert "No repository writes" in payload["pr_body"]


def test_issue_to_pr_execute_requires_explicit_token(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("XAGENT_GITHUB_TOKEN", raising=False)
    client = TestClient(app, headers={"x-api-key": "bootstrap"})

    response = client.post(
        "/api/v1/issue-to-pr/execute",
        headers=_csrf_headers(client),
        json={"issue_url": "https://github.com/acme/project/issues/42", "execute": True},
    )

    assert response.status_code == 403


def test_issue_to_pr_execute_requires_csrf_even_with_token(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    client = TestClient(app)

    response = client.post(
        "/api/v1/issue-to-pr/execute",
        json={"issue_url": "https://github.com/acme/project/issues/42", "execute": True},
    )

    assert response.status_code == 403
    assert "CSRF" in response.text


def test_issue_to_pr_execute_uses_fake_executor(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    async def fake_executor(plan: dict[str, object]) -> dict[str, object]:
        return {
            "status": "executed",
            "branch": plan["branch_name"],
            "pr_url": "https://github.com/acme/project/pull/1",
        }

    app.dependency_overrides[get_issue_to_pr_executor] = lambda: fake_executor
    client = TestClient(app, headers={"x-api-key": "bootstrap"})

    response = client.post(
        "/api/v1/issue-to-pr/execute",
        headers=_csrf_headers(client),
        json={"issue_url": "https://github.com/acme/project/issues/42", "execute": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "executed"
    assert payload["execute"] is True
    assert payload["pipeline_result"]["pr_url"].endswith("/pull/1")
