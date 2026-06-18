from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


SUPPORTED_MODEL_PROVIDERS = ("openai", "deepseek", "ollama")
DEFAULT_REQUIRED_MODEL_PROVIDERS = ("openai",)

ACCEPTANCE_DIMENSIONS = (
    "model_provider",
    "windows",
    "docker",
    "long_task",
    "recovery",
    "multi_agent",
    "ui_workbench",
)

ACCEPTANCE_LAYERS = (
    "p0_environment",
    "p0_runtime_evidence",
    "p0_product_workflow",
    "p0_release_closure",
)

REQUIRED_DOCKER_E2E_STEPS = (
    "docker_available",
    "docker_build",
    "compose_config",
    "compose_backend_health",
    "compose_down",
)

BASE_DESKTOP_ACCEPTANCE_STAGES = (
    "download_release",
    "unzip_install",
    "start_entrypoints",
    "configure_model",
    "execute_task",
    "view_report",
    "recovery_guidance",
    "workbench_open",
)

REQUIRED_BROWSER_ACCEPTANCE_STAGES = (
    "browser_open",
    "model_selected",
    "task_submitted",
    "report_viewed",
    "workbench_clicked",
    "diff_clicked",
    "recovery_clicked",
)

REQUIRED_DESKTOP_ACCEPTANCE_STAGES = (
    *BASE_DESKTOP_ACCEPTANCE_STAGES,
    *REQUIRED_BROWSER_ACCEPTANCE_STAGES,
)


@dataclass(frozen=True)
class AcceptanceTask:
    id: str
    dimension: str
    layer: str
    label: str
    source: str
    blocker_type: str
    next_action: str


REAL_ACCEPTANCE_TASKS = (
    AcceptanceTask(
        id="model_provider.required_smoke",
        dimension="model_provider",
        layer="p0_environment",
        label="Required real model providers pass smoke checks",
        source="model_smoke_report",
        blocker_type="environment_gap",
        next_action="Run provider smoke checks with the required real providers configured.",
    ),
    AcceptanceTask(
        id="windows.strict_environment",
        dimension="windows",
        layer="p0_environment",
        label="Strict Windows desktop environment is verified",
        source="real_acceptance_evidence or desktop_strict_e2e_report",
        blocker_type="environment_gap",
        next_action="Run strict Windows acceptance on a Windows host with a windows-native desktop backend.",
    ),
    AcceptanceTask(
        id="docker.strict_e2e",
        dimension="docker",
        layer="p0_environment",
        label="Docker strict E2E passes required runtime steps",
        source="docker_e2e_report",
        blocker_type="environment_gap",
        next_action="Start Docker Desktop, fix compose/runtime blockers, then rerun Docker strict E2E.",
    ),
    AcceptanceTask(
        id="long_task.closure_evidence",
        dimension="long_task",
        layer="p0_runtime_evidence",
        label="Long-task closure evidence is present",
        source="codex_parity_closure",
        blocker_type="product_gap",
        next_action="Collect passing long-task closure evidence in the closure report.",
    ),
    AcceptanceTask(
        id="recovery.long_term_stability",
        dimension="recovery",
        layer="p0_runtime_evidence",
        label="Long-term stability and recovery evidence is present",
        source="codex_parity_closure",
        blocker_type="product_gap",
        next_action="Collect recovery-gate, resumability, crash archive, and audit-chain evidence.",
    ),
    AcceptanceTask(
        id="multi_agent.readiness_runtime",
        dimension="multi_agent",
        layer="p0_runtime_evidence",
        label="Multi-agent readiness and runtime smoke pass",
        source="multi_agent_readiness_report",
        blocker_type="product_gap",
        next_action="Run multi-agent orchestration readiness and include a passing runtime smoke result.",
    ),
    AcceptanceTask(
        id="multi_agent.execution_closure",
        dimension="multi_agent",
        layer="p0_release_closure",
        label="Execution closure state machine blocks failed validation and allows passed validation",
        source="codex_parity_closure or multi_agent_readiness_report",
        blocker_type="product_gap",
        next_action="Restore execution-closure validation scenarios before accepting release evidence.",
    ),
    AcceptanceTask(
        id="ui_workbench.desktop_user_path",
        dimension="ui_workbench",
        layer="p0_product_workflow",
        label="Desktop user-path and browser workbench stages are complete",
        source="desktop_strict_e2e_report",
        blocker_type="product_gap",
        next_action="Rerun strict desktop user release E2E and cover every required workbench stage.",
    ),
    AcceptanceTask(
        id="ui_workbench.security_ux_hardening",
        dimension="ui_workbench",
        layer="p0_release_closure",
        label="User-side security and UX hardening gate passes",
        source="codex_parity_closure",
        blocker_type="product_gap",
        next_action="Collect user-side security and UX hardening evidence in the closure report.",
    ),
)


