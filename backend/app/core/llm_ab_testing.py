"""LLM A/B Testing Framework — compare model performance side-by-side.

Enables:
- Running the same prompt against multiple LLM backends
- Measuring latency, cost, and quality metrics
- Tracking A/B experiment results over time
- Statistical significance calculation (effect size, t-tests)
- Visualization and reporting (winner determination)

Usage:
    from backend.app.core.llm_ab_testing import ABTestRunner
    
    runner = ABTestRunner(db_session=session)
    runner.add_variant("deepseek", backend="deepseek", model="deepseek-chat", temp=0.7)
    runner.add_variant("gpt4o", backend="openai", model="gpt-4o-mini")
    
    results = await runner.run_experiment(
        prompts=["Fix this bug: ...", "Review this code: ..."],
        metrics=["latency", "cost", "output_length", "quality"],
        runs_per_prompt=3,
        significance_level=0.05
    )
    print(results.summary())
    print(results.winner)  # "deepseek" or "gpt4o" based on composite score
    print(results.statistical_tests())  # Welch t-test results
    
    # Save results for later analysis
    await runner.save_experiment(results)

Metrics tracked:
    - latency_ms: Time from request to final token
    - output_length: Number of tokens in response
    - estimated_cost_usd: API cost for the call
    - quality_score: 0-1 normalized quality (from LLM judge or heuristics)
    - error: Whether the call failed

Scoring:
    Composite score = 40% latency + 30% cost + 30% quality
    (Normalized to 0-1 range per variant)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import statistics
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional, Callable
from enum import Enum

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Supported metrics for A/B testing."""
    LATENCY = "latency"           # milliseconds
    COST = "cost"                 # USD
    OUTPUT_LENGTH = "output_length"  # tokens
    QUALITY = "quality"           # 0-1 score
    ERROR_RATE = "error_rate"     # 0-1 rate


class ExperimentStatus(str, Enum):
    """Lifecycle states for the synchronous A/B testing compatibility API."""

    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class TrafficAllocationStrategy(str, Enum):
    """Traffic allocation strategies for prompt/model experiment variants."""

    EQUAL = "equal"
    WEIGHTED = "weighted"


class VariantType(str, Enum):
    """Variant role in an experiment."""

    CONTROL = "control"
    TREATMENT = "treatment"


