"""Security policies and validation for code execution sandboxes."""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Optional, Set

from backend.app.core.approvals import ApprovalSubjectType
from backend.app.core.contracts import RiskLevel as CoreRiskLevel

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk level for code execution."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityViolation:
    """Represents a security violation."""

    risk_level: RiskLevel
    pattern: str
    message: str
    line_number: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass(frozen=True)
class EnterpriseSafetySubjectPolicy:
    """Normalized sandbox/admin policy for a mutating execution subject."""

    subject_type: ApprovalSubjectType
    default_sandbox_profile: str
    minimum_risk_level: CoreRiskLevel
    owner_gate_required: bool
    audit_required: bool
    admin_policy_required: bool
    allowed_decision_types: tuple[str, ...]
    blocked_without_approval: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["subject_type"] = self.subject_type.value
        payload["minimum_risk_level"] = self.minimum_risk_level.value
        return payload


APPROVAL_DECISION_TYPES = (
    "approve_once",
    "approve_for_run",
    "approve_for_session",
    "deny",
    "abort",
)

ENTERPRISE_SAFETY_POLICIES: tuple[EnterpriseSafetySubjectPolicy, ...] = (
    EnterpriseSafetySubjectPolicy(
        subject_type=ApprovalSubjectType.COMMAND,
        default_sandbox_profile="command_locked",
        minimum_risk_level=CoreRiskLevel.HIGH,
        owner_gate_required=True,
        audit_required=True,
        admin_policy_required=True,
        allowed_decision_types=APPROVAL_DECISION_TYPES,
        blocked_without_approval=True,
    ),
    EnterpriseSafetySubjectPolicy(
        subject_type=ApprovalSubjectType.FILE_CHANGE,
        default_sandbox_profile="filesystem_guarded",
        minimum_risk_level=CoreRiskLevel.HIGH,
        owner_gate_required=True,
        audit_required=True,
        admin_policy_required=True,
        allowed_decision_types=APPROVAL_DECISION_TYPES,
        blocked_without_approval=True,
    ),
    EnterpriseSafetySubjectPolicy(
        subject_type=ApprovalSubjectType.NETWORK_REQUEST,
        default_sandbox_profile="network_default_deny",
        minimum_risk_level=CoreRiskLevel.HIGH,
        owner_gate_required=True,
        audit_required=True,
        admin_policy_required=True,
        allowed_decision_types=APPROVAL_DECISION_TYPES,
        blocked_without_approval=True,
    ),
    EnterpriseSafetySubjectPolicy(
        subject_type=ApprovalSubjectType.MCP_ELICITATION,
        default_sandbox_profile="mcp_owner_gated",
        minimum_risk_level=CoreRiskLevel.MEDIUM,
        owner_gate_required=True,
        audit_required=True,
        admin_policy_required=True,
        allowed_decision_types=APPROVAL_DECISION_TYPES,
        blocked_without_approval=True,
    ),
    EnterpriseSafetySubjectPolicy(
        subject_type=ApprovalSubjectType.BROWSER_ACTION,
        default_sandbox_profile="browser_guarded",
        minimum_risk_level=CoreRiskLevel.MEDIUM,
        owner_gate_required=True,
        audit_required=True,
        admin_policy_required=True,
        allowed_decision_types=APPROVAL_DECISION_TYPES,
        blocked_without_approval=True,
    ),
    EnterpriseSafetySubjectPolicy(
        subject_type=ApprovalSubjectType.CHANNEL_SEND,
        default_sandbox_profile="channel_send_guarded",
        minimum_risk_level=CoreRiskLevel.MEDIUM,
        owner_gate_required=True,
        audit_required=True,
        admin_policy_required=True,
        allowed_decision_types=APPROVAL_DECISION_TYPES,
        blocked_without_approval=True,
    ),
    EnterpriseSafetySubjectPolicy(
        subject_type=ApprovalSubjectType.ISSUE_TO_PR_EXECUTE,
        default_sandbox_profile="github_mutation_guarded",
        minimum_risk_level=CoreRiskLevel.HIGH,
        owner_gate_required=True,
        audit_required=True,
        admin_policy_required=True,
        allowed_decision_types=APPROVAL_DECISION_TYPES,
        blocked_without_approval=True,
    ),
)


