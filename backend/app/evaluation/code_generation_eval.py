"""
Code generation evaluation module for X-Agent.

This module provides comprehensive evaluation metrics for generated code including
syntax correctness, functionality, quality, performance, and security assessments.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import re

logger = logging.getLogger(__name__)


class EvaluationMetric(Enum):
    """Code evaluation metrics."""
    SYNTAX_CORRECTNESS = "syntax_correctness"
    FUNCTIONALITY_COMPLETENESS = "functionality_completeness"
    CODE_QUALITY = "code_quality"
    PERFORMANCE = "performance"
    SECURITY = "security"
    MAINTAINABILITY = "maintainability"
    TEST_COVERAGE = "test_coverage"
    DOCUMENTATION = "documentation"


@dataclass
class MetricScore:
    """Score for a single metric."""
    metric: EvaluationMetric
    score: float  # 0-100
    details: str
    issues: List[str]
    recommendations: List[str]


@dataclass
class EvaluationReport:
    """Comprehensive code evaluation report."""
    overall_score: float  # 0-100
    metric_scores: Dict[str, MetricScore]
    summary: str
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    timestamp: str


class CodeGenerationEvaluator:
    """Evaluates generated code quality and correctness."""

    def __init__(self):
        """Initialize the evaluator."""
        from backend.app.core.code_quality_checker import CodeQualityChecker
        self.quality_checker = CodeQualityChecker()

    def evaluate(
        self,
        code: str,
        language: str,
        expected_functionality: Optional[str] = None,
        test_cases: Optional[List[Dict[str, Any]]] = None
    ) -> EvaluationReport:
        """
        Perform comprehensive code evaluation.

        Args:
            code: Generated code to evaluate
            language: Programming language
            expected_functionality: Description of expected functionality
            test_cases: Optional test cases to validate

        Returns:
            Comprehensive evaluation report
        """
        logger.info(f"Starting code evaluation for {language}")

        metric_scores = {}

        # Evaluate syntax correctness
        metric_scores[EvaluationMetric.SYNTAX_CORRECTNESS.value] = (
            self._evaluate_syntax_correctness(code, language)
        )

        # Evaluate functionality completeness
        metric_scores[EvaluationMetric.FUNCTIONALITY_COMPLETENESS.value] = (
            self._evaluate_functionality_completeness(code, language, expected_functionality)
        )

        # Evaluate code quality
        metric_scores[EvaluationMetric.CODE_QUALITY.value] = (
            self._evaluate_code_quality(code, language)
        )

        # Evaluate performance
        metric_scores[EvaluationMetric.PERFORMANCE.value] = (
            self._evaluate_performance(code, language)
        )

        # Evaluate security
        metric_scores[EvaluationMetric.SECURITY.value] = (
            self._evaluate_security(code, language)
        )

        # Evaluate maintainability
        metric_scores[EvaluationMetric.MAINTAINABILITY.value] = (
            self._evaluate_maintainability(code, language)
        )

        # Evaluate test coverage
        metric_scores[EvaluationMetric.TEST_COVERAGE.value] = (
            self._evaluate_test_coverage(code, language)
        )

        # Evaluate documentation
        metric_scores[EvaluationMetric.DOCUMENTATION.value] = (
            self._evaluate_documentation(code, language)
        )

        # Calculate overall score
        overall_score = sum(s.score for s in metric_scores.values()) / len(metric_scores)

        # Generate summary
        strengths, weaknesses = self._analyze_strengths_weaknesses(metric_scores)
        recommendations = self._generate_recommendations(metric_scores)

        summary = self._generate_summary(overall_score, metric_scores)

        logger.info(f"Code evaluation completed with overall score: {overall_score:.1f}")

        return EvaluationReport(
            overall_score=overall_score,
            metric_scores=metric_scores,
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
            timestamp=self._get_timestamp()
        )

    def _evaluate_syntax_correctness(self, code: str, language: str) -> MetricScore:
        """Evaluate syntax correctness."""
        issues = self.quality_checker.check_syntax(code, language)

        if not issues:
            score = 100.0
            details = "No syntax errors detected"
        else:
            critical_count = len([i for i in issues if i.severity.value == "critical"])
            score = max(0, 100 - (critical_count * 20 + len(issues) * 5))
            details = f"Found {len(issues)} syntax issues ({critical_count} critical)"

        recommendations = []
        if issues:
            recommendations.append("Fix all syntax errors before deployment")
            for issue in issues[:3]:
                recommendations.append(f"Line {issue.line}: {issue.message}")

        return MetricScore(
            metric=EvaluationMetric.SYNTAX_CORRECTNESS,
            score=score,
            details=details,
            issues=[f"Line {i.line}: {i.message}" for i in issues],
            recommendations=recommendations
        )

    def _evaluate_functionality_completeness(
        self,
        code: str,
        language: str,
        expected_functionality: Optional[str] = None
    ) -> MetricScore:
        """Evaluate functionality completeness."""
        issues = []
        recommendations = []

        # Check for main entry point
        if language.lower() == "python":
            has_main = "if __name__" in code or "def main" in code
        elif language.lower() in ["javascript", "typescript"]:
            has_main = "export" in code or "function main" in code
        else:
            has_main = True

        # Check for error handling
        has_error_handling = "try" in code or "catch" in code or "except" in code

        # Check for logging
        has_logging = "logger" in code or "logging" in code or "console" in code

        score = 100.0
        if not has_main:
            score -= 20
            issues.append("Missing main entry point")
            recommendations.append("Add main function or entry point")

        if not has_error_handling:
            score -= 15
            issues.append("Missing error handling")
            recommendations.append("Add try-catch or try-except blocks")

        if not has_logging:
            score -= 10
            issues.append("Missing logging")
            recommendations.append("Add logging for debugging")

        details = f"Completeness score: {score:.0f}/100"

        return MetricScore(
            metric=EvaluationMetric.FUNCTIONALITY_COMPLETENESS,
            score=score,
            details=details,
            issues=issues,
            recommendations=recommendations
        )

    def _evaluate_code_quality(self, code: str, language: str) -> MetricScore:
        """Evaluate code quality."""
        score = self.quality_checker.generate_quality_score(code, language)

        style_issues = self.quality_checker.check_style(code, language)
        complexity = self.quality_checker.check_complexity(code, language)

        issues = []
        recommendations = []

        if style_issues:
            issues.extend([f"Line {i.line}: {i.message}" for i in style_issues[:5]])
            recommendations.append("Fix code style issues")

        if complexity.cyclomatic_complexity > 10:
            issues.append(f"High cyclomatic complexity: {complexity.cyclomatic_complexity}")
            recommendations.append("Refactor to reduce complexity")

        if complexity.max_nesting_depth > 4:
            issues.append(f"Deep nesting: {complexity.max_nesting_depth} levels")
            recommendations.append("Reduce nesting depth")

        details = f"Quality score: {score:.0f}/100, Complexity: {complexity.cyclomatic_complexity:.1f}"

        return MetricScore(
            metric=EvaluationMetric.CODE_QUALITY,
            score=score,
            details=details,
            issues=issues,
            recommendations=recommendations
        )

    def _evaluate_performance(self, code: str, language: str) -> MetricScore:
        """Evaluate performance characteristics."""
        issues = []
        recommendations = []
        score = 100.0

        # Check for common performance issues
        if language.lower() == "python":
            # Check for nested loops
            nested_loops = len(re.findall(r'for.*:\s*.*for', code))
            if nested_loops > 2:
                score -= 10
                issues.append(f"Multiple nested loops detected ({nested_loops})")
                recommendations.append("Consider using list comprehensions or vectorization")

            # Check for inefficient string operations
            if "+=" in code and "str" in code:
                score -= 5
                issues.append("String concatenation in loop detected")
                recommendations.append("Use list and join() for string concatenation")

        # Check for memory leaks
        if "while True" in code and "break" not in code:
            score -= 10
            issues.append("Infinite loop without break condition")
            recommendations.append("Add proper loop termination condition")

        details = f"Performance score: {score:.0f}/100"

        return MetricScore(
            metric=EvaluationMetric.PERFORMANCE,
            score=score,
            details=details,
            issues=issues,
            recommendations=recommendations
        )

    def _evaluate_security(self, code: str, language: str) -> MetricScore:
        """Evaluate security."""
        security_issues = self.quality_checker.check_security(code, language)

        if not security_issues:
            score = 100.0
            details = "No security issues detected"
        else:
            critical_count = len([i for i in security_issues if i.severity.value == "critical"])
            high_count = len([i for i in security_issues if i.severity.value == "high"])
            score = max(0, 100 - (critical_count * 25 + high_count * 10))
            details = f"Found {len(security_issues)} security issues"

        recommendations = []
        if security_issues:
            for issue in security_issues[:3]:
                recommendations.append(issue.recommendation)

        return MetricScore(
            metric=EvaluationMetric.SECURITY,
            score=score,
            details=details,
            issues=[f"Line {i.line}: {i.description}" for i in security_issues],
            recommendations=recommendations
        )

    def _evaluate_maintainability(self, code: str, language: str) -> MetricScore:
        """Evaluate maintainability."""
        issues = []
        recommendations = []
        score = 100.0

        # Check for meaningful variable names
        short_vars = len(re.findall(r'\b[a-z]\b', code))
        if short_vars > 5:
            score -= 10
            issues.append(f"Too many single-letter variables ({short_vars})")
            recommendations.append("Use descriptive variable names")

        # Check for comments
        comment_ratio = len(re.findall(r'#|//', code)) / max(1, len(code.split('\n')))
        if comment_ratio < 0.05:
            score -= 5
            issues.append("Insufficient comments")
            recommendations.append("Add more comments explaining complex logic")

        # Check for function length
        functions = re.findall(r'def\s+\w+|function\s+\w+', code)
        if functions:
            avg_length = len(code) / len(functions)
            if avg_length > 200:
                score -= 10
                issues.append(f"Long functions detected (avg {avg_length:.0f} chars)")
                recommendations.append("Break long functions into smaller ones")

        details = f"Maintainability score: {score:.0f}/100"

        return MetricScore(
            metric=EvaluationMetric.MAINTAINABILITY,
            score=score,
            details=details,
            issues=issues,
            recommendations=recommendations
        )

    def _evaluate_test_coverage(self, code: str, language: str) -> MetricScore:
        """Evaluate test coverage."""
        issues = []
        recommendations = []

        # Check for test code
        has_tests = "test" in code.lower() or "assert" in code.lower()

        if has_tests:
            # Count test functions
            test_functions = len(re.findall(r'def test_|it\(|describe\(', code))
            score = min(100, 50 + test_functions * 10)
            details = f"Found {test_functions} test functions"
        else:
            score = 0
            details = "No tests found"
            issues.append("No test code detected")
            recommendations.append("Add unit tests for all functions")

        return MetricScore(
            metric=EvaluationMetric.TEST_COVERAGE,
            score=score,
            details=details,
            issues=issues,
            recommendations=recommendations
        )

    def _evaluate_documentation(self, code: str, language: str) -> MetricScore:
        """Evaluate documentation."""
        issues = []
        recommendations = []

        # Check for docstrings/comments
        docstring_count = len(re.findall(r'""".*?"""|\'\'\'.*?\'\'\'', code, re.DOTALL))
        comment_count = len(re.findall(r'#.*$|//.*$', code, re.MULTILINE))

        if docstring_count > 0 or comment_count > 0:
            score = min(100, 50 + docstring_count * 15 + comment_count * 2)
            details = f"Found {docstring_count} docstrings and {comment_count} comments"
        else:
            score = 0
            details = "No documentation found"
            issues.append("Missing docstrings and comments")
            recommendations.append("Add docstrings to all functions and classes")

        # Check for README or module-level documentation
        if not code.startswith('"""') and not code.startswith("'''"):
            score -= 10
            issues.append("Missing module-level documentation")
            recommendations.append("Add module docstring at the beginning")

        return MetricScore(
            metric=EvaluationMetric.DOCUMENTATION,
            score=score,
            details=details,
            issues=issues,
            recommendations=recommendations
        )

    def _analyze_strengths_weaknesses(
        self,
        metric_scores: Dict[str, MetricScore]
    ) -> Tuple[List[str], List[str]]:
        """Analyze strengths and weaknesses."""
        strengths = []
        weaknesses = []

        for metric_name, score in metric_scores.items():
            if score.score >= 90:
                strengths.append(f"{metric_name}: Excellent ({score.score:.0f}/100)")
            elif score.score >= 70:
                strengths.append(f"{metric_name}: Good ({score.score:.0f}/100)")
            elif score.score < 50:
                weaknesses.append(f"{metric_name}: Needs improvement ({score.score:.0f}/100)")

        return strengths, weaknesses

    def _generate_recommendations(
        self,
        metric_scores: Dict[str, MetricScore]
    ) -> List[str]:
        """Generate recommendations."""
        recommendations = []

        for score in metric_scores.values():
            if score.score < 80:
                recommendations.extend(score.recommendations[:2])

        return recommendations[:5]  # Return top 5 recommendations

    def _generate_summary(
        self,
        overall_score: float,
        metric_scores: Dict[str, MetricScore]
    ) -> str:
        """Generate evaluation summary."""
        if overall_score >= 90:
            status = "Excellent"
        elif overall_score >= 80:
            status = "Good"
        elif overall_score >= 70:
            status = "Acceptable"
        else:
            status = "Needs Improvement"

        return f"""
Code Evaluation Summary
======================

Overall Score: {overall_score:.1f}/100 ({status})

Metric Breakdown:
{chr(10).join(f"- {name}: {score.score:.0f}/100" for name, score in metric_scores.items())}

The generated code {status.lower()} in quality and is {'ready for production' if overall_score >= 80 else 'recommended for review before deployment'}.
"""

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
