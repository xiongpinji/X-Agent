from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.app.core.skill_curator import SkillEvidence, analyze_skill_evidence, score_skills


def test_score_skills_penalizes_failures_and_rewards_recent_success() -> None:
    now = datetime(2026, 6, 5, tzinfo=UTC)
    evidence = [
        SkillEvidence(skill_name="good", success=True, manual_rating=1.0, used_at=now),
        SkillEvidence(skill_name="good", success=True, manual_rating=0.9, used_at=now),
        SkillEvidence(skill_name="bad", success=False, error="failed", used_at=now - timedelta(days=20)),
    ]

    scores = {score.skill_name: score for score in score_skills(evidence, now=now)}

    assert scores["good"].score > scores["bad"].score
    assert scores["bad"].error_rate == 1.0
    assert scores["good"].success_rate == 1.0


def test_analyze_skill_evidence_proposes_improve_and_create() -> None:
    evidence = [
        SkillEvidence(skill_name="unstable", success=False, error="boom"),
        SkillEvidence(skill_name="manual:release-notes", success=True),
        SkillEvidence(skill_name="manual:release-notes", success=True),
    ]

    analysis = analyze_skill_evidence(evidence)

    actions = {(proposal.skill_name, proposal.action) for proposal in analysis.proposals}
    assert ("unstable", "improve") in actions
    assert ("release-notes", "create") in actions
    assert analysis.evidence_count == 3
