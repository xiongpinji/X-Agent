from __future__ import annotations
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

@dataclass
class CodeMatch:
    file_path: Path
    line_number: int
    content: str
    relevance_score: float
    context_lines: List[str] = field(default_factory=list)
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": str(self.file_path),
            "line_number": self.line_number,
            "content": self.content,
            "relevance_score": self.relevance_score,
            "context_lines": self.context_lines,
        }

@dataclass
class FileNode:
    path: Path
    file_type: str
    symbols: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    size: int = 0
    last_modified: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": str(self.path),
            "file_type": self.file_type,
            "symbols": self.symbols,
            "imports": self.imports,
            "size": self.size,
            "last_modified": self.last_modified.isoformat(),
        }

@dataclass
class DependencyEdge:
    from_file: Path
    to_file: Path
    import_statement: str
    edge_type: str = "import"
    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_file": str(self.from_file),
            "to_file": str(self.to_file),
            "import_statement": self.import_statement,
            "edge_type": self.edge_type,
        }

@dataclass
class DependencyGraph:
    nodes: Dict[Path, FileNode] = field(default_factory=dict)
    edges: List[DependencyEdge] = field(default_factory=list)
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {str(k): v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
        }

@dataclass
class IndexStats:
    total_files: int = 0
    indexed_files: int = 0
    total_symbols: int = 0
    index_time_seconds: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_files": self.total_files,
            "indexed_files": self.indexed_files,
            "total_symbols": self.total_symbols,
            "index_time_seconds": self.index_time_seconds,
            "last_updated": self.last_updated.isoformat(),
        }

