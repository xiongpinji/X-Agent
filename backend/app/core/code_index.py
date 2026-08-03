from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 索引时剪枝的通用垃圾目录（依赖安装/版本控制/缓存/构建产物）。
# 不剪枝时 rglob 会把 venv（数万文件）卷进来，sorted 全量物化 + 逐文件
# read_text 在本机实测 20s~120s+（Windows AV 扫描抖动），既拖慢每次 agent
# run，也让触发真实 AgentLoop 的测试随机撞 30s pytest-timeout 崩掉会话。
_SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn",
    "venv", ".venv", "env", ".env",
    "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".mypy_cache", ".tox", "dist", "build", "htmlcov", "site-packages",
    "archive", ".xagent_runtime",
})


@dataclass
class IndexedFile:
    path: str
    suffix: str
    size: int
    keywords: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    kind: str = "file"


class CodeIndex:
    """Lightweight repository index for file discovery and impact hints."""

    def __init__(self) -> None:
        self._files: list[IndexedFile] = []
        self._root: Path | None = None

    def index(self, root: str = ".", limit: int = 2_000) -> dict[str, Any]:
        base = Path(root).expanduser().resolve()
        self._root = base
        self._files = []
        if not base.exists():
            return {"root": str(base), "count": 0, "files": []}
        max_files = max(1, limit)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
            for name in sorted(filenames):
                if len(self._files) >= max_files:
                    break
                path = Path(dirpath) / name
                if not path.is_file():
                    continue
                try:
                    size = path.stat().st_size
                    text = path.read_text(encoding="utf-8", errors="ignore")[:20_000]
                except Exception:
                    size = 0
                    text = ""
                indexed = IndexedFile(
                    path=str(path.relative_to(base)),
                    suffix=path.suffix.lower(),
                    size=size,
                    keywords=self._extract_keywords(path.name + " " + text),
                    symbols=self._extract_symbols(text),
                    imports=self._extract_imports(text),
                    kind=self._kind_for(path),
                )
                self._files.append(indexed)
            if len(self._files) >= max_files:
                break
        return {"root": str(base), "count": len(self._files), "files": [file.__dict__ for file in self._files[: max(1, limit)]]}

    def related_files(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        terms = list(self._normalize_terms(query))
        scored: list[tuple[int, IndexedFile]] = []
        for file in self._files:
            haystack = f"{file.path} {file.suffix} {' '.join(file.keywords)} {' '.join(file.symbols)} {' '.join(file.imports)}".lower()
            score = sum(2 for term in terms if term in haystack)
            if score > 0:
                scored.append((score, file))
        scored.sort(key=lambda item: (-item[0], item[1].path))
        return [self._to_dict(file, score) for score, file in scored[: max(1, limit)]]

    def impact_hints(self, target: str = "", limit: int = 10) -> list[dict[str, Any]]:
        target_lower = target.lower().replace("\\", "/")
        hints: list[tuple[int, IndexedFile]] = []
        for file in self._files:
            score = 0
            lowered = file.path.lower().replace("\\", "/")
            if target_lower and (target_lower in lowered or lowered in target_lower):
                score += 6
            if any(token in lowered for token in ["main", "app", "router", "api", "core", "service", "test", "workflow", "agent"]):
                score += 1
            if target_lower and any(term in lowered for term in self._normalize_terms(target_lower)):
                score += 2
            if target_lower and any(term in " ".join(file.symbols).lower() for term in self._normalize_terms(target_lower)):
                score += 2
            if score > 0:
                hints.append((score, file))
        hints.sort(key=lambda item: (-item[0], item[1].path))
        return [self._to_dict(file, score) for score, file in hints[: max(1, limit)]]

    def test_files_for(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        terms = self._normalize_terms(query)
        scored: list[tuple[int, IndexedFile]] = []
        for file in self._files:
            lowered = file.path.lower()
            score = 0
            if "test" in lowered:
                score += 3
            if any(term in lowered for term in terms):
                score += 2
            if any(term in " ".join(file.symbols).lower() for term in terms):
                score += 2
            if any(term in " ".join(file.imports).lower() for term in terms):
                score += 1
            if score > 0:
                scored.append((score, file))
        scored.sort(key=lambda item: (-item[0], item[1].path))
        return [self._to_dict(file, score) for score, file in scored[: max(1, limit)]]

    def dependency_hints(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        terms = self._normalize_terms(query)
        scored: list[tuple[int, IndexedFile]] = []
        for file in self._files:
            haystack = f"{file.path} {' '.join(file.imports)} {' '.join(file.symbols)}".lower()
            score = sum(1 for term in terms if term in haystack)
            if score > 0:
                scored.append((score, file))
        scored.sort(key=lambda item: (-item[0], item[1].path))
        return [self._to_dict(file, score) for score, file in scored[: max(1, limit)]]

    @staticmethod
    def _normalize_terms(text: str) -> list[str]:
        return [term for term in text.lower().replace("/", " ").replace("\\", " ").split() if term]

    @staticmethod
    def _extract_keywords(text: str, limit: int = 8) -> list[str]:
        keywords: list[str] = []
        for token in text.replace("\n", " ").split():
            cleaned = token.strip(".,;:!?()[]{}<>\"'`~@#$%^&*-+=|\\/")
            if len(cleaned) < 3:
                continue
            lowered = cleaned.lower()
            if lowered not in keywords:
                keywords.append(lowered)
            if len(keywords) >= max(1, limit):
                break
        return keywords

    @staticmethod
    def _extract_symbols(text: str, limit: int = 12) -> list[str]:
        symbols: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("def ", "class ", "async def ", "function ", "export function ", "export const ", "const ", "interface ", "type ")):
                token = stripped.split()[1] if len(stripped.split()) > 1 else stripped
                token = token.split("(")[0].split(":")[0].strip("{:= ")
                if token and token not in symbols:
                    symbols.append(token)
            if len(symbols) >= max(1, limit):
                break
        return symbols

    @staticmethod
    def _extract_imports(text: str, limit: int = 12) -> list[str]:
        imports: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ", "use ", "require(", "#include", "using ")):
                cleaned = stripped.replace("\t", " ")
                if cleaned not in imports:
                    imports.append(cleaned[:160])
            if len(imports) >= max(1, limit):
                break
        return imports

    @staticmethod
    def _kind_for(path: Path) -> str:
        lowered = path.name.lower()
        if "test" in lowered or lowered.startswith("test_"):
            return "test"
        if lowered in {"main.py", "app.py", "index.ts", "index.js", "__init__.py"}:
            return "entrypoint"
        return "file"

    @staticmethod
    def _to_dict(file: IndexedFile, score: int) -> dict[str, Any]:
        return {"path": file.path, "suffix": file.suffix, "size": file.size, "keywords": file.keywords, "symbols": file.symbols, "imports": file.imports, "kind": file.kind, "score": score}


code_index = CodeIndex()
