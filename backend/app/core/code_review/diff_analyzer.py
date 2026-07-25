"""Diff 解析与影响分析。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class FileChange:
    """单个文件的变更。"""

    path: str
    additions: int = 0
    deletions: int = 0
    diff_hunks: list[str] = field(default_factory=list)
    language: str = ""

    @property
    def total_changes(self) -> int:
        return self.additions + self.deletions


@dataclass
class DiffAnalysis:
    """Diff 分析结果。"""

    files: list[FileChange] = field(default_factory=list)
    total_additions: int = 0
    total_deletions: int = 0
    affected_modules: list[str] = field(default_factory=list)
    risk_level: str = "low"  # low / medium / high

    @property
    def file_count(self) -> int:
        return len(self.files)


class DiffAnalyzer:
    """解析 unified diff 并分析影响范围。"""

    _FILE_HEADER_RE = re.compile(r"^diff --git a/(.*?) b/(.*)$")
    _HUNK_RE = re.compile(r"^@@ .+? @@(.*)$")

    def analyze(self, diff_text: str) -> DiffAnalysis:
        """解析 unified diff 文本。"""
        analysis = DiffAnalysis()
        current_file: FileChange | None = None
        current_hunk_lines: list[str] = []

        for line in diff_text.splitlines():
            file_match = self._FILE_HEADER_RE.match(line)
            if file_match:
                # 保存上一个文件
                if current_file:
                    if current_hunk_lines:
                        current_file.diff_hunks.append("\n".join(current_hunk_lines))
                    analysis.files.append(current_file)
                path = file_match.group(2)
                current_file = FileChange(path=path, language=self._detect_language(path))
                current_hunk_lines = []
                continue

            if current_file is None:
                continue

            if line.startswith("+") and not line.startswith("+++"):
                current_file.additions += 1
                analysis.total_additions += 1
                current_hunk_lines.append(line)
            elif line.startswith("-") and not line.startswith("---"):
                current_file.deletions += 1
                analysis.total_deletions += 1
                current_hunk_lines.append(line)
            elif self._HUNK_RE.match(line):
                if current_hunk_lines:
                    current_file.diff_hunks.append("\n".join(current_hunk_lines))
                    current_hunk_lines = []
                current_hunk_lines.append(line)

        # 最后一个文件
        if current_file:
            if current_hunk_lines:
                current_file.diff_hunks.append("\n".join(current_hunk_lines))
            analysis.files.append(current_file)

        # 分析影响模块
        analysis.affected_modules = self._extract_modules(analysis.files)
        analysis.risk_level = self._assess_risk(analysis)
        return analysis

    def _detect_language(self, path: str) -> str:
        ext_map = {
            ".py": "python", ".ts": "typescript", ".js": "javascript",
            ".rs": "rust", ".go": "go", ".java": "java", ".yaml": "yaml",
            ".yml": "yaml", ".json": "json", ".md": "markdown",
        }
        for ext, lang in ext_map.items():
            if path.endswith(ext):
                return lang
        return "unknown"

    def _extract_modules(self, files: list[FileChange]) -> list[str]:
        modules: set[str] = set()
        for f in files:
            parts = f.path.split("/")
            if len(parts) >= 2:
                modules.add("/".join(parts[:2]))
            elif parts:
                modules.add(parts[0])
        return sorted(modules)

    def _assess_risk(self, analysis: DiffAnalysis) -> str:
        total = analysis.total_additions + analysis.total_deletions
        if total > 500 or analysis.file_count > 20:
            return "high"
        if total > 100 or analysis.file_count > 5:
            return "medium"
        return "low"
