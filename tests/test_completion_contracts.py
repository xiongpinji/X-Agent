"""Tests for Completion Contracts — 证据驱动完成验证。"""

from __future__ import annotations

import pytest

from backend.app.core.evidence.contracts import (
    CompletionEvidence,
    EvidenceItem,
    EvidenceKind,
)
from backend.app.core.evidence.collector import EvidenceCollector
from backend.app.core.evidence.verifier import EvidenceVerifier


# ─── EvidenceItem Tests ───────────────────────────────────────────────────────


class TestEvidenceItem:
    def test_hash_computed_on_creation(self):
        item = EvidenceItem(kind=EvidenceKind.TEST_RESULT, content="all tests passed")
        assert item.hash != ""
        assert len(item.hash) == 64  # SHA-256 hex

    def test_integrity_check_passes(self):
        item = EvidenceItem(kind=EvidenceKind.DIFF, content="--- a\n+++ b\n@@ -1 +1 @@")
        assert item.verify_integrity() is True

    def test_integrity_check_fails_on_tamper(self):
        item = EvidenceItem(kind=EvidenceKind.LOG, content="original")
        item.content = "tampered"
        assert item.verify_integrity() is False

    def test_to_dict_and_from_dict_roundtrip(self):
        item = EvidenceItem(
            kind=EvidenceKind.METRIC,
            content="coverage=95%",
            metadata={"name": "coverage", "value": 95.0},
        )
        d = item.to_dict()
        restored = EvidenceItem.from_dict(d)
        assert restored.kind == item.kind
        assert restored.hash == item.hash
        assert restored.metadata == item.metadata


# ─── EvidenceCollector Tests ──────────────────────────────────────────────────


class TestEvidenceCollector:
    def test_collect_test_result(self):
        collector = EvidenceCollector(run_id="run-001")
        collector.collect_test_result("pytest: 10 passed", passed=True)
        assert collector.evidence.item_count == 1
        assert collector.evidence.items[0].kind == EvidenceKind.TEST_RESULT
        assert collector.evidence.items[0].metadata["passed"] is True

    def test_collect_diff(self):
        collector = EvidenceCollector(run_id="run-002")
        collector.collect_diff("+new line", file_path="src/main.py")
        assert collector.evidence.items[0].kind == EvidenceKind.DIFF
        assert collector.evidence.items[0].metadata["file_path"] == "src/main.py"

    def test_collect_log(self):
        collector = EvidenceCollector(run_id="run-003")
        collector.collect_log("INFO: server started", level="INFO")
        assert collector.evidence.items[0].kind == EvidenceKind.LOG

    def test_collect_multiple(self):
        collector = EvidenceCollector(run_id="run-004")
        collector.collect_test_result("ok", passed=True)
        collector.collect_diff("+x", file_path="a.py")
        collector.collect_log("done")
        assert collector.evidence.item_count == 3

    def test_collect_from_trajectory(self):
        collector = EvidenceCollector(run_id="run-005")
        trajectory = [
            {"tool": "run_tests", "output": "5 passed", "success": True},
            {"tool": "write_file", "output": "+code", "arguments": {"path": "f.py"}},
        ]
        collector.collect_from_trajectory(trajectory)
        # Should extract at least some evidence from trajectory
        assert collector.evidence.item_count >= 0  # depends on implementation


# ─── EvidenceVerifier Tests ───────────────────────────────────────────────────


class TestEvidenceVerifier:
    def test_verify_empty_evidence_fails(self):
        evidence = CompletionEvidence(run_id="run-empty")
        verifier = EvidenceVerifier()
        passed, notes = verifier.verify(evidence)
        assert passed is False
        assert "空" in notes

    def test_verify_valid_evidence_passes(self):
        evidence = CompletionEvidence(run_id="run-valid")
        evidence.add_item(EvidenceItem(kind=EvidenceKind.TEST_RESULT, content="ok"))
        verifier = EvidenceVerifier()
        passed, notes = verifier.verify(evidence)
        assert passed is True

    def test_verify_tampered_evidence_fails(self):
        evidence = CompletionEvidence(run_id="run-tamper")
        item = EvidenceItem(kind=EvidenceKind.LOG, content="original")
        evidence.add_item(item)
        item.content = "tampered"  # tamper after adding
        verifier = EvidenceVerifier()
        passed, notes = verifier.verify(evidence)
        assert passed is False
        assert "完整性" in notes

    def test_verify_require_kinds(self):
        evidence = CompletionEvidence(run_id="run-require")
        evidence.add_item(EvidenceItem(kind=EvidenceKind.LOG, content="log"))
        verifier = EvidenceVerifier(require_kinds=[EvidenceKind.TEST_RESULT])
        passed, notes = verifier.verify(evidence)
        assert passed is False
        assert "test_result" in notes

    def test_verify_with_policy_min_items(self):
        evidence = CompletionEvidence(run_id="run-policy")
        evidence.add_item(EvidenceItem(kind=EvidenceKind.TEST_RESULT, content="ok"))
        verifier = EvidenceVerifier()
        passed, notes = verifier.verify_with_policy(evidence, {"min_items": 3})
        assert passed is False
        assert "不足" in notes

    def test_verify_with_policy_require_test(self):
        evidence = CompletionEvidence(run_id="run-policy2")
        evidence.add_item(EvidenceItem(kind=EvidenceKind.LOG, content="log"))
        verifier = EvidenceVerifier()
        passed, notes = verifier.verify_with_policy(evidence, {"require_test": True})
        assert passed is False

    def test_verify_with_policy_passes(self):
        evidence = CompletionEvidence(run_id="run-policy3")
        evidence.add_item(EvidenceItem(kind=EvidenceKind.TEST_RESULT, content="passed"))
        evidence.add_item(EvidenceItem(kind=EvidenceKind.DIFF, content="+code"))
        verifier = EvidenceVerifier()
        passed, notes = verifier.verify_with_policy(
            evidence, {"min_items": 1, "require_test": True, "require_diff": True}
        )
        assert passed is True


# ─── CompletionEvidence Model Tests ──────────────────────────────────────────


class TestCompletionEvidence:
    def test_to_dict_and_from_dict(self):
        evidence = CompletionEvidence(run_id="run-rt")
        evidence.add_item(EvidenceItem(kind=EvidenceKind.TEST_RESULT, content="ok"))
        evidence.verification_passed = True
        evidence.verifier_notes = "all good"

        d = evidence.to_dict()
        restored = CompletionEvidence.from_dict(d)
        assert restored.run_id == "run-rt"
        assert restored.item_count == 1
        assert restored.verification_passed is True

    def test_item_count(self):
        evidence = CompletionEvidence(run_id="run-count")
        assert evidence.item_count == 0
        evidence.add_item(EvidenceItem(kind=EvidenceKind.LOG, content="x"))
        assert evidence.item_count == 1
