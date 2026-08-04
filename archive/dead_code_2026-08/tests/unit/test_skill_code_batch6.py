"""Batch 6: 技能与代码系统全覆盖测试"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, UTC


# ═══════════════════════════════════════════════════════════════════════════════
# SKILL_SYSTEM_V2 MODULE
# ═══════════════════════════════════════════════════════════════════════════════

class TestSkillSystemEnums:
    def test_skill_status_values(self):
        from backend.app.core.skill_system_v2 import SkillStatus
        assert SkillStatus.DRAFT == "draft"
        assert SkillStatus.PUBLISHED == "published"
        assert SkillStatus.ACTIVE == "active"
        assert SkillStatus.DISABLED == "disabled"

    def test_skill_category_values(self):
        from backend.app.core.skill_system_v2 import SkillCategory
        assert SkillCategory.PRODUCTIVITY == "productivity"
        assert SkillCategory.DEVELOPMENT == "development"
        assert SkillCategory.CUSTOM == "custom"

    def test_skill_risk_level_values(self):
        from backend.app.core.skill_system_v2 import SkillRiskLevel
        assert SkillRiskLevel.LOW == "low"
        assert SkillRiskLevel.CRITICAL == "critical"

    def test_execution_status_values(self):
        from backend.app.core.skill_system_v2 import ExecutionStatus
        assert ExecutionStatus.PENDING == "pending"
        assert ExecutionStatus.SUCCESS == "success"
        assert ExecutionStatus.FAILED == "failed"


class TestSkillParameter:
    def test_parameter_creation(self):
        from backend.app.core.skill_system_v2 import SkillParameter
        param = SkillParameter(
            name="count",
            type="number",
            description="Number of items",
            required=True,
        )
        assert param.name == "count"
        assert param.type == "number"

    def test_validate_required_missing(self):
        from backend.app.core.skill_system_v2 import SkillParameter
        param = SkillParameter(name="x", type="string", description="d", required=True)
        valid, err = param.validate(None)
        assert not valid
        assert "required" in err

    def test_validate_optional_missing(self):
        from backend.app.core.skill_system_v2 import SkillParameter
        param = SkillParameter(name="x", type="string", description="d", required=False)
        valid, err = param.validate(None)
        assert valid
        assert err is None

    def test_validate_type_mismatch(self):
        from backend.app.core.skill_system_v2 import SkillParameter
        param = SkillParameter(name="x", type="number", description="d")
        valid, err = param.validate("not_a_number")
        assert not valid
        assert "type" in err

    def test_validate_enum(self):
        from backend.app.core.skill_system_v2 import SkillParameter
        param = SkillParameter(name="x", type="string", description="d", enum=["a", "b"])
        valid, err = param.validate("c")
        assert not valid
        assert "one of" in err

    def test_validate_range(self):
        from backend.app.core.skill_system_v2 import SkillParameter
        param = SkillParameter(name="x", type="number", description="d", min_value=0, max_value=10)
        valid, err = param.validate(15)
        assert not valid
        valid2, _ = param.validate(5)
        assert valid2

    def test_validate_pattern(self):
        from backend.app.core.skill_system_v2 import SkillParameter
        param = SkillParameter(name="x", type="string", description="d", pattern=r"^\d+$")
        valid, err = param.validate("abc")
        assert not valid
        valid2, _ = param.validate("123")
        assert valid2


class TestSkillMetadata:
    def test_metadata_creation(self):
        from backend.app.core.skill_system_v2 import SkillMetadata
        meta = SkillMetadata(name="Test Skill", version="2.0.0")
        assert meta.name == "Test Skill"
        assert meta.version == "2.0.0"
        assert meta.skill_id is not None


class TestSkillExecutionContext:
    def test_context_creation(self):
        from backend.app.core.skill_system_v2 import SkillExecutionContext
        ctx = SkillExecutionContext(
            execution_id="exec-1",
            skill_id="skill-1",
            user_id="user-1",
        )
        assert ctx.execution_id == "exec-1"


class TestSkillExecutionResult:
    def test_result_creation(self):
        from backend.app.core.skill_system_v2 import SkillExecutionResult
        result = SkillExecutionResult(
            success=True,
            data={"data": "test"},
        )
        assert result.success is True
        assert result.data == {"data": "test"}


class TestSkillRegistry:
    def test_registry_initialization(self):
        from backend.app.core.skill_system_v2 import SkillRegistry
        registry = SkillRegistry()
        assert registry is not None

    async def test_registry_register_and_get(self):
        from backend.app.core.skill_system_v2 import SkillRegistry, SkillMetadata, SkillStatus

        class MockSkill:
            metadata = SkillMetadata(name="mock", version="1.0.0")
            async def execute(self, ctx): pass

        registry = SkillRegistry()
        skill = MockSkill()
        await registry.register(skill)
        # Verify it was registered
        assert len(registry._skills) >= 1


class TestSkillExecutor:
    def test_executor_initialization(self):
        from backend.app.core.skill_system_v2 import SkillExecutor, SkillRegistry
        registry = SkillRegistry()
        executor = SkillExecutor(registry)
        assert executor is not None


# ═══════════════════════════════════════════════════════════════════════════════
# SKILL_REVIEW_SYSTEM MODULE
# ═══════════════════════════════════════════════════════════════════════════════

class TestSkillReviewEnums:
    def test_review_status_values(self):
        from backend.app.core.skill_review_system import ReviewStatus
        assert ReviewStatus.PENDING == "pending"
        assert ReviewStatus.APPROVED == "approved"
        assert ReviewStatus.REJECTED == "rejected"

    def test_report_reason_values(self):
        from backend.app.core.skill_review_system import ReportReason
        assert ReportReason.SPAM == "spam"
        assert ReportReason.INAPPROPRIATE == "inappropriate"


class TestSkillReview:
    def test_review_creation(self):
        from backend.app.core.skill_review_system import SkillReview, ReviewStatus
        review = SkillReview(
            skill_id="s1",
            user_id="u1",
            user_name="Tester",
            rating=4,
            title="Good skill",
            comment="Works well",
        )
        assert review.rating == 4
        assert review.status == ReviewStatus.PENDING

    def test_review_to_dict(self):
        from backend.app.core.skill_review_system import SkillReview
        review = SkillReview(skill_id="s1", user_id="u1", rating=5)
        d = review.to_dict()
        assert d["skill_id"] == "s1"
        assert d["rating"] == 5
        assert "created_at" in d


class TestReviewReport:
    def test_report_creation(self):
        from backend.app.core.skill_review_system import ReviewReport, ReportReason
        report = ReviewReport(
            review_id="r1",
            reporter_id="u2",
            reason=ReportReason.SPAM,
            description="Spam content",
        )
        assert report.reason == ReportReason.SPAM

    def test_report_to_dict(self):
        from backend.app.core.skill_review_system import ReviewReport
        report = ReviewReport(review_id="r1", reporter_id="u2")
        d = report.to_dict()
        assert d["review_id"] == "r1"
        assert d["resolved_at"] is None


class TestSkillReviewSystem:
    def test_system_initialization(self):
        from backend.app.core.skill_review_system import SkillReviewSystem
        system = SkillReviewSystem()
        assert system.reviews == {}

    def test_add_review(self):
        from backend.app.core.skill_review_system import SkillReviewSystem
        system = SkillReviewSystem()
        success, err, review = system.add_review(
            skill_id="s1",
            user_id="u1",
            user_name="Tester",
            rating=5,
            title="Great",
            comment="Works well",
        )
        assert success
        assert "s1" in system.reviews
        assert len(system.reviews["s1"]) == 1

    def test_get_reviews(self):
        from backend.app.core.skill_review_system import SkillReviewSystem
        system = SkillReviewSystem()
        system.add_review(skill_id="s1", user_id="u1", user_name="T", rating=4, title="Good")
        # By default get_reviews only returns APPROVED, pass status=None for all
        reviews = system.get_reviews("s1", status=None)
        assert len(reviews) == 1

    def test_get_average_rating_no_approved(self):
        from backend.app.core.skill_review_system import SkillReviewSystem
        system = SkillReviewSystem()
        system.add_review(skill_id="s1", user_id="u1", user_name="T", rating=4, title="Nice")
        # Reviews are pending by default, so average is 0
        avg = system.get_average_rating("s1")
        assert avg == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# CODE_UNDERSTANDING MODULE
# ═══════════════════════════════════════════════════════════════════════════════

class TestCodeUnderstandingEnums:
    def test_code_language_values(self):
        from backend.app.core.code_understanding import CodeLanguage
        assert CodeLanguage.PYTHON == "python"
        assert CodeLanguage.JAVASCRIPT == "javascript"
        assert CodeLanguage.RUST == "rust"

    def test_symbol_kind_values(self):
        from backend.app.core.code_understanding import SymbolKind
        assert SymbolKind.CLASS == "class"
        assert SymbolKind.FUNCTION == "function"
        assert SymbolKind.METHOD == "method"

    def test_design_pattern_values(self):
        from backend.app.core.code_understanding import DesignPattern
        assert DesignPattern.SINGLETON == "singleton"
        assert DesignPattern.FACTORY == "factory"
        assert DesignPattern.OBSERVER == "observer"


class TestCodeSymbol:
    def test_symbol_creation(self):
        from backend.app.core.code_understanding import CodeSymbol, SymbolKind
        sym = CodeSymbol(
            name="MyClass",
            kind=SymbolKind.CLASS,
            line_start=10,
            line_end=50,
        )
        assert sym.name == "MyClass"
        assert sym.kind == SymbolKind.CLASS

    def test_symbol_to_dict(self):
        from backend.app.core.code_understanding import CodeSymbol, SymbolKind
        sym = CodeSymbol(name="func", kind=SymbolKind.FUNCTION, line_start=1, line_end=5)
        d = sym.to_dict()
        assert d["name"] == "func"
        assert d["complexity"] == 1


class TestCodeDependency:
    def test_dependency_creation(self):
        from backend.app.core.code_understanding import CodeDependency
        dep = CodeDependency(source="A", target="B", kind="import")
        assert dep.source == "A"
        assert dep.strength == 1.0

    def test_dependency_to_dict(self):
        from backend.app.core.code_understanding import CodeDependency
        dep = CodeDependency(source="A", target="B", kind="call", line=10)
        d = dep.to_dict()
        assert d["kind"] == "call"
        assert d["line"] == 10


class TestCodeMetrics:
    def test_metrics_creation(self):
        from backend.app.core.code_understanding import CodeMetrics
        m = CodeMetrics(cyclomatic_complexity=5, lines_of_code=100)
        assert m.cyclomatic_complexity == 5
        assert m.lines_of_code == 100

    def test_metrics_to_dict(self):
        from backend.app.core.code_understanding import CodeMetrics
        m = CodeMetrics()
        d = m.to_dict()
        assert "cyclomatic_complexity" in d
        assert d["nesting_depth"] == 0


class TestCodeAnalysis:
    def test_analysis_creation(self):
        from backend.app.core.code_understanding import CodeAnalysis, CodeLanguage
        analysis = CodeAnalysis(file_path="test.py", language=CodeLanguage.PYTHON)
        assert analysis.file_path == "test.py"
        assert analysis.symbols == []


class TestPythonAnalyzer:
    def test_analyzer_creation(self):
        from backend.app.core.code_understanding import PythonAnalyzer
        code = "def hello(): pass"
        analyzer = PythonAnalyzer(code, "test.py")
        assert analyzer is not None
        assert analyzer.file_path == "test.py"

    def test_analyze_simple_code(self):
        from backend.app.core.code_understanding import PythonAnalyzer
        code = '''
def hello(name):
    """Say hello."""
    return f"Hello, {name}!"

class Greeter:
    def greet(self):
        pass
'''
        analyzer = PythonAnalyzer(code, "test.py")
        result = analyzer.analyze()
        assert result is not None
        assert len(result.symbols) >= 2


class TestCodeUnderstandingEngine:
    def test_engine_creation(self):
        from backend.app.core.code_understanding import CodeUnderstandingEngine
        engine = CodeUnderstandingEngine()
        assert engine is not None


# ═══════════════════════════════════════════════════════════════════════════════
# CODE_REFACTORING MODULE
# ═══════════════════════════════════════════════════════════════════════════════

class TestRefactoringEnums:
    def test_refactoring_type_values(self):
        from backend.app.core.code_refactoring import RefactoringType
        assert RefactoringType.EXTRACT_METHOD == "extract_method"
        assert RefactoringType.RENAME == "rename"
        assert RefactoringType.MOVE == "move"

    def test_refactoring_status_values(self):
        from backend.app.core.code_refactoring import RefactoringStatus
        assert RefactoringStatus.PROPOSED == "proposed"
        assert RefactoringStatus.APPLIED == "applied"
        assert RefactoringStatus.FAILED == "failed"


class TestRefactoringOpportunity:
    def test_opportunity_creation(self):
        from backend.app.core.code_refactoring import RefactoringOpportunity, RefactoringType
        opp = RefactoringOpportunity(
            type=RefactoringType.EXTRACT_METHOD,
            location="file.py:10",
            description="Extract method",
            severity="medium",
            confidence=0.8,
        )
        assert opp.type == RefactoringType.EXTRACT_METHOD
        assert opp.confidence == 0.8

    def test_opportunity_to_dict(self):
        from backend.app.core.code_refactoring import RefactoringOpportunity, RefactoringType
        opp = RefactoringOpportunity(
            type=RefactoringType.RENAME,
            location="file.py:5",
            description="Rename variable",
            severity="low",
            confidence=0.9,
        )
        d = opp.to_dict()
        assert d["severity"] == "low"


class TestRefactoringChange:
    def test_change_creation(self):
        from backend.app.core.code_refactoring import RefactoringChange, RefactoringType
        change = RefactoringChange(
            file_path="test.py",
            start_line=1,
            end_line=5,
            original_code="x=1",
            new_code="x = 1",
            description="Fix spacing",
            change_type=RefactoringType.RENAME,
        )
        assert change.file_path == "test.py"

    def test_change_to_dict(self):
        from backend.app.core.code_refactoring import RefactoringChange, RefactoringType
        change = RefactoringChange(
            file_path="a.py", start_line=1, end_line=2,
            original_code="old", new_code="new",
            description="d", change_type=RefactoringType.RENAME,
        )
        d = change.to_dict()
        assert d["original_code"] == "old"


class TestRefactoringPlan:
    def test_plan_creation(self):
        from backend.app.core.code_refactoring import RefactoringPlan, RefactoringType
        plan = RefactoringPlan(refactoring_type=RefactoringType.EXTRACT_METHOD)
        assert plan.refactoring_type == RefactoringType.EXTRACT_METHOD
        assert plan.changes == []
        assert plan.plan_id is not None

    def test_plan_to_dict(self):
        from backend.app.core.code_refactoring import RefactoringPlan, RefactoringType
        plan = RefactoringPlan(refactoring_type=RefactoringType.RENAME)
        d = plan.to_dict()
        assert "plan_id" in d
        assert d["risk_level"] == "low"


class TestRefactoringResult:
    def test_result_creation(self):
        from backend.app.core.code_refactoring import (
            RefactoringResult, RefactoringPlan, RefactoringStatus, RefactoringType
        )
        plan = RefactoringPlan(refactoring_type=RefactoringType.RENAME)
        result = RefactoringResult(status=RefactoringStatus.APPLIED, plan=plan)
        assert result.status == RefactoringStatus.APPLIED
        assert result.changes_applied == 0


class TestRefactoringDetector:
    def test_detector_creation(self):
        from backend.app.core.code_refactoring import RefactoringDetector
        detector = RefactoringDetector()
        assert detector is not None


class TestCodeRefactoringEngine:
    def test_engine_creation(self):
        from backend.app.core.code_refactoring import CodeRefactoringEngine
        engine = CodeRefactoringEngine()
        assert engine is not None


# ═══════════════════════════════════════════════════════════════════════════════
# CODE_GENERATION MODULE
# ═══════════════════════════════════════════════════════════════════════════════

class TestCodeGenerationEnums:
    def test_generation_mode_values(self):
        from backend.app.core.code_generation import GenerationMode
        assert GenerationMode.COMPLETE == "complete"
        assert GenerationMode.SNIPPET == "snippet"
        assert GenerationMode.REFACTOR == "refactor"

    def test_code_style_values(self):
        from backend.app.core.code_generation import CodeStyle
        assert CodeStyle.GOOGLE == "google"
        assert CodeStyle.PEP8 == "pep8"


class TestCodeTemplate:
    def test_template_creation(self):
        from backend.app.core.code_generation import CodeTemplate
        tmpl = CodeTemplate(
            name="class_template",
            language="python",
            category="class",
            template="class {{name}}:\n    pass",
        )
        assert tmpl.name == "class_template"

    def test_template_render(self):
        from backend.app.core.code_generation import CodeTemplate
        tmpl = CodeTemplate(
            name="t", language="python", category="class",
            template="class {{name}}:\n    '''{{doc}}'''",
        )
        result = tmpl.render(name="Foo", doc="A foo class")
        assert "class Foo:" in result
        assert "A foo class" in result


class TestGenerationContext:
    def test_context_creation(self):
        from backend.app.core.code_generation import GenerationContext, CodeStyle
        ctx = GenerationContext(
            project_root="/project",
            file_path="/project/main.py",
            language="python",
        )
        assert ctx.language == "python"
        assert ctx.style == CodeStyle.PEP8

    def test_context_to_dict(self):
        from backend.app.core.code_generation import GenerationContext
        ctx = GenerationContext(project_root="/p", file_path="/p/f.py", language="python")
        d = ctx.to_dict()
        assert d["project_root"] == "/p"


class TestGenerationRequest:
    def test_request_creation(self):
        from backend.app.core.code_generation import (
            GenerationRequest, GenerationContext, GenerationMode
        )
        ctx = GenerationContext(project_root="/p", file_path="/p/f.py", language="python")
        req = GenerationRequest(description="Create a function", context=ctx)
        assert req.mode == GenerationMode.COMPLETE
        assert req.request_id is not None

    def test_request_to_dict(self):
        from backend.app.core.code_generation import GenerationRequest, GenerationContext
        ctx = GenerationContext(project_root="/p", file_path="/p/f.py", language="python")
        req = GenerationRequest(description="test", context=ctx)
        d = req.to_dict()
        assert d["description"] == "test"


class TestGeneratedCode:
    def test_generated_code_creation(self):
        from backend.app.core.code_generation import GeneratedCode, GenerationMode
        code = GeneratedCode(
            code="def hello(): pass",
            language="python",
            mode=GenerationMode.COMPLETE,
        )
        assert code.confidence == 0.8
        assert code.generation_id is not None

    def test_generated_code_to_dict(self):
        from backend.app.core.code_generation import GeneratedCode, GenerationMode
        code = GeneratedCode(code="x=1", language="python", mode=GenerationMode.SNIPPET)
        d = code.to_dict()
        assert d["code"] == "x=1"


class TestPromptEngineer:
    def test_build_system_prompt(self):
        from backend.app.core.code_generation import PromptEngineer, GenerationContext
        ctx = GenerationContext(project_root="/p", file_path="/p/f.py", language="python")
        prompt = PromptEngineer.build_system_prompt(ctx)
        assert "python" in prompt.lower()


class TestCodeGenerationEngine:
    def test_engine_creation(self):
        from backend.app.core.code_generation import CodeGenerationEngine
        engine = CodeGenerationEngine()
        assert engine is not None


# ═══════════════════════════════════════════════════════════════════════════════
# CODE_FORMATTER MODULE
# ═══════════════════════════════════════════════════════════════════════════════

class TestCodeFormatter:
    def test_formatter_creation(self):
        from backend.app.core.code_formatter import CodeFormatter
        fmt = CodeFormatter()
        assert fmt.max_line_length == 100
        assert fmt.indent_size == 4

    def test_format_python_fallback(self):
        from backend.app.core.code_formatter import CodeFormatter
        fmt = CodeFormatter()
        code = "x=1\ny =  2\nz=x+y"
        result = fmt._format_python_fallback(code)
        assert "x = 1" in result
        assert "y = 2" in result

    def test_format_python(self):
        from backend.app.core.code_formatter import CodeFormatter
        fmt = CodeFormatter()
        code = "def foo():\n    return 1"
        result = fmt.format_python(code)
        assert "def foo" in result

    def test_format_javascript_fallback(self):
        from backend.app.core.code_formatter import CodeFormatter
        fmt = CodeFormatter()
        code = "const x=1;\nlet y =  2;"
        result = fmt._format_javascript_fallback(code)
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# LLM_EVALUATION MODULE
# ═══════════════════════════════════════════════════════════════════════════════

class TestLLMEvaluationEnums:
    def test_evaluation_metric_values(self):
        from backend.app.core.llm_evaluation import EvaluationMetric
        assert EvaluationMetric.ACCURACY == "accuracy"
        assert EvaluationMetric.RELEVANCE == "relevance"
        assert EvaluationMetric.SAFETY == "safety"

    def test_evaluation_method_values(self):
        from backend.app.core.llm_evaluation import EvaluationMethod
        assert EvaluationMethod.HUMAN == "human"
        assert EvaluationMethod.AUTOMATED == "automated"


class TestEvaluationScore:
    def test_score_creation(self):
        from backend.app.core.llm_evaluation import EvaluationScore, EvaluationMetric
        score = EvaluationScore(metric=EvaluationMetric.ACCURACY, score=0.95)
        assert score.metric == EvaluationMetric.ACCURACY
        assert score.score == 0.95
        assert score.confidence == 0.0


class TestLLMResponse:
    def test_response_creation(self):
        from backend.app.core.llm_evaluation import LLMResponse
        resp = LLMResponse(
            prompt="What is Python?",
            response="Python is a programming language.",
            model_name="gpt-4",
            provider="openai",
        )
        assert resp.model_name == "gpt-4"
        assert resp.response_id is not None


class TestEvaluation:
    def test_evaluation_creation(self):
        from backend.app.core.llm_evaluation import Evaluation, EvaluationMethod
        eval_obj = Evaluation(
            response_id="r1",
            method=EvaluationMethod.AUTOMATED,
        )
        assert eval_obj.method == EvaluationMethod.AUTOMATED
        assert eval_obj.scores == []

    def test_add_score_and_calculate(self):
        from backend.app.core.llm_evaluation import Evaluation, EvaluationMethod, EvaluationMetric
        eval_obj = Evaluation(response_id="r1", method=EvaluationMethod.HUMAN)
        eval_obj.add_score(EvaluationMetric.ACCURACY, 0.8)
        eval_obj.add_score(EvaluationMetric.RELEVANCE, 0.6)
        assert eval_obj.overall_score == pytest.approx(0.7)
        assert len(eval_obj.scores) == 2

    def test_calculate_overall_score_empty(self):
        from backend.app.core.llm_evaluation import Evaluation, EvaluationMethod
        eval_obj = Evaluation(response_id="r1", method=EvaluationMethod.HUMAN)
        assert eval_obj.calculate_overall_score() == 0.0


class TestEvaluationDataset:
    def test_dataset_creation(self):
        from backend.app.core.llm_evaluation import EvaluationDataset
        ds = EvaluationDataset(name="Test Dataset")
        assert ds.name == "Test Dataset"
        assert ds.size == 0

    def test_add_test_case(self):
        from backend.app.core.llm_evaluation import EvaluationDataset
        ds = EvaluationDataset(name="DS")
        ds.add_test_case("What is 2+2?", "4")
        assert ds.size == 1
        assert ds.test_cases[0]["prompt"] == "What is 2+2?"


class TestEvaluationRun:
    def test_run_creation(self):
        from backend.app.core.llm_evaluation import EvaluationRun
        run = EvaluationRun(
            dataset_id="ds1",
            model_name="gpt-4",
            provider="openai",
        )
        assert run.status == "running"
        assert run.run_id is not None


class TestLLMEvaluation:
    def test_evaluation_system_creation(self):
        from backend.app.core.llm_evaluation import LLMEvaluation
        system = LLMEvaluation()
        assert system is not None

    def test_record_response(self):
        from backend.app.core.llm_evaluation import LLMEvaluation
        system = LLMEvaluation()
        resp = system.record_response(
            prompt="test",
            response="answer",
            model_name="m",
            provider="p",
        )
        assert resp.response_id in system._responses
        assert resp.prompt == "test"
