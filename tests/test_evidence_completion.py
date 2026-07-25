"""证据驱动完成模块测试。"""
import pytest
from pathlib import Path
import tempfile

from backend.app.core.evidence.contracts import (
    CompletionEvidence,
    EvidenceItem,
    EvidenceKind,
)
from backend.app.core.evidence.collector import EvidenceCollector
from backend.app.core.evidence.verifier import EvidenceVerifier
from backend.app.core.evidence.storage import EvidenceStorage


class TestEvidenceContracts:
    """数据模型测试。"""

    def test_evidence_item_hash_auto(self):
        item = EvidenceItem(kind=EvidenceKind.LOG, content="hello")
        assert item.hash != ""
        assert item.verify_integrity()

    def test_evidence_item_tamper_detection(self):
        item = EvidenceItem(kind=EvidenceKind.LOG, content="hello")
        item.content = "tampered"
        assert not item.verify_integrity()

    def test_evidence_item_serialization(self):
        item = EvidenceItem(kind=EvidenceKind.TEST_RESULT, content="passed", metadata={"suite": "unit"})
        d = item.to_dict()
        restored = EvidenceItem.from_dict(d)
        assert restored.kind == EvidenceKind.TEST_RESULT
        assert restored.content == "passed"
        assert restored.hash == item.hash

    def test_completion_evidence_add_and_count(self):
        ev = CompletionEvidence(run_id="run-1")
        assert ev.item_count == 0
        ev.add_item(EvidenceItem(kind=EvidenceKind.LOG, content="x"))
        assert ev.item_count == 1

    def test_completion_evidence_serialization(self):
        ev = CompletionEvidence(run_id="run-2")
        ev.add_item(EvidenceItem(kind=EvidenceKind.DIFF, content="+line"))
        d = ev.to_dict()
        restored = CompletionEvidence.from_dict(d)
        assert restored.run_id == "run-2"
        assert restored.item_count == 1


class TestEvidenceCollector:
    """收集器测试。"""

    def test_collect_test_result(self):
        collector = EvidenceCollector("run-10")
        collector.collect_test_result("all passed", passed=True)
        ev = collector.finalize()
        assert ev.item_count == 1
        assert ev.items[0].kind == EvidenceKind.TEST_RESULT

    def test_collect_diff(self):
        collector = EvidenceCollector("run-11")
        collector.collect_diff("+new line", file_path="main.py")
        ev = collector.finalize()
        assert ev.items[0].metadata["file_path"] == "main.py"

    def test_collect_metric(self):
        collector = EvidenceCollector("run-12")
        collector.collect_metric("latency", 42.5, "ms")
        ev = collector.finalize()
        assert "latency=42.5ms" in ev.items[0].content

    def test_collect_from_trajectory(self):
        collector = EvidenceCollector("run-13")
        trajectory = [
            {"type": "tool_call", "tool": "search", "result": "found 3"},
            {"type": "test_execution", "output": "ok", "passed": True},
            {"type": "file_change", "diff": "+x", "path": "a.py"},
        ]
        collector.collect_from_trajectory(trajectory)
        ev = collector.finalize()
        assert ev.item_count == 3


class TestEvidenceVerifier:
    """验证器测试。"""

    def test_verify_empty_fails(self):
        ev = CompletionEvidence(run_id="run-20")
        verifier = EvidenceVerifier()
        passed, notes = verifier.verify(ev)
        assert not passed
        assert "为空" in notes

    def test_verify_valid_passes(self):
        ev = CompletionEvidence(run_id="run-21")
        ev.add_item(EvidenceItem(kind=EvidenceKind.LOG, content="ok"))
        verifier = EvidenceVerifier()
        passed, _ = verifier.verify(ev)
        assert passed

    def test_verify_require_kinds(self):
        ev = CompletionEvidence(run_id="run-22")
        ev.add_item(EvidenceItem(kind=EvidenceKind.LOG, content="ok"))
        verifier = EvidenceVerifier(require_kinds=[EvidenceKind.TEST_RESULT])
        passed, notes = verifier.verify(ev)
        assert not passed
        assert "test_result" in notes

    def test_verify_tampered(self):
        ev = CompletionEvidence(run_id="run-23")
        item = EvidenceItem(kind=EvidenceKind.LOG, content="original")
        ev.add_item(item)
        item.content = "tampered"
        verifier = EvidenceVerifier()
        passed, notes = verifier.verify(ev)
        assert not passed
        assert "hash" in notes

    def test_verify_with_policy(self):
        ev = CompletionEvidence(run_id="run-24")
        ev.add_item(EvidenceItem(kind=EvidenceKind.TEST_RESULT, content="pass"))
        ev.add_item(EvidenceItem(kind=EvidenceKind.DIFF, content="+x"))
        verifier = EvidenceVerifier()
        passed, _ = verifier.verify_with_policy(ev, {"min_items": 2, "require_test": True, "require_diff": True})
        assert passed


class TestEvidenceStorage:
    """存储测试。"""

    def test_save_and_load(self, tmp_path):
        storage = EvidenceStorage(store_dir=tmp_path)
        ev = CompletionEvidence(run_id="run-30")
        ev.add_item(EvidenceItem(kind=EvidenceKind.LOG, content="data"))
        storage.save(ev)
        loaded = storage.load("run-30")
        assert loaded is not None
        assert loaded.run_id == "run-30"
        assert loaded.item_count == 1

    def test_load_nonexistent(self, tmp_path):
        storage = EvidenceStorage(store_dir=tmp_path)
        assert storage.load("nope") is None

    def test_exists_and_delete(self, tmp_path):
        storage = EvidenceStorage(store_dir=tmp_path)
        ev = CompletionEvidence(run_id="run-31")
        storage.save(ev)
        assert storage.exists("run-31")
        storage.delete("run-31")
        assert not storage.exists("run-31")

    def test_list_all(self, tmp_path):
        storage = EvidenceStorage(store_dir=tmp_path)
        storage.save(CompletionEvidence(run_id="a"))
        storage.save(CompletionEvidence(run_id="b"))
        assert set(storage.list_all()) == {"a", "b"}
