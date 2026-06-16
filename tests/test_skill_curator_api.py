from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.settings import get_settings


def _csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/csrf-token")
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def test_skill_curator_analyze_endpoint_returns_scores_and_proposals() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/skill-curator/analyze",
        headers=_csrf_headers(client),
        json={
            "evidence": [
                {"skill_name": "unstable", "success": False, "error": "boom"},
                {"skill_name": "manual:triage", "success": True},
                {"skill_name": "manual:triage", "success": True},
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence_count"] == 3
    assert payload["scores"]
    assert any(item["action"] == "create" for item in payload["proposals"])


def test_skill_curator_draft_endpoint_writes_only_to_staging(tmp_path: Path) -> None:
    client = TestClient(app)
    draft_root = tmp_path / "drafts"

    response = client.post(
        "/api/v1/skill-curator/draft",
        headers=_csrf_headers(client),
        json={
            "skill_name": "Release Notes",
            "description": "Draft release notes from merged work.",
            "trigger": "Use after a release branch is ready.",
            "steps": ["Collect changes", "Group by user impact"],
            "dry_run": False,
            "draft_root": str(draft_root),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "drafted"
    assert payload["activated"] is False
    draft_path = Path(payload["draft_path"])
    assert draft_path.exists()
    assert draft_root in draft_path.parents
    assert "Review before installing" in draft_path.read_text(encoding="utf-8")


def test_skill_curator_draft_rejects_custom_root_when_api_key_required(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XAGENT_REQUIRE_API_KEY", "true")
    get_settings.cache_clear()
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/skill-curator/draft",
            headers=_csrf_headers(client),
            json={
                "skill_name": "Release Notes",
                "dry_run": False,
                "draft_root": str(tmp_path / "drafts"),
            },
        )

        assert response.status_code == 403
    finally:
        get_settings.cache_clear()
