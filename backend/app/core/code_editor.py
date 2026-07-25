"""
Advanced code editing capabilities for X-Agent.
Provides precise code manipulation at AST level with formatting and refactoring support.
"""

from __future__ import annotations

import ast
import difflib
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import black
import isort


class EditType(StrEnum):
    """Types of code edits supported."""
    INSERT = "insert"
    REPLACE = "replace"
    DELETE = "delete"
    REFACTOR = "refactor"
    FORMAT = "format"


@dataclass
class CodeEdit:
    """Represents a single code edit operation."""
    type: EditType
    file_path: str
    start_line: int
    end_line: int
    old_content: str
    new_content: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "type": self.type.value,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "old_content": self.old_content,
            "new_content": self.new_content,
            "description": self.description,
        }


@dataclass
class EditResult:
    """Result of applying code edits."""
    success: bool
    file_path: str
    edits_applied: int
    errors: list[str] = field(default_factory=list)
    diff: str = ""
    formatted_content: str | None = None


class ASTAnalyzer:
    """Analyzes Python code using AST for precise editing."""

    @staticmethod
    def find_function(code: str, function_name: str) -> tuple[int, int] | None:
        """Find function definition line range."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    return node.lineno - 1, node.end_lineno or node.lineno
            return None
        except SyntaxError:
            return None

    @staticmethod
    def find_class(code: str, class_name: str) -> tuple[int, int] | None:
        """Find class definition line range."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    return node.lineno - 1, node.end_lineno or node.lineno
            return None
        except SyntaxError:
            return None

    @staticmethod
    def find_imports(code: str) -> list[tuple[int, int]]:
        """Find all import statement line ranges."""
        try:
            tree = ast.parse(code)
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imports.append((node.lineno - 1, node.end_lineno or node.lineno))
            return sorted(imports)
        except SyntaxError:
            return []

    @staticmethod
    def validate_syntax(code: str) -> tuple[bool, str | None]:
        """Validate Python syntax."""
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, str(e)


class CodeFormatter:
    """Formats and normalizes code."""

    @staticmethod
    async def format_python(code: str, line_length: int = 88) -> str:
        """Format Python code using Black."""
        try:
            return black.format_str(code, line_length=line_length)
        except Exception:
            return code

    @staticmethod
    async def sort_imports(code: str) -> str:
        """Sort imports using isort."""
        try:
            return isort.code(code)
        except Exception:
            return code

    @staticmethod
    async def format_and_sort(code: str) -> str:
        """Format and sort imports."""
        code = await CodeFormatter.sort_imports(code)
        code = await CodeFormatter.format_python(code)
        return code


class CodeRefactorer:
    """Suggests and applies code refactoring."""

    @staticmethod
    def suggest_rename(code: str, old_name: str, new_name: str) -> str:
        """Suggest variable/function rename."""
        # Simple regex-based rename (AST-based would be more precise)
        pattern = r'\b' + re.escape(old_name) + r'\b'
        return re.sub(pattern, new_name, code)

    @staticmethod
    def extract_method(code: str, start_line: int, end_line: int,
                      method_name: str) -> tuple[str, str]:
        """Extract lines into a new method."""
        lines = code.split('\n')
        extracted_lines = lines[start_line:end_line]
        '\n'.join(extracted_lines)

        # Create method signature
        method_def = f"def {method_name}():\n"
        for line in extracted_lines:
            method_def += f"    {line}\n"

        # Replace original with method call
        new_lines = [*lines[:start_line], f"    {method_name}()", *lines[end_line:]]
        new_code = '\n'.join(new_lines)

        return new_code, method_def

    @staticmethod
    def remove_dead_code(code: str) -> str:
        """Remove unreachable code patterns."""
        lines = code.split('\n')
        result = []
        skip_until_dedent = False

        for i, line in enumerate(lines):
            if skip_until_dedent:
                if line and not line[0].isspace():
                    skip_until_dedent = False
                else:
                    continue

            # Skip obvious dead code patterns
            if 'return' in line and i + 1 < len(lines):
                next_line = lines[i + 1]
                if next_line.strip() and next_line[0].isspace():
                    skip_until_dedent = True

            result.append(line)

        return '\n'.join(result)


class CodeCompleter:
    """Provides intelligent code completion suggestions."""

    @staticmethod
    def suggest_completions(code: str, line: int, column: int) -> list[str]:
        """Suggest code completions at given position."""
        lines = code.split('\n')
        if line >= len(lines):
            return []

        current_line = lines[line][:column]

        # Extract the partial identifier
        match = re.search(r'(\w+)$', current_line)
        if not match:
            return []

        partial = match.group(1)

        # Collect available names from code
        try:
            tree = ast.parse(code)
            names = set()

            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    names.add(node.id)
                elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    names.add(node.name)

            # Filter by partial match
            completions = [n for n in names if n.startswith(partial)]
            return sorted(completions)[:10]
        except SyntaxError:
            return []


