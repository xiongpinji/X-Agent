from backend.app.core.long_task_merge_gates import (
    build_completion_report_merge_gate,
    build_merge_authorization,
    build_validation_evidence_gate,
    decide_parent_acceptance_gate,
)


def test_validation_evidence_gate_passes_when_all_commands_have_evidence() -> None:
    gate = build_validation_evidence_gate(
        status="completed",
        validation_passed=True,
        changed_files=["app.py", "app.py", "tests/test_app.py"],
        validation_commands=["pytest tests/test_app.py -q"],
        validation_evidence=[
            {"command": "pytest tests/test_app.py -q", "status": "passed", "exit_code": 0}
        ],
        audit={"fingerprint": "audit-1"},
        merge_plan={"fingerprint": "plan-1"},
        source_matrix={"fingerprint": "matrix-1"},
    )

    assert gate["status"] == "passed"
    assert gate["next_action"] == "deliver_parallel_subagent_merge"
    assert gate["changed_files"] == ["app.py", "tests/test_app.py"]
    assert gate["missing_validation_evidence_count"] == 0

    permissions = build_completion_report_merge_gate(gate)
    assert permissions["completion_allowed"] is True
    assert permissions["report_allowed"] is True
    assert permissions["merge_allowed"] is True
    assert permissions["passed_validation_allows_report_merge"] is True
    assert permissions["failed_validation_blocks_completion"] is False


def test_validation_evidence_gate_blocks_missing_command_evidence() -> None:
    gate = build_validation_evidence_gate(
        status="completed",
        validation_passed=None,
        validation_commands=["pytest tests/test_app.py -q"],
        validation_evidence=[],
    )

    assert gate["status"] == "missing_evidence"
    assert gate["next_action"] == "collect_parallel_validation_evidence"
    assert gate["missing_validation_evidence_commands"] == ["pytest tests/test_app.py -q"]

    permissions = build_completion_report_merge_gate(gate)
    assert permissions["completion_allowed"] is False
    assert permissions["report_allowed"] is False
    assert permissions["merge_allowed"] is False
    assert permissions["failed_validation_blocks_completion"] is True


def test_validation_evidence_gate_routes_failed_validation_to_rollback() -> None:
    gate = build_validation_evidence_gate(
        status="failed",
        validation_passed=False,
        validation_commands=["pytest -q"],
        audit={"failure_reason": "pytest failed"},
    )

    assert gate["status"] == "failed"
    assert gate["next_action"] == "rollback_parallel_subagent_merge"
    assert gate["failure_reason"] == "pytest failed"

    permissions = build_completion_report_merge_gate(gate)
    assert permissions["next_action"] == "repair_failure_then_rerun_validation"
    assert permissions["failed_validation_blocks_completion"] is True


def test_parent_acceptance_gate_waits_after_completed_parallel_execution() -> None:
    decision = decide_parent_acceptance_gate(
        matrix={"status": "waiting_parent_acceptance", "fingerprint": "matrix-1"},
        audit={"status": "completed"},
        parent_package={
            "requires_parent_acceptance": True,
            "parent_acceptance": {},
        },
    )

    assert decision["status"] == "waiting_parent_acceptance"
    assert decision["next_action"] == "request_parallel_parent_acceptance"
    assert decision["requires_parent_acceptance"] is True
    assert decision["merge_authorized"] is False


def test_parent_acceptance_gate_blocks_missing_validation_evidence_before_merge() -> None:
    decision = decide_parent_acceptance_gate(
        matrix={"status": "waiting_parent_acceptance"},
        audit={"status": "completed"},
        parent_package={"requires_parent_acceptance": True, "parent_acceptance": {"decision": "accepted"}},
        final_validation_gate={
            "status": "missing_evidence",
            "next_action": "collect_parallel_validation_evidence",
            "missing_validation_evidence_count": 1,
        },
    )

    assert decision["status"] == "validation_evidence_blocked"
    assert decision["next_action"] == "collect_parallel_validation_evidence"
    assert decision["ledger"]["final_validation_evidence_gate_status"] == "missing_evidence"


