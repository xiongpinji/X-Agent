from __future__ import annotations

from backend.app.core.patch_risk_analysis import (
    analyze_patch_paths,
    classify_patch_path,
    is_sensitive_patch_path,
    normalize_patch_path,
)


def test_normalize_patch_path_uses_repo_relative_posix_form() -> None:
    assert normalize_patch_path(r".\backend\app\main.py") == "backend/app/main.py"
    assert normalize_patch_path("/config//settings.yaml") == "config/settings.yaml"


def test_sensitive_patch_paths_match_secret_files_directories_and_names() -> None:
    for path in (
        ".env",
        ".npmrc",
        "secrets/prod.env",
        ".ssh/id_rsa",
        "config/api_token.txt",
        "credentials/service-account.json",
    ):
        assert is_sensitive_patch_path(path)
        classification = classify_patch_path(path)
        assert classification.layer == "secret"
        assert classification.risk == "critical"
        assert classification.sandbox_profile == "manual_review"
        assert classification.approval_required is True
        assert classification.allowed_by_default is False


def test_release_surface_paths_require_release_review() -> None:
    for path in (
        "Dockerfile",
        "docker-compose.yml",
        ".github/workflows/ci.yml",
        "deploy/kubernetes/base/deployment.yaml",
    ):
        classification = classify_patch_path(path)

        assert classification.layer == "release"
        assert classification.risk == "high"
        assert classification.sandbox_profile == "release_review"
        assert classification.approval_required is True
        assert classification.allowed_by_default is False


def test_configuration_test_generated_and_source_paths_are_classified() -> None:
    assert classify_patch_path("pyproject.toml").layer == "configuration"
    assert classify_patch_path("config/settings.yaml").sandbox_profile == "restricted_patch"
    assert classify_patch_path("tests/test_app.py").layer == "test"
    assert classify_patch_path("frontend/src/App.test.tsx").layer == "test"
    assert classify_patch_path("dist/app.js").allowed_by_default is False
    assert classify_patch_path("backend/app/core/service.py").layer == "implementation"
    assert classify_patch_path("backend/app/core/service.py").risk == "low"


def test_workspace_boundary_escape_requires_manual_review() -> None:
    classification = classify_patch_path("../outside.env")

    assert classification.layer == "workspace_boundary"
    assert classification.risk == "critical"
    assert classification.approval_required is True


def test_analyze_patch_paths_dedupes_and_reports_review_issues() -> None:
    report = analyze_patch_paths(
        [
            r".\backend\app\main.py",
            "backend/app/main.py",
            ".env",
            ".github/workflows/ci.yml",
            "pyproject.toml",
            "tests/test_app.py",
        ]
    )

    assert report["kind"] == "patch_risk_analysis"
    assert report["ok"] is False
    assert report["status"] == "review_required"
    assert report["summary"] == {
        "total": 5,
        "approval_required": 2,
        "max_risk": "critical",
        "layers": {
            "implementation": 1,
            "secret": 1,
            "release": 1,
            "configuration": 1,
            "test": 1,
        },
    }
    assert report["sensitive_targets"] == [".env"]
    assert report["release_surface_targets"] == [".github/workflows/ci.yml"]
    assert report["configuration_targets"] == ["pyproject.toml"]
    assert [issue["code"] for issue in report["issues"]] == [
        "patch_sensitive_file_requires_review",
        "patch_release_surface_requires_review",
    ]


def test_analyze_patch_paths_passes_for_non_review_targets() -> None:
    report = analyze_patch_paths(["backend/app/core/service.py", "tests/test_service.py", "config/app.yaml"])

    assert report["ok"] is True
    assert report["status"] == "passed"
    assert report["summary"]["max_risk"] == "medium"
    assert report["issues"] == []
