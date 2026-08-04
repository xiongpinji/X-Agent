"""
Intelligent code completion and suggestion engine with context-aware recommendations.

This module provides advanced code completion capabilities including:
- Smart code completion with multiple options
- Context-aware suggestion ranking
- Code snippet completion
- Import suggestion
- API documentation integration
- Learning from project patterns
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class CompletionKind(StrEnum):
    """Types of code completions."""
    KEYWORD = "keyword"
    VARIABLE = "variable"
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    SNIPPET = "snippet"
    IMPORT = "import"
    PROPERTY = "property"
    METHOD = "method"
    CONSTANT = "constant"


class CompletionTrigger(StrEnum):
    """Triggers for code completion."""
    DOT = "dot"  # obj.
    PARENTHESIS = "parenthesis"  # func(
    BRACKET = "bracket"  # arr[
    SPACE = "space"  # after keyword
    IMPORT = "import"  # import statement
    MANUAL = "manual"  # user requested


@dataclass
class CompletionItem:
    """A single completion suggestion."""
    label: str
    kind: CompletionKind
    detail: str | None = None
    documentation: str | None = None
    insert_text: str | None = None
    sort_text: str | None = None
    filter_text: str | None = None
    score: float = 0.5  # 0.0 to 1.0
    range: dict[str, int] | None = None  # start, end positions
    additional_edits: list[dict[str, Any]] = field(default_factory=list)
    is_snippet: bool = False
    snippet_params: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "label": self.label,
            "kind": self.kind,
            "detail": self.detail,
            "documentation": self.documentation,
            "insert_text": self.insert_text,
            "sort_text": self.sort_text,
            "filter_text": self.filter_text,
            "score": self.score,
            "range": self.range,
            "additional_edits": self.additional_edits,
            "is_snippet": self.is_snippet,
            "snippet_params": self.snippet_params,
        }


@dataclass
class CompletionContext:
    """Context for code completion."""
    file_path: str
    language: str
    line: int
    column: int
    line_text: str
    file_content: str
    trigger: CompletionTrigger = CompletionTrigger.MANUAL
    prefix: str = ""
    available_symbols: list[str] = field(default_factory=list)
    imported_modules: list[str] = field(default_factory=list)
    current_scope: str | None = None
    parent_scope: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "language": self.language,
            "line": self.line,
            "column": self.column,
            "line_text": self.line_text,
            "trigger": self.trigger,
            "prefix": self.prefix,
            "available_symbols": self.available_symbols,
            "imported_modules": self.imported_modules,
            "current_scope": self.current_scope,
            "parent_scope": self.parent_scope,
        }


@dataclass
class CompletionResult:
    """Result of code completion."""
    items: list[CompletionItem] = field(default_factory=list)
    is_incomplete: bool = False
    context: CompletionContext | None = None
    completion_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "items": [item.to_dict() for item in self.items],
            "is_incomplete": self.is_incomplete,
            "context": self.context.to_dict() if self.context else None,
            "completion_id": self.completion_id,
        }


class SymbolProvider:
    """Provides available symbols for completion."""

    def __init__(self):
        self.builtin_keywords = self._load_builtin_keywords()
        self.common_imports = self._load_common_imports()

    def _load_builtin_keywords(self) -> dict[str, list[str]]:
        """Load built-in keywords for languages."""
        return {
            "python": [
                "if", "else", "elif", "for", "while", "def", "class", "return",
                "import", "from", "as", "try", "except", "finally", "with",
                "lambda", "yield", "async", "await", "pass", "break", "continue",
                "raise", "assert", "del", "global", "nonlocal", "True", "False", "None"
            ],
            "javascript": [
                "if", "else", "for", "while", "do", "switch", "case", "default",
                "function", "return", "const", "let", "var", "class", "extends",
                "import", "export", "from", "as", "try", "catch", "finally",
                "throw", "async", "await", "new", "this", "super", "static",
                "true", "false", "null", "undefined"
            ],
            "typescript": [
                "if", "else", "for", "while", "do", "switch", "case", "default",
                "function", "return", "const", "let", "var", "class", "extends",
                "import", "export", "from", "as", "try", "catch", "finally",
                "throw", "async", "await", "new", "this", "super", "static",
                "interface", "type", "enum", "namespace", "module", "declare",
                "true", "false", "null", "undefined"
            ],
        }

    def _load_common_imports(self) -> dict[str, list[str]]:
        """Load common imports for languages."""
        return {
            "python": [
                "os", "sys", "json", "re", "datetime", "time", "random",
                "collections", "itertools", "functools", "operator",
                "pathlib", "tempfile", "shutil", "subprocess",
                "requests", "urllib", "http", "socket",
                "logging", "warnings", "traceback",
                "unittest", "pytest", "mock",
                "numpy", "pandas", "matplotlib", "scipy",
                "flask", "django", "fastapi", "starlette",
                "sqlalchemy", "psycopg2", "pymongo",
            ],
            "javascript": [
                "fs", "path", "os", "util", "events", "stream",
                "http", "https", "url", "querystring",
                "crypto", "zlib", "buffer",
                "express", "react", "vue", "angular",
                "lodash", "moment", "axios", "fetch",
                "jest", "mocha", "chai", "sinon",
                "webpack", "babel", "typescript",
            ],
        }

    def get_keywords(self, language: str) -> list[str]:
        """Get keywords for language."""
        return self.builtin_keywords.get(language, [])

    def get_common_imports(self, language: str) -> list[str]:
        """Get common imports for language."""
        return self.common_imports.get(language, [])


class CompletionScorer:
    """Score and rank completion items."""

    @staticmethod
    def score_items(items: list[CompletionItem], context: CompletionContext) -> list[CompletionItem]:
        """Score and sort completion items."""
        for item in items:
            score = CompletionScorer._calculate_score(item, context)
            item.score = score

        # Sort by score descending
        items.sort(key=lambda x: (-x.score, x.label))
        return items

    @staticmethod
    def _calculate_score(item: CompletionItem, context: CompletionContext) -> float:
        """Calculate score for completion item."""
        score = 0.5

        # Prefix matching
        if context.prefix and item.label.lower().startswith(context.prefix.lower()):
            score += 0.3

        # Exact match
        if item.label.lower() == context.prefix.lower():
            score += 0.2

        # Kind preference
        kind_scores = {
            CompletionKind.VARIABLE: 0.1,
            CompletionKind.FUNCTION: 0.15,
            CompletionKind.CLASS: 0.15,
            CompletionKind.KEYWORD: 0.05,
            CompletionKind.SNIPPET: 0.2,
            CompletionKind.IMPORT: 0.1,
        }
        score += kind_scores.get(item.kind, 0.0)

        # Scope relevance
        if context.current_scope and item.label in context.available_symbols:
            score += 0.1

        # Frequency bonus (common items)
        if item.label in ["print", "len", "range", "str", "int", "list", "dict"]:
            score += 0.05

        return min(1.0, score)


class SnippetProvider:
    """Provides code snippets for completion."""

    @staticmethod
    def get_snippets(language: str) -> dict[str, CompletionItem]:
        """Get code snippets for language."""
        if language == "python":
            return SnippetProvider._get_python_snippets()
        elif language in ["javascript", "typescript"]:
            return SnippetProvider._get_js_snippets()
        return {}

    @staticmethod
    def _get_python_snippets() -> dict[str, CompletionItem]:
        """Get Python code snippets."""
        return {
            "if": CompletionItem(
                label="if",
                kind=CompletionKind.SNIPPET,
                insert_text="if ${1:condition}:\n    ${2:pass}",
                is_snippet=True,
                snippet_params=["condition", "body"],
                documentation="If statement"
            ),
            "for": CompletionItem(
                label="for",
                kind=CompletionKind.SNIPPET,
                insert_text="for ${1:item} in ${2:iterable}:\n    ${3:pass}",
                is_snippet=True,
                snippet_params=["item", "iterable", "body"],
                documentation="For loop"
            ),
            "def": CompletionItem(
                label="def",
                kind=CompletionKind.SNIPPET,
                insert_text="def ${1:function_name}(${2:args}):\n    \"\"\"${3:docstring}\"\"\"\n    ${4:pass}",
                is_snippet=True,
                snippet_params=["function_name", "args", "docstring", "body"],
                documentation="Function definition"
            ),
            "class": CompletionItem(
                label="class",
                kind=CompletionKind.SNIPPET,
                insert_text="class ${1:ClassName}:\n    \"\"\"${2:docstring}\"\"\"\n\n    def __init__(self${3:, args}):\n        ${4:pass}",
                is_snippet=True,
                snippet_params=["ClassName", "docstring", "args", "body"],
                documentation="Class definition"
            ),
            "try": CompletionItem(
                label="try",
                kind=CompletionKind.SNIPPET,
                insert_text="try:\n    ${1:pass}\nexcept ${2:Exception} as ${3:e}:\n    ${4:pass}",
                is_snippet=True,
                snippet_params=["try_body", "exception", "var", "except_body"],
                documentation="Try-except block"
            ),
        }

    @staticmethod
    def _get_js_snippets() -> dict[str, CompletionItem]:
        """Get JavaScript code snippets."""
        return {
            "if": CompletionItem(
                label="if",
                kind=CompletionKind.SNIPPET,
                insert_text="if (${1:condition}) {\n    ${2:}\n}",
                is_snippet=True,
                snippet_params=["condition", "body"],
                documentation="If statement"
            ),
            "for": CompletionItem(
                label="for",
                kind=CompletionKind.SNIPPET,
                insert_text="for (let ${1:i} = 0; ${1:i} < ${2:length}; ${1:i}++) {\n    ${3:}\n}",
                is_snippet=True,
                snippet_params=["i", "length", "body"],
                documentation="For loop"
            ),
            "function": CompletionItem(
                label="function",
                kind=CompletionKind.SNIPPET,
                insert_text="function ${1:functionName}(${2:args}) {\n    ${3:}\n}",
                is_snippet=True,
                snippet_params=["functionName", "args", "body"],
                documentation="Function definition"
            ),
            "class": CompletionItem(
                label="class",
                kind=CompletionKind.SNIPPET,
                insert_text="class ${1:ClassName} {\n    constructor(${2:args}) {\n        ${3:}\n    }\n}",
                is_snippet=True,
                snippet_params=["ClassName", "args", "body"],
                documentation="Class definition"
            ),
            "try": CompletionItem(
                label="try",
                kind=CompletionKind.SNIPPET,
                insert_text="try {\n    ${1:}\n} catch (${2:error}) {\n    ${3:}\n}",
                is_snippet=True,
                snippet_params=["try_body", "error", "catch_body"],
                documentation="Try-catch block"
            ),
        }


class CodeCompletionEngine:
    """Main code completion engine."""

    def __init__(self):
        self.symbol_provider = SymbolProvider()
        self.completion_scorer = CompletionScorer()
        self.snippet_provider = SnippetProvider()
        self.completion_history: list[CompletionResult] = []

    def complete(self, context: CompletionContext, limit: int = 20) -> CompletionResult:
        """Generate code completions."""
        items = []

        # Get completions based on trigger
        if context.trigger == CompletionTrigger.IMPORT:
            items = self._complete_import(context)
        elif context.trigger == CompletionTrigger.DOT:
            items = self._complete_member(context)
        elif context.trigger == CompletionTrigger.PARENTHESIS:
            items = self._complete_function_args(context)
        else:
            items = self._complete_general(context)

        # Add snippets
        snippets = self.snippet_provider.get_snippets(context.language)
        items.extend(snippets.values())

        # Score and sort
        items = self.completion_scorer.score_items(items, context)

        # Limit results
        items = items[:limit]

        result = CompletionResult(
            items=items,
            context=context,
        )

        self.completion_history.append(result)
        return result

    def _complete_import(self, context: CompletionContext) -> list[CompletionItem]:
        """Complete import statements."""
        items = []
        common_imports = self.symbol_provider.get_common_imports(context.language)

        for imp in common_imports:
            if imp.startswith(context.prefix):
                items.append(CompletionItem(
                    label=imp,
                    kind=CompletionKind.IMPORT,
                    detail=f"Import {imp}",
                    insert_text=imp,
                ))

        return items

    def _complete_member(self, context: CompletionContext) -> list[CompletionItem]:
        """Complete member access (obj.member)."""
        items = []

        # Extract object name from line
        match = re.search(r"(\w+)\.$", context.line_text)
        if match:
            obj_name = match.group(1)

            # Get common methods/properties for object
            common_members = self._get_common_members(obj_name, context.language)
            for member in common_members:
                if member.startswith(context.prefix):
                    items.append(CompletionItem(
                        label=member,
                        kind=CompletionKind.PROPERTY,
                        detail=f"Member of {obj_name}",
                        insert_text=member,
                    ))

        return items

    def _complete_function_args(self, context: CompletionContext) -> list[CompletionItem]:
        """Complete function arguments."""
        items = []

        # Extract function name
        match = re.search(r"(\w+)\($", context.line_text)
        if match:
            func_name = match.group(1)

            # Get function signature
            signature = self._get_function_signature(func_name, context.language)
            if signature:
                items.append(CompletionItem(
                    label=func_name,
                    kind=CompletionKind.FUNCTION,
                    detail=signature,
                    documentation=f"Function: {func_name}",
                ))

        return items

    def _complete_general(self, context: CompletionContext) -> list[CompletionItem]:
        """General code completion."""
        items = []

        # Add keywords
        keywords = self.symbol_provider.get_keywords(context.language)
        for keyword in keywords:
            if keyword.startswith(context.prefix):
                items.append(CompletionItem(
                    label=keyword,
                    kind=CompletionKind.KEYWORD,
                    insert_text=keyword,
                ))

        # Add available symbols
        for symbol in context.available_symbols:
            if symbol.startswith(context.prefix):
                items.append(CompletionItem(
                    label=symbol,
                    kind=CompletionKind.VARIABLE,
                    insert_text=symbol,
                ))

        # Add imported modules
        for module in context.imported_modules:
            if module.startswith(context.prefix):
                items.append(CompletionItem(
                    label=module,
                    kind=CompletionKind.MODULE,
                    insert_text=module,
                ))

        return items

    def _get_common_members(self, obj_name: str, language: str) -> list[str]:
        """Get common members for object."""
        # Common members for built-in types
        members_map = {
            "python": {
                "str": ["upper", "lower", "strip", "split", "join", "replace", "find"],
                "list": ["append", "extend", "insert", "remove", "pop", "clear", "sort"],
                "dict": ["keys", "values", "items", "get", "pop", "clear", "update"],
            },
            "javascript": {
                "string": ["toUpperCase", "toLowerCase", "trim", "split", "replace", "indexOf"],
                "array": ["push", "pop", "shift", "unshift", "slice", "splice", "map", "filter"],
                "object": ["keys", "values", "entries", "assign", "create", "defineProperty"],
            },
        }

        members = members_map.get(language, {}).get(obj_name, [])
        return members

    def _get_function_signature(self, func_name: str, language: str) -> str | None:
        """Get function signature."""
        # Common function signatures
        signatures = {
            "python": {
                "print": "print(*args, sep=' ', end='\\n', file=None, flush=False)",
                "len": "len(object) -> integer",
                "range": "range(stop) or range(start, stop[, step])",
                "str": "str(object='') -> str",
                "int": "int(x=0) -> integer",
                "list": "list(iterable=()) -> list",
                "dict": "dict(**kwargs) -> dict",
            },
            "javascript": {
                "console.log": "console.log(...args)",
                "Array.map": "array.map(callback(element, index, array), thisArg)",
                "Array.filter": "array.filter(callback(element, index, array), thisArg)",
                "Object.keys": "Object.keys(obj) -> array",
                "JSON.stringify": "JSON.stringify(value, replacer, space)",
                "JSON.parse": "JSON.parse(text, reviver)",
            },
        }

        return signatures.get(language, {}).get(func_name)

    def suggest_imports(self, context: CompletionContext, symbols: list[str]) -> list[CompletionItem]:
        """Suggest imports for symbols."""
        items = []

        for symbol in symbols:
            if symbol not in context.imported_modules:
                items.append(CompletionItem(
                    label=f"import {symbol}",
                    kind=CompletionKind.IMPORT,
                    detail=f"Import {symbol}",
                    insert_text=f"import {symbol}",
                ))

        return items

    def suggest_refactoring(self, context: CompletionContext) -> list[CompletionItem]:
        """Suggest refactoring opportunities."""
        items = []

        # Check for long lines
        if len(context.line_text) > 100:
            items.append(CompletionItem(
                label="Break long line",
                kind=CompletionKind.SNIPPET,
                detail="Line is too long, consider breaking it",
                documentation="This line exceeds 100 characters",
            ))

        # Check for duplicate code
        if self._has_duplicate_code(context):
            items.append(CompletionItem(
                label="Extract method",
                kind=CompletionKind.SNIPPET,
                detail="Duplicate code detected, consider extracting to method",
                documentation="This code appears to be duplicated",
            ))

        return items

    def _has_duplicate_code(self, context: CompletionContext) -> bool:
        """Check if code has duplicates."""
        # Simple heuristic - check if similar lines appear multiple times
        lines = context.file_content.split("\n")
        current_line = context.line_text.strip()

        if not current_line:
            return False

        count = sum(1 for line in lines if line.strip() == current_line)
        return count > 1
