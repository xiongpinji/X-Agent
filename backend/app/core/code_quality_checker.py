"""
Code quality checker for X-Agent.

This module provides comprehensive code quality analysis including syntax checking,
style validation, complexity analysis, security scanning, and improvement suggestions.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re
import ast
import logging

logger = logging.getLogger(__name__)


class IssueSeverity(Enum):
    """Issue severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Issue:
    """Represents a code quality issue."""
    line: int
    column: int
    message: str
    severity: IssueSeverity
    code: str
    suggestion: Optional[str] = None


@dataclass
class ComplexityReport:
    """Code complexity analysis report."""
    cyclomatic_complexity: float
    cognitive_complexity: float
    lines_of_code: int
    functions_count: int
    classes_count: int
    average_function_length: float
    max_nesting_depth: int
    issues: List[str]


@dataclass
class SecurityIssue:
    """Represents a security issue."""
    line: int
    issue_type: str
    description: str
    severity: IssueSeverity
    recommendation: str


@dataclass
class Suggestion:
    """Code improvement suggestion."""
    category: str
    description: str
    priority: str
    example: Optional[str] = None


class CodeQualityChecker:
    """Comprehensive code quality checker."""

    def __init__(self):
        """Initialize the code quality checker."""
        self.python_issues = []
        self.security_patterns = self._init_security_patterns()

    def _init_security_patterns(self) -> Dict[str, Tuple[str, str]]:
        """Initialize security vulnerability patterns."""
        return {
            "sql_injection": (
                r"(execute|query|sql)\s*\(\s*['\"].*\{.*\}.*['\"]",
                "Potential SQL injection vulnerability"
            ),
            "hardcoded_secret": (
                r"(password|secret|api_key|token)\s*=\s*['\"].*['\"]",
                "Hardcoded secret detected"
            ),
            "unsafe_pickle": (
                r"pickle\.(load|loads)",
                "Unsafe pickle usage - can execute arbitrary code"
            ),
            "eval_usage": (
                r"\b(eval|exec)\s*\(",
                "Dangerous eval/exec usage"
            ),
            "insecure_random": (
                r"random\.(randint|choice|shuffle)",
                "Insecure random for cryptographic purposes"
            ),
        }

    def check_syntax(self, code: str, language: str) -> List[Issue]:
        """
        Check code for syntax errors.

        Args:
            code: Source code to check
            language: Programming language (python, javascript, typescript, java)

        Returns:
            List of syntax issues found
        """
        issues = []

        if language.lower() == "python":
            issues.extend(self._check_python_syntax(code))
        elif language.lower() in ["javascript", "typescript"]:
            issues.extend(self._check_javascript_syntax(code))
        elif language.lower() == "java":
            issues.extend(self._check_java_syntax(code))

        return issues

    def _check_python_syntax(self, code: str) -> List[Issue]:
        """Check Python syntax."""
        issues = []
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(Issue(
                line=e.lineno or 0,
                column=e.offset or 0,
                message=f"Syntax error: {e.msg}",
                severity=IssueSeverity.CRITICAL,
                code="E001",
                suggestion=f"Check line {e.lineno}: {e.text}"
            ))
        except Exception as e:
            issues.append(Issue(
                line=0,
                column=0,
                message=f"Parse error: {str(e)}",
                severity=IssueSeverity.HIGH,
                code="E002"
            ))
        return issues

    def _check_javascript_syntax(self, code: str) -> List[Issue]:
        """Check JavaScript/TypeScript syntax."""
        issues = []
        # Basic regex-based checks
        if re.search(r'var\s+\w+\s*=', code):
            issues.append(Issue(
                line=1,
                column=0,
                message="Use 'const' or 'let' instead of 'var'",
                severity=IssueSeverity.MEDIUM,
                code="JS001",
                suggestion="Replace 'var' with 'const' or 'let'"
            ))
        return issues

    def _check_java_syntax(self, code: str) -> List[Issue]:
        """Check Java syntax."""
        issues = []
        # Basic regex-based checks
        if not re.search(r'public\s+class\s+\w+', code):
            issues.append(Issue(
                line=1,
                column=0,
                message="Missing public class declaration",
                severity=IssueSeverity.HIGH,
                code="JAVA001"
            ))
        return issues

    def check_style(self, code: str, language: str) -> List[Issue]:
        """
        Check code style and formatting.

        Args:
            code: Source code to check
            language: Programming language

        Returns:
            List of style issues found
        """
        issues = []

        if language.lower() == "python":
            issues.extend(self._check_python_style(code))
        elif language.lower() in ["javascript", "typescript"]:
            issues.extend(self._check_javascript_style(code))

        return issues

    def _check_python_style(self, code: str) -> List[Issue]:
        """Check Python code style (PEP 8)."""
        issues = []
        lines = code.split('\n')

        for i, line in enumerate(lines, 1):
            # Check line length
            if len(line) > 100:
                issues.append(Issue(
                    line=i,
                    column=100,
                    message=f"Line too long ({len(line)} > 100 characters)",
                    severity=IssueSeverity.LOW,
                    code="E501"
                ))

            # Check trailing whitespace
            if line != line.rstrip():
                issues.append(Issue(
                    line=i,
                    column=len(line.rstrip()),
                    message="Trailing whitespace",
                    severity=IssueSeverity.LOW,
                    code="W291"
                ))

            # Check multiple statements on one line
            if ';' in line and not line.strip().startswith('#'):
                issues.append(Issue(
                    line=i,
                    column=line.index(';'),
                    message="Multiple statements on one line",
                    severity=IssueSeverity.MEDIUM,
                    code="E702"
                ))

            # Check operator spacing (e.g., x=1 should be x = 1)
            if re.search(r'\w=[^=]', line) and not line.strip().startswith('#'):
                # Avoid false positives: keyword args, default params, comparisons
                if not re.search(r'(def|lambda|if|elif|while|for|return|assert|raise|except|import|from)\s', line):
                    issues.append(Issue(
                        line=i,
                        column=line.index('='),
                        message="Missing spaces around operator '='",
                        severity=IssueSeverity.MEDIUM,
                        code="E225"
                    ))

        return issues

    def _check_javascript_style(self, code: str) -> List[Issue]:
        """Check JavaScript/TypeScript code style."""
        issues = []
        lines = code.split('\n')

        for i, line in enumerate(lines, 1):
            # Check line length
            if len(line) > 100:
                issues.append(Issue(
                    line=i,
                    column=100,
                    message=f"Line too long ({len(line)} > 100 characters)",
                    severity=IssueSeverity.LOW,
                    code="JS501"
                ))

            # Check for console.log in production code
            if 'console.log' in line and not line.strip().startswith('//'):
                issues.append(Issue(
                    line=i,
                    column=line.index('console.log'),
                    message="Remove console.log from production code",
                    severity=IssueSeverity.MEDIUM,
                    code="JS001"
                ))

        return issues

    def check_complexity(self, code: str, language: str) -> ComplexityReport:
        """
        Analyze code complexity.

        Args:
            code: Source code to analyze
            language: Programming language

        Returns:
            Complexity analysis report
        """
        if language.lower() == "python":
            return self._analyze_python_complexity(code)
        else:
            return self._analyze_generic_complexity(code)

    def _analyze_python_complexity(self, code: str) -> ComplexityReport:
        """Analyze Python code complexity."""
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError):
            return ComplexityReport(
                cyclomatic_complexity=0,
                cognitive_complexity=0,
                lines_of_code=len(code.split('\n')),
                functions_count=0,
                classes_count=0,
                average_function_length=0,
                max_nesting_depth=0,
                issues=["Failed to parse code"]
            )

        functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

        cyclomatic = self._calculate_cyclomatic_complexity(tree)
        cognitive = self._calculate_cognitive_complexity(tree)
        max_depth = self._calculate_max_nesting_depth(tree)

        avg_func_length = (
            sum(node.end_lineno - node.lineno for node in functions) / len(functions)
            if functions else 0
        )

        issues = []
        if cyclomatic > 10:
            issues.append(f"High cyclomatic complexity: {cyclomatic}")
        if cognitive > 15:
            issues.append(f"High cognitive complexity: {cognitive}")
        if max_depth > 4:
            issues.append(f"Deep nesting detected: {max_depth} levels")
        if avg_func_length > 50:
            issues.append(f"Average function length too long: {avg_func_length:.0f} lines")

        return ComplexityReport(
            cyclomatic_complexity=cyclomatic,
            cognitive_complexity=cognitive,
            lines_of_code=len(code.split('\n')),
            functions_count=len(functions),
            classes_count=len(classes),
            average_function_length=avg_func_length,
            max_nesting_depth=max_depth,
            issues=issues
        )

    def _analyze_generic_complexity(self, code: str) -> ComplexityReport:
        """Analyze generic code complexity using regex."""
        lines = code.split('\n')

        # Count control flow statements
        control_flow = sum(
            len(re.findall(r'\b(if|else|elif|for|while|switch|case)\b', line))
            for line in lines
        )

        return ComplexityReport(
            cyclomatic_complexity=control_flow + 1,
            cognitive_complexity=control_flow,
            lines_of_code=len(lines),
            functions_count=len(re.findall(r'\b(def|function|func)\b', code)),
            classes_count=len(re.findall(r'\b(class|interface)\b', code)),
            average_function_length=0,
            max_nesting_depth=0,
            issues=[]
        )

    def _calculate_cyclomatic_complexity(self, tree: ast.AST) -> float:
        """Calculate cyclomatic complexity."""
        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
        return complexity

    def _calculate_cognitive_complexity(self, tree: ast.AST) -> float:
        """Calculate cognitive complexity."""
        complexity = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For)):
                complexity += 1
            elif isinstance(node, ast.ExceptHandler):
                complexity += 1
        return complexity

    def _calculate_max_nesting_depth(self, tree: ast.AST, depth: int = 0) -> int:
        """Calculate maximum nesting depth."""
        max_depth = depth
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.With, ast.Try)):
                child_depth = self._calculate_max_nesting_depth(node, depth + 1)
                max_depth = max(max_depth, child_depth)
            else:
                child_depth = self._calculate_max_nesting_depth(node, depth)
                max_depth = max(max_depth, child_depth)
        return max_depth

    def check_security(self, code: str, language: str) -> List[SecurityIssue]:
        """
        Check code for security vulnerabilities.

        Args:
            code: Source code to check
            language: Programming language

        Returns:
            List of security issues found
        """
        issues = []

        if language.lower() == "python":
            issues.extend(self._check_python_security(code))
        elif language.lower() in ["javascript", "typescript"]:
            issues.extend(self._check_javascript_security(code))

        return issues

    def _check_python_security(self, code: str) -> List[SecurityIssue]:
        """Check Python code for security issues."""
        issues = []
        lines = code.split('\n')

        for i, line in enumerate(lines, 1):
            for pattern_name, (pattern, description) in self.security_patterns.items():
                if re.search(pattern, line):
                    issues.append(SecurityIssue(
                        line=i,
                        issue_type=pattern_name,
                        description=description,
                        severity=IssueSeverity.HIGH,
                        recommendation=f"Review and fix {pattern_name} vulnerability"
                    ))

        return issues

    def _check_javascript_security(self, code: str) -> List[SecurityIssue]:
        """Check JavaScript/TypeScript code for security issues."""
        issues = []
        lines = code.split('\n')

        for i, line in enumerate(lines, 1):
            # Check for eval
            if re.search(r'\beval\s*\(', line):
                issues.append(SecurityIssue(
                    line=i,
                    issue_type="eval_usage",
                    description="Dangerous eval() usage",
                    severity=IssueSeverity.CRITICAL,
                    recommendation="Avoid eval() - use safer alternatives"
                ))

            # Check for innerHTML
            if re.search(r'\.innerHTML\s*=', line):
                issues.append(SecurityIssue(
                    line=i,
                    issue_type="xss_vulnerability",
                    description="Potential XSS vulnerability with innerHTML",
                    severity=IssueSeverity.HIGH,
                    recommendation="Use textContent or sanitize HTML"
                ))

        return issues

    def suggest_improvements(self, code: str, language: str) -> List[Suggestion]:
        """
        Suggest code improvements.

        Args:
            code: Source code to analyze
            language: Programming language

        Returns:
            List of improvement suggestions
        """
        suggestions = []

        # Check for missing type hints (Python)
        if language.lower() == "python":
            if not re.search(r'->\s*\w+', code):
                suggestions.append(Suggestion(
                    category="Type Safety",
                    description="Add return type hints to functions",
                    priority="high",
                    example="def function() -> str:\n    return 'result'"
                ))

            if not re.search(r':\s*\w+\s*=', code):
                suggestions.append(Suggestion(
                    category="Type Safety",
                    description="Add type hints to variables",
                    priority="high",
                    example="name: str = 'value'"
                ))

        # Check for missing docstrings
        if not re.search(r'""".*"""', code, re.DOTALL):
            suggestions.append(Suggestion(
                category="Documentation",
                description="Add docstrings to functions and classes",
                priority="high"
            ))

        # Check for error handling
        if language.lower() == "python":
            if 'try:' not in code:
                suggestions.append(Suggestion(
                    category="Error Handling",
                    description="Add try-except blocks for error handling",
                    priority="medium"
                ))

        # Check for logging
        if 'logger' not in code and 'logging' not in code:
            suggestions.append(Suggestion(
                category="Observability",
                description="Add logging for debugging and monitoring",
                priority="medium"
            ))

        return suggestions

    def generate_quality_score(
        self,
        code: str,
        language: str
    ) -> float:
        """
        Generate overall code quality score (0-100).

        Args:
            code: Source code to analyze
            language: Programming language

        Returns:
            Quality score from 0 to 100
        """
        score = 100.0

        # Syntax errors (critical)
        syntax_issues = self.check_syntax(code, language)
        score -= len([i for i in syntax_issues if i.severity == IssueSeverity.CRITICAL]) * 20

        # Style issues
        style_issues = self.check_style(code, language)
        score -= len([i for i in style_issues if i.severity == IssueSeverity.HIGH]) * 5
        score -= len([i for i in style_issues if i.severity == IssueSeverity.MEDIUM]) * 2

        # Complexity issues
        complexity = self.check_complexity(code, language)
        if complexity.cyclomatic_complexity > 10:
            score -= 10
        if complexity.max_nesting_depth > 4:
            score -= 5

        # Security issues
        security_issues = self.check_security(code, language)
        score -= len([i for i in security_issues if i.severity == IssueSeverity.CRITICAL]) * 15
        score -= len([i for i in security_issues if i.severity == IssueSeverity.HIGH]) * 10

        return max(0, min(100, score))
