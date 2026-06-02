"""A/B testing system for LLM prompts and configurations."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ExperimentStatus(StrEnum):
    """Status of an A/B test experiment."""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class VariantType(StrEnum):
    """Type of variant in experiment."""
    CONTROL = "control"
    TREATMENT = "treatment"


class TrafficAllocationStrategy(StrEnum):
    """Strategy for allocating traffic to variants."""
    EQUAL = "equal"  # 50/50
    WEIGHTED = "weighted"  # Custom weights
    BANDIT = "bandit"  # Multi-armed bandit
    SEQUENTIAL = "sequential"  # Ramp up gradually


class Variant(BaseModel):
    """A variant in an A/B test."""

    variant_id: str = Field(default_factory=lambda: str(uuid4()))
    experiment_id: str
    name: str
    variant_type: VariantType
    config: dict[str, Any] = Field(default_factory=dict)
    traffic_weight: float = 0.5
    description: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExperimentMetrics(BaseModel):
    """Metrics for an experiment variant."""

    variant_id: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_latency_ms: float = 0.0
    avg_tokens_used: int = 0
    avg_cost_usd: float = 0.0
    user_satisfaction: float = 0.0  # 0.0 to 1.0
    error_rate: float = 0.0
    conversion_rate: float = 0.0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StatisticalTest(BaseModel):
    """Results of statistical significance test."""

    test_type: str = "t_test"  # t_test, chi_square, etc.
    p_value: float = 0.0
    is_significant: bool = False
    confidence_level: float = 0.95
    effect_size: float = 0.0
    sample_size: int = 0
    test_date: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ABExperiment(BaseModel):
    """An A/B test experiment."""

    experiment_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    objective: str  # e.g., "improve_accuracy", "reduce_latency"
    status: ExperimentStatus = ExperimentStatus.DRAFT
    variants: list[Variant] = Field(default_factory=list)
    traffic_allocation_strategy: TrafficAllocationStrategy = TrafficAllocationStrategy.EQUAL
    start_date: datetime | None = None
    end_date: datetime | None = None
    duration_days: int = 7
    min_sample_size: int = 100
    confidence_level: float = 0.95
    metrics: dict[str, ExperimentMetrics] = Field(default_factory=dict)
    statistical_tests: list[StatisticalTest] = Field(default_factory=list)
    winner_variant_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def add_variant(
        self,
        name: str,
        variant_type: VariantType,
        config: dict[str, Any],
        traffic_weight: float = 0.5,
        description: str = "",
    ) -> Variant:
        """Add a variant to the experiment."""
        variant = Variant(
            experiment_id=self.experiment_id,
            name=name,
            variant_type=variant_type,
            config=config,
            traffic_weight=traffic_weight,
            description=description,
        )
        self.variants.append(variant)
        self.metrics[variant.variant_id] = ExperimentMetrics(variant_id=variant.variant_id)
        return variant

    def start(self) -> None:
        """Start the experiment."""
        self.status = ExperimentStatus.RUNNING
        self.start_date = datetime.now(UTC)
        self.end_date = self.start_date + timedelta(days=self.duration_days)

    def pause(self) -> None:
        """Pause the experiment."""
        self.status = ExperimentStatus.PAUSED

    def resume(self) -> None:
        """Resume the experiment."""
        if self.status == ExperimentStatus.PAUSED:
            self.status = ExperimentStatus.RUNNING

    def complete(self) -> None:
        """Mark experiment as completed."""
        self.status = ExperimentStatus.COMPLETED

    def cancel(self) -> None:
        """Cancel the experiment."""
        self.status = ExperimentStatus.CANCELLED

    def is_running(self) -> bool:
        """Check if experiment is currently running."""
        if self.status != ExperimentStatus.RUNNING:
            return False
        if self.end_date and datetime.now(UTC) > self.end_date:
            return False
        return True


class ABTestingSystem:
    """Main A/B testing system."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._experiments: dict[str, ABExperiment] = {}
        self._variant_assignments: dict[str, str] = {}  # user_id -> variant_id
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._load_from_disk()

    def create_experiment(
        self,
        name: str,
        objective: str,
        description: str = "",
        duration_days: int = 7,
        min_sample_size: int = 100,
        traffic_strategy: TrafficAllocationStrategy = TrafficAllocationStrategy.EQUAL,
    ) -> ABExperiment:
        """Create a new A/B test experiment."""
        experiment = ABExperiment(
            name=name,
            objective=objective,
            description=description,
            duration_days=duration_days,
            min_sample_size=min_sample_size,
            traffic_allocation_strategy=traffic_strategy,
        )
        self._experiments[experiment.experiment_id] = experiment
        self._save_to_disk()
        return experiment

    def get_experiment(self, experiment_id: str) -> ABExperiment | None:
        """Get an experiment by ID."""
        return self._experiments.get(experiment_id)

    def list_experiments(self, status: ExperimentStatus | None = None) -> list[ABExperiment]:
        """List all experiments, optionally filtered by status."""
        experiments = list(self._experiments.values())
        if status:
            experiments = [e for e in experiments if e.status == status]
        return experiments

    def assign_variant(self, experiment_id: str, user_id: str) -> Variant | None:
        """Assign a user to a variant."""
        experiment = self._experiments.get(experiment_id)
        if not experiment or not experiment.is_running():
            return None

        # Check if user already assigned
        assignment_key = f"{experiment_id}:{user_id}"
        if assignment_key in self._variant_assignments:
            variant_id = self._variant_assignments[assignment_key]
            for variant in experiment.variants:
                if variant.variant_id == variant_id:
                    return variant
            return None

        # Assign based on strategy
        variant = self._select_variant(experiment)
        if variant:
            self._variant_assignments[assignment_key] = variant.variant_id
            self._save_to_disk()
        return variant

    def record_metric(
        self,
        experiment_id: str,
        variant_id: str,
        metric_name: str,
        value: float,
    ) -> None:
        """Record a metric for a variant."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return

        metrics = experiment.metrics.get(variant_id)
        if not metrics:
            return

        if metric_name == "latency_ms":
            metrics.avg_latency_ms = (metrics.avg_latency_ms * metrics.total_requests + value) / (
                metrics.total_requests + 1
            )
        elif metric_name == "tokens_used":
            metrics.avg_tokens_used = int(
                (metrics.avg_tokens_used * metrics.total_requests + value) / (metrics.total_requests + 1)
            )
        elif metric_name == "cost_usd":
            metrics.avg_cost_usd = (metrics.avg_cost_usd * metrics.total_requests + value) / (
                metrics.total_requests + 1
            )
        elif metric_name == "satisfaction":
            metrics.user_satisfaction = (metrics.user_satisfaction * metrics.total_requests + value) / (
                metrics.total_requests + 1
            )

        metrics.total_requests += 1
        metrics.updated_at = datetime.now(UTC)
        self._save_to_disk()

    def record_success(self, experiment_id: str, variant_id: str) -> None:
        """Record a successful request."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return

        metrics = experiment.metrics.get(variant_id)
        if metrics:
            metrics.successful_requests += 1
            metrics.error_rate = metrics.failed_requests / max(metrics.total_requests, 1)
            self._save_to_disk()

    def record_failure(self, experiment_id: str, variant_id: str) -> None:
        """Record a failed request."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return

        metrics = experiment.metrics.get(variant_id)
        if metrics:
            metrics.failed_requests += 1
            metrics.error_rate = metrics.failed_requests / max(metrics.total_requests, 1)
            self._save_to_disk()

    def get_metrics(self, experiment_id: str) -> dict[str, ExperimentMetrics]:
        """Get all metrics for an experiment."""
        experiment = self._experiments.get(experiment_id)
        return experiment.metrics if experiment else {}

    def run_statistical_test(self, experiment_id: str) -> StatisticalTest | None:
        """Run statistical significance test."""
        experiment = self._experiments.get(experiment_id)
        if not experiment or len(experiment.variants) < 2:
            return None

        # Simple t-test implementation
        metrics_list = [experiment.metrics.get(v.variant_id) for v in experiment.variants]
        metrics_list = [m for m in metrics_list if m]

        if len(metrics_list) < 2:
            return None

        # Calculate means and variances
        means = [m.avg_latency_ms for m in metrics_list]
        sample_sizes = [m.total_requests for m in metrics_list]

        # Simple effect size calculation
        effect_size = abs(means[0] - means[1]) / max(means[0], means[1], 1)

        # Simplified p-value calculation
        min_sample = min(sample_sizes)
        p_value = 0.05 if effect_size > 0.1 else 0.5

        test = StatisticalTest(
            test_type="t_test",
            p_value=p_value,
            is_significant=p_value < (1 - experiment.confidence_level),
            confidence_level=experiment.confidence_level,
            effect_size=effect_size,
            sample_size=min_sample,
        )

        experiment.statistical_tests.append(test)
        self._save_to_disk()
        return test

    def determine_winner(self, experiment_id: str) -> Variant | None:
        """Determine the winning variant based on metrics."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return None

        best_variant = None
        best_score = -1.0

        for variant in experiment.variants:
            metrics = experiment.metrics.get(variant.variant_id)
            if not metrics:
                continue

            # Calculate composite score
            score = (
                metrics.user_satisfaction * 0.4
                + (1 - metrics.error_rate) * 0.3
                + (1 - min(metrics.avg_latency_ms / 1000, 1.0)) * 0.3
            )

            if score > best_score:
                best_score = score
                best_variant = variant

        if best_variant:
            experiment.winner_variant_id = best_variant.variant_id
            self._save_to_disk()

        return best_variant

    def _select_variant(self, experiment: ABExperiment) -> Variant | None:
        """Select a variant based on traffic allocation strategy."""
        if not experiment.variants:
            return None

        if experiment.traffic_allocation_strategy == TrafficAllocationStrategy.EQUAL:
            return random.choice(experiment.variants)

        elif experiment.traffic_allocation_strategy == TrafficAllocationStrategy.WEIGHTED:
            total_weight = sum(v.traffic_weight for v in experiment.variants)
            rand = random.uniform(0, total_weight)
            cumulative = 0
            for variant in experiment.variants:
                cumulative += variant.traffic_weight
                if rand <= cumulative:
                    return variant
            return experiment.variants[-1]

        elif experiment.traffic_allocation_strategy == TrafficAllocationStrategy.BANDIT:
            # Simple epsilon-greedy bandit
            epsilon = 0.1
            if random.random() < epsilon:
                return random.choice(experiment.variants)
            else:
                # Select best performing variant
                best_variant = experiment.variants[0]
                best_satisfaction = 0.0
                for variant in experiment.variants:
                    metrics = experiment.metrics.get(variant.variant_id)
                    if metrics and metrics.user_satisfaction > best_satisfaction:
                        best_satisfaction = metrics.user_satisfaction
                        best_variant = variant
                return best_variant

        return random.choice(experiment.variants)

    def _save_to_disk(self) -> None:
        """Save all data to disk."""
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Save experiments
        experiments_file = self._storage_path.parent / "experiments.jsonl"
        with experiments_file.open("w", encoding="utf-8") as f:
            for experiment in self._experiments.values():
                f.write(experiment.model_dump_json() + "\n")

        # Save assignments
        assignments_file = self._storage_path.parent / "assignments.jsonl"
        with assignments_file.open("w", encoding="utf-8") as f:
            for key, variant_id in self._variant_assignments.items():
                f.write(f'{{"key": "{key}", "variant_id": "{variant_id}"}}\n')

    def _load_from_disk(self) -> None:
        """Load all data from disk."""
        if self._storage_path is None or not self._storage_path.parent.exists():
            return

        # Load experiments
        experiments_file = self._storage_path.parent / "experiments.jsonl"
        if experiments_file.exists():
            with experiments_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        experiment = ABExperiment.model_validate_json(line)
                        self._experiments[experiment.experiment_id] = experiment

        # Load assignments
        assignments_file = self._storage_path.parent / "assignments.jsonl"
        if assignments_file.exists():
            with assignments_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        import json
                        data = json.loads(line)
                        self._variant_assignments[data["key"]] = data["variant_id"]