def build_p0_acceptance_matrix(
    *,
    closure_payload: Mapping[str, Any] | None = None,
    real_acceptance_payload: Mapping[str, Any] | None = None,
    desktop_strict_e2e_payload: Mapping[str, Any] | None = None,
    model_smoke_payload: Mapping[str, Any] | None = None,
    docker_e2e_payload: Mapping[str, Any] | None = None,
    multi_agent_readiness_payload: Mapping[str, Any] | None = None,
    required_model_providers: Sequence[str] | None = None,
) -> dict[str, Any]:
    required_providers = normalize_required_model_providers(required_model_providers)
    rows = [
        _evaluate_task(
            task,
            closure_payload=closure_payload,
            real_acceptance_payload=real_acceptance_payload,
            desktop_strict_e2e_payload=desktop_strict_e2e_payload,
            model_smoke_payload=model_smoke_payload,
            docker_e2e_payload=docker_e2e_payload,
            multi_agent_readiness_payload=multi_agent_readiness_payload,
            required_model_providers=required_providers,
        )
        for task in REAL_ACCEPTANCE_TASKS
    ]
    blockers = [_release_blocker(row) for row in rows if row["ok"] is not True and row["blocking"] is True]
    return {
        "kind": "p0_acceptance_matrix",
        "version": 1,
        "ok": not blockers,
        "status": "acceptance_ready" if not blockers else "blocked",
        "required_model_providers": list(required_providers),
        "dimensions": _summarize_axis(rows, axis="dimension", expected=ACCEPTANCE_DIMENSIONS),
        "layers": _summarize_axis(rows, axis="layer", expected=ACCEPTANCE_LAYERS),
        "summary": {
            "total": len(rows),
            "passed": sum(1 for row in rows if row["ok"] is True),
            "blocked": len(blockers),
            "dimension_count": len(ACCEPTANCE_DIMENSIONS),
            "layer_count": len(ACCEPTANCE_LAYERS),
        },
        "rows": rows,
        "release_blockers": blockers,
        "next_actions": _dedupe(str(blocker["next_action"]) for blocker in blockers if blocker.get("next_action")),
    }


def build_p0_acceptance_matrix_from_bundle(
    evidence: Mapping[str, Mapping[str, Any] | None],
    *,
    required_model_providers: Sequence[str] | None = None,
) -> dict[str, Any]:
    return build_p0_acceptance_matrix(
        closure_payload=evidence.get("closure_payload") or evidence.get("codex_parity_closure"),
        real_acceptance_payload=evidence.get("real_acceptance_payload") or evidence.get("real_acceptance_evidence"),
        desktop_strict_e2e_payload=evidence.get("desktop_strict_e2e_payload")
        or evidence.get("desktop_strict_e2e_report"),
        model_smoke_payload=evidence.get("model_smoke_payload") or evidence.get("model_smoke_report"),
        docker_e2e_payload=evidence.get("docker_e2e_payload") or evidence.get("docker_e2e_report"),
        multi_agent_readiness_payload=evidence.get("multi_agent_readiness_payload")
        or evidence.get("multi_agent_readiness_report"),
        required_model_providers=required_model_providers,
    )


