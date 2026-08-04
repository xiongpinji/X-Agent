"""
Integration examples and tests for code generation quality system.

This module demonstrates how to use the code generation quality system
and provides test cases for all components.
"""

import asyncio
import pytest
from typing import Dict, Any

# Import the modules
from backend.app.prompts.code_generation import (
    get_system_prompt,
    get_review_prompt,
    get_language_patterns,
    CodeGenerationConfig
)
from backend.app.core.code_quality_checker import CodeQualityChecker
from backend.app.core.code_formatter import CodeFormatter
from backend.app.workflows.code_generation_workflow import (
    CodeGenerationWorkflow,
    CodeGenerationRequest,
    CodeLanguage
)
from backend.app.evaluation.code_generation_eval import CodeGenerationEvaluator


# ============================================================================
# Example 1: Basic Code Generation
# ============================================================================

async def example_basic_code_generation():
    """Example: Generate Python code for a simple function."""
    print("\n" + "="*70)
    print("Example 1: Basic Code Generation")
    print("="*70)

    workflow = CodeGenerationWorkflow()

    request = CodeGenerationRequest(
        description="Create a Python function that calculates the factorial of a number",
        language=CodeLanguage.PYTHON,
        include_tests=True,
        include_docs=True
    )

    result = await workflow.generate_code(request)

    print(f"\nGenerated Code:\n{result.code}")
    print(f"\nQuality Score: {result.quality_score:.1f}/100")
    print(f"Issues: {len(result.issues)}")
    print(f"Suggestions: {len(result.suggestions)}")


# ============================================================================
# Example 2: Code Quality Checking
# ============================================================================

def example_code_quality_checking():
    """Example: Check code quality."""
    print("\n" + "="*70)
    print("Example 2: Code Quality Checking")
    print("="*70)

    checker = CodeQualityChecker()

    # Sample code with issues
    code = """
def calculate_factorial(n):
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0 or n == 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result = result * i
    return result

# Usage
print(calculate_factorial(5))
"""

    # Check syntax
    syntax_issues = checker.check_syntax(code, "python")
    print(f"\nSyntax Issues: {len(syntax_issues)}")

    # Check style
    style_issues = checker.check_style(code, "python")
    print(f"Style Issues: {len(style_issues)}")
    for issue in style_issues[:3]:
        print(f"  - Line {issue.line}: {issue.message}")

    # Check complexity
    complexity = checker.check_complexity(code, "python")
    print(f"\nComplexity Analysis:")
    print(f"  - Cyclomatic Complexity: {complexity.cyclomatic_complexity}")
    print(f"  - Lines of Code: {complexity.lines_of_code}")
    print(f"  - Functions: {complexity.functions_count}")

    # Check security
    security_issues = checker.check_security(code, "python")
    print(f"\nSecurity Issues: {len(security_issues)}")

    # Get suggestions
    suggestions = checker.suggest_improvements(code, "python")
    print(f"\nSuggestions: {len(suggestions)}")
    for suggestion in suggestions[:3]:
        print(f"  - {suggestion.category}: {suggestion.description}")

    # Get quality score
    score = checker.generate_quality_score(code, "python")
    print(f"\nOverall Quality Score: {score:.1f}/100")


# ============================================================================
# Example 3: Code Formatting
# ============================================================================

def example_code_formatting():
    """Example: Format and optimize code."""
    print("\n" + "="*70)
    print("Example 3: Code Formatting")
    print("="*70)

    formatter = CodeFormatter()

    # Sample code with formatting issues
    code = """
import os
from typing import List
import sys
import json

def process_data(data:List[str])->str:
    result=""
    for item in data:
        result=result+item
    return result
"""

    print(f"\nOriginal Code:\n{code}")

    # Format code
    formatted = formatter.format_code(
        code,
        "python",
        add_type_hints=True,
        add_docstrings=True
    )

    print(f"\nFormatted Code:\n{formatted}")

    # Optimize imports
    optimized = formatter.optimize_imports(code, "python")
    print(f"\nOptimized Imports:\n{optimized}")


# ============================================================================
# Example 4: Code Evaluation
# ============================================================================

def example_code_evaluation():
    """Example: Evaluate code quality."""
    print("\n" + "="*70)
    print("Example 4: Code Evaluation")
    print("="*70)

    evaluator = CodeGenerationEvaluator()

    code = """
\"\"\"
Calculate factorial of a number.
\"\"\"

def factorial(n: int) -> int:
    \"\"\"
    Calculate factorial.

    Args:
        n: Non-negative integer

    Returns:
        Factorial of n

    Raises:
        ValueError: If n is negative
    \"\"\"
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0 or n == 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def test_factorial():
    \"\"\"Test factorial function.\"\"\"
    assert factorial(0) == 1
    assert factorial(1) == 1
    assert factorial(5) == 120

    try:
        factorial(-1)
        assert False, "Should raise ValueError"
    except ValueError:
        pass
"""

    report = evaluator.evaluate(code, "python")

    print(f"\nEvaluation Report:")
    print(f"Overall Score: {report.overall_score:.1f}/100")
    print(f"\nMetric Scores:")
    for metric_name, score in report.metric_scores.items():
        print(f"  - {metric_name}: {score.score:.1f}/100")

    print(f"\nStrengths:")
    for strength in report.strengths:
        print(f"  - {strength}")

    print(f"\nWeaknesses:")
    for weakness in report.weaknesses:
        print(f"  - {weakness}")

    print(f"\nRecommendations:")
    for rec in report.recommendations[:3]:
        print(f"  - {rec}")