class CodebaseIndex:
    SUPPORTED_EXTENSIONS = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
    }
    IGNORE_DIRS = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        "dist",
        "build",
        ".egg-info",
        ".tox",
        "coverage",
    }
    def __init__(self) -> None:
        self._files: Dict[Path, FileNode] = {}
        self._file_contents: Dict[Path, str] = {}
        self._dependency_graph: DependencyGraph = DependencyGraph()
        self._stats = IndexStats()
        self._root_path: Optional[Path] = None
    def build_index(self, root_path: Path | str, patterns: Optional[List[str]] = None) -> IndexStats:
        start_time = time.time()
        root_path = Path(root_path).resolve()
        if not root_path.exists():
            logger.warning(f"Root path does not exist: {root_path}")
            return self._stats
        self._root_path = root_path
        self._files.clear()
        self._file_contents.clear()
        self._dependency_graph = DependencyGraph()
        file_count = 0
        for file_path in self._scan_files(root_path, patterns):
            try:
                self._index_file(file_path)
                file_count += 1
            except Exception as e:
                logger.debug(f"Failed to index file {file_path}: {e}")
        self._build_dependency_graph()
        self._stats.total_files = file_count
        self._stats.indexed_files = len(self._files)
        self._stats.total_symbols = sum(len(node.symbols) for node in self._files.values())
        self._stats.index_time_seconds = time.time() - start_time
        self._stats.last_updated = datetime.now(timezone.utc)
        logger.info(f"Index complete: {self._stats.indexed_files} files, {self._stats.total_symbols} symbols, {self._stats.index_time_seconds:.2f}s")
        return self._stats
    def update_index(self, changed_files: List[Path | str]) -> IndexStats:
        start_time = time.time()
        updated_count = 0
        for file_path in changed_files:
            file_path = Path(file_path).resolve()
            if not file_path.exists():
                if file_path in self._files:
                    del self._files[file_path]
                    if file_path in self._file_contents:
                        del self._file_contents[file_path]
                    updated_count += 1
            else:
                try:
                    self._index_file(file_path)
                    updated_count += 1
                except Exception as e:
                    logger.debug(f"Failed to update file index {file_path}: {e}")
        self._build_dependency_graph()
        self._stats.total_symbols = sum(len(node.symbols) for node in self._files.values())
        # Bug fix: update_index previously left indexed_files stale after deletions
        # (only build_index recomputed it). Recompute here too so the file count
        # reflects additions/removals — mirrors build_index().
        self._stats.indexed_files = len(self._files)
        self._stats.index_time_seconds = time.time() - start_time
        self._stats.last_updated = datetime.now(timezone.utc)
        logger.info(f"Incremental update complete: {updated_count} files updated")
        return self._stats
    def search(self, query: str, file_types: Optional[List[str]] = None, limit: int = 20) -> List[CodeMatch]:
        results: List[Tuple[float, CodeMatch]] = []
        query_terms = self._normalize_query(query)
        for file_path, node in self._files.items():
            if file_types and node.file_type not in file_types:
                continue
            score = self._calculate_relevance(query_terms, node, file_path)
            if score > 0:
                matches = self._find_matches_in_file(file_path, query_terms)
                for line_num, content, context in matches:
                    match = CodeMatch(file_path=file_path, line_number=line_num, content=content, relevance_score=score, context_lines=context)
                    results.append((score, match))
        results.sort(key=lambda x: -x[0])
        return [match for _, match in results[:limit]]
    def get_dependencies(self, file_path: Path | str) -> DependencyGraph:
        file_path = Path(file_path).resolve()
        graph = DependencyGraph()
        if file_path in self._files:
            graph.nodes[file_path] = self._files[file_path]
            for edge in self._dependency_graph.edges:
                if edge.from_file == file_path:
                    graph.edges.append(edge)
                    if edge.to_file in self._files:
                        graph.nodes[edge.to_file] = self._files[edge.to_file]
        return graph
    def get_dependents(self, file_path: Path | str) -> List[Path]:
        file_path = Path(file_path).resolve()
        dependents: Set[Path] = set()
        for edge in self._dependency_graph.edges:
            if edge.to_file == file_path:
                dependents.add(edge.from_file)
        return list(dependents)
    def _scan_files(self, root_path: Path, patterns: Optional[List[str]] = None) -> List[Path]:
        files: List[Path] = []
        for path in root_path.rglob("*"):
            if not path.is_file():
                continue
            if any(part in self.IGNORE_DIRS for part in path.parts):
                continue
            if patterns:
                if any(path.match(pattern) for pattern in patterns):
                    files.append(path)
            else:
                if path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    files.append(path)
        return sorted(files)
    def _index_file(self, file_path: Path) -> None:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.debug(f"Failed to read file {file_path}: {e}")
            return
        file_type = self.SUPPORTED_EXTENSIONS.get(file_path.suffix.lower(), "unknown")
        size = file_path.stat().st_size
        symbols = self._extract_symbols(content, file_type)
        imports = self._extract_imports(content, file_type)
        node = FileNode(path=file_path, file_type=file_type, symbols=symbols, imports=imports, size=size, last_modified=datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc))
        self._files[file_path] = node
        self._file_contents[file_path] = content
    def _extract_symbols(self, content: str, file_type: str) -> List[str]:
        symbols: List[str] = []
        if file_type == "python":
            patterns = [r"^\s*(?:async\s+)?def\s+(\w+)", r"^\s*class\s+(\w+)"]
        elif file_type in ("typescript", "javascript"):
            patterns = [r"(?:export\s+)?(?:async\s+)?function\s+(\w+)", r"(?:export\s+)?class\s+(\w+)", r"(?:export\s+)?(?:const|let|var)\s+(\w+)"]
        else:
            patterns = [r"(?:def|function|func)\s+(\w+)", r"class\s+(\w+)"]
        for line in content.splitlines():
            for pattern in patterns:
                matches = re.findall(pattern, line, re.MULTILINE)
                for match in matches:
                    if match and match not in symbols:
                        symbols.append(match)
        return symbols[:100]
    def _extract_imports(self, content: str, file_type: str) -> List[str]:
        imports: List[str] = []
        if file_type == "python":
            patterns = [r"^import\s+(.+?)(?:\s+as\s+\w+)?$", r"^from\s+(.+?)\s+import"]
        elif file_type in ("typescript", "javascript"):
            patterns = [r"^import\s+(?:{[^}]*}|[\w*]+)\s+from\s+['\"](.+?)['\"]" , r"^require\s*\(\s+['\"](.+?)['\"]\s*\)"]
        else:
            patterns = [r"^import\s+(.+)", r"^from\s+(.+)"]
        for line in content.splitlines():
            for pattern in patterns:
                matches = re.findall(pattern, line, re.MULTILINE)
                for match in matches:
                    if match and match not in imports:
                        imports.append(match)
        return imports[:50]
    def _build_dependency_graph(self) -> None:
        self._dependency_graph = DependencyGraph()
        for file_path, node in self._files.items():
            self._dependency_graph.nodes[file_path] = node
        for file_path, node in self._files.items():
            for import_stmt in node.imports:
                target_files = self._resolve_import(file_path, import_stmt)
                for target_file in target_files:
                    if target_file in self._files:
                        edge = DependencyEdge(from_file=file_path, to_file=target_file, import_statement=import_stmt, edge_type="import")
                        self._dependency_graph.edges.append(edge)
    def _resolve_import(self, from_file: Path, import_stmt: str) -> List[Path]:
        targets: List[Path] = []
        if not self._root_path:
            return targets
        import_path = import_stmt.strip().strip("\'\"" )
        if import_path.startswith("."):
            base_dir = from_file.parent
            parts = import_path.split(".")
            for _ in range(len(parts) - 1):
                if base_dir.parent != base_dir:
                    base_dir = base_dir.parent
            remaining = parts[-1].replace("/", "\\")
            for ext in self.SUPPORTED_EXTENSIONS.keys():
                candidate = base_dir / (remaining + ext)
                if candidate in self._files:
                    targets.append(candidate)
        else:
            import_path = import_path.replace("/", "\\").replace(".", "\\")
            for file_path in self._files.keys():
                if import_path in str(file_path):
                    targets.append(file_path)
        return targets
    def _normalize_query(self, query: str) -> List[str]:
        terms = re.split(r"[\s\-_/\\]+", query.lower())
        return [term for term in terms if term and len(term) > 1]
    def _calculate_relevance(self, query_terms: List[str], node: FileNode, file_path: Path) -> float:
        score = 0.0
        file_name = file_path.name.lower()
        for term in query_terms:
            if term in file_name:
                score += 2.0
        symbols_str = " ".join(node.symbols).lower()
        for term in query_terms:
            if term in symbols_str:
                score += 1.5
        imports_str = " ".join(node.imports).lower()
        for term in query_terms:
            if term in imports_str:
                score += 0.5
        path_str = str(file_path).lower()
        for term in query_terms:
            if term in path_str:
                score += 1.0
        return score
    def _find_matches_in_file(self, file_path: Path, query_terms: List[str]) -> List[Tuple[int, str, List[str]]]:
        matches: List[Tuple[int, str, List[str]]] = []
        if file_path not in self._file_contents:
            return matches
        content = self._file_contents[file_path]
        lines = content.splitlines()
        for line_num, line in enumerate(lines, 1):
            line_lower = line.lower()
            if any(term in line_lower for term in query_terms):
                start = max(0, line_num - 3)
                end = min(len(lines), line_num + 2)
                context = lines[start:end]
                matches.append((line_num, line, context))
        return matches[:10]
    def get_stats(self) -> IndexStats:
        return self._stats
    def get_file_info(self, file_path: Path | str) -> Optional[Dict[str, Any]]:
        file_path = Path(file_path).resolve()
        if file_path not in self._files:
            return None
        node = self._files[file_path]
        return {
            "path": str(file_path),
            "file_type": node.file_type,
            "symbols": node.symbols,
            "imports": node.imports,
            "size": node.size,
            "last_modified": node.last_modified.isoformat(),
        }
    def list_files(self, file_type: Optional[str] = None) -> List[Dict[str, Any]]:
        files: List[Dict[str, Any]] = []
        for file_path, node in self._files.items():
            if file_type and node.file_type != file_type:
                continue
            files.append({
                "path": str(file_path),
                "file_type": node.file_type,
                "size": node.size,
                "symbols_count": len(node.symbols),
                "imports_count": len(node.imports),
            })
        return sorted(files, key=lambda x: x["path"])

_global_index: Optional[CodebaseIndex] = None

def get_codebase_index() -> CodebaseIndex:
    global _global_index
    if _global_index is None:
        _global_index = CodebaseIndex()
    return _global_index

def set_codebase_index(index: CodebaseIndex) -> None:
    global _global_index
    _global_index = index
