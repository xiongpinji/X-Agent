from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.core.code_index import CodeIndex, code_index


@dataclass
class TestMappingResult:
    query: str
    related_files: list[dict[str, Any]] = field(default_factory=list)
    test_files: list[dict[str, Any]] = field(default_factory=list)
    impact_hints: list[dict[str, Any]] = field(default_factory=list)
    dependency_hints: list[dict[str, Any]] = field(default_factory=list)
    recommended_commands: list[str] = field(default_factory=list)


class TestMapper:
    """Map a code change query to relevant test files."""

    def __init__(self, index: CodeIndex | None = None) -> None:
        self.index = index or code_index

    def map(self, query: str, limit: int = 10) -> TestMappingResult:
        related = self.index.related_files(query, limit=limit)
        tests = self.index.test_files_for(query, limit=limit)
        impact = self.index.impact_hints(query, limit=limit)
        dependencies = self.index.dependency_hints(query, limit=limit)
        commands = self._commands_from_mapping(tests)
        return TestMappingResult(
            query=query,
            related_files=related,
            test_files=tests,
            impact_hints=impact,
            dependency_hints=dependencies,
            recommended_commands=commands,
        )

    @staticmethod
    def _commands_from_mapping(test_files: list[dict[str, Any]]) -> list[str]:
        commands: list[str] = []
        for item in test_files[:5]:
            path = str(item.get("path", "")).strip()
            if not path:
                continue
            if path.endswith(".py"):
                commands.append(f"pytest {path}")
            elif path.endswith((".ts", ".tsx", ".js", ".jsx")):
                commands.append(f"npm test -- {path}")
        if not commands:
            commands.append("pytest")
        return list(dict.fromkeys(commands))


test_mapper = TestMapper()