def get_enterprise_safety_policy(
    subject_type: ApprovalSubjectType,
) -> EnterpriseSafetySubjectPolicy | None:
    for policy in ENTERPRISE_SAFETY_POLICIES:
        if policy.subject_type == subject_type:
            return policy
    return None


def list_enterprise_safety_policies() -> list[EnterpriseSafetySubjectPolicy]:
    return list(ENTERPRISE_SAFETY_POLICIES)


class PythonSecurityValidator:
    """Validates Python code for security violations."""

    # Critical patterns that must be blocked
    # Critical patterns that must be blocked (真正的逃逸/执行/IO/反序列化威胁)。
    # 不含 isinstance/hasattr/type/super/callable 等常规安全内置，
    # 也不含 __init__/__str__/__eq__ 等正常类会定义的 dunder（否则误杀任意类定义）。
    CRITICAL_PATTERNS = {
        r"__import__\s*\(",
        r"\beval\s*\(",
        r"\bexec\s*\(",
        r"\bcompile\s*\(",
        r"\bglobals\s*\(",
        r"\blocals\s*\(",
        r"\bvars\s*\(",
        r"\bgetattr\s*\(",
        r"\bsetattr\s*\(",
        r"\bdelattr\s*\(",
        # 真正用于沙箱逃逸的内省链
        r"__subclasses__",
        r"__bases__",
        r"__mro__",
        r"__globals__",
        r"__builtins__",
        r"__code__",
        r"__closure__",
        r"__getattribute__",
        r"__reduce__",
        r"__reduce_ex__",
        r"__subclasshook__",
    }

    # High-risk patterns that should be flagged
    HIGH_RISK_PATTERNS = {
        r"import\s+os\b",
        r"import\s+sys\b",
        r"import\s+subprocess\b",
        r"import\s+socket\b",
        r"import\s+threading\b",
        r"import\s+multiprocessing\b",
        r"import\s+asyncio\b",
        r"import\s+ctypes\b",
        r"import\s+pickle\b",
        r"import\s+shelve\b",
        r"import\s+marshal\b",
        r"import\s+imp\b",
        r"import\s+importlib\b",
        r"from\s+os\s+import",
        r"from\s+sys\s+import",
        r"from\s+subprocess\s+import",
        r"from\s+socket\s+import",
        r"from\s+threading\s+import",
        r"from\s+multiprocessing\s+import",
        r"from\s+asyncio\s+import",
        r"from\s+ctypes\s+import",
        r"from\s+pickle\s+import",
        r"open\s*\(",
        r"file\s*\(",
        r"input\s*\(",
        r"raw_input\s*\(",
    }

    # Medium-risk patterns
    MEDIUM_RISK_PATTERNS = {
        r"lambda\s+",
        r"map\s*\(",
        r"filter\s*\(",
        r"reduce\s*\(",
        r"sorted\s*\(",
        r"reversed\s*\(",
        r"enumerate\s*\(",
        r"zip\s*\(",
        r"all\s*\(",
        r"any\s*\(",
        r"sum\s*\(",
        r"min\s*\(",
        r"max\s*\(",
        r"pow\s*\(",
        r"divmod\s*\(",
        r"abs\s*\(",
        r"round\s*\(",
        r"format\s*\(",
        r"repr\s*\(",
        r"ascii\s*\(",
        r"ord\s*\(",
        r"chr\s*\(",
        r"bin\s*\(",
        r"oct\s*\(",
        r"hex\s*\(",
        r"id\s*\(",
        r"hash\s*\(",
        r"len\s*\(",
        r"list\s*\(",
        r"dict\s*\(",
        r"set\s*\(",
        r"tuple\s*\(",
        r"frozenset\s*\(",
        r"range\s*\(",
        r"slice\s*\(",
        r"memoryview\s*\(",
        r"bytearray\s*\(",
        r"bytes\s*\(",
        r"str\s*\(",
        r"bool\s*\(",
        r"int\s*\(",
        r"float\s*\(",
        r"complex\s*\(",
    }

    def __init__(self):
        """Initialize validator."""
        self.critical_patterns = [re.compile(p, re.IGNORECASE) for p in self.CRITICAL_PATTERNS]
        self.high_risk_patterns = [re.compile(p, re.IGNORECASE) for p in self.HIGH_RISK_PATTERNS]
        self.medium_risk_patterns = [re.compile(p, re.IGNORECASE) for p in self.MEDIUM_RISK_PATTERNS]

    def validate(self, code: str) -> list[SecurityViolation]:
        """Validate Python code for security violations.

        Args:
            code: Python code to validate

        Returns:
            List of security violations
        """
        violations: list[SecurityViolation] = []
        lines = code.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Skip comments and empty lines
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Check critical patterns
            for pattern in self.critical_patterns:
                if pattern.search(line):
                    violations.append(
                        SecurityViolation(
                            risk_level=RiskLevel.CRITICAL,
                            pattern=pattern.pattern,
                            message=f"Critical security violation: {pattern.pattern}",
                            line_number=line_num,
                            suggestion="This pattern is not allowed in sandboxed code",
                        )
                    )

            # Check high-risk patterns
            for pattern in self.high_risk_patterns:
                if pattern.search(line):
                    violations.append(
                        SecurityViolation(
                            risk_level=RiskLevel.HIGH,
                            pattern=pattern.pattern,
                            message=f"High-risk pattern detected: {pattern.pattern}",
                            line_number=line_num,
                            suggestion="Consider using safer alternatives",
                        )
                    )

            # Check medium-risk patterns
            for pattern in self.medium_risk_patterns:
                if pattern.search(line):
                    violations.append(
                        SecurityViolation(
                            risk_level=RiskLevel.MEDIUM,
                            pattern=pattern.pattern,
                            message=f"Medium-risk pattern detected: {pattern.pattern}",
                            line_number=line_num,
                        )
                    )

        return violations


