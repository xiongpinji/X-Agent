from __future__ import annotations

from pathlib import Path

from scripts.stage3_staging_rehearsal_workflow_contract import DEFAULT_WORKFLOW, run_contract


def _copy_workflow(tmp_path: Path) -> Path:
    workflow = tmp_path / "deploy.yml"
    workflow.write_text(DEFAULT_WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8")
    return workflow


def test_stage3_staging_rehearsal_contract_accepts_current_workflow() -> None:
    report = run_contract()

    assert report.status == "passed"
    assert report.findings == []
    assert report.requirements_checked >= 1


def test_stage3_staging_rehearsal_contract_requires_confirmation_guard(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace("confirm-stage3-staging-deploy", "confirm"),
        encoding="utf-8",
    )

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "dry_run_default_and_confirmation" for finding in report.findings)


def test_stage3_staging_rehearsal_contract_rejects_production_environment(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace(
            "  deploy-staging:\n",
            "  deploy-staging:\n    environment:\n      name: production\n",
        ),
        encoding="utf-8",
    )

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "no_production_environment" for finding in report.findings)


def test_stage3_staging_rehearsal_contract_rejects_release_creation(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace(
            "    steps:\n    - name: Checkout selected release SHA\n",
            "    steps:\n    - uses: actions/create-release@v1\n    - name: Checkout selected release SHA\n",
        ),
        encoding="utf-8",
    )

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "no_release_creation" for finding in report.findings)


def test_stage3_staging_rehearsal_contract_requires_smoke_and_rollback(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace("kubectl rollout undo deployment/xagent-api -n staging", ""),
        encoding="utf-8",
    )

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "smoke_and_rollback_evidence" for finding in report.findings)
