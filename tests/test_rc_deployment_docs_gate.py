from __future__ import annotations

import json
from pathlib import Path

from scripts.rc_deployment_docs_gate import build_deployment_docs_gate


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _owner_gate_lines() -> str:
    return """
- feishu_webhook_contract
- github_issue_to_pr_dry_run
- github_issue_to_pr_execute_preflight
- hosted_github_actions_commercial_rc
- refresh_release_chain_owner_verified
"""


def _runbook_text() -> str:
    return f"""
# Runbook

This is not a GA claim and not a full Codex/Hermes parity claim.
It records current final gate status ready_with_owner_gates and
full_parity_claimed=false.

Required env:
- XAGENT_APP_MODE=production
- XAGENT_REQUIRE_API_KEY=true
- XAGENT_BOOTSTRAP_API_KEY
- prohibited_secret_artifacts
- XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL
- XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA
- 40-character hex git commit SHA

Commands:
- python scripts/rc_final_gate.py --require-ready-to-tag
- python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal
- --require-stage3-rehearsal
- python scripts/rc_refresh_release_chain.py --provider deepseek --owner-verified --timeout 60
- --owner-verified
- python scripts/rc_evidence_pack.py
- python scripts/rc_release_receipt.py
- --allow-missing-evidence-pack
- Final final gate remains strict
- python scripts/rc_owner_gate_runner.py --gate all --dry-run --env-file .xagent_runtime/reports/rc-owner-env-template.env
- python scripts/rc_owner_gate_runner.py --gate github_issue_to_pr_dry_run
- python scripts/rc_external_smoke.py --provider deepseek
- --require-configured
- --env-file .xagent_runtime/reports/rc-owner-env-template.env
- --github-actions-preflight
- python scripts/rc_owner_handoff_gate.py
- python scripts/stage3_owner_domain_guide.py --domain "<REAL_DOMAIN>"
- stage3-owner-domain-guide-20260618.json
- stage3-owner-domain-guide-20260618.md
- rc-external-smoke.json
- use `--release-sha <40-character-sha>` only
- python scripts/stage3_https_preflight.py --domain "<REAL_DOMAIN>"
- --https-preflight-report .xagent_runtime\reports\stage3-https-preflight-20260618.json
- prefill_refs.https_preflight_applied=true
- stage3-https-preflight-20260618.json
- stage3-https-preflight-20260618.md
- python scripts/stage3_owner_evidence_todo.py
- stage3-owner-evidence-todo-20260618.json
- stage3-owner-evidence-todo-20260618.md
- python scripts/stage3_owner_quickstart.py
- stage3-owner-quickstart-20260618.json
- stage3-owner-quickstart-20260618.md
- temporary wildcard DNS such as `sslip.io`
- owner-verified hosted GitHub Actions `head_sha`
- docker compose --env-file .env.production
- kubectl rollout status deployment/xagent-api

Handoff:
- x-agent-commercial-rc-receipt.json
- .zip.sha256
- rc_evidence_pack.py
- .xagent_runtime/release/
- .xagent_runtime/
- ROLLBACK_PROCEDURE.md
- status=completed
- conclusion=success
- head_sha_verified=true
- read_probe.state=open
- npm ci
- local user/runtime path findings
- manifest unsafe paths
- file hygiene findings
- candidate files for local user/runtime path findings
- release receipt freshness
- approval_request
- owner_env_template
- owner_gate_checklist
- missing_env_groups
- unresolved_env_names
- owner_gate_unresolved_env_names
- Replace owner env template placeholder values
- env_preflight
- Trigger the hosted Commercial RC Gate workflow
- generated_at
- pip-audit
- Python vulnerability audit evidence
- python -m pip show pip-audit

Owner gates:
{_owner_gate_lines()}
"""