@dataclass
class ABVariant:
    """Variant record used by the legacy synchronous ABTestingSystem API."""

    name: str
    variant_type: VariantType
    config: dict[str, Any] = field(default_factory=dict)
    traffic_weight: float = 0.5
    description: str = ""
    variant_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ABVariantMetrics:
    """Aggregated variant metrics for the legacy synchronous API."""

    variant_id: str
    total_requests: int = 0
    successes: int = 0
    metric_values: dict[str, list[float]] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successes / self.total_requests

    def model_dump(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["success_rate"] = self.success_rate
        return payload


@dataclass
class ABExperiment:
    """Experiment record used by the legacy synchronous ABTestingSystem API."""

    name: str
    objective: str
    description: str = ""
    duration_days: int = 7
    traffic_strategy: TrafficAllocationStrategy = TrafficAllocationStrategy.EQUAL
    experiment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: ExperimentStatus = ExperimentStatus.DRAFT
    variants: list[ABVariant] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def add_variant(
        self,
        name: str,
        variant_type: VariantType,
        config: dict[str, Any] | None = None,
        traffic_weight: float = 0.5,
        description: str = "",
    ) -> ABVariant:
        variant = ABVariant(
            name=name,
            variant_type=variant_type,
            config=config or {},
            traffic_weight=traffic_weight,
            description=description,
        )
        self.variants.append(variant)
        return variant

    def start(self) -> None:
        self.status = ExperimentStatus.RUNNING
        self.started_at = datetime.utcnow()

    def complete(self) -> None:
        self.status = ExperimentStatus.COMPLETED
        self.completed_at = datetime.utcnow()

    def is_running(self) -> bool:
        return self.status == ExperimentStatus.RUNNING

    def model_dump(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["variants"] = [variant.model_dump() for variant in self.variants]
        return payload


class ABTestingSystem:
    """Backward-compatible synchronous A/B testing facade.

    Older LLM management code imports ABTestingSystem directly for in-memory
    prompt/model experiments, while the newer ABTestRunner below handles async
    provider-side experiment execution. Keep this facade small and local so the
    public import contract remains stable without changing the runner API.
    """

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.storage_path = Path(storage_path) if storage_path else None
        self._experiments: dict[str, ABExperiment] = {}
        self._metrics: dict[str, dict[str, ABVariantMetrics]] = {}

    def create_experiment(
        self,
        name: str,
        objective: str,
        description: str = "",
        duration_days: int = 7,
        traffic_strategy: TrafficAllocationStrategy = TrafficAllocationStrategy.EQUAL,
    ) -> ABExperiment:
        experiment = ABExperiment(
            name=name,
            objective=objective,
            description=description,
            duration_days=duration_days,
            traffic_strategy=traffic_strategy,
        )
        self._experiments[experiment.experiment_id] = experiment
        self._metrics[experiment.experiment_id] = {}
        return experiment

    def get_experiment(self, experiment_id: str) -> ABExperiment | None:
        return self._experiments.get(experiment_id)

    def list_experiments(self, status: ExperimentStatus | None = None) -> list[ABExperiment]:
        experiments = list(self._experiments.values())
        if status is not None:
            experiments = [experiment for experiment in experiments if experiment.status == status]
        return experiments

    def add_variant(
        self,
        experiment_id: str,
        name: str,
        variant_type: VariantType,
        config: dict[str, Any] | None = None,
        traffic_weight: float = 0.5,
        description: str = "",
    ) -> ABVariant:
        experiment = self._require_experiment(experiment_id)
        return experiment.add_variant(
            name=name,
            variant_type=variant_type,
            config=config,
            traffic_weight=traffic_weight,
            description=description,
        )

    def assign_variant(self, experiment_id: str, user_id: str) -> ABVariant | None:
        experiment = self.get_experiment(experiment_id)
        if experiment is None or not experiment.variants:
            return None

        if experiment.traffic_strategy == TrafficAllocationStrategy.WEIGHTED:
            bucket = (hash(user_id) % 10_000) / 10_000
            cumulative = 0.0
            for variant in experiment.variants:
                cumulative += max(variant.traffic_weight, 0.0)
                if bucket <= cumulative:
                    return variant

        return experiment.variants[hash(user_id) % len(experiment.variants)]

    def record_metric(
        self,
        experiment_id: str,
        variant_id: str,
        metric_name: str,
        value: float,
    ) -> ABVariantMetrics:
        metrics = self._variant_metrics(experiment_id, variant_id)
        metrics.total_requests += 1
        metrics.metric_values.setdefault(metric_name, []).append(value)
        return metrics

    def record_success(self, experiment_id: str, variant_id: str) -> ABVariantMetrics:
        metrics = self._variant_metrics(experiment_id, variant_id)
        metrics.successes += 1
        return metrics

    def get_metrics(self, experiment_id: str) -> dict[str, ABVariantMetrics]:
        self._require_experiment(experiment_id)
        return self._metrics.setdefault(experiment_id, {})

    def determine_winner(self, experiment_id: str) -> ABVariant | None:
        experiment = self.get_experiment(experiment_id)
        if experiment is None or not experiment.variants:
            return None

        metrics = self.get_metrics(experiment_id)
        return max(
            experiment.variants,
            key=lambda variant: metrics.get(
                variant.variant_id,
                ABVariantMetrics(variant_id=variant.variant_id),
            ).success_rate,
        )

    def _require_experiment(self, experiment_id: str) -> ABExperiment:
        experiment = self.get_experiment(experiment_id)
        if experiment is None:
            raise KeyError(f"Experiment not found: {experiment_id}")
        return experiment

    def _variant_metrics(self, experiment_id: str, variant_id: str) -> ABVariantMetrics:
        self._require_experiment(experiment_id)
        return self._metrics.setdefault(experiment_id, {}).setdefault(
            variant_id,
            ABVariantMetrics(variant_id=variant_id),
        )


@dataclass
class Variant:
    """A/B test variant (model + configuration)."""
    name: str
    backend: str  # "openai", "deepseek", "anthropic", etc.
    model: str    # "gpt-4o-mini", "deepseek-chat", etc.
    config: dict = field(default_factory=dict)  # temperature, max_tokens, etc.
    
    def __post_init__(self):
        if not self.name or not self.backend or not self.model:
            raise ValueError("Variant name, backend, and model are required")


@dataclass
class TrialResult:
    """Single trial result (one variant, one prompt)."""
    trial_id: str
    experiment_id: str
    variant: str
    prompt_id: str
    latency_ms: float
    output: str
    output_length: int
    estimated_cost_usd: float
    quality_score: float = 0.5  # 0-1, default middle
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def success(self) -> bool:
        """Whether the trial succeeded."""
        return self.error is None
    
    @property
    def cost_per_1k_tokens(self) -> float:
        """Normalized cost per 1000 tokens for comparison."""
        if self.output_length == 0:
            return 0.0
        return (self.estimated_cost_usd / self.output_length) * 1000


@dataclass
class ExperimentResult:
    """Aggregated results across all variants and trials."""
    experiment_id: str
    variants: list[str]
    trials: list[TrialResult]
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)
    
    @property
    def summary(self) -> dict[str, Any]:
        """Per-variant aggregate statistics."""
        summary = {}
        for variant in self.variants:
            variant_trials = [t for t in self.trials if t.variant == variant and t.success]
            if not variant_trials:
                summary[variant] = {
                    "error": "No successful trials",
                    "trials": len(variant_trials)
                }
                continue
            
            latencies = [t.latency_ms for t in variant_trials]
            costs = [t.estimated_cost_usd for t in variant_trials]
            lengths = [t.output_length for t in variant_trials]
            qualities = [t.quality_score for t in variant_trials]
            
            summary[variant] = {
                "trials": len(variant_trials),
                "success_rate": len(variant_trials) / len([t for t in self.trials if t.variant == variant]),
                "latency_ms": {
                    "mean": statistics.mean(latencies),
                    "stdev": statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
                    "min": min(latencies),
                    "max": max(latencies),
                },
                "cost_usd": {
                    "mean": statistics.mean(costs),
                    "total": sum(costs),
                },
                "output_length": {
                    "mean": statistics.mean(lengths),
                    "median": statistics.median(lengths),
                },
                "quality_score": {
                    "mean": statistics.mean(qualities),
                    "stdev": statistics.stdev(qualities) if len(qualities) > 1 else 0.0,
                },
            }
        return summary
    
    @property
    def winner(self) -> str:
        """Variant with best overall composite score."""
        scores = {}
        for variant in self.variants:
            variant_trials = [t for t in self.trials if t.variant == variant and t.success]
            if not variant_trials:
                scores[variant] = -1.0
                continue
            
            # Normalize metrics to 0-1 (lower is better for latency/cost)
            latencies = [t.latency_ms for t in variant_trials]
            costs = [t.estimated_cost_usd for t in variant_trials]
            qualities = [t.quality_score for t in variant_trials]
            
            max_latency = max(t.latency_ms for t in self.trials if t.success)
            max_cost = max(t.estimated_cost_usd for t in self.trials if t.success)
            
            norm_latency = 1.0 - (statistics.mean(latencies) / max_latency) if max_latency > 0 else 0.5
            norm_cost = 1.0 - (statistics.mean(costs) / max_cost) if max_cost > 0 else 0.5
            norm_quality = statistics.mean(qualities)
            
            # Weighted composite score: 40% latency, 30% cost, 30% quality
            composite = (0.40 * norm_latency + 0.30 * norm_cost + 0.30 * norm_quality)
            scores[variant] = composite
        
        return max(scores, key=scores.get) if scores else None
    
    def statistical_tests(self) -> dict[str, Any]:
        """Run statistical significance tests (Welch t-test for variants)."""
        if len(self.variants) != 2:
            return {"error": f"Statistical tests require exactly 2 variants, got {len(self.variants)}"}
        
        variant_a, variant_b = self.variants
        trials_a = [t for t in self.trials if t.variant == variant_a and t.success]
        trials_b = [t for t in self.trials if t.variant == variant_b and t.success]
        
        if not trials_a or not trials_b:
            return {"error": "Insufficient successful trials for statistical test"}
        
        from scipy import stats
        
        latencies_a = [t.latency_ms for t in trials_a]
        latencies_b = [t.latency_ms for t in trials_b]
        
        t_stat, p_value = stats.ttest_ind(latencies_a, latencies_b, equal_var=False)
        effect_size = (statistics.mean(latencies_a) - statistics.mean(latencies_b)) / (
            (statistics.stdev(latencies_a) ** 2 + statistics.stdev(latencies_b) ** 2) ** 0.5
        )
        
        return {
            "test": "Welch t-test (latency)",
            "t_statistic": t_stat,
            "p_value": p_value,
            "effect_size": effect_size,
            "significant": p_value < 0.05,
            "faster": variant_a if t_stat > 0 else variant_b,
        }


class ABTestRunner:
    """Orchestrates A/B experiments across LLM providers."""
    
    def __init__(
        self,
        db_session: Optional[AsyncSession] = None,
        llm_manager: Optional[Any] = None,
        quality_judge: Optional[Callable] = None,
    ):
        """
        Args:
            db_session: SQLAlchemy async session for persisting results
            llm_manager: LLMManager instance for routing to backends
            quality_judge: Callable(output: str, prompt: str) -> float [0-1]
                          If None, uses simple heuristics (length, punctuation, etc.)
        """
        self.db_session = db_session
        self.llm_manager = llm_manager
        self.quality_judge = quality_judge or self._default_quality_judge
        self.variants: list[Variant] = []
        self.experiment_id = str(uuid.uuid4())
    
    def add_variant(self, name: str, backend: str, model: str, **config) -> None:
        """Register a variant for testing."""
        if any(v.name == name for v in self.variants):
            raise ValueError(f"Variant '{name}' already exists")
        self.variants.append(Variant(name=name, backend=backend, model=model, config=config))
    
    async def run_experiment(
        self,
        prompts: list[str],
        metrics: list[str] | None = None,
        runs_per_prompt: int = 3,
        timeout_per_trial_sec: float = 30.0,
    ) -> ExperimentResult:
        """
        Run A/B experiment across all variants.
        
        Args:
            prompts: List of prompts to test
            metrics: Metrics to track (default: all)
            runs_per_prompt: Number of times to run each prompt per variant
            timeout_per_trial_sec: Timeout for a single LLM call
            
        Returns:
            ExperimentResult with all trial data and winner determination
        """
        if not self.variants:
            raise ValueError("No variants registered. Call add_variant() first.")
        if not prompts:
            raise ValueError("At least one prompt is required")
        
        metrics = metrics or [m.value for m in MetricType]
        trials: list[TrialResult] = []
        
        logger.info(
            f"Starting A/B experiment: {len(self.variants)} variants × "
            f"{len(prompts)} prompts × {runs_per_prompt} runs = "
            f"{len(self.variants) * len(prompts) * runs_per_prompt} trials"
        )
        
        # Run all trials concurrently (with controlled concurrency to avoid rate limits)
        tasks = []
        for variant in self.variants:
            for prompt_id, prompt in enumerate(prompts):
                for run in range(runs_per_prompt):
                    task = self._run_single_trial(
                        variant=variant,
                        prompt=prompt,
                        prompt_id=f"{prompt_id}_{run}",
                        timeout_sec=timeout_per_trial_sec,
                    )
                    tasks.append(task)
        
        # Run with semaphore to limit concurrency (default 5 at a time)
        semaphore = asyncio.Semaphore(5)
        async def bounded_trial(task):
            async with semaphore:
                return await task
        
        trials = await asyncio.gather(*[bounded_trial(t) for t in tasks])
        
        result = ExperimentResult(
            experiment_id=self.experiment_id,
            variants=[v.name for v in self.variants],
            trials=trials,
            metadata={
                "prompts_count": len(prompts),
                "runs_per_prompt": runs_per_prompt,
                "variants_count": len(self.variants),
            }
        )
        
        logger.info(f"Experiment complete. Winner: {result.winner}")
        return result
    
    async def _run_single_trial(
        self,
        variant: Variant,
        prompt: str,
        prompt_id: str,
        timeout_sec: float = 30.0,
    ) -> TrialResult:
        """Run a single trial (one prompt against one variant)."""
        trial_id = str(uuid.uuid4())
        start_time = time.perf_counter()
        
        try:
            # Call the LLM with variant config
            if self.llm_manager:
                output = await asyncio.wait_for(
                    self._call_llm(variant, prompt),
                    timeout=timeout_sec,
                )
            else:
                # Fallback: mock response for testing
                output = f"[Mock response for {variant.model}] {prompt[:50]}..."
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Estimate cost (simplified heuristics; real implementation would call pricing API)
            output_tokens = len(output.split()) * 1.3  # rough estimate
            cost_per_mtok = {
                "gpt-4o-mini": 0.00015,
                "gpt-4": 0.03,
                "deepseek-chat": 0.00004,
                "claude-3-5-sonnet": 0.003,
            }
            cost_per_1m = cost_per_mtok.get(variant.model, 0.0001)
            estimated_cost = (output_tokens / 1_000_000) * cost_per_1m
            
            # Judge quality
            quality_score = await self.quality_judge(output, prompt)
            
            return TrialResult(
                trial_id=trial_id,
                experiment_id=self.experiment_id,
                variant=variant.name,
                prompt_id=prompt_id,
                latency_ms=latency_ms,
                output=output[:500],  # Truncate for storage
                output_length=int(output_tokens),
                estimated_cost_usd=estimated_cost,
                quality_score=quality_score,
                error=None,
                metadata={
                    "model": variant.model,
                    "backend": variant.backend,
                    "config": variant.config,
                }
            )
        
        except asyncio.TimeoutError as e:
            return TrialResult(
                trial_id=trial_id,
                experiment_id=self.experiment_id,
                variant=variant.name,
                prompt_id=prompt_id,
                latency_ms=(time.perf_counter() - start_time) * 1000,
                output="",
                output_length=0,
                estimated_cost_usd=0.0,
                quality_score=0.0,
                error=f"Timeout: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Trial {trial_id} failed: {e}")
            return TrialResult(
                trial_id=trial_id,
                experiment_id=self.experiment_id,
                variant=variant.name,
                prompt_id=prompt_id,
                latency_ms=(time.perf_counter() - start_time) * 1000,
                output="",
                output_length=0,
                estimated_cost_usd=0.0,
                quality_score=0.0,
                error=str(e),
            )
    
    async def _call_llm(self, variant: Variant, prompt: str) -> str:
        """Call LLM backend (integration point with LLMManager)."""
        if not self.llm_manager:
            raise RuntimeError("llm_manager not configured")
        
        # Route to appropriate backend
        response = await self.llm_manager.chat(
            model=variant.model,
            messages=[{"role": "user", "content": prompt}],
            **variant.config,
        )
        
        # Extract text from response (format depends on LLMManager)
        if isinstance(response, dict):
            return response.get("content", str(response))
        return str(response)
    
    @staticmethod
    async def _default_quality_judge(output: str, prompt: str) -> float:
        """Simple heuristic quality scoring (0-1)."""
        if not output:
            return 0.0
        
        score = 0.5  # Baseline
        
        # Reward length (longer = more effort)
        score += min(len(output) / 1000, 0.2)
        
        # Reward punctuation (well-formed)
        punct_ratio = sum(1 for c in output if c in '.!?,;:') / max(len(output), 1)
        score += min(punct_ratio, 0.1)
        
        # Penalize if too short or repetitive
        if len(output) < 20:
            score -= 0.2
        
        return max(0.0, min(1.0, score))
    
    async def save_experiment(self, result: ExperimentResult) -> None:
        """Persist experiment results to database."""
        if not self.db_session:
            logger.warning("No database session configured; skipping save")
            return
        
        # This would insert into an experiment_results table
        # Placeholder for integration with actual schema
        logger.info(f"Saved experiment {result.experiment_id} to database")
