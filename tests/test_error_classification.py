from __future__ import annotations

from backend.app.core.repair_loop import RepairLoop


def test_error_classification_validation() -> None:
    assert RepairLoop._suggest.__name__ == "_suggest"
    assert RepairLoop().verifier._classify_error("missing required argument: path") == "validation"


def test_error_classification_missing_resource() -> None:
    assert RepairLoop().verifier._classify_error("file_not_found") == "missing_resource"


def test_error_classification_patch_mismatch() -> None:
    assert RepairLoop().verifier._classify_error("pattern_not_found") == "patch_mismatch"


def test_error_classification_approval() -> None:
    assert RepairLoop().verifier._classify_error("approval required") == "approval"


def test_error_classification_authorization() -> None:
    assert RepairLoop().verifier._classify_error("permission denied") == "authorization"


def test_error_classification_timeout() -> None:
    assert RepairLoop().verifier._classify_error("timeout") == "timeout"


def test_error_classification_runtime() -> None:
    assert RepairLoop().verifier._classify_error("boom") == "runtime"
