from __future__ import annotations

from backend.app.core.skill_curator.models import (
    SkillCuratorAnalysis,
    SkillEvidence,
    SkillImprovementProposal,
)
from backend.app.core.skill_curator.scoring import score_skills


def analyze_skill_evidence(evidence: list[SkillEvidence]) -> SkillCuratorAnalysis:
    scores = score_skills(evidence)
    proposals: list[SkillImprovementProposal] = []
    seen_manual: set[str] = set()

    for score in scores:
        if score.skill_name.startswith("manual:"):
            name = score.skill_name.removeprefix("manual:")
            if name not in seen_manual and score.frequency >= 2:
                seen_manual.add(name)
                proposals.append(
                    SkillImprovementProposal(
                        skill_name=name,
                        action="create",
                        reason="Repeated manual workflow evidence is ready for skill drafting.",
                        confidence=min(0.95, 0.5 + score.frequency * 0.1),
                        safety_level="review_required",
                    )
                )
            continue

        if score.success_rate < 0.7 or score.error_rate > 0.25:
            proposals.append(
                SkillImprovementProposal(
                    skill_name=score.skill_name,
                    action="improve",
                    reason="Low success rate or repeated errors detected in recent evidence.",
                    confidence=max(0.5, 1.0 - score.success_rate),
                    safety_level="review_required",
                )
            )
        elif score.frequency <= 1 and score.recency_score < 0.3:
            proposals.append(
                SkillImprovementProposal(
                    skill_name=score.skill_name,
                    action="review",
                    reason="Skill appears stale or underused.",
                    confidence=0.6,
                    safety_level="safe",
                )
            )

    return SkillCuratorAnalysis(
        scores=scores,
        proposals=proposals,
        evidence_count=len(evidence),
    )