# ============================================================================
# Example 5: Complete Workflow
# ============================================================================

async def example_complete_workflow():
    """Example: Complete code generation workflow."""
    print("\n" + "="*70)
    print("Example 5: Complete Workflow")
    print("="*70)

    workflow = CodeGenerationWorkflow()
    evaluator = CodeGenerationEvaluator()

    # Step 1: Generate code
    print("\nStep 1: Generating code...")
    request = CodeGenerationRequest(
        description="""
        Create a Python class for managing a simple in-memory cache with:
        1. Set and get methods
        2. TTL (time-to-live) support
        3. Maximum size limit
        4. LRU eviction policy
        """,
        language=CodeLanguage.PYTHON,
        include_tests=True,
        include_docs=True
    )

    result = await workflow.generate_code(request)
    print(f"Generated code with quality score: {result.quality_score:.1f}/100")

    # Step 2: Evaluate code
    print("\nStep 2: Evaluating code...")
    report = evaluator.evaluate(result.code, "python")
    print(f"Evaluation score: {report.overall_score:.1f}/100")

    # Step 3: Display results
    print(f"\nGenerated Code:\n{result.code[:500]}...")
    print(f"\nGenerated Tests:\n{result.tests[:300] if result.tests else 'N/A'}...")
    print(f"\nGenerated Documentation:\n{result.documentation[:300] if result.documentation else 'N/A'}...")


# ============================================================================
# Test Cases
# ============================================================================

class TestCodeQualityChecker:
    """Test cases for CodeQualityChecker."""

    def test_syntax_check_valid_python(self):
        """Test syntax check with valid Python code."""
        checker = CodeQualityChecker()
        code = "def hello():\n    return 'world'"
        issues = checker.check_syntax(code, "python")
        assert len(issues) == 0

    def test_syntax_check_invalid_python(self):
        """Test syntax check with invalid Python code."""
        checker = CodeQualityChecker()
        code = "def hello(\n    return 'world'"
        issues = checker.check_syntax(code, "python")
        assert len(issues) > 0

    def test_style_check(self):
        """Test style checking."""
        checker = CodeQualityChecker()
        code = "x=1\ny=2"
        issues = checker.check_style(code, "python")
        assert len(issues) > 0

    def test_complexity_analysis(self):
        """Test complexity analysis."""
        checker = CodeQualityChecker()
        code = """
def complex_function(n):
    if n > 0:
        for i in range(n):
            if i % 2 == 0:
                while i > 0:
                    i -= 1
        """
        report = checker.check_complexity(code, "python")
        assert report.cyclomatic_complexity > 1

    def test_security_check(self):
        """Test security checking."""
        checker = CodeQualityChecker()
        code = "password = 'secret123'"
        issues = checker.check_security(code, "python")
        assert len(issues) > 0

    def test_quality_score(self):
        """Test quality score generation."""
        checker = CodeQualityChecker()
        code = "def hello():\n    return 'world'"
        score = checker.generate_quality_score(code, "python")
        assert 0 <= score <= 100


class TestCodeFormatter:
    """Test cases for CodeFormatter."""

    def test_format_python(self):
        """Test Python code formatting."""
        formatter = CodeFormatter()
        code = "x=1\ny=2"
        formatted = formatter.format_python(code)
        assert formatted is not None

    def test_optimize_imports(self):
        """Test import optimization."""
        formatter = CodeFormatter()
        code = "import os\nfrom typing import List\nimport sys"
        optimized = formatter.optimize_imports(code, "python")
        assert optimized is not None

    def test_add_type_hints(self):
        """Test adding type hints."""
        formatter = CodeFormatter()
        code = "def hello():\n    return 'world'"
        with_hints = formatter.add_type_hints(code, "python")
        assert with_hints is not None

    def test_add_docstrings(self):
        """Test adding docstrings."""
        formatter = CodeFormatter()
        code = "def hello():\n    return 'world'"
        with_docs = formatter.add_docstrings(code, "python")
        assert with_docs is not None


class TestCodeGenerationEvaluator:
    """Test cases for CodeGenerationEvaluator."""

    def test_evaluate_syntax_correctness(self):
        """Test syntax correctness evaluation."""
        evaluator = CodeGenerationEvaluator()
        code = "def hello():\n    return 'world'"
        report = evaluator.evaluate(code, "python")
        assert report.metric_scores["syntax_correctness"].score == 100.0

    def test_evaluate_documentation(self):
        """Test documentation evaluation."""
        evaluator = CodeGenerationEvaluator()
        code = '"""Module docstring."""\n\ndef hello():\n    """Function docstring."""\n    return "world"'
        report = evaluator.evaluate(code, "python")
        assert report.metric_scores["documentation"].score > 50

    def test_overall_score(self):
        """Test overall score calculation."""
        evaluator = CodeGenerationEvaluator()
        code = "def hello():\n    return 'world'"
        report = evaluator.evaluate(code, "python")
        assert 0 <= report.overall_score <= 100


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("X-Agent Code Generation Quality System - Examples")
    print("="*70)

    # Run synchronous examples
    example_code_quality_checking()
    example_code_formatting()
    example_code_evaluation()

    # Run asynchronous examples
    await example_basic_code_generation()
    await example_complete_workflow()

    print("\n" + "="*70)
    print("Examples completed successfully!")
    print("="*70)


if __name__ == "__main__":
    # Run examples
    asyncio.run(main())

    # Run tests
    print("\n" + "="*70)
    print("Running Tests")
    print("="*70)
    pytest.main([__file__, "-v"])
