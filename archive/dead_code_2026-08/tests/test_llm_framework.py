"""Tests for LLM framework components."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from backend.app.core.llm_ab_testing import ABTestingSystem, ExperimentStatus, TrafficAllocationStrategy, VariantType
from backend.app.core.llm_api import (
    AddTestCaseRequest,
    AddVariantRequest,
    CreateAlertRuleRequest,
    CreateDatasetRequest,
    CreateExperimentRequest,
    CreateTemplateRequest,
    CreateVersionRequest,
    LLMAPIHandler,
    RecordMetricRequest,
    RecordResponseRequest,
)
from backend.app.core.llm_evaluation import EvaluationMethod, LLMEvaluation
from backend.app.core.llm_manager import LLMManager
from backend.app.core.llm_monitoring import AlertSeverity, LLMMonitoring, MetricType
from backend.app.core.prompt_engineering import PromptEngineering, PromptType


class TestPromptEngineering:
    """Tests for prompt engineering framework."""

    def test_create_template(self):
        """Test creating a prompt template."""
        pe = PromptEngineering()
        template = pe.create_template(
            name="Test Template",
            content="Hello {name}, how are you?",
            prompt_type=PromptType.USER,
        )
        assert template.name == "Test Template"
        assert template.variables == ["name"]

    def test_format_template(self):
        """Test formatting a template."""
        pe = PromptEngineering()
        template = pe.create_template(
            name="Test",
            content="Hello {name}",
        )
        result = template.format(name="World")
        assert result == "Hello World"

    def test_create_version(self):
        """Test creating a template version."""
        pe = PromptEngineering()
        template = pe.create_template(
            name="Test",
            content="Original content",
        )
        version = pe.create_version(
            template.template_id,
            "Updated content",
            changes="Improved clarity",
        )
        assert version.version == 1
        assert version.content == "Updated content"

    def test_activate_version(self):
        """Test activating a version."""
        pe = PromptEngineering()
        template = pe.create_template(
            name="Test",
            content="Original",
        )
        v1 = pe.create_version(template.template_id, "Version 1")
        v2 = pe.create_version(template.template_id, "Version 2")

        pe.activate_version(template.template_id, 2)
        active = pe.get_active_version(template.template_id)
        assert active.version == 2

    def test_few_shot_examples(self):
        """Test few-shot example management."""
        pe = PromptEngineering()
        template = pe.create_template(
            name="Test",
            content="Classify: {text}",
        )
        example = pe.add_few_shot_example(
            template.template_id,
            input_text="This is great",
            output_text="positive",
        )
        assert example is not None
        examples = pe.get_few_shot_examples(template.template_id)
        assert len(examples) == 1


class TestABTesting:
    """Tests for A/B testing system."""

    def test_create_experiment(self):
        """Test creating an experiment."""
        ab = ABTestingSystem()
        exp = ab.create_experiment(
            name="Test Experiment",
            objective="improve_quality",
        )
        assert exp.name == "Test Experiment"
        assert exp.status == ExperimentStatus.DRAFT

    def test_add_variants(self):
        """Test adding variants to experiment."""
        ab = ABTestingSystem()
        exp = ab.create_experiment(
            name="Test",
            objective="test",
        )
        v1 = exp.add_variant(
            name="Control",
            variant_type=VariantType.CONTROL,
            config={"version": 1},
        )
        v2 = exp.add_variant(
            name="Treatment",
            variant_type=VariantType.TREATMENT,
            config={"version": 2},
        )
        assert len(exp.variants) == 2

    def test_start_experiment(self):
        """Test starting an experiment."""
        ab = ABTestingSystem()
        exp = ab.create_experiment(
            name="Test",
            objective="test",
        )
        exp.start()
        assert exp.status == ExperimentStatus.RUNNING
        assert exp.is_running()

    def test_assign_variant(self):
        """Test assigning user to variant."""
        ab = ABTestingSystem()
        exp = ab.create_experiment(
            name="Test",
            objective="test",
        )
        exp.add_variant("Control", VariantType.CONTROL, {})
        exp.add_variant("Treatment", VariantType.TREATMENT, {})
        exp.start()

        variant = ab.assign_variant(exp.experiment_id, "user123")
        assert variant is not None

    def test_record_metrics(self):
        """Test recording metrics."""
        ab = ABTestingSystem()
        exp = ab.create_experiment(
            name="Test",
            objective="test",
        )
        variant = exp.add_variant("Control", VariantType.CONTROL, {})
        exp.start()

        ab.record_metric(exp.experiment_id, variant.variant_id, "latency_ms", 100.0)
        ab.record_success(exp.experiment_id, variant.variant_id)

        metrics = ab.get_metrics(exp.experiment_id)
        assert metrics[variant.variant_id].total_requests == 1


class TestMonitoring:
    """Tests for monitoring system."""

    def test_record_metric(self):
        """Test recording a metric."""
        mon = LLMMonitoring()
        metric = mon.record_metric(
            metric_type=MetricType.LATENCY,
            value=100.0,
            model_name="gpt-4",
        )
        assert metric.value == 100.0

    def test_record_cost(self):
        """Test recording cost."""
        mon = LLMMonitoring()
        cost = mon.record_cost(
            model_name="gpt-4",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            input_price_per_1k=0.03,
            output_price_per_1k=0.06,
        )
        assert cost.total_tokens == 150
        assert cost.cost_usd > 0

    def test_alert_rules(self):
        """Test alert rules."""
        mon = LLMMonitoring()
        rule = mon.create_alert_rule(
            name="High Latency",
            metric_type=MetricType.LATENCY,
            condition="greater_than",
            threshold=5000.0,
            severity=AlertSeverity.WARNING,
        )
        assert rule.name == "High Latency"

    def test_performance_summary(self):
        """Test performance summary."""
        mon = LLMMonitoring()
        mon.record_metric(MetricType.LATENCY, 100.0)
        mon.record_metric(MetricType.LATENCY, 200.0)

        summary = mon.get_performance_summary(hours=24)
        assert summary["avg_latency_ms"] > 0


class TestEvaluation:
    """Tests for evaluation system."""

    def test_record_response(self):
        """Test recording a response."""
        ev = LLMEvaluation()
        response = ev.record_response(
            prompt="What is 2+2?",
            response="4",
            model_name="gpt-4",
            provider="openai",
        )
        assert response.prompt == "What is 2+2?"

    def test_evaluate_response(self):
        """Test evaluating a response."""
        ev = LLMEvaluation()
        response = ev.record_response(
            prompt="What is 2+2?",
            response="The answer is 4",
            model_name="gpt-4",
            provider="openai",
        )
        evaluation = ev.evaluate_response(response.response_id)
        assert evaluation is not None
        assert evaluation.overall_score > 0

    def test_create_dataset(self):
        """Test creating a dataset."""
        ev = LLMEvaluation()
        dataset = ev.create_dataset(
            name="Test Dataset",
            description="Test",
        )
        assert dataset.name == "Test Dataset"

    def test_add_test_case(self):
        """Test adding test case."""
        ev = LLMEvaluation()
        dataset = ev.create_dataset(name="Test")
        ev.add_test_case(
            dataset.dataset_id,
            prompt="What is 2+2?",
            expected_output="4",
        )
        assert dataset.size == 1

    def test_evaluation_run(self):
        """Test evaluation run."""
        ev = LLMEvaluation()
        dataset = ev.create_dataset(name="Test")
        ev.add_test_case(dataset.dataset_id, "What is 2+2?", "4")

        run = ev.create_evaluation_run(
            dataset.dataset_id,
            model_name="gpt-4",
            provider="openai",
        )
        assert run is not None
        assert run.status == "running"


class TestLLMManager:
    """Tests for integrated LLM manager."""

    def test_setup_prompt_optimization(self):
        """Test setting up prompt optimization workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LLMManager(tmpdir)
            result = manager.setup_prompt_optimization_workflow(
                template_name="Test",
                template_content="Hello {name}",
                test_cases=[
                    {"prompt": "Say hello", "expected_output": "Hello"},
                ],
            )
            assert "template_id" in result
            assert "dataset_id" in result

    def test_setup_ab_test(self):
        """Test setting up A/B test."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LLMManager(tmpdir)
            template = manager.prompt_engineering.create_template(
                name="Test",
                content="Test",
            )
            result = manager.setup_ab_test_for_prompts(
                experiment_name="Test",
                template_id=template.template_id,
                variant_configs=[
                    {"name": "Control", "version": 1},
                    {"name": "Treatment", "version": 2},
                ],
            )
            assert "experiment_id" in result

    def test_setup_monitoring_alerts(self):
        """Test setting up monitoring alerts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LLMManager(tmpdir)
            result = manager.setup_monitoring_alerts()
            assert result["count"] == 4

    def test_comprehensive_report(self):
        """Test comprehensive report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LLMManager(tmpdir)
            report = manager.get_comprehensive_report()
            assert "prompt_engineering" in report
            assert "ab_testing" in report
            assert "monitoring" in report
            assert "evaluation" in report


class TestLLMAPI:
    """Tests for API handler."""

    def test_create_template_api(self):
        """Test creating template via API."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LLMManager(tmpdir)
            handler = LLMAPIHandler(manager)

            request = CreateTemplateRequest(
                name="Test",
                content="Hello {name}",
            )
            result = handler.create_template(request)
            assert result["success"]
            assert "template_id" in result

    def test_create_experiment_api(self):
        """Test creating experiment via API."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LLMManager(tmpdir)
            handler = LLMAPIHandler(manager)

            request = CreateExperimentRequest(
                name="Test",
                objective="test",
            )
            result = handler.create_experiment(request)
            assert result["success"]

    def test_record_metric_api(self):
        """Test recording metric via API."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LLMManager(tmpdir)
            handler = LLMAPIHandler(manager)

            request = RecordMetricRequest(
                metric_type=MetricType.LATENCY,
                value=100.0,
            )
            result = handler.record_metric(request)
            assert result["success"]

    def test_dashboard_metrics_api(self):
        """Test getting dashboard metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LLMManager(tmpdir)
            handler = LLMAPIHandler(manager)

            result = handler.get_dashboard_metrics()
            assert result["success"]
            assert "metrics" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
