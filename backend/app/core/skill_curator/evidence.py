from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from backend.app.core.skill_curator.models import SkillEvidence


def normalize_evidence(records: Iterable[dict[str, object] | SkillEvidence]) -> list[SkillEvidence]:
    evidence: list[SkillEvidence] = []
    for record in records:
        if isinstance(record, SkillEvidence):
            evidence.append(record)
        else:
            evidence.append(SkillEvidence.model_validate(record))
    return evidence


def load_evidence_jsonl(path: Path) -> list[SkillEvidence]:
    if not path.exists():
        return []
    rows: list[SkillEvidence] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(SkillEvidence.model_validate(json.loads(line)))
    return rows