def _checklist_text() -> str:
    return f"""
# Checklist

Target: commercial release candidate, not a GA.
Do not make a full competitor-parity claim.
Current RC final gate status: ready_with_owner_gates.
Boundary: full_parity_claimed=false.

- RC final gate
- RC evidence pack
- --allow-missing-evidence-pack
- --owner-verified
- Final final gate remains strict
- RC refresh release chain
- RC owner gate runner
- RC owner handoff gate
- rc_delivery_status.py
- --gate github_issue_to_pr_dry_run must not require XAGENT_GITHUB_TOKEN
- read_probe.state=open
- Deployment owner generates and stores final production secrets
- prohibited_secret_artifacts
- Final staged files match `docs/RC_STAGING_MANIFEST.md`
- Installer dry-runs use `npm ci`, not `npm install`
- local user/runtime path findings
- tracked-secret, local user/runtime path, manifest unsafe paths, excluded-area reference, and
- file hygiene scans
- release receipt freshness
- approval_request
- owner_env_template
- owner_gate_checklist
- missing_env_groups
- unresolved_env_names
- owner_gate_unresolved_env_names
- Replace owner env template placeholder values
- env_preflight
- Trigger the hosted Commercial RC Gate workflow
- XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA
- 40-character hex git commit SHA
- head_sha_verified=true
- generated_at
- pip-audit
- Python vulnerability audit evidence
- python -m pip show pip-audit
- Latest staging plan dry-run planned 113 files across 6 commands.
- x-agent-commercial-rc-receipt.json
- .zip.sha256
- rc_evidence_pack.py
- .xagent_runtime/release/

Owner gates:
{_owner_gate_lines()}
"""


def _quickstart_text() -> str:
    return """
# Quickstart

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-xagent.ps1 -DryRun
```

```sh
sh scripts/install-xagent.sh --dry-run
python scripts/rc_owner_gate_runner.py --gate all --dry-run --env-file .xagent_runtime/reports/rc-owner-env-template.env
python scripts/rc_runtime_smoke.py
```

See docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md.
"""


def _release_notes_text() -> str:
    return """
# Release Notes

Status: commercial release candidate, not GA.

- scripts/rc_final_gate.py
- scripts/rc_evidence_pack.py
- scripts/rc_delivery_status.py
- rc_evidence_pack.py
- --allow-missing-evidence-pack
- Final final gate remains strict
- ready_with_owner_gates
- not ready_for_rc_tag
- scripts/rc_delivery_status.py
- owner_finalize_pending
- full_parity_claimed=false
- docs/RC_STAGING_MANIFEST.md
- npm ci
- local user/runtime path findings
- local user/runtime path scanning
- manifest unsafe paths
- candidate file hygiene scanning
- release receipt freshness
- approval_request
- prohibited secret artifact paths
- owner_env_template
- owner_gate_checklist
- missing owner env groups
- unresolved_env_names
- owner_gate_unresolved_env_names
- Replace owner env template placeholder values
- env_preflight
- XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA
- 40-character hex git commit SHA
- head_sha_verified=true
- generated_at
- pip-audit
- Python vulnerability audit evidence
- python -m pip show pip-audit
- x-agent-commercial-rc-receipt.json
- .zip.sha256
- .xagent_runtime/release/

This release does not claim full Codex or Hermes parity.
"""


def _reports(tmp_path: Path) -> dict[str, Path]:
    final = _write_json(
        tmp_path / "reports" / "rc-final-gate.json",
        {
            "status": "ready_with_owner_gates",
            "full_parity_claimed": False,
            "release_decision": {"can_tag_rc_now": False},
            "owner_gates": [
                {"name": "feishu_webhook_contract", "status": "action_required"},
                {"name": "github_issue_to_pr_dry_run", "status": "action_required"},
                {"name": "github_issue_to_pr_execute_preflight", "status": "action_required"},
                {"name": "hosted_github_actions_commercial_rc", "status": "action_required"},
            ],
        },
    )
    receipt = _write_json(
        tmp_path / "release" / "x-agent-commercial-rc-receipt.json",
        {
            "status": "created",
            "artifact": {
                "path": str(tmp_path / "release" / "bundle.zip"),
                "sha256": "a" * 64,
            },
        },
    )
    pack = _write_json(
        tmp_path / "reports" / "rc-evidence-pack.json",
        {
            "status": "created",
            "output_path": str(tmp_path / "release" / "evidence.zip"),
            "pack_sha256": "b" * 64,
        },
    )
    staging = _write_json(
        tmp_path / "reports" / "rc-staging-plan.json",
        {
            "status": "planned",
            "file_count": 113,
            "command_count": 6,
        },
    )
    return {
        "runbook": _write_text(tmp_path / "docs" / "COMMERCIAL_DEPLOYMENT_RUNBOOK.md", _runbook_text()),
        "checklist": _write_text(tmp_path / "docs" / "RC_COMMERCIAL_DEPLOYMENT_CHECKLIST.md", _checklist_text()),
        "quickstart": _write_text(tmp_path / "docs" / "INSTALL_QUICKSTART.md", _quickstart_text()),
        "notes": _write_text(tmp_path / "RELEASE_NOTES.md", _release_notes_text()),
        "final": final,
        "receipt": receipt,
        "pack": pack,
        "staging": staging,
    }


