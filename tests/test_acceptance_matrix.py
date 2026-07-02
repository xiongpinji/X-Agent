from __future__ import annotations

import pytest

from backend.app.core import acceptance_matrix


def test_p0_acceptance_matrix_happy_path_layers_all_dimensions() -> None:
    matrix = acceptance_matrix.build_p0_acceptance_matrix(
        closure_payload=_closure_report(ok=True),
        real_acceptance_payload=_real_acceptance_report(windows_status="passed"),
        desktop_strict_e2e_payload=_desktop_strict_e2e_report(ok=True),
        model_smoke_payload=_model_smoke_report({"openai": "passed", "deepseek": "passed", "ollama": "passed"}),
        docker_e2e_payload=_docker_e2e_report(passed=True),
        multi_agent_readiness_payload=_multi_agent_readiness_report(ok=True, runtime_smoke=True),
    )

    assert matrix["kind"] == "p0_acceptance_matrix"
    assert matrix["ok"] is True
    assert matrix["status"] == "acceptance_ready"
    assert matrix["summary"] == {
        "total": 9,
        "passed": 9,
        "blocked": 0,
        "dimension_count": 7,
        "layer_count": 4,
    }
    assert set(matrix["dimensions"]) == set(acceptance_matrix.ACCEPTANCE_DIMENSIONS)
    assert all(item["status"] == "passed" for item in matrix["dimensions"].values())
    assert all(item["status"] == "passed" for item in matrix["layers"].values())
    assert [row["id"] for row in matrix["rows"]] == [task.id for task in acceptance_matrix.REAL_ACCEPTANCE_TASKS]
    assert matrix["release_blockers"] == []
    assert matrix["next_actions"] == []


def test_p0_acceptance_matrix_keeps_model_provider_subset_and_optional_openai_gap() -> None:
    matrix = acceptance_matrix.build_p0_acceptance_matrix(
        closure_payload=_closure_report(ok=True),
        real_acceptance_payload=_real_acceptance_report(windows_status="passed"),
        desktop_strict_e2e_payload=_desktop_strict_e2e_report(ok=True),
        model_smoke_payload=_model_smoke_report(
            {
                "openai": ("skipped", "missing_api_key"),
                "deepseek": "passed",
                "ollama": "passed",
            }
        ),
        docker_e2e_payload=_docker_e2e_report(passed=True),
        multi_agent_readiness_payload=_multi_agent_readiness_report(ok=True, runtime_smoke=True),
        required_model_providers=("deepseek", "ollama"),
    )

    row = _row(matrix, "model_provider.required_smoke")
    assert matrix["ok"] is True
    assert matrix["required_model_providers"] == ["deepseek", "ollama"]
    assert row["ok"] is True
    assert row["evidence"]["provider_statuses"] == {"deepseek": "passed", "ollama": "passed"}
    assert row["evidence"]["unavailable_optional_providers"] == [
        {
            "provider": "openai",
            "status": "skipped",
            "reason": "openai_missing_key",
            "acceptance_impact": "environment_not_configured",
        }
    ]


def test_p0_acceptance_matrix_surfaces_docker_and_model_environment_blockers() -> None:
    matrix = acceptance_matrix.build_p0_acceptance_matrix(
        closure_payload=_closure_report(ok=True),
        real_acceptance_payload=_real_acceptance_report(windows_status="passed"),
        desktop_strict_e2e_payload=_desktop_strict_e2e_report(ok=True),
        model_smoke_payload=_model_smoke_report({"openai": "passed", "deepseek": "skipped", "ollama": "passed"}),
        docker_e2e_payload=_docker_e2e_report(passed=False, docker_proxy=True),
        multi_agent_readiness_payload=_multi_agent_readiness_report(ok=True, runtime_smoke=True),
        required_model_providers=("openai", "deepseek"),
    )

    docker = _row(matrix, "docker.strict_e2e")
    model = _row(matrix, "model_provider.required_smoke")
    assert matrix["ok"] is False
    assert matrix["status"] == "blocked"
    assert matrix["dimensions"]["docker"]["status"] == "blocked"
    assert matrix["layers"]["p0_environment"]["blocked"] == 2
    assert docker["evidence"]["blocker"]["reason"] == "docker_hub_https_proxy"
    assert model["evidence"]["provider_statuses"]["deepseek"] == "skipped"
    assert [
        (blocker["id"], blocker["type"], blocker["counts_as_code_failure"])
        for blocker in matrix["release_blockers"]
    ] == [
        ("model_provider.required_smoke", "environment_gap", False),
        ("docker.strict_e2e", "environment_gap", False),
    ]


