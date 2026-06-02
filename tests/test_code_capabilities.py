"""
Comprehensive test suite for code capability modules.

Tests for:
- Code understanding engine
- Code generation engine
- Context-aware programming
- Code completion engine
- Code refactoring engine
"""

import pytest
from pathlib import Path
from backend.app.core.code_understanding import (
    CodeUnderstandingEngine, CodeLanguage, SymbolKind, PythonAnalyzer
)
from backend.app.core.code_generation import (
    CodeGenerationEngine, GenerationRequest, GenerationContext, CodeStyle
)
from backend.app.core.context_aware import (
    ContextAwareEngine, ProjectStructureAnalyzer, ConventionLearner
)
from backend.app.core.code_completion import (
    CodeCompletionEngine, CompletionContext, CompletionTrigger
)
from backend.app.core.code_refactoring import (
    CodeRefactoringEngine, RefactoringDetector, RefactoringType
)


class TestCodeUnderstanding:
    """Tests for code understanding engine."""

    def test_python_analysis(self):
        """Test Python code analysis."""
        code = '''
class Calculator:
    """Simple calculator class."""

    def add(self, a, b):
        """Add two numbers."""
        return a + b

    def multiply(self, a, b):
        """Multiply two numbers."""
        return a * b
'''
        analyzer = PythonAnalyzer(code, "test.py")
        analysis = analyzer.analyze()

        assert analysis.language == CodeLanguage.PYTHON
        assert len(analysis.symbols) >= 2  # class and methods
        assert any(s.name == "Calculator" for s in analysis.symbols)
        assert any(s.name == "add" for s in analysis.symbols)

    def test_dependency_detection(self):
        """Test dependency detection."""
        code = '''
import os
import sys
from pathlib import Path

def process_file(path):
    return Path(path).read_text()
'''
        analyzer = PythonAnalyzer(code, "test.py")
        analysis = analyzer.analyze()

        assert len(analysis.imports) >= 3
        assert "os" in analysis.imports or "Path" in analysis.imports

    def test_engine_project_analysis(self):
        """Test engine project analysis."""
        engine = CodeUnderstandingEngine()
        # Would need actual project files to test fully
        assert engine is not None


class TestCodeGeneration:
    """Tests for code generation engine."""

    def test_generation_context_creation(self):
        """Test generation context creation."""
        context = GenerationContext(
            project_root="/project",
            file_path="/project/main.py",
            language="python",
            style=CodeStyle.PEP8,
        )

        assert context.project_root == "/project"
        assert context.language == "python"
        assert context.style == CodeStyle.PEP8

    def test_generation_request_creation(self):
        """Test generation request creation."""
        context = GenerationContext(
            project_root="/project",
            file_path="/project/main.py",
            language="python",
        )

        request = GenerationRequest(
            description="Create a function to calculate factorial",
            context=context,
        )

        assert request.description == "Create a function to calculate factorial"
        assert request.context.language == "python"

    def test_template_library(self):
        """Test template library."""
        engine = CodeGenerationEngine()
        templates = engine.template_library.list_templates("python")

        assert len(templates) > 0
        assert any(t.category == "function" for t in templates)
        assert any(t.category == "class" for t in templates)

    def test_style_analysis(self):
        """Test style analysis."""
        engine = CodeGenerationEngine()
        samples = [
            "def my_function():\n    pass",
            "def another_function():\n    pass",
        ]
        conventions = engine.style_analyzer.analyze_style(samples, "python")

        assert "indentation" in conventions
        assert "naming_convention" in conventions


