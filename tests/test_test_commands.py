from __future__ import annotations

from backend.app.core.verification import VerificationEngine


def test_test_commands_for_python_files() -> None:
    commands = VerificationEngine._suggest_test_commands([{"path": "tests/test_app.py"}])
    assert commands == ["pytest tests/test_app.py"]


def test_test_commands_for_frontend_files() -> None:
    commands = VerificationEngine._suggest_test_commands([{"path": "tests/app.spec.ts"}])
    assert commands == ["npm test -- tests/app.spec.ts"]


def test_test_commands_for_empty_mapping() -> None:
    commands = VerificationEngine._suggest_test_commands([])
    assert commands == ["pytest"]