def normalize_required_model_providers(providers: Sequence[str] | None) -> tuple[str, ...]:
    raw_providers = DEFAULT_REQUIRED_MODEL_PROVIDERS if providers is None else providers
    normalized: list[str] = []
    for raw_provider in raw_providers:
        provider = str(raw_provider).strip().lower()
        if not provider:
            continue
        if provider not in SUPPORTED_MODEL_PROVIDERS:
            raise ValueError(
                f"Unsupported required model provider: {raw_provider}. "
                f"Use one of: {', '.join(SUPPORTED_MODEL_PROVIDERS)}."
            )
        if provider not in normalized:
            normalized.append(provider)
    if not normalized:
        raise ValueError("At least one required model provider must be configured.")
    return tuple(normalized)


def _evaluate_task(
    task: AcceptanceTask,
    *,
    closure_payload: Mapping[str, Any] | None,
    real_acceptance_payload: Mapping[str, Any] | None,
    desktop_strict_e2e_payload: Mapping[str, Any] | None,
    model_smoke_payload: Mapping[str, Any] | None,
    docker_e2e_payload: Mapping[str, Any] | None,
    multi_agent_readiness_payload: Mapping[str, Any] | None,
    required_model_providers: tuple[str, ...],
) -> dict[str, Any]:
    evaluators = {
        "model_provider.required_smoke": lambda: _model_provider_evidence(
            model_smoke_payload,
            required_model_providers=required_model_providers,
        ),
        "windows.strict_environment": lambda: _windows_evidence(
            real_acceptance_payload=real_acceptance_payload,
            desktop_strict_e2e_payload=desktop_strict_e2e_payload,
        ),
        "docker.strict_e2e": lambda: _docker_evidence(docker_e2e_payload),
        "long_task.closure_evidence": lambda: _closure_gate_evidence(closure_payload, "long_task_closure_evidence"),
        "recovery.long_term_stability": lambda: _closure_gate_evidence(
            closure_payload,
            "long_term_stability_recovery",
        ),
        "multi_agent.readiness_runtime": lambda: _multi_agent_runtime_evidence(multi_agent_readiness_payload),
        "multi_agent.execution_closure": lambda: _execution_closure_evidence(
            closure_payload=closure_payload,
            multi_agent_readiness_payload=multi_agent_readiness_payload,
        ),
        "ui_workbench.desktop_user_path": lambda: _desktop_stage_evidence(desktop_strict_e2e_payload),
        "ui_workbench.security_ux_hardening": lambda: _closure_gate_evidence(
            closure_payload,
            "user_side_security_ux_hardening",
        ),
    }
    evidence = evaluators[task.id]()
    ok = evidence["ok"] is True
    return {
        "id": task.id,
        "dimension": task.dimension,
        "layer": task.layer,
        "label": task.label,
        "source": task.source,
        "ok": ok,
        "status": "passed" if ok else evidence.get("status", "blocked"),
        "blocking": not ok,
        "blocker_type": task.blocker_type,
        "summary": evidence.get("summary"),
        "evidence": evidence,
        "next_action": "" if ok else task.next_action,
    }


def _model_provider_evidence(
    payload: Mapping[str, Any] | None,
    *,
    required_model_providers: tuple[str, ...],
) -> dict[str, Any]:
    if not payload:
        return _missing("Model smoke report is missing.")
    by_provider = _model_results_by_provider(payload)
    statuses = {provider: by_provider.get(provider, {}).get("status", "missing") for provider in required_model_providers}
    missing_or_blocked = [provider for provider, status in statuses.items() if status != "passed"]
    ok = not missing_or_blocked
    return {
        "ok": ok,
        "status": "passed" if ok else "blocked",
        "summary": "Required model providers passed."
        if ok
        else f"Required model providers are not passed: {', '.join(missing_or_blocked)}.",
        "kind": payload.get("kind"),
        "report_ok": payload.get("ok"),
        "required_providers": list(required_model_providers),
        "provider_statuses": statuses,
        "unavailable_optional_providers": _unavailable_optional_model_providers(
            by_provider,
            required_model_providers=required_model_providers,
        ),
    }


