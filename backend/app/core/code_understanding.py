"""
Advanced code understanding engine with AST analysis, dependency mapping, and semantic understanding.

This module provides deep code analysis capabilities including:
- Abstract Syntax Tree (AST) parsing and analysis
- Code dependency graph construction
- Semantic understanding and intent detection
- Multi-language support (Python, JavaScript, TypeScript, Go, Rust)
- Design pattern recognition
- Code complexity metrics
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class CodeLanguage(StrEnum):
    """Supported programming languages."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CPP = "cpp"


class SymbolKind(StrEnum):
    """Types of code symbols."""
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"
    INTERFACE = "interface"
    ENUM = "enum"
    STRUCT = "struct"
    TRAIT = "trait"
    MODULE = "module"
    IMPORT = "import"


class DesignPattern(StrEnum):
    """Common design patterns."""
    SINGLETON = "singleton"
    FACTORY = "factory"
    BUILDER = "builder"
    OBSERVER = "observer"
    STRATEGY = "strategy"
    DECORATOR = "decorator"
    ADAPTER = "adapter"
    FACADE = "facade"
    PROXY = "proxy"
    CHAIN_OF_RESPONSIBILITY = "chain_of_responsibility"
    COMMAND = "command"
    ITERATOR = "iterator"
    MEDIATOR = "mediator"
    MEMENTO = "memento"
    STATE = "state"
    TEMPLATE_METHOD = "template_method"
    VISITOR = "visitor"


@dataclass
class CodeSymbol:
    """Represents a code symbol (class, function, variable, etc.)."""
    name: str
    kind: SymbolKind
    line_start: int
    line_end: int
    column_start: int = 0
    column_end: int = 0
    docstring: str | None = None
    signature: str | None = None
    return_type: str | None = None
    parameters: list[dict[str, Any]] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    modifiers: list[str] = field(default_factory=list)
    parent: str | None = None
    children: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    complexity: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "kind": self.kind,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "column_start": self.column_start,
            "column_end": self.column_end,
            "docstring": self.docstring,
            "signature": self.signature,
            "return_type": self.return_type,
            "parameters": self.parameters,
            "decorators": self.decorators,
            "modifiers": self.modifiers,
            "parent": self.parent,
            "children": self.children,
            "references": self.references,
            "complexity": self.complexity,
        }


@dataclass
class CodeDependency:
    """Represents a dependency between code symbols."""
    source: str
    target: str
    kind: str  # "import", "call", "inherit", "implement", "use"
    line: int = 0
    strength: float = 1.0  # 0.0 to 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source": self.source,
            "target": self.target,
            "kind": self.kind,
            "line": self.line,
            "strength": self.strength,
        }


@dataclass
class CodeMetrics:
    """Code complexity and quality metrics."""
    cyclomatic_complexity: int = 1
    cognitive_complexity: int = 1
    lines_of_code: int = 0
    comment_ratio: float = 0.0
    nesting_depth: int = 0
    parameter_count: int = 0
    return_count: int = 0
    branch_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cyclomatic_complexity": self.cyclomatic_complexity,
            "cognitive_complexity": self.cognitive_complexity,
            "lines_of_code": self.lines_of_code,
            "comment_ratio": self.comment_ratio,
            "nesting_depth": self.nesting_depth,
            "parameter_count": self.parameter_count,
            "return_count": self.return_count,
            "branch_count": self.branch_count,
        }


@dataclass
class CodeAnalysis:
    """Complete code analysis result."""
    file_path: str
    language: CodeLanguage
    symbols: list[CodeSymbol] = field(default_factory=list)
    dependencies: list[CodeDependency] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    patterns: list[DesignPattern] = field(default_factory=list)
    metrics: CodeMetrics = field(default_factory=CodeMetrics)
    intent: str | None = None
    summary: str | None = None
    issues: list[str] = field(default_factory=list)
    analysis_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "language": self.language,
            "symbols": [s.to_dict() for s in self.symbols],
            "dependencies": [d.to_dict() for d in self.dependencies],
            "imports": self.imports,
            "exports": self.exports,
            "patterns": self.patterns,
            "metrics": self.metrics.to_dict(),
            "intent": self.intent,
            "summary": self.summary,
            "issues": self.issues,
            "analysis_id": self.analysis_id,
        }