def test_parent_acceptance_gate_blocks_strict_patch_violation() -> None:
    decision = decide_parent_acceptance_gate(
        matrix={"merge_ready": True},
        audit={"status": "completed"},
        parent_package={"requires_parent_acceptance": True, "parent_acceptance": {"decision": "accepted"}},
        merge_authorization={"status": "authorized"},
        strict_patch={
            "blocked": True,
            "requires_human_review": True,
            "action": "rollback_or_manual_review",
        },
    )

    assert decision["status"] == "strict_patch_plan_blocked"
    assert decision["next_action"] == "rollback_or_manual_review"
    assert decision["merge_authorized"] is True


def test_parent_acceptance_gate_allows_authorized_ready_merge() -> None:
    decision = decide_parent_acceptance_gate(
        matrix={"merge_ready": True, "merge_authorized": True, "fingerprint": "matrix-1"},
        audit={"status": "completed"},
        parent_package={
            "requires_parent_acceptance": True,
            "parent_acceptance": {"decision": "accepted", "id": "acceptance-1"},
        },
        merge_authorization={"id": "auth-1", "status": "authorized"},
    )

    assert decision["status"] == "ready_to_merge"
    assert decision["next_action"] == "execute_parallel_subagent_merge_sequence"
    assert decision["merge_authorized"] is True
    assert decision["merge_ready"] is True
    assert decision["ledger"]["parent_acceptance_id"] == "acceptance-1"


def test_parent_acceptance_gate_routes_completed_merge_to_delivery() -> None:
    decision = decide_parent_acceptance_gate(
        matrix={"status": "merged"},
        audit={"status": "completed"},
        parent_package={"parent_acceptance": {"decision": "accepted"}},
        merge_result={"status": "completed", "merge_execution_audit_fingerprint": "merge-audit-1"},
        final_validation_gate={"status": "passed"},
    )

    assert decision["status"] == "merged"
    assert decision["next_action"] == "deliver_parallel_subagent_merge"
    assert decision["ledger"]["merge_execution_audit_fingerprint"] == "merge-audit-1"


def test_merge_authorization_requires_accepted_parent_decision() -> None:
    blocked = build_merge_authorization(
        parent_decision="revision_requested",
        phase_id="phase-1",
        phase_title="dev",
        parent_acceptance_id="acceptance-1",
        matrix={"fingerprint": "matrix-1"},
    )

    assert blocked["status"] == "blocked"
    assert blocked["next_action"] == "request_parallel_parent_acceptance"


def test_merge_authorization_blocks_when_parent_gate_is_blocked() -> None:
    blocked = build_merge_authorization(
        parent_decision="accepted",
        phase_id="phase-1",
        phase_title="dev",
        parent_acceptance_id="acceptance-1",
        matrix={"fingerprint": "matrix-1"},
        parent_gate={
            "status": "validation_evidence_blocked",
            "next_action": "collect_parallel_validation_evidence",
            "fingerprint": "gate-1",
        },
    )

    assert blocked["status"] == "blocked"
    assert blocked["parent_acceptance_gate_fingerprint"] == "gate-1"
    assert blocked["next_action"] == "collect_parallel_validation_evidence"


def test_merge_authorization_records_merge_plan_when_parent_gate_passes() -> None:
    authorized = build_merge_authorization(
        parent_decision="accepted",
        phase_id="phase-1",
        phase_title="dev",
        parent_acceptance_id="acceptance-1",
        matrix={"fingerprint": "matrix-1"},
        audit={"status": "completed"},
        parent_gate={"status": "waiting_parent_acceptance", "fingerprint": "gate-1"},
        merge_plan={"fingerprint": "plan-1", "merge_step_count": 2, "status": "ready"},
        authorized_at="2026-05-29T10:00:00+00:00",
        authorization_id="auth-1",
    )

    assert authorized["status"] == "authorized"
    assert authorized["id"] == "auth-1"
    assert authorized["next_action"] == "execute_parallel_subagent_merge_sequence"
    assert authorized["matrix_fingerprint"] == "matrix-1"
    assert authorized["parent_acceptance_gate_fingerprint"] == "gate-1"
    assert authorized["merge_plan_fingerprint"] == "plan-1"
    assert authorized["merge_step_count"] == 2