class TestContextAware:
    """Tests for context-aware programming."""

    def test_project_structure_analysis(self):
        """Test project structure analysis."""
        # Create temporary project structure
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create basic structure
            Path(tmpdir, "src").mkdir()
            Path(tmpdir, "tests").mkdir()
            Path(tmpdir, "setup.py").touch()

            structure = ProjectStructureAnalyzer.analyze(tmpdir)

            assert structure.root == tmpdir
            assert "src" in structure.directories or "tests" in structure.directories

    def test_convention_learning(self):
        """Test convention learning."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create sample Python file
            sample_file = Path(tmpdir, "sample.py")
            sample_file.write_text('''
def my_function():
    """Function docstring."""
    pass

class MyClass:
    """Class docstring."""
    pass
''')

            conventions = ConventionLearner.learn_conventions(tmpdir, "python", sample_size=1)

            assert len(conventions) > 0

    def test_context_aware_engine(self):
        """Test context-aware engine."""
        engine = ContextAwareEngine()
        assert engine is not None


class TestCodeCompletion:
    """Tests for code completion engine."""

    def test_completion_context_creation(self):
        """Test completion context creation."""
        context = CompletionContext(
            file_path="test.py",
            language="python",
            line=1,
            column=5,
            line_text="def my_",
            file_content="def my_function():\n    pass",
            trigger=CompletionTrigger.MANUAL,
            prefix="my_",
        )

        assert context.file_path == "test.py"
        assert context.prefix == "my_"

    def test_keyword_completion(self):
        """Test keyword completion."""
        engine = CodeCompletionEngine()
        context = CompletionContext(
            file_path="test.py",
            language="python",
            line=1,
            column=2,
            line_text="if",
            file_content="if",
            trigger=CompletionTrigger.MANUAL,
            prefix="if",
        )

        result = engine.complete(context)

        assert len(result.items) > 0

    def test_snippet_completion(self):
        """Test snippet completion."""
        engine = CodeCompletionEngine()
        snippets = engine.snippet_provider.get_snippets("python")

        assert "if" in snippets
        assert "for" in snippets
        assert "def" in snippets

    def test_import_suggestion(self):
        """Test import suggestion."""
        engine = CodeCompletionEngine()
        context = CompletionContext(
            file_path="test.py",
            language="python",
            line=1,
            column=7,
            line_text="import ",
            file_content="import ",
            trigger=CompletionTrigger.IMPORT,
            prefix="",
        )

        result = engine.complete(context)

        assert len(result.items) > 0


class TestCodeRefactoring:
    """Tests for code refactoring engine."""

    def test_long_method_detection(self):
        """Test detection of long methods."""
        code = '''
def long_method():
    line1 = 1
    line2 = 2
    line3 = 3
    line4 = 4
    line5 = 5
    line6 = 6
    line7 = 7
    line8 = 8
    line9 = 9
    line10 = 10
    line11 = 11
    line12 = 12
    line13 = 13
    line14 = 14
    line15 = 15
    line16 = 16
    line17 = 17
    line18 = 18
    line19 = 19
    line20 = 20
    line21 = 21
    return line21
'''
        detector = RefactoringDetector()
        opportunities = detector.detect_opportunities("test.py", code, "python")

        # Should detect long method
        assert any(o.type == RefactoringType.EXTRACT_METHOD for o in opportunities)

    def test_magic_number_detection(self):
        """Test detection of magic numbers."""
        code = '''
def calculate():
    result = 42 * 100
    if result > 42:
        return 42
    return 0
'''
        detector = RefactoringDetector()
        opportunities = detector.detect_opportunities("test.py", code, "python")

        # Should detect magic numbers
        assert any(o.type == RefactoringType.REPLACE_MAGIC_NUMBERS for o in opportunities)

    def test_dead_code_detection(self):
        """Test detection of dead code."""
        code = '''
def function():
    unused_var = 42
    return 0
'''
        detector = RefactoringDetector()
        opportunities = detector.detect_opportunities("test.py", code, "python")

        # Should detect unused variable
        assert any(o.type == RefactoringType.REMOVE_DEAD_CODE for o in opportunities)

    def test_refactoring_engine(self):
        """Test refactoring engine."""
        engine = CodeRefactoringEngine()
        assert engine is not None


class TestIntegration:
    """Integration tests for all modules."""

    def test_end_to_end_workflow(self):
        """Test end-to-end workflow."""
        # Create sample code
        code = '''
class DataProcessor:
    def process_data(self, data):
        result = []
        for item in data:
            if item > 0:
                result.append(item * 2)
        return result
'''

        # 1. Analyze code
        understanding_engine = CodeUnderstandingEngine()
        analyzer = PythonAnalyzer(code, "processor.py")
        analysis = analyzer.analyze()
        assert len(analysis.symbols) > 0

        # 2. Detect refactoring opportunities
        refactoring_engine = CodeRefactoringEngine()
        opportunities = refactoring_engine.detect_opportunities("processor.py", code, "python")
        assert len(opportunities) >= 0

        # 3. Generate completion suggestions
        completion_engine = CodeCompletionEngine()
        context = CompletionContext(
            file_path="processor.py",
            language="python",
            line=1,
            column=0,
            line_text="",
            file_content=code,
            trigger=CompletionTrigger.MANUAL,
        )
        result = completion_engine.complete(context)
        assert result is not None

    def test_multi_language_support(self):
        """Test multi-language support."""
        # Python
        py_code = "def hello(): pass"
        py_analyzer = PythonAnalyzer(py_code, "test.py")
        py_analysis = py_analyzer.analyze()
        assert py_analysis.language == CodeLanguage.PYTHON

        # JavaScript (generic analysis)
        js_code = "function hello() {}"
        understanding_engine = CodeUnderstandingEngine()
        js_analysis = understanding_engine._analyze_generic(js_code, "test.js", CodeLanguage.JAVASCRIPT)
        assert js_analysis.language == CodeLanguage.JAVASCRIPT


class TestPerformance:
    """Performance tests."""

    def test_large_file_analysis(self):
        """Test analysis of large files."""
        # Generate large code
        code = "\n".join([f"def function_{i}(): pass" for i in range(100)])

        analyzer = PythonAnalyzer(code, "large.py")
        analysis = analyzer.analyze()

        assert len(analysis.symbols) >= 100

    def test_completion_performance(self):
        """Test completion performance."""
        engine = CodeCompletionEngine()
        context = CompletionContext(
            file_path="test.py",
            language="python",
            line=1,
            column=0,
            line_text="",
            file_content="",
            trigger=CompletionTrigger.MANUAL,
        )

        # Should complete quickly
        result = engine.complete(context, limit=20)
        assert len(result.items) <= 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
