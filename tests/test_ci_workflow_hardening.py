from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_WORKFLOW = ROOT / ".github" / "workflows" / "test.yml"


def _workflow_text() -> str:
    return TEST_WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_test_workflow_pins_qdrant_image_tag() -> None:
    text = _workflow_text()

    assert "qdrant/qdrant:latest" not in text
    assert text.count("qdrant/qdrant:v1.7.0") == 4


def test_test_workflow_integration_tests_do_not_fail_open_on_prs() -> None:
    text = _workflow_text()

    assert "continue-on-error: ${{ github.event_name == 'pull_request' }}" not in text


def test_test_workflow_summary_uses_actual_job_results() -> None:
    text = _workflow_text()

    assert "${{ needs.unit-tests.result }}" in text
    assert "${{ needs.integration-tests.result }}" in text
    assert "${{ needs.contract-tests.result }}" in text
    assert "- Integration Tests: ✓" not in text
    assert "- Contract Tests: ✓" not in text