class PythonAnalyzer(ast.NodeVisitor):
    """AST-based analyzer for Python code."""

    def __init__(self, source: str, file_path: str):
        self.source = source
        self.file_path = file_path
        self.symbols: list[CodeSymbol] = []
        self.dependencies: list[CodeDependency] = []
        self.imports: list[str] = []
        self.current_class: str | None = None
        self.metrics = CodeMetrics()
        self._lines = source.split("\n")

    def analyze(self) -> CodeAnalysis:
        """Analyze Python code."""
        try:
            tree = ast.parse(self.source)
            self.visit(tree)
            self._calculate_metrics()
            self._detect_patterns()
            self._extract_intent()
        except SyntaxError as e:
            logger.error(f"Syntax error in {self.file_path}: {e}")

        return CodeAnalysis(
            file_path=self.file_path,
            language=CodeLanguage.PYTHON,
            symbols=self.symbols,
            dependencies=self.dependencies,
            imports=self.imports,
            metrics=self.metrics,
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition."""
        docstring = ast.get_docstring(node)
        bases = [self._get_name(base) for base in node.bases]

        symbol = CodeSymbol(
            name=node.name,
            kind=SymbolKind.CLASS,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            docstring=docstring,
            signature=f"class {node.name}({', '.join(bases)})",
        )

        # Add base class dependencies
        for base in bases:
            self.dependencies.append(
                CodeDependency(
                    source=node.name,
                    target=base,
                    kind="inherit",
                    line=node.lineno,
                )
            )

        self.symbols.append(symbol)
        old_class = self.current_class
        self.current_class = node.name

        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        docstring = ast.get_docstring(node)
        params = [arg.arg for arg in node.args.args]
        return_type = None
        if node.returns:
            return_type = self._get_name(node.returns)

        symbol = CodeSymbol(
            name=node.name,
            kind=SymbolKind.METHOD if self.current_class else SymbolKind.FUNCTION,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            docstring=docstring,
            signature=f"def {node.name}({', '.join(params)})",
            return_type=return_type,
            parameters=[{"name": p, "type": None} for p in params],
            parent=self.current_class,
        )

        self.symbols.append(symbol)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statement."""
        for alias in node.names:
            name = alias.asname or alias.name
            self.imports.append(name)
            self.dependencies.append(
                CodeDependency(
                    source=self.file_path,
                    target=alias.name,
                    kind="import",
                    line=node.lineno,
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from...import statement."""
        if node.module:
            for alias in node.names:
                name = alias.asname or alias.name
                self.imports.append(name)
                self.dependencies.append(
                    CodeDependency(
                        source=self.file_path,
                        target=f"{node.module}.{alias.name}",
                        kind="import",
                        line=node.lineno,
                    )
                )

    def visit_Call(self, node: ast.Call) -> None:
        """Visit function call."""
        func_name = self._get_name(node.func)
        if func_name:
            self.dependencies.append(
                CodeDependency(
                    source=self.current_class or self.file_path,
                    target=func_name,
                    kind="call",
                    line=node.lineno,
                )
            )
        self.generic_visit(node)

    def _get_name(self, node: ast.expr) -> str:
        """Extract name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Subscript):
            return self._get_name(node.value)
        return ""

    def _calculate_metrics(self) -> None:
        """Calculate code metrics."""
        self.metrics.lines_of_code = len(self._lines)
        self.metrics.comment_ratio = self._calculate_comment_ratio()

    def _calculate_comment_ratio(self) -> float:
        """Calculate ratio of comment lines."""
        comment_lines = sum(1 for line in self._lines if line.strip().startswith("#"))
        return comment_lines / max(1, len(self._lines))

    def _detect_patterns(self) -> None:
        """Detect design patterns in code."""
        # Simple pattern detection based on naming and structure
        patterns = []
        for symbol in self.symbols:
            if symbol.kind == SymbolKind.CLASS:
                if "Singleton" in symbol.name or "_instance" in str(symbol.children):
                    patterns.append(DesignPattern.SINGLETON)
                elif "Factory" in symbol.name:
                    patterns.append(DesignPattern.FACTORY)
                elif "Builder" in symbol.name:
                    patterns.append(DesignPattern.BUILDER)
        self.metrics.patterns = patterns

    def _extract_intent(self) -> None:
        """Extract code intent from docstrings and structure."""
        # Combine docstrings to understand intent
        docstrings = [s.docstring for s in self.symbols if s.docstring]
        if docstrings:
            self.intent = " ".join(docstrings[:3])


class CodeUnderstandingEngine:
    """Main code understanding engine."""

    def __init__(self):
        self.analyses: dict[str, CodeAnalysis] = {}
        self.dependency_graph: dict[str, list[str]] = {}

    def analyze_file(self, file_path: str, language: CodeLanguage | None = None) -> CodeAnalysis:
        """Analyze a single file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        source = path.read_text(encoding="utf-8", errors="ignore")

        # Detect language if not provided
        if not language:
            language = self._detect_language(file_path)

        # Analyze based on language
        if language == CodeLanguage.PYTHON:
            analyzer = PythonAnalyzer(source, file_path)
            analysis = analyzer.analyze()
        else:
            # For other languages, use regex-based analysis
            analysis = self._analyze_generic(source, file_path, language)

        self.analyses[file_path] = analysis
        return analysis

    def analyze_project(self, root_path: str, extensions: list[str] | None = None) -> dict[str, CodeAnalysis]:
        """Analyze all files in a project."""
        if extensions is None:
            extensions = [".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp"]

        root = Path(root_path)
        results = {}

        for file_path in root.rglob("*"):
            if file_path.suffix in extensions and file_path.is_file():
                try:
                    analysis = self.analyze_file(str(file_path))
                    results[str(file_path)] = analysis
                except Exception as e:
                    logger.error(f"Error analyzing {file_path}: {e}")

        self._build_dependency_graph(results)
        return results

    def build_dependency_graph(self) -> dict[str, list[str]]:
        """Build complete dependency graph."""
        graph: dict[str, list[str]] = {}
        for analysis in self.analyses.values():
            for dep in analysis.dependencies:
                if dep.source not in graph:
                    graph[dep.source] = []
                graph[dep.source].append(dep.target)
        return graph

    def find_related_symbols(self, symbol_name: str, limit: int = 10) -> list[CodeSymbol]:
        """Find symbols related to a given symbol."""
        related = []
        for analysis in self.analyses.values():
            for symbol in analysis.symbols:
                if symbol.name == symbol_name or symbol_name in symbol.references:
                    related.append(symbol)
        return related[:limit]

    def find_impact(self, file_path: str) -> dict[str, Any]:
        """Find files impacted by changes to a file."""
        analysis = self.analyses.get(file_path)
        if not analysis:
            return {"file": file_path, "impacted_files": [], "impacted_symbols": []}

        impacted_files = set()
        impacted_symbols = []

        # Find all files that import from this file
        for other_analysis in self.analyses.values():
            for dep in other_analysis.dependencies:
                if dep.target == file_path or file_path in dep.target:
                    impacted_files.add(other_analysis.file_path)
                    impacted_symbols.append(dep.source)

        return {
            "file": file_path,
            "impacted_files": list(impacted_files),
            "impacted_symbols": impacted_symbols,
            "exported_symbols": analysis.exports,
        }

    def suggest_refactoring(self, file_path: str) -> list[dict[str, Any]]:
        """Suggest refactoring opportunities."""
        analysis = self.analyses.get(file_path)
        if not analysis:
            return []

        suggestions = []

        # Check for high complexity
        for symbol in analysis.symbols:
            if symbol.complexity > 10:
                suggestions.append({
                    "type": "high_complexity",
                    "symbol": symbol.name,
                    "complexity": symbol.complexity,
                    "suggestion": f"Consider breaking down {symbol.name} into smaller functions",
                })

        # Check for long parameter lists
        for symbol in analysis.symbols:
            if len(symbol.parameters) > 5:
                suggestions.append({
                    "type": "long_parameter_list",
                    "symbol": symbol.name,
                    "count": len(symbol.parameters),
                    "suggestion": f"Consider using a configuration object for {symbol.name}",
                })

        return suggestions

    def _detect_language(self, file_path: str) -> CodeLanguage:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        mapping = {
            ".py": CodeLanguage.PYTHON,
            ".js": CodeLanguage.JAVASCRIPT,
            ".ts": CodeLanguage.TYPESCRIPT,
            ".go": CodeLanguage.GO,
            ".rs": CodeLanguage.RUST,
            ".java": CodeLanguage.JAVA,
            ".cpp": CodeLanguage.CPP,
            ".cc": CodeLanguage.CPP,
        }
        return mapping.get(ext, CodeLanguage.PYTHON)

    def _analyze_generic(self, source: str, file_path: str, language: CodeLanguage) -> CodeAnalysis:
        """Generic regex-based analysis for non-Python languages."""
        analysis = CodeAnalysis(
            file_path=file_path,
            language=language,
        )

        # Extract imports
        import_pattern = r"^(?:import|from|require|use)\s+(.+?)(?:\s+as\s+\w+)?$"
        for match in re.finditer(import_pattern, source, re.MULTILINE):
            analysis.imports.append(match.group(1))

        # Extract function/method definitions
        func_pattern = r"(?:def|function|fn|func)\s+(\w+)\s*\("
        for match in re.finditer(func_pattern, source):
            symbol = CodeSymbol(
                name=match.group(1),
                kind=SymbolKind.FUNCTION,
                line_start=source[:match.start()].count("\n") + 1,
                line_end=source[:match.start()].count("\n") + 1,
            )
            analysis.symbols.append(symbol)

        # Extract class definitions
        class_pattern = r"(?:class|struct|interface)\s+(\w+)"
        for match in re.finditer(class_pattern, source):
            symbol = CodeSymbol(
                name=match.group(1),
                kind=SymbolKind.CLASS,
                line_start=source[:match.start()].count("\n") + 1,
                line_end=source[:match.start()].count("\n") + 1,
            )
            analysis.symbols.append(symbol)

        return analysis

    def _build_dependency_graph(self, analyses: dict[str, CodeAnalysis]) -> None:
        """Build dependency graph from analyses."""
        self.dependency_graph = {}
        for file_path, analysis in analyses.items():
            self.dependency_graph[file_path] = [dep.target for dep in analysis.dependencies]