def _windows_evidence(
    *,
    real_acceptance_payload: Mapping[str, Any] | None,
    desktop_strict_e2e_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    windows_step = _real_acceptance_step(real_acceptance_payload, target="windows")
    if windows_step and windows_step.get("status") == "passed":
        return {
            "ok": True,
            "status": "passed",
            "summary": "Windows real acceptance step passed.",
            "source": "real_acceptance_evidence",
            "step": windows_step,
        }
    if desktop_strict_e2e_payload:
        model_env = desktop_strict_e2e_payload.get("model_environment")
        model_env = model_env if isinstance(model_env, Mapping) else {}
        backend = str(model_env.get("desktop_backend") or "").strip().lower()
        ok = desktop_strict_e2e_payload.get("ok") is True and backend == "windows-native"
        return {
            "ok": ok,
            "status": "passed" if ok else "blocked",
            "summary": "Strict desktop E2E used windows-native backend."
            if ok
            else "Strict desktop E2E did not prove a windows-native backend.",
            "source": "desktop_strict_e2e_report",
            "desktop_backend": backend or None,
            "report_ok": desktop_strict_e2e_payload.get("ok"),
            "real_acceptance_step_status": windows_step.get("status") if windows_step else None,
        }
    if windows_step:
        return {"ok": False, "status": "blocked", "summary": "Windows real acceptance step is blocked.", "step": windows_step}
    return _missing("Windows strict environment evidence is missing.")


def _docker_evidence(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return _missing("Docker strict E2E report is missing.")
    by_name = _results_by_name(payload)
    statuses = {step: by_name.get(step, {}).get("status", "missing") for step in REQUIRED_DOCKER_E2E_STEPS}
    failed_steps = [step for step, status in statuses.items() if status != "passed"]
    ok = payload.get("ok") is True and not failed_steps
    blocker = _docker_environment_blocker(payload)
    return {
        "ok": ok,
        "status": "passed" if ok else "blocked",
        "summary": "Docker strict E2E passed required steps."
        if ok
        else blocker.get("summary")
        if blocker
        else f"Docker strict E2E has blocked steps: {', '.join(failed_steps)}.",
        "kind": payload.get("kind"),
        "report_ok": payload.get("ok"),
        "required_steps": list(REQUIRED_DOCKER_E2E_STEPS),
        "step_statuses": statuses,
        "failed_steps": failed_steps,
        "blocker": blocker,
    }


def _closure_gate_evidence(payload: Mapping[str, Any] | None, gate_id: str) -> dict[str, Any]:
    if not payload:
        return _missing(f"Closure report is missing gate {gate_id}.")
    gate = _closure_gate(payload, gate_id)
    if not gate:
        return {
            "ok": False,
            "status": "missing",
            "summary": f"Closure gate {gate_id} is missing.",
            "gate_id": gate_id,
            "closure_status": payload.get("status"),
        }
    ok = gate.get("ok") is True
    return {
        "ok": ok,
        "status": "passed" if ok else "blocked",
        "summary": gate.get("summary") or ("Gate passed." if ok else f"Gate {gate_id} is blocked."),
        "gate_id": gate_id,
        "gate_status": gate.get("status"),
        "closure_status": payload.get("status"),
        "gate_evidence": gate.get("evidence", {}),
    }


def _multi_agent_runtime_evidence(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return _missing("Multi-agent readiness report is missing.")
    runtime_smoke = payload.get("runtime_smoke") if isinstance(payload.get("runtime_smoke"), Mapping) else {}
    runtime_status = runtime_smoke.get("status")
    ok = payload.get("ok") is True and (not runtime_smoke or runtime_status == "passed")
    return {
        "ok": ok,
        "status": "passed" if ok else "blocked",
        "summary": "Multi-agent readiness and runtime smoke passed."
        if ok
        else "Multi-agent readiness is blocked or runtime smoke is not passed.",
        "kind": payload.get("kind"),
        "report_ok": payload.get("ok"),
        "report_status": payload.get("status"),
        "score": payload.get("score"),
        "runtime_smoke_status": runtime_status,
        "gaps": payload.get("gaps", []),
    }


def _execution_closure_evidence(
    *,
    closure_payload: Mapping[str, Any] | None,
    multi_agent_readiness_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    closure_evidence = _closure_gate_evidence(closure_payload, "execution_closure_state_machine")
    if closure_evidence["ok"] is True:
        return closure_evidence
    if not multi_agent_readiness_payload:
        return closure_evidence
    execution = multi_agent_readiness_payload.get("execution_closure")
    execution = execution if isinstance(execution, Mapping) else {}
    scenarios = execution.get("validation_scenarios") if isinstance(execution.get("validation_scenarios"), list) else []
    failed_blocks = any(
        isinstance(item, Mapping)
        and item.get("validation_status") == "failed"
        and item.get("completion_allowed") is False
        and item.get("report_allowed") is False
        and item.get("merge_allowed") is False
        for item in scenarios
    )
    passed_allows = any(
        isinstance(item, Mapping)
        and item.get("validation_status") == "passed"
        and item.get("completion_allowed") is True
        and item.get("report_allowed") is True
        and item.get("merge_allowed") is True
        for item in scenarios
    )
    ok = failed_blocks and passed_allows
    return {
        "ok": ok,
        "status": "passed" if ok else "blocked",
        "summary": "Execution closure validation scenarios are enforced."
        if ok
        else "Execution closure validation scenarios are incomplete.",
        "source": "multi_agent_readiness_report",
        "failed_validation_blocks_completion": failed_blocks,
        "passed_validation_allows_completion": passed_allows,
        "scenario_count": len(scenarios),
        "closure_gate_status": closure_evidence["status"],
    }


def _desktop_stage_evidence(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return _missing("Desktop strict E2E report is missing.")
    by_stage = {
        str(item.get("id") or item.get("name")).strip(): item
        for item in _desktop_stage_items(payload)
        if isinstance(item, Mapping) and (item.get("id") or item.get("name"))
    }
    missing = [stage for stage in REQUIRED_DESKTOP_ACCEPTANCE_STAGES if stage not in by_stage]
    blocked = [
        stage
        for stage, item in by_stage.items()
        if stage in REQUIRED_DESKTOP_ACCEPTANCE_STAGES and not _status_passed(item)
    ]
    ok = payload.get("ok") is True and not missing and not blocked
    return {
        "ok": ok,
        "status": "passed" if ok else "blocked",
        "summary": "Desktop user-path and workbench stages passed."
        if ok
        else f"Desktop user-path stages are incomplete: missing={missing}, blocked={blocked}.",
        "kind": payload.get("kind"),
        "report_ok": payload.get("ok"),
        "required_stages": list(REQUIRED_DESKTOP_ACCEPTANCE_STAGES),
        "passed": [
            stage
            for stage in REQUIRED_DESKTOP_ACCEPTANCE_STAGES
            if stage in by_stage and _status_passed(by_stage[stage])
        ],
        "missing": missing,
        "blocked": blocked,
    }


def _desktop_stage_items(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    items: list[Mapping[str, Any]] = []
    acceptance_stages = payload.get("acceptance_stages")
    if isinstance(acceptance_stages, list):
        items.extend(item for item in acceptance_stages if isinstance(item, Mapping))
    browser_e2e = payload.get("browser_e2e")
    if isinstance(browser_e2e, Mapping) and isinstance(browser_e2e.get("stages"), list):
        items.extend(item for item in browser_e2e["stages"] if isinstance(item, Mapping))
    return items


def _summarize_axis(rows: Sequence[Mapping[str, Any]], *, axis: str, expected: Sequence[str]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for value in expected:
        scoped_rows = [row for row in rows if row.get(axis) == value]
        blocked = [row for row in scoped_rows if row.get("ok") is not True]
        summary[value] = {
            "ok": not blocked,
            "status": "passed" if not blocked else "blocked",
            "total": len(scoped_rows),
            "passed": len(scoped_rows) - len(blocked),
            "blocked": len(blocked),
            "blocked_ids": [str(row["id"]) for row in blocked],
        }
    return summary


def _release_blocker(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "dimension": row["dimension"],
        "layer": row["layer"],
        "type": row["blocker_type"],
        "summary": row["summary"],
        "next_action": row["next_action"],
        "counts_as_code_failure": row["blocker_type"] == "code_gap",
    }


def _real_acceptance_step(payload: Mapping[str, Any] | None, *, target: str) -> Mapping[str, Any] | None:
    if not payload:
        return None
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), list) else []
    steps = payload.get("steps") if isinstance(payload.get("steps"), list) else []
    for item in [*evidence, *steps]:
        if isinstance(item, Mapping) and item.get("target") == target:
            return item
    return None


def _closure_gate(payload: Mapping[str, Any], gate_id: str) -> Mapping[str, Any] | None:
    gates = payload.get("gates") if isinstance(payload.get("gates"), list) else []
    return next((gate for gate in gates if isinstance(gate, Mapping) and gate.get("id") == gate_id), None)


def _model_results_by_provider(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    results = payload.get("results") if isinstance(payload.get("results"), list) else []
    return {
        str(item.get("provider")).strip().lower(): item
        for item in results
        if isinstance(item, Mapping) and item.get("provider")
    }


def _unavailable_optional_model_providers(
    by_provider: Mapping[str, Mapping[str, Any]],
    *,
    required_model_providers: tuple[str, ...],
) -> list[dict[str, Any]]:
    required = set(required_model_providers)
    unavailable = []
    for provider, item in by_provider.items():
        if provider in required:
            continue
        if str(item.get("status") or "").strip().lower() != "skipped":
            continue
        skip_reason = str(item.get("skip_reason") or "").strip().lower()
        reason = f"{provider}_missing_key" if skip_reason == "missing_api_key" else skip_reason or "skipped"
        unavailable.append(
            {
                "provider": provider,
                "status": item.get("status"),
                "reason": reason,
                "acceptance_impact": "environment_not_configured",
            }
        )
    return unavailable


def _results_by_name(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    results = payload.get("results") if isinstance(payload.get("results"), list) else []
    return {
        str(item.get("name")).strip(): item
        for item in results
        if isinstance(item, Mapping) and item.get("name")
    }


def _docker_environment_blocker(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    parts: list[str] = []
    for item in payload.get("results", []) if isinstance(payload.get("results"), list) else []:
        if not isinstance(item, Mapping) or item.get("status") == "passed":
            continue
        parts.append(str(item.get("error") or ""))
        details = item.get("details")
        if isinstance(details, Mapping):
            parts.append(str(details))
    haystack = "\n".join(parts).lower()
    if "docker desktop has no https proxy" in haystack or "registry-1.docker.io" in haystack:
        return {
            "reason": "docker_hub_https_proxy",
            "summary": "Docker Desktop cannot reach Docker Hub to resolve the base image.",
            "acceptance_impact": "environment_not_configured",
        }
    if "docker daemon" in haystack or "docker is not available" in haystack:
        return {
            "reason": "docker_daemon_unavailable",
            "summary": "Docker daemon is not available.",
            "acceptance_impact": "environment_not_configured",
        }
    return None


def _status_passed(item: Mapping[str, Any]) -> bool:
    return item.get("ok") is True or item.get("status") in {"passed", "ready", "complete"}


def _missing(summary: str) -> dict[str, Any]:
    return {"ok": False, "status": "missing", "summary": summary}


def _dedupe(values: Any) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value and value not in deduped:
            deduped.append(value)
    return deduped
