"""API endpoints for LLM management system."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.core.llm_ab_testing import ExperimentStatus, TrafficAllocationStrategy, VariantType
from backend.app.core.llm_evaluation import EvaluationMethod, EvaluationMetric
from backend.app.core.llm_manager import LLMManager
from backend.app.core.llm_monitoring import AlertSeverity, MetricType
from backend.app.core.prompt_engineering import PromptType


# Request/Response Models
class CreateTemplateRequest(BaseModel):
    """Request to create a prompt template."""

    name: str
    content: str
    prompt_type: PromptType = PromptType.USER
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class CreateVersionRequest(BaseModel):
    """Request to create a prompt version."""

    template_id: str
    content: str
    changes: str = ""


class CreateExperimentRequest(BaseModel):
    """Request to create an A/B test experiment."""

    name: str
    objective: str
    description: str = ""
    duration_days: int = 7
    traffic_strategy: TrafficAllocationStrategy = TrafficAllocationStrategy.EQUAL


class AddVariantRequest(BaseModel):
    """Request to add a variant to an experiment."""

    experiment_id: str
    name: str
    variant_type: VariantType
    config: dict[str, Any] = Field(default_factory=dict)
    traffic_weight: float = 0.5


class RecordMetricRequest(BaseModel):
    """Request to record a metric."""

    metric_type: MetricType
    value: float
    model_name: str = ""
    provider: str = ""


class CreateAlertRuleRequest(BaseModel):
    """Request to create an alert rule."""

    name: str
    metric_type: MetricType
    condition: str
    threshold: float
    severity: AlertSeverity


class RecordResponseRequest(BaseModel):
    """Request to record an LLM response."""

    prompt: str
    response: str
    model_name: str
    provider: str


class CreateDatasetRequest(BaseModel):
    """Request to create an evaluation dataset."""

    name: str
    description: str = ""


class AddTestCaseRequest(BaseModel):
    """Request to add a test case to a dataset."""

    dataset_id: str
    prompt: str
    expected_output: str


class CreateEvaluationRunRequest(BaseModel):
    """Request to create an evaluation run."""

    dataset_id: str
    model_name: str
    provider: str


class LLMAPIHandler:
    """Handler for LLM management API endpoints."""

    def __init__(self, manager: LLMManager) -> None:
        self.manager = manager

    # Prompt Engineering Endpoints
    def create_template(self, request: CreateTemplateRequest) -> dict[str, Any]:
        """Create a new prompt template."""
        template = self.manager.prompt_engineering.create_template(
            name=request.name,
            content=request.content,
            prompt_type=request.prompt_type,
            description=request.description,
            tags=request.tags,
        )
        return {
            "success": True,
            "template_id": template.template_id,
            "template": template.model_dump(),
        }

    def get_template(self, template_id: str) -> dict[str, Any]:
        """Get a template by ID."""
        template = self.manager.prompt_engineering.get_template(template_id)
        if not template:
            return {"success": False, "error": "Template not found"}
        return {
            "success": True,
            "template": template.model_dump(),
        }

    def list_templates(self, tags: list[str] | None = None) -> dict[str, Any]:
        """List all templates."""
        templates = self.manager.prompt_engineering.list_templates(tags=tags)
        return {
            "success": True,
            "count": len(templates),
            "templates": [t.model_dump() for t in templates],
        }

    def create_version(self, request: CreateVersionRequest) -> dict[str, Any]:
        """Create a new version of a template."""
        version = self.manager.prompt_engineering.create_version(
            template_id=request.template_id,
            content=request.content,
            changes=request.changes,
        )
        if not version:
            return {"success": False, "error": "Template not found"}
        return {
            "success": True,
            "version_id": version.version_id,
            "version": version.model_dump(),
        }

    def list_versions(self, template_id: str) -> dict[str, Any]:
        """List all versions of a template."""
        versions = self.manager.prompt_engineering.list_versions(template_id)
        return {
            "success": True,
            "count": len(versions),
            "versions": [v.model_dump() for v in versions],
        }

    def activate_version(self, template_id: str, version: int) -> dict[str, Any]:
        """Activate a specific version."""
        result = self.manager.prompt_engineering.activate_version(template_id, version)
        if not result:
            return {"success": False, "error": "Version not found"}
        return {
            "success": True,
            "version": result.model_dump(),
        }

    # A/B Testing Endpoints
    def create_experiment(self, request: CreateExperimentRequest) -> dict[str, Any]:
        """Create an A/B test experiment."""
        experiment = self.manager.ab_testing.create_experiment(
            name=request.name,
            objective=request.objective,
            description=request.description,
            duration_days=request.duration_days,
            traffic_strategy=request.traffic_strategy,
        )
        return {
            "success": True,
            "experiment_id": experiment.experiment_id,
            "experiment": experiment.model_dump(),
        }

    def get_experiment(self, experiment_id: str) -> dict[str, Any]:
        """Get an experiment by ID."""
        experiment = self.manager.ab_testing.get_experiment(experiment_id)
        if not experiment:
            return {"success": False, "error": "Experiment not found"}
        return {
            "success": True,
            "experiment": experiment.model_dump(),
        }

    def list_experiments(self, status: ExperimentStatus | None = None) -> dict[str, Any]:
        """List experiments."""
        experiments = self.manager.ab_testing.list_experiments(status=status)
        return {
            "success": True,
            "count": len(experiments),
            "experiments": [e.model_dump() for e in experiments],
        }

    def add_variant(self, request: AddVariantRequest) -> dict[str, Any]:
        """Add a variant to an experiment."""
        experiment = self.manager.ab_testing.get_experiment(request.experiment_id)
        if not experiment:
            return {"success": False, "error": "Experiment not found"}

        variant = self.manager.ab_testing.add_variant(
            request.experiment_id,
            name=request.name,
            variant_type=request.variant_type,
            config=request.config,
            traffic_weight=request.traffic_weight,
        )
        return {
            "success": True,
            "variant_id": variant.variant_id,
            "variant": variant.model_dump(),
        }

    def start_experiment(self, experiment_id: str) -> dict[str, Any]:
        """Start an experiment."""
        experiment = self.manager.ab_testing.get_experiment(experiment_id)
        if not experiment:
            return {"success": False, "error": "Experiment not found"}
        experiment.start()
        return {
            "success": True,
            "experiment": experiment.model_dump(),
        }

    def get_experiment_metrics(self, experiment_id: str) -> dict[str, Any]:
        """Get metrics for an experiment."""
        experiment = self.manager.ab_testing.get_experiment(experiment_id)
        if not experiment:
            return {"success": False, "error": "Experiment not found"}

        metrics = self.manager.ab_testing.get_metrics(experiment_id)
        return {
            "success": True,
            "metrics": {k: v.model_dump() for k, v in metrics.items()},
        }

    def determine_winner(self, experiment_id: str) -> dict[str, Any]:
        """Determine the winning variant."""
        winner = self.manager.ab_testing.determine_winner(experiment_id)
        if not winner:
            return {"success": False, "error": "Could not determine winner"}
        return {
            "success": True,
            "winner": winner.model_dump(),
        }

    # Monitoring Endpoints
    def record_metric(self, request: RecordMetricRequest) -> dict[str, Any]:
        """Record a metric."""
        metric = self.manager.monitoring.record_metric(
            metric_type=request.metric_type,
            value=request.value,
            model_name=request.model_name,
            provider=request.provider,
        )
        return {
            "success": True,
            "metric_id": metric.metric_id,
        }

    def get_metrics(
        self,
        metric_type: MetricType | None = None,
        model_name: str | None = None,
        hours: int = 24,
    ) -> dict[str, Any]:
        """Get metrics."""
        metrics = self.manager.monitoring.get_metrics(
            metric_type=metric_type,
            model_name=model_name,
            hours=hours,
        )
        return {
            "success": True,
            "count": len(metrics),
            "metrics": [m.model_dump() for m in metrics],
        }

    def get_performance_summary(self, hours: int = 24) -> dict[str, Any]:
        """Get performance summary."""
        summary = self.manager.monitoring.get_performance_summary(hours=hours)
        return {
            "success": True,
            "summary": summary,
        }

    def get_cost_summary(self, hours: int = 24) -> dict[str, Any]:
        """Get cost summary."""
        summary = self.manager.monitoring.get_cost_summary(hours=hours)
        return {
            "success": True,
            "summary": summary,
        }

    def create_alert_rule(self, request: CreateAlertRuleRequest) -> dict[str, Any]:
        """Create an alert rule."""
        rule = self.manager.monitoring.create_alert_rule(
            name=request.name,
            metric_type=request.metric_type,
            condition=request.condition,
            threshold=request.threshold,
            severity=request.severity,
        )
        return {
            "success": True,
            "rule_id": rule.rule_id,
            "rule": rule.model_dump(),
        }

    def get_alerts(self, resolved: bool | None = None, hours: int = 24) -> dict[str, Any]:
        """Get alerts."""
        alerts = self.manager.monitoring.get_alerts(resolved=resolved, hours=hours)
        return {
            "success": True,
            "count": len(alerts),
            "alerts": [a.model_dump() for a in alerts],
        }

    # Evaluation Endpoints
    def record_response(self, request: RecordResponseRequest) -> dict[str, Any]:
        """Record an LLM response."""
        response = self.manager.evaluation.record_response(
            prompt=request.prompt,
            response=request.response,
            model_name=request.model_name,
            provider=request.provider,
        )
        return {
            "success": True,
            "response_id": response.response_id,
        }

    def evaluate_response(self, response_id: str) -> dict[str, Any]:
        """Evaluate a response."""
        evaluation = self.manager.evaluation.evaluate_response(
            response_id,
            method=EvaluationMethod.AUTOMATED,
        )
        if not evaluation:
            return {"success": False, "error": "Response not found"}
        return {
            "success": True,
            "evaluation_id": evaluation.evaluation_id,
            "evaluation": evaluation.model_dump(),
        }

    def create_dataset(self, request: CreateDatasetRequest) -> dict[str, Any]:
        """Create an evaluation dataset."""
        dataset = self.manager.evaluation.create_dataset(
            name=request.name,
            description=request.description,
        )
        return {
            "success": True,
            "dataset_id": dataset.dataset_id,
            "dataset": dataset.model_dump(),
        }

    def list_datasets(self) -> dict[str, Any]:
        """List datasets."""
        datasets = self.manager.evaluation.list_datasets()
        return {
            "success": True,
            "count": len(datasets),
            "datasets": [d.model_dump() for d in datasets],
        }

    def add_test_case(self, request: AddTestCaseRequest) -> dict[str, Any]:
        """Add a test case to a dataset."""
        success = self.manager.evaluation.add_test_case(
            dataset_id=request.dataset_id,
            prompt=request.prompt,
            expected_output=request.expected_output,
        )
        if not success:
            return {"success": False, "error": "Dataset not found"}
        return {"success": True}

    def create_evaluation_run(self, request: CreateEvaluationRunRequest) -> dict[str, Any]:
        """Create an evaluation run."""
        run = self.manager.evaluation.create_evaluation_run(
            dataset_id=request.dataset_id,
            model_name=request.model_name,
            provider=request.provider,
        )
        if not run:
            return {"success": False, "error": "Dataset not found"}
        return {
            "success": True,
            "run_id": run.run_id,
            "run": run.model_dump(),
        }

    def get_evaluation_report(self, run_id: str) -> dict[str, Any]:
        """Get evaluation report."""
        report = self.manager.evaluation.get_evaluation_report(run_id)
        if not report:
            return {"success": False, "error": "Run not found"}
        return {
            "success": True,
            "report": report,
        }

    # Dashboard Endpoints
    def get_comprehensive_report(self) -> dict[str, Any]:
        """Get comprehensive report."""
        report = self.manager.get_comprehensive_report()
        return {
            "success": True,
            "report": report,
        }

    def get_dashboard_metrics(self) -> dict[str, Any]:
        """Get metrics for dashboard."""
        metrics = self.manager.export_metrics_for_dashboard()
        return {
            "success": True,
            "metrics": metrics,
        }

    def get_recommendations(self) -> dict[str, Any]:
        """Get optimization recommendations."""
        recommendations = self.manager.get_optimization_recommendations()
        return {
            "success": True,
            "count": len(recommendations),
            "recommendations": recommendations,
        }
