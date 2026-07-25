"""证据数据模型。"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class EvidenceKind(StrEnum):
    """证据类型枚举。"""

    TEST_RESULT = "test_result"
    SCREENSHOT = "screenshot"
    DIFF = "diff"
    LOG = "log"
    METRIC = "metric"


@dataclass
class EvidenceItem:
    """单条证据。"""

    kind: EvidenceKind
    content: str | bytes
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.hash:
            self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """SHA-256 完整性校验。"""
        data = self.content if isinstance(self.content, bytes) else self.content.encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def verify_integrity(self) -> bool:
        """验证内容未被篡改。"""
        return self._compute_hash() == self.hash

    def to_dict(self) -> dict[str, Any]:
        content_str = (
            self.content if isinstance(self.content, str) else self.content.decode("utf-8", errors="replace")
        )
        return {
            "kind": self.kind.value,
            "content": content_str,
            "timestamp": self.timestamp.isoformat(),
            "hash": self.hash,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceItem:
        return cls(
            kind=EvidenceKind(data["kind"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            hash=data.get("hash", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CompletionEvidence:
    """一次运行的完整证据包。"""

    run_id: str
    items: list[EvidenceItem] = field(default_factory=list)
    verification_passed: bool = False
    verifier_notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def add_item(self, item: EvidenceItem) -> None:
        self.items.append(item)

    @property
    def item_count(self) -> int:
        return len(self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "items": [item.to_dict() for item in self.items],
            "verification_passed": self.verification_passed,
            "verifier_notes": self.verifier_notes,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompletionEvidence:
        return cls(
            run_id=data["run_id"],
            items=[EvidenceItem.from_dict(i) for i in data.get("items", [])],
            verification_passed=data.get("verification_passed", False),
            verifier_notes=data.get("verifier_notes", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(UTC),
        )