class ASTSecurityValidator:
    """AST-based security validator for Python code.

    Provides a second layer of defense against obfuscated/mixed patterns
    that regex-based validation might miss. Analyzes the abstract syntax tree
    to detect dangerous operations at the semantic level.
    """

    # Safe modules that can be imported
    SAFE_MODULES = {
        "math",
        "json",
        "datetime",
        "re",
        "collections",
        "itertools",
        "functools",
        "typing",
        "decimal",
        "statistics",
        "random",
        "string",
        "textwrap",
        "operator",
        "copy",
        "pprint",
        "enum",
        "dataclasses",
        "abc",
        "numbers",
        "cmath",
        "fractions",
        "heapq",
        "bisect",
        "array",
        "struct",
        "codecs",
        "unicodedata",
        "stringprep",
        "readline",
        "rlcompleter",
    }

    # Dangerous built-in functions that should be blocked
    # 仅保留真正能导致逃逸/任意执行/IO 的内置；isinstance/hasattr/super/type 等
    # 是常规安全用法，不应判 CRITICAL（否则正常沙箱代码被误杀）。
    DANGEROUS_BUILTINS = {
        "__import__",
        "eval",
        "exec",
        "compile",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
        "open",
        "file",
        "input",
        "raw_input",
    }

    # Dangerous attributes that indicate escape attempts
    DANGEROUS_ATTRIBUTES = {
        "__globals__",
        "__builtins__",
        "__subclasses__",
        "__bases__",
        "__mro__",
        "__class__",
        "__dict__",
        "__code__",
        "__loader__",
        "__spec__",
        "__cached__",
        "__file__",
        "__name__",
        "__package__",
        "__doc__",
        "__annotations__",
        "__getattribute__",
        "__setattr__",
        "__delattr__",
        "__getattr__",
        "__setitem__",
        "__delitem__",
        "__getitem__",
        "__call__",
        "__new__",
        "__init__",
        "__del__",
    }

    # Dangerous module prefixes
    DANGEROUS_MODULES = {
        "os",
        "sys",
        "subprocess",
        "socket",
        "threading",
        "multiprocessing",
        "asyncio",
        "ctypes",
        "pickle",
        "shelve",
        "marshal",
        "imp",
        "importlib",
    }

    def __init__(self, allowed_imports: Optional[Set[str]] = None):
        """Initialize AST validator.

        Args:
            allowed_imports: Additional modules to allow importing (extends SAFE_MODULES)
        """
        self.safe_modules = self.SAFE_MODULES.copy()
        if allowed_imports:
            self.safe_modules.update(allowed_imports)

    def validate(self, code: str) -> list[SecurityViolation]:
        """Validate Python code using AST analysis.

        Args:
            code: Python code to validate

        Returns:
            List of security violations
        """
        violations: list[SecurityViolation] = []

        # Try to parse the code into an AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            # Syntax errors are treated as security violations
            violations.append(
                SecurityViolation(
                    risk_level=RiskLevel.CRITICAL,
                    pattern="SyntaxError",
                    message=f"Code contains syntax error: {e.msg}",
                    line_number=e.lineno,
                    suggestion="Fix the syntax error before execution",
                )
            )
            return violations

        # Walk the AST and check for violations
        for node in ast.walk(tree):
            violations.extend(self._check_node(node))

        return violations

    def _check_node(self, node: ast.AST) -> list[SecurityViolation]:
        """Check a single AST node for violations.

        Args:
            node: AST node to check

        Returns:
            List of violations found in this node
        """
        violations: list[SecurityViolation] = []

        # Check Import nodes
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split(".")[0]
                if module_name in self.DANGEROUS_MODULES:
                    violations.append(
                        SecurityViolation(
                            risk_level=RiskLevel.CRITICAL,
                            pattern=f"import {module_name}",
                            message=f"Dangerous module import: {module_name}",
                            line_number=node.lineno,
                            suggestion=f"Module '{module_name}' is not allowed",
                        )
                    )
                elif module_name not in self.safe_modules:
                    violations.append(
                        SecurityViolation(
                            risk_level=RiskLevel.HIGH,
                            pattern=f"import {module_name}",
                            message=f"Unapproved module import: {module_name}",
                            line_number=node.lineno,
                            suggestion=f"Module '{module_name}' is not in the allowed list",
                        )
                    )

        # Check ImportFrom nodes
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module.split(".")[0] if node.module else ""
            if module_name in self.DANGEROUS_MODULES:
                violations.append(
                    SecurityViolation(
                        risk_level=RiskLevel.CRITICAL,
                        pattern=f"from {module_name} import",
                        message=f"Dangerous module import: {module_name}",
                        line_number=node.lineno,
                        suggestion=f"Module '{module_name}' is not allowed",
                    )
                )
            elif module_name and module_name not in self.safe_modules:
                violations.append(
                    SecurityViolation(
                        risk_level=RiskLevel.HIGH,
                        pattern=f"from {module_name} import",
                        message=f"Unapproved module import: {module_name}",
                        line_number=node.lineno,
                        suggestion=f"Module '{module_name}' is not in the allowed list",
                    )
                )

        # Check Call nodes for dangerous functions
        elif isinstance(node, ast.Call):
            func_name = self._get_call_name(node.func)
            if func_name in self.DANGEROUS_BUILTINS:
                violations.append(
                    SecurityViolation(
                        risk_level=RiskLevel.CRITICAL,
                        pattern=f"{func_name}()",
                        message=f"Dangerous function call: {func_name}",
                        line_number=node.lineno,
                        suggestion=f"Function '{func_name}' is not allowed in sandboxed code",
                    )
                )

        # Check Attribute nodes for dangerous attributes
        elif isinstance(node, ast.Attribute):
            if node.attr in self.DANGEROUS_ATTRIBUTES:
                violations.append(
                    SecurityViolation(
                        risk_level=RiskLevel.CRITICAL,
                        pattern=f".{node.attr}",
                        message=f"Dangerous attribute access: {node.attr}",
                        line_number=node.lineno,
                        suggestion=f"Attribute '{node.attr}' is not allowed in sandboxed code",
                    )
                )

        return violations

    def _get_call_name(self, func: ast.expr) -> Optional[str]:
        """Extract the function name from a Call node's func attribute.

        Args:
            func: The func attribute of an ast.Call node

        Returns:
            The function name if it's a simple Name or Attribute, None otherwise
        """
        if isinstance(func, ast.Name):
            return func.id
        elif isinstance(func, ast.Attribute):
            # For chained attributes like os.system, return the final attribute
            return func.attr
        return None