def test_p0_acceptance_matrix_blocks_missing_ui_workbench_stage() -> None:
    matrix = acceptance_matrix.build_p0_acceptance_matrix(
        closure_payload=_closure_report(ok=True),
        real_acceptance_payload=_real_acceptance_report(windows_status="passed"),
        desktop_strict_e2e_payload=_desktop_strict_e2e_report(ok=True, missing_stage="diff_clicked"),
        model_smoke_payload=_model_smoke_report({"openai": "passed", "deepseek": "passed", "ollama": "passed"}),
        docker_e2e_payload=_docker_e2e_report(passed=True),
        multi_agent_readiness_payload=_multi_agent_readiness_report(ok=True, runtime_smoke=True),
    )

    row = _row(matrix, "ui_workbench.desktop_user_path")
    assert matrix["ok"] is False
    assert matrix["dimensions"]["ui_workbench"]["blocked_ids"] == ["ui_workbench.desktop_user_path"]
    assert row["status"] == "blocked"
    assert row["evidence"]["missing"] == ["diff_clicked"]
    assert "ui_workbench.desktop_user_path" in [blocker["id"] for blocker in matrix["release_blockers"]]


def test_p0_acceptance_matrix_can_fall_back_to_multi_agent_execution_closure() -> None:
    closure = _closure_report(ok=False)
    closure["gates"] = [gate for gate in closure["gates"] if gate["id"] != "execution_closure_state_machine"]

    matrix = acceptance_matrix.build_p0_acceptance_matrix(
        closure_payload=closure,
        real_acceptance_payload=_real_acceptance_report(windows_status="passed"),
        desktop_strict_e2e_payload=_desktop_strict_e2e_report(ok=True),
        model_smoke_payload=_model_smoke_report({"openai": "passed", "deepseek": "passed", "ollama": "passed"}),
        docker_e2e_payload=_docker_e2e_report(passed=True),
        multi_agent_readiness_payload=_multi_agent_readiness_report(ok=True, runtime_smoke=True),
    )

    row = _row(matrix, "multi_agent.execution_closure")
    assert row["ok"] is True
    assert row["evidence"]["source"] == "multi_agent_readiness_report"
    assert row["evidence"]["failed_validation_blocks_completion"] is True
    assert row["evidence"]["passed_validation_allows_completion"] is True


def test_p0_acceptance_matrix_from_bundle_accepts_report_key_aliases() -> None:
    matrix = acceptance_matrix.build_p0_acceptance_matrix_from_bundle(
        {
            "codex_parity_closure": _closure_report(ok=True),
            "real_acceptance_evidence": _real_acceptance_report(windows_status="passed"),
            "desktop_strict_e2e_report": _desktop_strict_e2e_report(ok=True),
            "model_smoke_report": _model_smoke_report({"deepseek": "passed", "ollama": "passed"}),
            "docker_e2e_report": _docker_e2e_report(passed=True),
            "multi_agent_readiness_report": _multi_agent_readiness_report(ok=True, runtime_smoke=True),
        },
        required_model_providers=("deepseek", "ollama"),
    )

    assert matrix["ok"] is True
    assert matrix["required_model_providers"] == ["deepseek", "ollama"]


def test_p0_acceptance_matrix_rejects_empty_required_provider_list() -> None:
    with pytest.raises(ValueError, match="At least one required model provider"):
        acceptance_matrix.build_p0_acceptance_matrix(required_model_providers=[])


def test_real_acceptance_tasks_cover_required_dimensions_and_layers() -> None:
    task_ids = [task.id for task in acceptance_matrix.REAL_ACCEPTANCE_TASKS]
    assert len(task_ids) == len(set(task_ids))
    assert {task.dimension for task in acceptance_matrix.REAL_ACCEPTANCE_TASKS} == set(
        acceptance_matrix.ACCEPTANCE_DIMENSIONS
    )
    assert {task.layer for task in acceptance_matrix.REAL_ACCEPTANCE_TASKS} == set(acceptance_matrix.ACCEPTANCE_LAYERS)


def _row(matrix: dict, row_id: str) -> dict:
    return next(row for row in matrix["rows"] if row["id"] == row_id)


