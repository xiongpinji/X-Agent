"""证据验证器 - 校验证据包完整性与充分性。"""
from __future__ import annotations

import logging
from typing import Any

from backend.app.core.evidence.contracts import (
    CompletionEvidence,
    EvidenceKind,
)

logger = logging.getLogger(__name__)


class EvidenceVerifier:
    """验证证据包的完整性和充分性。"""

    def __init__(self, require_kinds: list[EvidenceKind] | None = None) -> None:
        """初始化验证器。

        Args:
            require_kinds: 必须包含的证据类型列表，None 表示不强制。
        """
        self._require_kinds = require_kinds or []

    def verify(self, evidence: CompletionEvidence) -> tuple[bool, str]:
        """验证证据包。

        Returns:
            (passed, notes) 元组。
        """
        issues: list[str] = []

        # 1. 完整性校验：每条证据 hash 未被篡改
        for i, item in enumerate(evidence.items):
            if not item.verify_integrity():
                issues.append(f"证据[{i}] 完整性校验失败 (hash mismatch)")

        # 2. 充分性校验：必须包含指定类型
        if self._require_kinds:
            present_kinds = {item.kind for item in evidence.items}
            for required in self._require_kinds:
                if required not in present_kinds:
                    issues.append(f"缺少必需证据类型: {required.value}")

        # 3. 非空校验
        if not evidence.items:
            issues.append("证据包为空")

        passed = len(issues) == 0
        notes = "; ".join(issues) if issues else "验证通过"

        evidence.verification_passed = passed
        evidence.verifier_notes = notes

        logger.info(f"[{evidence.run_id}] 证据验证: passed={passed}, notes={notes}")
        return passed, notes

    def verify_with_policy(self, evidence: CompletionEvidence, policy: dict[str, Any]) -> tuple[bool, str]:
        """基于策略验证。

        Policy 示例:
            {"min_items": 2, "require_test": True, "require_diff": True}
        """
        issues: list[str] = []

        min_items = policy.get("min_items", 0)
        if evidence.item_count < min_items:
            issues.append(f"证据数量不足: {evidence.item_count} < {min_items}")

        present_kinds = {item.kind for item in evidence.items}

        if policy.get("require_test") and EvidenceKind.TEST_RESULT not in present_kinds:
            issues.append("策略要求包含测试结果证据")

        if policy.get("require_diff") and EvidenceKind.DIFF not in present_kinds:
            issues.append("策略要求包含 diff 证据")

        # 先执行基础验证
        base_passed, base_notes = self.verify(evidence)
        if not base_passed:
            issues.append(base_notes)

        passed = len(issues) == 0
        notes = "; ".join(issues) if issues else "策略验证通过"
        evidence.verification_passed = passed
        evidence.verifier_notes = notes
        return passed, notes
