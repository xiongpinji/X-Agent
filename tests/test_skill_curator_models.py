from __future__ import annotations

from backend.app.core.skill_curator import SkillDraftRequest, SkillEvidence
from backend.app.core.skill_curator.writer import render_skill_markdown


def test_skill_evidence_defaults_are_safe() -> None:
    evidence = SkillEvidence(skill_name="python-debugging")

    assert evidence.success is True
    assert evidence.duration_seconds == 0
    assert evidence.used_at is not None


def test_skill_draft_markdown_contains_review_safety_note() -> None:
    request = SkillDraftRequest(
        skill_name="python-debugging",
        description="Debug Python failures.",
        trigger="Use for failing Python tests.",
        steps=["Read the failure", "Patch the cause", "Run the test"],
    )

    content = render_skill_markdown(request)

    assert "name: python-debugging" in content
    assert "Run the test" in content
    assert "Review before installing" in content


def test_skill_draft_request_defaults_to_dry_run() -> None:
    request = SkillDraftRequest(skill_name="docs-polish")
    assert request.dry_run is True