def _closure_report(*, ok: bool) -> dict:
    return {
        "kind": "codex_parity_closure",
        "ok": ok,
        "status": "acceptance_ready" if ok else "wiring_ready",
        "gates": [
            {
                "id": "long_task_closure_evidence",
                "ok": ok,
                "status": "passed" if ok else "blocked",
                "summary": "Long-task closure evidence is release-ready.",
                "evidence": {"timeline": True},
            },
            {
                "id": "long_term_stability_recovery",
                "ok": ok,
                "status": "passed" if ok else "blocked",
                "summary": "Recovery evidence is release-ready.",
                "evidence": {"checks": [{"name": "recovery_gate", "status": "passed"}]},
            },
            {
                "id": "execution_closure_state_machine",
                "ok": ok,
                "status": "passed" if ok else "blocked",
                "summary": "Execution closure state machine is enforced.",
                "evidence": {"failed_validation": {"report_allowed": False}},
            },
            {
                "id": "user_side_security_ux_hardening",
                "ok": ok,
                "status": "passed" if ok else "blocked",
                "summary": "User-side security and UX hardening evidence is release-ready.",
                "evidence": {"checks": {"strict_desktop_user_path": True}},
            },
        ],
    }


def _real_acceptance_report(*, windows_status: str) -> dict:
    return {
        "kind": "real_acceptance_evidence",
        "ok": windows_status == "passed",
        "status": windows_status,
        "evidence": [
            {
                "name": "windows_real_environment_preflight",
                "target": "windows",
                "status": windows_status,
                "ok": windows_status == "passed",
            }
        ],
    }


def _desktop_strict_e2e_report(*, ok: bool, missing_stage: str | None = None) -> dict:
    desktop_stages = [
        {"id": stage_id, "ok": True, "status": "passed"}
        for stage_id in acceptance_matrix.BASE_DESKTOP_ACCEPTANCE_STAGES
        if stage_id != missing_stage
    ]
    browser_stages = [
        {"id": stage_id, "ok": True, "status": "passed"}
        for stage_id in acceptance_matrix.REQUIRED_BROWSER_ACCEPTANCE_STAGES
        if stage_id != missing_stage
    ]
    return {
        "kind": "desktop_user_release_strict_e2e_report",
        "ok": ok,
        "model_environment": {
            "llm_backend": "deepseek",
            "desktop_backend": "windows-native",
            "llm_api_key_present": True,
        },
        "acceptance_stages": desktop_stages,
        "browser_e2e": {"ok": ok, "stages": browser_stages},
    }


def _model_smoke_report(provider_statuses: dict[str, str | tuple[str, str]]) -> dict:
    results = []
    for provider, raw_status in provider_statuses.items():
        status, skip_reason = raw_status if isinstance(raw_status, tuple) else (raw_status, None)
        item = {"provider": provider, "status": status, "model": f"{provider}-model"}
        if skip_reason:
            item["skip_reason"] = skip_reason
        results.append(item)
    return {
        "kind": "model_smoke_report",
        "ok": all(item["status"] == "passed" for item in results),
        "results": results,
    }


def _docker_e2e_report(*, passed: bool, docker_proxy: bool = False) -> dict:
    failed_error = (
        "python:3.12-slim registry-1.docker.io failed because Docker Desktop has no HTTPS proxy"
        if docker_proxy
        else "Timed out waiting for backend health."
    )
    return {
        "kind": "container_runtime_check",
        "ok": passed,
        "status": "passed" if passed else "failed",
        "results": [
            {"name": "docker_available", "status": "passed", "error": None},
            {
                "name": "docker_build",
                "status": "passed" if passed or not docker_proxy else "failed",
                "error": None if passed or not docker_proxy else failed_error,
            },
            {"name": "compose_config", "status": "passed", "error": None},
            {
                "name": "compose_backend_health",
                "status": "passed" if passed else "failed",
                "error": None if passed else failed_error,
            },
            {"name": "compose_down", "status": "passed" if passed else "missing", "error": None if passed else "compose never started"},
        ],
    }


def _multi_agent_readiness_report(*, ok: bool, runtime_smoke: bool) -> dict:
    return {
        "kind": "multi_agent_orchestration_readiness",
        "ok": ok,
        "status": "ready" if ok else "gapped",
        "score": 100 if ok else 83,
        "runtime_smoke": {"status": "passed" if runtime_smoke else "failed"},
        "execution_closure": {
            "kind": "execution_closure_state_machine",
            "status": "passed" if ok else "blocked",
            "validation_scenarios": [
                {
                    "validation_status": "failed",
                    "completion_allowed": False,
                    "report_allowed": False,
                    "merge_allowed": False,
                },
                {
                    "validation_status": "passed",
                    "completion_allowed": True,
                    "report_allowed": True,
                    "merge_allowed": True,
                },
            ],
        },
        "gaps": [] if ok else ["runtime_smoke failed"],
    }