def _gate(paths: dict[str, Path]):
    return build_deployment_docs_gate(
        runbook_path=paths["runbook"],
        checklist_path=paths["checklist"],
        install_quickstart_path=paths["quickstart"],
        release_notes_path=paths["notes"],
        final_gate_path=paths["final"],
        release_receipt_path=paths["receipt"],
        evidence_pack_path=paths["pack"],
        staging_plan_path=paths["staging"],
    )


def _gate_allow_missing_pack(paths: dict[str, Path]):
    return build_deployment_docs_gate(
        runbook_path=paths["runbook"],
        checklist_path=paths["checklist"],
        install_quickstart_path=paths["quickstart"],
        release_notes_path=paths["notes"],
        final_gate_path=paths["final"],
        release_receipt_path=paths["receipt"],
        evidence_pack_path=paths["pack"],
        staging_plan_path=paths["staging"],
        allow_missing_evidence_pack=True,
    )


def test_deployment_docs_gate_passes_for_current_handoff_docs(tmp_path: Path) -> None:
    report = _gate(_reports(tmp_path))

    assert report.status == "passed"
    assert {check.name: check.status for check in report.checks}["artifact_handoff_docs"] == "passed"


def test_deployment_docs_gate_rejects_missing_runbook_token(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["runbook"].write_text(_runbook_text().replace("XAGENT_APP_MODE=production", ""), encoding="utf-8")

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "runbook_document")
    assert "XAGENT_APP_MODE=production" in str(check.error)


def test_deployment_docs_gate_requires_strict_provider_handoff_command(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["runbook"].write_text(
        _runbook_text().replace("--require-configured", "", 1),
        encoding="utf-8",
    )

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "runbook_document")
    assert "--require-configured" in str(check.error)


def test_deployment_docs_gate_requires_owner_placeholder_reporting_tokens(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["runbook"].write_text(
        _runbook_text().replace("unresolved_env_names", ""),
        encoding="utf-8",
    )

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "runbook_document")
    assert "unresolved_env_names" in str(check.error)


def test_deployment_docs_gate_requires_stage3_https_preflight_command(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["runbook"].write_text(
        _runbook_text().replace("python scripts/stage3_https_preflight.py", ""),
        encoding="utf-8",
    )

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "runbook_document")
    assert "stage3_https_preflight.py" in str(check.error)


def test_deployment_docs_gate_requires_stage3_owner_domain_guide_command(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["runbook"].write_text(
        _runbook_text().replace("python scripts/stage3_owner_domain_guide.py", ""),
        encoding="utf-8",
    )

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "runbook_document")
    assert "stage3_owner_domain_guide.py" in str(check.error)


def test_deployment_docs_gate_requires_stage3_preflight_owner_draft_prefill(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["runbook"].write_text(
        _runbook_text().replace("--https-preflight-report", ""),
        encoding="utf-8",
    )

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "runbook_document")
    assert "--https-preflight-report" in str(check.error)


def test_deployment_docs_gate_requires_stage3_owner_evidence_todo_command(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["runbook"].write_text(
        _runbook_text().replace("python scripts/stage3_owner_evidence_todo.py", ""),
        encoding="utf-8",
    )

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "runbook_document")
    assert "stage3_owner_evidence_todo.py" in str(check.error)


def test_deployment_docs_gate_requires_stage3_owner_quickstart_command(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["runbook"].write_text(
        _runbook_text().replace("python scripts/stage3_owner_quickstart.py", ""),
        encoding="utf-8",
    )

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "runbook_document")
    assert "stage3_owner_quickstart.py" in str(check.error)


def test_deployment_docs_gate_requires_stage3_rehearsal_final_gate_command(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["runbook"].write_text(
        _runbook_text().replace("python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal", ""),
        encoding="utf-8",
    )

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "runbook_document")
    assert "--require-stage3-rehearsal" in str(check.error)


def test_deployment_docs_gate_requires_owner_gate_ids(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["checklist"].write_text(_checklist_text().replace("feishu_webhook_contract", ""), encoding="utf-8")

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "owner_gate_docs")
    assert "feishu_webhook_contract" in str(check.error)


