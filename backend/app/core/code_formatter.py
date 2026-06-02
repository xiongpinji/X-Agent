"""
Code formatter for X-Agent.

This module provides code formatting and optimization capabilities for multiple
programming languages including Python, JavaScript/TypeScript, and Java.
"""

from typing import List, Dict, Any, Optional
import re
import logging

logger = logging.getLogger(__name__)


class CodeFormatter:
    """Code formatter and optimizer."""

    def __init__(self):
        """Initialize the code formatter."""
        self.max_line_length = 100
        self.indent_size = 4

    def format_python(self, code: str, style: str = "pep8") -> str:
        """
        Format Python code according to PEP 8 or other styles.

        Args:
            code: Python source code
            style: Formatting style (pep8, google, airbnb)

        Returns:
            Formatted Python code
        """
        try:
            # Try to use black if available
            import black
            try:
                return black.format_str(code, mode=black.FileMode())
            except Exception as e:
                logger.warning(f"Black formatting failed: {e}, using fallback")
        except ImportError:
            logger.debug("Black not available, using fallback formatter")

        return self._format_python_fallback(code)

    def _format_python_fallback(self, code: str) -> str:
        """Fallback Python formatter when black is not available."""
        lines = code.split('\n')
        formatted_lines = []

        for line in lines:
            # Remove trailing whitespace
            line = line.rstrip()

            # Fix spacing around operators
            line = re.sub(r'\s*=\s*', ' = ', line)
            line = re.sub(r'\s*\+\s*', ' + ', line)
            line = re.sub(r'\s*-\s*', ' - ', line)
            line = re.sub(r'\s*\*\s*', ' * ', line)
            line = re.sub(r'\s*/\s*', ' / ', line)

            # Fix spacing after commas
            line = re.sub(r',([^ ])', r', \1', line)

            # Fix spacing around colons (but not in slices)
            line = re.sub(r':\s*(?=[^:])', ': ', line)

            formatted_lines.append(line)

        return '\n'.join(formatted_lines)

    def format_javascript(self, code: str, style: str = "airbnb") -> str:
        """
        Format JavaScript/TypeScript code.

        Args:
            code: JavaScript/TypeScript source code
            style: Formatting style (airbnb, google, standard)

        Returns:
            Formatted code
        """
        try:
            # Try to use prettier if available
            import subprocess
            result = subprocess.run(
                ['prettier', '--parser', 'babel'],
                input=code,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout
        except Exception as e:
            logger.debug(f"Prettier formatting failed: {e}, using fallback")

        return self._format_javascript_fallback(code)

    def _format_javascript_fallback(self, code: str) -> str:
        """Fallback JavaScript formatter."""
        lines = code.split('\n')
        formatted_lines = []
        indent_level = 0

        for line in lines:
            stripped = line.strip()

            # Decrease indent for closing braces
            if stripped.startswith('}') or stripped.startswith(']'):
                indent_level = max(0, indent_level - 1)

            # Add indentation
            if stripped:
                formatted_line = '  ' * indent_level + stripped
            else:
                formatted_line = ''

            formatted_lines.append(formatted_line)

            # Increase indent for opening braces
            if stripped.endswith('{') or stripped.endswith('['):
                indent_level += 1

        return '\n'.join(formatted_lines)

    def format_java(self, code: str) -> str:
        """
        Format Java code.

        Args:
            code: Java source code

        Returns:
            Formatted code
        """
        return self._format_java_fallback(code)

    def _format_java_fallback(self, code: str) -> str:
        """Fallback Java formatter."""
        lines = code.split('\n')
        formatted_lines = []
        indent_level = 0

        for line in lines:
            stripped = line.strip()

            # Decrease indent for closing braces
            if stripped.startswith('}'):
                indent_level = max(0, indent_level - 1)

            # Add indentation
            if stripped:
                formatted_line = '    ' * indent_level + stripped
            else:
                formatted_line = ''

            formatted_lines.append(formatted_line)

            # Increase indent for opening braces
            if stripped.endswith('{'):
                indent_level += 1

        return '\n'.join(formatted_lines)

    def optimize_imports(self, code: str, language: str) -> str:
        """
        Optimize import statements.

        Args:
            code: Source code
            language: Programming language

        Returns:
            Code with optimized imports
        """
        if language.lower() == "python":
            return self._optimize_python_imports(code)
        elif language.lower() in ["javascript", "typescript"]:
            return self._optimize_javascript_imports(code)
        elif language.lower() == "java":
            return self._optimize_java_imports(code)

        return code

    def _optimize_python_imports(self, code: str) -> str:
        """Optimize Python imports."""
        lines = code.split('\n')
        import_lines = []
        other_lines = []
        in_imports = True

        for line in lines:
            if in_imports and (line.startswith('import ') or line.startswith('from ')):
                import_lines.append(line)
            else:
                if line.strip() and not line.startswith('#'):
                    in_imports = False
                other_lines.append(line)

        # Sort imports
        import_lines.sort()

        # Group imports
        stdlib_imports = []
        third_party_imports = []
        local_imports = []

        for imp in import_lines:
            if imp.startswith('from .') or imp.startswith('import .'):
                local_imports.append(imp)
            elif any(stdlib in imp for stdlib in ['os', 'sys', 'json', 'logging', 'typing', 'asyncio']):
                stdlib_imports.append(imp)
            else:
                third_party_imports.append(imp)

        # Combine with blank lines between groups
        result_imports = []
        if stdlib_imports:
            result_imports.extend(stdlib_imports)
        if third_party_imports:
            if result_imports:
                result_imports.append('')
            result_imports.extend(third_party_imports)
        if local_imports:
            if result_imports:
                result_imports.append('')
            result_imports.extend(local_imports)

        return '\n'.join(result_imports + other_lines)

    def _optimize_javascript_imports(self, code: str) -> str:
        """Optimize JavaScript/TypeScript imports."""
        lines = code.split('\n')
        import_lines = []
        other_lines = []
        in_imports = True

        for line in lines:
            if in_imports and (line.startswith('import ') or line.startswith('export ')):
                import_lines.append(line)
            else:
                if line.strip() and not line.startswith('//'):
                    in_imports = False
                other_lines.append(line)

        # Sort imports
        import_lines.sort()

        return '\n'.join(import_lines + other_lines)

    def _optimize_java_imports(self, code: str) -> str:
        """Optimize Java imports."""
        lines = code.split('\n')
        import_lines = []
        other_lines = []
        in_imports = True

        for line in lines:
            if in_imports and line.startswith('import '):
                import_lines.append(line)
            else:
                if line.strip() and not line.startswith('//'):
                    in_imports = False
                other_lines.append(line)

        # Sort imports
        import_lines.sort()

        return '\n'.join(import_lines + other_lines)

    def remove_unused_code(self, code: str, language: str) -> str:
        """
        Remove unused code (basic implementation).

        Args:
            code: Source code
            language: Programming language

        Returns:
            Code with unused code removed
        """
        if language.lower() == "python":
            return self._remove_unused_python(code)
        elif language.lower() in ["javascript", "typescript"]:
            return self._remove_unused_javascript(code)

        return code

    def _remove_unused_python(self, code: str) -> str:
        """Remove unused Python code."""
        lines = code.split('\n')
        result_lines = []

        # Track variable usage
        defined_vars = set()
        used_vars = set()

        # First pass: collect definitions and usages
        for line in lines:
            # Skip comments and empty lines
            if line.strip().startswith('#') or not line.strip():
                continue

            # Find variable definitions
            if re.match(r'\s*\w+\s*=', line):
                var_name = re.match(r'\s*(\w+)\s*=', line).group(1)
                defined_vars.add(var_name)

            # Find variable usages
            for var in defined_vars:
                if re.search(rf'\b{var}\b', line) and not re.match(rf'\s*{var}\s*=', line):
                    used_vars.add(var)

        # Second pass: filter out unused definitions
        for line in lines:
            # Keep non-definition lines
            if not re.match(r'\s*\w+\s*=', line):
                result_lines.append(line)
            else:
                var_name = re.match(r'\s*(\w+)\s*=', line).group(1)
                if var_name in used_vars or var_name.startswith('_'):
                    result_lines.append(line)

        return '\n'.join(result_lines)

    def _remove_unused_javascript(self, code: str) -> str:
        """Remove unused JavaScript code."""
        lines = code.split('\n')
        result_lines = []

        # Track variable usage
        defined_vars = set()
        used_vars = set()

        # First pass: collect definitions and usages
        for line in lines:
            # Skip comments and empty lines
            if line.strip().startswith('//') or not line.strip():
                continue

            # Find variable definitions
            if re.match(r'\s*(const|let|var)\s+\w+', line):
                var_name = re.match(r'\s*(const|let|var)\s+(\w+)', line).group(2)
                defined_vars.add(var_name)

            # Find variable usages
            for var in defined_vars:
                if re.search(rf'\b{var}\b', line) and not re.match(rf'\s*(const|let|var)\s+{var}', line):
                    used_vars.add(var)

        # Second pass: filter out unused definitions
        for line in lines:
            # Keep non-definition lines
            if not re.match(r'\s*(const|let|var)\s+\w+', line):
                result_lines.append(line)
            else:
                var_name = re.match(r'\s*(const|let|var)\s+(\w+)', line).group(2)
                if var_name in used_vars or var_name.startswith('_'):
                    result_lines.append(line)

        return '\n'.join(result_lines)

    def add_type_hints(self, code: str, language: str) -> str:
        """
        Add type hints to code (basic implementation).

        Args:
            code: Source code
            language: Programming language

        Returns:
            Code with type hints added
        """
        if language.lower() == "python":
            return self._add_python_type_hints(code)
        elif language.lower() == "typescript":
            return self._add_typescript_type_hints(code)

        return code

    def _add_python_type_hints(self, code: str) -> str:
        """Add Python type hints."""
        lines = code.split('\n')
        result_lines = []

        for line in lines:
            # Add type hints to function definitions
            if re.match(r'\s*def\s+\w+\s*\(', line):
                # Add basic type hints if missing
                if '->' not in line:
                    # Find the closing parenthesis
                    match = re.match(r'(\s*def\s+\w+\s*\([^)]*\))', line)
                    if match:
                        func_def = match.group(1)
                        rest = line[len(func_def):]
                        line = func_def + ' -> Any:' if ':' in rest else func_def + ' -> Any'

            result_lines.append(line)

        return '\n'.join(result_lines)

    def _add_typescript_type_hints(self, code: str) -> str:
        """Add TypeScript type hints."""
        lines = code.split('\n')
        result_lines = []

        for line in lines:
            # Add type hints to function definitions
            if re.match(r'\s*(async\s+)?function\s+\w+\s*\(', line):
                # Add basic type hints if missing
                if ': ' not in line or '->' not in line:
                    # This is a simplified implementation
                    pass

            result_lines.append(line)

        return '\n'.join(result_lines)

    def add_docstrings(self, code: str, language: str) -> str:
        """
        Add docstrings to code (basic implementation).

        Args:
            code: Source code
            language: Programming language

        Returns:
            Code with docstrings added
        """
        if language.lower() == "python":
            return self._add_python_docstrings(code)
        elif language.lower() in ["javascript", "typescript"]:
            return self._add_javascript_docstrings(code)

        return code

    def _add_python_docstrings(self, code: str) -> str:
        """Add Python docstrings."""
        lines = code.split('\n')
        result_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check for function or class definition
            if re.match(r'\s*(def|class)\s+\w+', line):
                result_lines.append(line)
                i += 1

                # Check if next line is already a docstring
                if i < len(lines) and '"""' not in lines[i]:
                    # Add docstring
                    indent = len(line) - len(line.lstrip()) + 4
                    result_lines.append(' ' * indent + '"""Function/class description."""')

            else:
                result_lines.append(line)
                i += 1

        return '\n'.join(result_lines)

    def _add_javascript_docstrings(self, code: str) -> str:
        """Add JavaScript JSDoc comments."""
        lines = code.split('\n')
        result_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check for function definition
            if re.match(r'\s*(async\s+)?(function|const|let)\s+\w+', line):
                # Check if previous line is already a comment
                if not (result_lines and result_lines[-1].strip().startswith('/**')):
                    indent = len(line) - len(line.lstrip())
                    result_lines.append(' ' * indent + '/**')
                    result_lines.append(' ' * indent + ' * Function description.')
                    result_lines.append(' ' * indent + ' */')

                result_lines.append(line)
                i += 1

            else:
                result_lines.append(line)
                i += 1

        return '\n'.join(result_lines)

    def format_code(self, code: str, language: str, **options) -> str:
        """
        Format code with all optimizations.

        Args:
            code: Source code
            language: Programming language
            **options: Additional formatting options

        Returns:
            Formatted and optimized code
        """
        # Format code
        if language.lower() == "python":
            code = self.format_python(code)
        elif language.lower() in ["javascript", "typescript"]:
            code = self.format_javascript(code)
        elif language.lower() == "java":
            code = self.format_java(code)

        # Optimize imports
        code = self.optimize_imports(code, language)

        # Add type hints if requested
        if options.get('add_type_hints', True):
            code = self.add_type_hints(code, language)

        # Add docstrings if requested
        if options.get('add_docstrings', True):
            code = self.add_docstrings(code, language)

        return code