class JavaScriptSecurityValidator:
    """Validates JavaScript code for security violations."""

    # Critical patterns
    CRITICAL_PATTERNS = {
        r"require\s*\(\s*['\"]child_process['\"]",
        r"require\s*\(\s*['\"]fs['\"]",
        r"require\s*\(\s*['\"]net['\"]",
        r"require\s*\(\s*['\"]dgram['\"]",
        r"require\s*\(\s*['\"]http['\"]",
        r"require\s*\(\s*['\"]https['\"]",
        r"require\s*\(\s*['\"]cluster['\"]",
        r"require\s*\(\s*['\"]worker_threads['\"]",
        r"require\s*\(\s*['\"]vm['\"]",
        r"eval\s*\(",
        r"Function\s*\(",
        r"process\.exit",
        r"process\.kill",
        r"process\.env",
        r"global\.",
        r"__dirname",
        r"__filename",
        r"require\.cache",
        r"module\.exports",
        r"exports\.",
        r"setTimeout\s*\(",
        r"setInterval\s*\(",
        r"setImmediate\s*\(",
    }

    # High-risk patterns
    HIGH_RISK_PATTERNS = {
        r"require\s*\(",
        r"import\s+",
        r"fetch\s*\(",
        r"XMLHttpRequest",
        r"WebSocket",
        r"\.then\s*\(",
        r"async\s+",
        r"await\s+",
        r"Promise\s*\(",
        r"new\s+Promise",
        r"\.catch\s*\(",
        r"\.finally\s*\(",
    }

    def __init__(self):
        """Initialize validator."""
        self.critical_patterns = [re.compile(p, re.IGNORECASE) for p in self.CRITICAL_PATTERNS]
        self.high_risk_patterns = [re.compile(p, re.IGNORECASE) for p in self.HIGH_RISK_PATTERNS]

    def validate(self, code: str) -> list[SecurityViolation]:
        """Validate JavaScript code for security violations.

        Args:
            code: JavaScript code to validate

        Returns:
            List of security violations
        """
        violations: list[SecurityViolation] = []
        lines = code.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Skip comments and empty lines
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                continue

            # Check critical patterns
            for pattern in self.critical_patterns:
                if pattern.search(line):
                    violations.append(
                        SecurityViolation(
                            risk_level=RiskLevel.CRITICAL,
                            pattern=pattern.pattern,
                            message=f"Critical security violation: {pattern.pattern}",
                            line_number=line_num,
                            suggestion="This pattern is not allowed in sandboxed code",
                        )
                    )

            # Check high-risk patterns
            for pattern in self.high_risk_patterns:
                if pattern.search(line):
                    violations.append(
                        SecurityViolation(
                            risk_level=RiskLevel.HIGH,
                            pattern=pattern.pattern,
                            message=f"High-risk pattern detected: {pattern.pattern}",
                            line_number=line_num,
                            suggestion="Consider using safer alternatives",
                        )
                    )

        return violations


