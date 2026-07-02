from __future__ import annotations

from backend.app.core.integration_rollout_guardrails import (
    build_integration_rollout_guardrails,
    evaluate_rollout_guardrail,
)


def _ready_component(kind: str) -> dict[str, object]:
    return {
        "kind": kind,
        "status": "ready",
        "ok": True,
        "evidence_refs": [f"{kind}:handoff"],
    }


def test_rollout_guardrails_are_ready_with_required_evidence() -> None:
    guardrails = build_integration_rollout_guardrails(
        {
            "guardrail_id": "rollout-1",
            "adoption_readme": {
                **_ready_component("integration_adoption_readme"),
                "validation": {
                    "commands": ["python -m pytest tests/test_integration_adoption_readme.py -q"],
                    "results": ["6 passed"],
                },
            },
            "final_review_brief": {
                **_ready_component("integration_final_review_brief"),
                "owner_summary": {"owners": ["mainline"]},
            },
            "closure_checklist": _ready_component("integration_closure_checklist"),
            "rollback_plan": {"steps": ["remove secondary candidate from staging"]},
            "risks": [{"code": "low_surface_area", "severity": "low"}],
        }
    )

    assert guardrails["kind"] == "integration_rollout_guardrails"
    assert guardrails["ok"] is True
    assert guardrails["status"] == "ready"
    assert guardrails["safe_to_rollout"] is True
    assert guardrails["summary"]["guardrail_count"] == 7
    assert guardrails["blocked_guardrails"] == []
    assert guardrails["review_guardrails"] == []
    assert guardrails["next_actions"] == ["review_rollout_guardrails_with_mainline"]


def test_missing_rollback_and_risk_summary_need_review() -> None:
    guardrails = build_integration_rollout_guardrails(
        {
            "adoption_readme": {
                **_ready_component("integration_adoption_readme"),
                "validation": {
                    "commands": ["python -m pytest tests/test_integration_adoption_readme.py -q"],
                    "results": ["6 passed"],
                },
            },
            "final_review_brief": {
                **_ready_component("integration_final_review_brief"),
                "owner_summary": {"owners": ["mainline"]},
            },
            "closure_checklist": _ready_component("integration_closure_checklist"),
        }
    )

    assert guardrails["status"] == "needs_review"
    assert guardrails["review_guardrails"] == ["rollback_plan_ready", "risk_summary_ready"]
    assert guardrails["next_actions"] == [
        "attach_rollout_rollback_plan",
        "attach_rollout_risk_summary",
        "rebuild_integration_rollout_guardrails",
    ]


def test_high_risk_payload_blocks_rollout_guardrails() -> None:
    guardrails = build_integration_rollout_guardrails(
        {
            "adoption_readme": {
                **_ready_component("integration_adoption_readme"),
                "validation": {
                    "commands": ["python -m pytest tests/test_integration_adoption_readme.py -q"],
                    "results": ["6 passed"],
                },
            },
            "final_review_brief": {
                **_ready_component("integration_final_review_brief"),
                "owner_summary": {"owners": ["mainline"]},
            },
            "closure_checklist": _ready_component("integration_closure_checklist"),
            "rollback": {"steps": ["remove candidate"]},
            "risks": [{"code": "destructive_migration", "severity": "critical"}],
        }
    )

    assert guardrails["status"] == "blocked"
    assert guardrails["safe_to_rollout"] is False
    assert guardrails["blocked_guardrails"] == ["risk_summary_ready"]
    assert guardrails["issues"][-1]["code"] == "rollout_guardrail_blocked"
    assert guardrails["next_actions"] == [
        "resolve_rollout_blockers",
        "attach_rollout_risk_summary",
        "rebuild_integration_rollout_guardrails",
    ]


def test_validation_failure_blocks_rollout_guardrails() -> None:
    guardrails = build_integration_rollout_guardrails(
        {
            "adoption_readme": _ready_component("integration_adoption_readme"),
            "final_review_brief": {
                **_ready_component("integration_final_review_brief"),
                "owner_summary": {"owners": ["mainline"]},
            },
            "closure_checklist": _ready_component("integration_closure_checklist"),
            "rollback": {"steps": ["remove candidate"]},
            "validation": {
                "commands": ["python -m pytest tests/test_integration_adoption_readme.py -q"],
                "results": ["1 failed"],
            },
            "risks": [{"code": "low_surface_area", "severity": "low"}],
        }
    )

    assert guardrails["status"] == "blocked"
    assert guardrails["blocked_guardrails"] == ["validation_evidence_ready"]
    assert guardrails["next_actions"] == [
        "resolve_rollout_blockers",
        "attach_rollout_validation_evidence",
        "rebuild_integration_rollout_guardrails",
    ]


def test_components_aliases_are_accepted() -> None:
    guardrails = build_integration_rollout_guardrails(
        {
            "components": [
                {
                    **_ready_component("integration_adoption_readme"),
                    "validation": {
                        "commands": ["python -m pytest tests/test_integration_adoption_readme.py -q"],
                        "results": ["6 passed"],
                    },
                },
                {
                    **_ready_component("integration_final_review_brief"),
                    "owner_summary": {"owners": ["mainline"]},
                },
                _ready_component("integration_closure_checklist"),
            ],
            "rollback": {"steps": ["remove candidate"]},
            "risks": [{"code": "low_surface_area", "severity": "low"}],
        }
    )

    assert guardrails["status"] == "ready"
    assert guardrails["summary"]["validation_command_count"] == 1


def test_evaluate_single_rollout_guardrail() -> None:
    guardrail = evaluate_rollout_guardrail(
        "rollback_plan_ready",
        status="ready",
        evidence_refs=["rollback steps"],
        reasons=["guardrail ready"],
    )

    assert guardrail.guardrail_id == "rollback_plan_ready"
    assert guardrail.status == "ready"
    assert guardrail.severity == "low"
    assert guardrail.evidence_refs == ("rollback steps",)
