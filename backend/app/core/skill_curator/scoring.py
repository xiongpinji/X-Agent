from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from backend.app.core.skill_curator.models import SkillEvidence, SkillScore


def _recency_score(latest: datetime, now: datetime) -> float:
    age_days = max((now - latest).total_seconds() / 86400.0, 0.0)
    if age_days <= 1:
        return 1.0
    if age_days >= 30:
        return 0.1
    return max(0.1, 1.0 - (age_days / 30.0))


def score_skills(evidence: list[SkillEvidence], now: datetime | None = None) -> list[SkillScore]:
    now = now or datetime.now(UTC)
    grouped: dict[str, list[SkillEvidence]] = defaultdict(list)
    for item in evidence:
        grouped[item.skill_name].append(item)

    scores: list[SkillScore] = []
    max_frequency = max((len(items) for items in grouped.values()), default=1)
    for skill_name, items in grouped.items():
        total = len(items)
        successes = sum(1 for item in items if item.success)
        failures = total - successes
        success_rate = successes / total if total else 0.0
        error_rate = failures / total if total else 0.0
        latest = max(item.used_at for item in items)
        recency = _recency_score(latest, now)
        ratings = [item.manual_rating for item in items if item.manual_rating is not None]
        rating = sum(ratings) / len(ratings) if ratings else 0.5
        frequency_score = total / max_frequency if max_frequency else 0.0
        score = (
            success_rate * 0.4
            + recency * 0.2
            + frequency_score * 0.2
            + rating * 0.2
            - error_rate * 0.15
        )
        scores.append(
            SkillScore(
                skill_name=skill_name,
                score=max(0.0, min(1.0, score)),
                success_rate=success_rate,
                frequency=total,
                error_rate=error_rate,
                recency_score=recency,
                rating_score=rating,
            )
        )
    return sorted(scores, key=lambda item: item.score)