class MultiFileEditor:
    """Manages edits across multiple files."""

    def __init__(self):
        self.edits: dict[str, list[CodeEdit]] = {}
        self.file_contents: dict[str, str] = {}

    async def load_file(self, file_path: str) -> bool:
        """Load file content."""
        try:
            path = Path(file_path)
            if path.exists():
                self.file_contents[file_path] = path.read_text()
                return True
            return False
        except Exception:
            return False

    async def add_edit(self, edit: CodeEdit) -> bool:
        """Add an edit operation."""
        if edit.file_path not in self.edits:
            self.edits[edit.file_path] = []

        # Validate edit
        if edit.file_path not in self.file_contents:
            await self.load_file(edit.file_path)

        if edit.file_path not in self.file_contents:
            return False

        self.edits[edit.file_path].append(edit)
        return True

    async def apply_edits(self, file_path: str) -> EditResult:
        """Apply all edits to a file."""
        if file_path not in self.edits:
            return EditResult(success=True, file_path=file_path, edits_applied=0)

        if file_path not in self.file_contents:
            await self.load_file(file_path)

        content = self.file_contents.get(file_path, "")
        lines = content.split('\n')

        # Sort edits by line number (reverse to avoid offset issues)
        sorted_edits = sorted(self.edits[file_path],
                            key=lambda e: e.start_line, reverse=True)

        errors = []
        applied = 0

        for edit in sorted_edits:
            try:
                if edit.type == EditType.REPLACE:
                    lines[edit.start_line:edit.end_line] = edit.new_content.split('\n')
                    applied += 1
                elif edit.type == EditType.INSERT:
                    lines.insert(edit.start_line, edit.new_content)
                    applied += 1
                elif edit.type == EditType.DELETE:
                    del lines[edit.start_line:edit.end_line]
                    applied += 1
            except Exception as e:
                errors.append(f"Edit failed at line {edit.start_line}: {e!s}")

        new_content = '\n'.join(lines)

        # Validate syntax
        valid, error = ASTAnalyzer.validate_syntax(new_content)
        if not valid:
            errors.append(f"Syntax error: {error}")
            return EditResult(success=False, file_path=file_path,
                            edits_applied=0, errors=errors)

        # Generate diff
        diff = '\n'.join(difflib.unified_diff(
            content.split('\n'),
            new_content.split('\n'),
            fromfile=file_path,
            tofile=file_path,
            lineterm=''
        ))

        # Format code
        formatted = await CodeFormatter.format_and_sort(new_content)

        return EditResult(
            success=True,
            file_path=file_path,
            edits_applied=applied,
            errors=errors,
            diff=diff,
            formatted_content=formatted
        )

    async def apply_all_edits(self) -> dict[str, EditResult]:
        """Apply all edits to all files."""
        results = {}
        for file_path in self.edits:
            results[file_path] = await self.apply_edits(file_path)
        return results

    async def save_changes(self, file_path: str) -> bool:
        """Save changes to disk."""
        try:
            result = await self.apply_edits(file_path)
            if result.success and result.formatted_content:
                Path(file_path).write_text(result.formatted_content)
                return True
            return False
        except Exception:
            return False


class CodeEditor:
    """Main code editing interface."""

    def __init__(self):
        self.multi_editor = MultiFileEditor()
        self.analyzer = ASTAnalyzer()
        self.formatter = CodeFormatter()
        self.refactorer = CodeRefactorer()
        self.completer = CodeCompleter()

    async def edit_file(self, file_path: str, edits: list[CodeEdit]) -> EditResult:
        """Apply multiple edits to a file."""
        await self.multi_editor.load_file(file_path)

        for edit in edits:
            await self.multi_editor.add_edit(edit)

        return await self.multi_editor.apply_edits(file_path)

    async def format_file(self, file_path: str) -> str:
        """Format a file."""
        await self.multi_editor.load_file(file_path)
        content = self.multi_editor.file_contents.get(file_path, "")
        return await self.formatter.format_and_sort(content)

    async def refactor_rename(self, file_path: str, old_name: str,
                             new_name: str) -> EditResult:
        """Refactor: rename variable/function."""
        await self.multi_editor.load_file(file_path)
        content = self.multi_editor.file_contents.get(file_path, "")
        new_content = self.refactorer.suggest_rename(content, old_name, new_name)

        edit = CodeEdit(
            type=EditType.REFACTOR,
            file_path=file_path,
            start_line=0,
            end_line=len(content.split('\n')),
            old_content=content,
            new_content=new_content,
            description=f"Rename {old_name} to {new_name}"
        )

        await self.multi_editor.add_edit(edit)
        return await self.multi_editor.apply_edits(file_path)

    def get_completions(self, file_path: str, line: int, column: int) -> list[str]:
        """Get code completions."""
        content = self.multi_editor.file_contents.get(file_path, "")
        return self.completer.suggest_completions(content, line, column)