def validate_python_code(code: str, allowed_imports: Optional[Set[str]] = None) -> tuple[bool, list[SecurityViolation]]:
    """Validate Python code and return violations.

    Uses a two-layer defense: regex-based patterns (first pass) and AST analysis (second pass).

    Args:
        code: Python code to validate
        allowed_imports: Additional modules to allow importing

    Returns:
        Tuple of (is_safe, violations)
    """
    violations: list[SecurityViolation] = []

    # First pass: regex-based validation
    regex_validator = PythonSecurityValidator()
    violations.extend(regex_validator.validate(code))

    # Second pass: AST-based validation
    ast_validator = ASTSecurityValidator(allowed_imports=allowed_imports)
    violations.extend(ast_validator.validate(code))

    # Code is safe if there are no critical violations
    is_safe = not any(v.risk_level == RiskLevel.CRITICAL for v in violations)

    return is_safe, violations


def validate_javascript_code(code: str) -> tuple[bool, list[SecurityViolation]]:
    """Validate JavaScript code and return violations.

    Args:
        code: JavaScript code to validate

    Returns:
        Tuple of (is_safe, violations)
    """
    validator = JavaScriptSecurityValidator()
    violations = validator.validate(code)

    # Code is safe if there are no critical violations
    is_safe = not any(v.risk_level == RiskLevel.CRITICAL for v in violations)

    return is_safe, violations