def test_deployment_docs_gate_rejects_final_gate_full_parity_claim(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    _write_json(
        paths["final"],
        {
            "status": "ready_with_owner_gates",
            "full_parity_claimed": True,
            "release_decision": {"can_tag_rc_now": False},
            "owner_gates": [],
        },
    )

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "release_state_docs")
    assert "full parity" in str(check.error)


def test_deployment_docs_gate_rejects_docs_full_parity_overclaim(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["notes"].write_text(
        _release_notes_text() + "\nFull Codex/Hermes parity achieved.\n",
        encoding="utf-8",
    )

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "overclaim_boundary_docs")
    assert "full Codex/Hermes parity achieved" in str(check.error)


def test_deployment_docs_gate_rejects_docs_ready_to_tag_overclaim(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["checklist"].write_text(
        _checklist_text() + "\ncan_tag_rc_now=true\nCurrent final gate status is ready_for_rc_tag.\n",
        encoding="utf-8",
    )

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "overclaim_boundary_docs")
    assert "can_tag_rc_now=true" in str(check.error)


def test_deployment_docs_gate_allows_negated_ready_to_tag_boundary(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["checklist"].write_text(
        _checklist_text() + "\nCurrent final gate status is not `ready_for_rc_tag`.\n",
        encoding="utf-8",
    )

    report = _gate(paths)

    assert report.status == "passed"


def test_deployment_docs_gate_allows_conditional_ready_to_tag_handoff(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["runbook"].write_text(
        _runbook_text()
        + "\nAfter owner-controlled evidence is verified, the final gate reports `ready_for_rc_tag`.\n",
        encoding="utf-8",
    )

    report = _gate(paths)

    assert report.status == "passed"


def test_deployment_docs_gate_rejects_current_ready_to_tag_claim_with_condition_word(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["runbook"].write_text(
        _runbook_text()
        + "\nCurrent final gate status is `ready_for_rc_tag` after docs refresh.\n",
        encoding="utf-8",
    )

    report = _gate(paths)

    assert report.status == "failed"
    overclaim = next(check for check in report.checks if check.name == "overclaim_boundary_docs")
    assert overclaim.status == "failed"
    assert "ready_for_rc_tag" in str(overclaim.error)


def test_deployment_docs_gate_allows_owner_verified_tag_ready_snapshot_with_tag_blocker(
    tmp_path: Path,
) -> None:
    paths = _reports(tmp_path)
    snapshot = """
Owner-verified RC evidence snapshot reports `ready_for_rc_tag` for commit `643a017b3a2ae00be212d186e2681a147b46bf6b`;
the already-pushed tag `x-agent-commercial-rc-20260608` currently resolves to `08cd6d114e0c0cb357ccea3e529aed7b2aea1045`;
do not use that tag until the owner creates a new tag or explicitly approves correcting the pushed tag.
"""
    paths["runbook"].write_text(_runbook_text() + snapshot, encoding="utf-8")
    paths["checklist"].write_text(_checklist_text() + snapshot, encoding="utf-8")
    paths["notes"].write_text(_release_notes_text() + snapshot, encoding="utf-8")

    report = _gate(paths)

    assert report.status == "passed"
    release_state = next(check for check in report.checks if check.name == "release_state_docs")
    overclaim = next(check for check in report.checks if check.name == "overclaim_boundary_docs")
    assert release_state.details["owner_verified_tag_ready_snapshot_docs"] == {
        "runbook": True,
        "checklist": True,
        "release_notes": True,
    }
    assert overclaim.status == "passed"


def test_deployment_docs_gate_rejects_unsafe_ready_to_tag_claim_even_with_snapshot(
    tmp_path: Path,
) -> None:
    paths = _reports(tmp_path)
    snapshot = """
Owner-verified RC evidence snapshot reports `ready_for_rc_tag` for commit `643a017b3a2ae00be212d186e2681a147b46bf6b`;
the already-pushed tag `x-agent-commercial-rc-20260608` currently resolves to `08cd6d114e0c0cb357ccea3e529aed7b2aea1045`;
do not use that tag until the owner creates a new tag or explicitly approves correcting the pushed tag.
"""
    unsafe_claim = "\nCurrent final gate status is ready_for_rc_tag.\nready to tag the RC now.\ncan_tag_rc_now=true\n"
    paths["runbook"].write_text(_runbook_text() + snapshot + unsafe_claim, encoding="utf-8")
    paths["checklist"].write_text(_checklist_text() + snapshot, encoding="utf-8")
    paths["notes"].write_text(_release_notes_text() + snapshot, encoding="utf-8")

    report = _gate(paths)

    assert report.status == "failed"
    overclaim = next(check for check in report.checks if check.name == "overclaim_boundary_docs")
    assert "ready_for_rc_tag" in str(overclaim.error)
    assert "ready to tag the RC now" in str(overclaim.error)
    assert "can_tag_rc_now=true" in str(overclaim.error)


def test_deployment_docs_gate_requires_evidence_pack_sha_and_path(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    _write_json(paths["pack"], {"status": "created", "output_path": "", "pack_sha256": ""})

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "artifact_handoff_docs")
    assert "evidence pack output path/sha256 is incomplete" in str(check.error)


def test_deployment_docs_gate_can_bootstrap_before_first_evidence_pack(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    _write_json(paths["pack"], {"status": "failed", "output_path": "", "pack_sha256": ""})

    report = _gate_allow_missing_pack(paths)

    assert report.status == "passed"
    check = next(item for item in report.checks if item.name == "artifact_handoff_docs")
    assert check.details["evidence_pack_bootstrap_allowed"] is True


def test_deployment_docs_gate_can_bootstrap_before_first_receipt_and_evidence_pack(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["receipt"].unlink()
    _write_json(paths["pack"], {"status": "failed", "output_path": "", "pack_sha256": ""})

    report = _gate_allow_missing_pack(paths)

    assert report.status == "passed"
    check = next(item for item in report.checks if item.name == "artifact_handoff_docs")
    assert check.details["release_receipt_bootstrap_allowed"] is True
    assert check.details["evidence_pack_bootstrap_allowed"] is True


def test_deployment_docs_gate_requires_receipt_after_bootstrap(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["receipt"].unlink()

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "artifact_handoff_docs")
    assert "x-agent-commercial-rc-receipt.json" in str(check.error)


def test_deployment_docs_gate_allows_bootstrap_final_gate_evidence_pack_blocker(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    _write_json(
        paths["final"],
        {
            "status": "failed",
            "full_parity_claimed": False,
            "release_decision": {"can_tag_rc_now": False},
            "local_gates": [
                {"name": "release_audit", "ok": True},
                {
                    "name": "evidence_pack",
                    "ok": False,
                    "error": "evidence pack is older than required release reports",
                    "details": {"stale_reports": [{"name": "source_bundle"}]},
                },
            ],
            "owner_gates": [
                {"name": "feishu_webhook_contract", "status": "action_required"},
                {"name": "github_issue_to_pr_dry_run", "status": "action_required"},
                {"name": "github_issue_to_pr_execute_preflight", "status": "action_required"},
                {"name": "hosted_github_actions_commercial_rc", "status": "action_required"},
            ],
        },
    )

    report = _gate_allow_missing_pack(paths)

    assert report.status == "passed"
    check = next(item for item in report.checks if item.name == "release_state_docs")
    assert check.details["final_gate_bootstrap_allowed"] is True
    assert check.details["bootstrap_blockers"] == ["evidence_pack"]


def test_deployment_docs_gate_requires_artifact_handoff_tokens(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["runbook"].write_text(_runbook_text().replace(".zip.sha256", ""), encoding="utf-8")
    paths["checklist"].write_text(_checklist_text().replace(".zip.sha256", ""), encoding="utf-8")

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "artifact_handoff_docs")
    assert ".zip.sha256" in str(check.error)


def test_deployment_docs_gate_requires_release_notes_artifact_handoff_tokens(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["notes"].write_text(
        _release_notes_text().replace("x-agent-commercial-rc-receipt.json", ""),
        encoding="utf-8",
    )

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "artifact_handoff_docs")
    assert "release_notes missing artifact handoff tokens" in str(check.error)
    assert "x-agent-commercial-rc-receipt.json" in str(check.error)


def test_deployment_docs_gate_rejects_stale_staging_plan_counts(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    paths["checklist"].write_text(
        _checklist_text().replace("planned 113 files across 6 commands", "planned 91 files across 5 commands"),
        encoding="utf-8",
    )

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "staging_plan_docs")
    assert "planned 113 files" in str(check.error)
    assert "across 6 commands" in str(check.error)
