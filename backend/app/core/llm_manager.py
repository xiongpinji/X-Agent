"""Integrated LLM management system combining routing, caching, and deduplication.

Combines:
- Multi-model routing
- Request caching
- Request deduplication
- Cost optimization
- Performance monitoring
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from backend.app.core.llm import LLMResponse, LLMRouter, BaseLLMBackend
from backend.app.core.llm_cache import get_llm_cache_manager, LLMCacheManager
from backend.app.core.llm_deduplicator import get_deduplicator, LLMDeduplicator
from backend.app.core.llm_ab_testing import ABTestingSystem, ExperimentStatus, TrafficAllocationStrategy, VariantType
from backend.app.core.llm_evaluation import EvaluationMethod, LLMEvaluation
from backend.app.core.llm_monitoring import AlertSeverity, LLMMonitoring, MetricType
from backend.app.core.prompt_engineering import PromptEngineering, PromptType

logger = logging.getLogger(__name__)


@dataclass
class LLMCallMetrics:
    """Metrics for an LLM call."""

    model: str
    latency_ms: float
    tokens_used: int
    cost: float
    cache_hit: bool
    deduplicated: bool
    dedup_type: Optional[str] = None


class LLMManager:
    """Unified LLM management system with routing, caching, and deduplication."""

    def __init__(
        self,
        router: Optional[LLMRouter] = None,
        cache_manager: Optional[LLMCacheManager] = None,
        deduplicator: Optional[LLMDeduplicator] = None,
        storage_path: str | Path | None = None,
        enable_cache: bool = True,
        enable_dedup: bool = True,
    ) -> None:
        """Initialize LLM manager.

        Args:
            router: LLM router for model selection
            cache_manager: Cache manager for response caching
            deduplicator: Deduplicator for request deduplication
            storage_path: Path for storing metrics and configurations
            enable_cache: Enable response caching
            enable_dedup: Enable request deduplication
        """
        self._router = router
        self._cache_manager = cache_manager or get_llm_cache_manager()
        self._deduplicator = deduplicator or get_deduplicator()
        self._enable_cache = enable_cache
        self._enable_dedup = enable_dedup
        self._metrics: list[LLMCallMetrics] = []
        self._lock = asyncio.Lock()

        # Initialize subsystems
        storage_path = Path(storage_path) if storage_path else None
        self.prompt_engineering = PromptEngineering(storage_path / "prompts" if storage_path else None)
        self.ab_testing = ABTestingSystem(storage_path / "ab_tests" if storage_path else None)
        self.monitoring = LLMMonitoring(storage_path / "monitoring" if storage_path else None)
        self.evaluation = LLMEvaluation(storage_path / "evaluation" if storage_path else None)

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        use_cache: Optional[bool] = None,
        use_dedup: Optional[bool] = None,
    ) -> LLMResponse:
        """Send a chat request with caching and deduplication.

        Args:
            messages: Chat messages
            tools: Available tools
            model: Specific model to use (if None, router selects)
            temperature: Temperature for generation
            use_cache: Override cache setting
            use_dedup: Override dedup setting

        Returns:
            LLM response
        """
        if self._router is None:
            raise RuntimeError("LLM router not configured")

        tools = tools or []
        use_cache = use_cache if use_cache is not None else self._enable_cache
        use_dedup = use_dedup if use_dedup is not None else self._enable_dedup

        start_time = time.perf_counter()

        # Count every request exactly once for dedup statistics. Deduplication
        # events (cache / in-flight) are recorded separately as a SUBSET of this
        # total, so the dedup rate stays a meaningful 0-100% fraction.
        if use_dedup:
            self._deduplicator.record_request()

        # Step 1: Check cache
        if use_cache:
            cached_response = await self._cache_manager.get_cached_response(
                messages, model or "default", temperature
            )
            if cached_response:
                logger.info(f"Cache hit for model {model or 'default'}")
                # A cache hit is still a completed call: record it so
                # total_calls / cache_hits metrics count every request.
                latency_ms = (time.perf_counter() - start_time) * 1000
                await self._record_metrics(
                    LLMCallMetrics(
                        model=cached_response.model,
                        latency_ms=latency_ms,
                        tokens_used=cached_response.tokens_used,
                        cost=cached_response.cost,
                        cache_hit=True,
                        deduplicated=use_dedup,
                        dedup_type="cache" if use_dedup else None,
                    )
                )
                if use_dedup:
                    self._deduplicator.record_deduplication("cache")
                return cached_response

        # Step 2: Deduplicate concurrent in-flight duplicates.
        # register_or_get_in_flight atomically tells us whether we are the
        # PRIMARY (must call the LLM and resolve the future) or a FOLLOWER
        # (await the primary's result). The old code made the primary await its
        # own freshly-created future, which only resolves after the LLM call it
        # had not made yet -> deadlock until the 300s in-flight timeout.
        signature = None
        if use_dedup:
            signature, is_primary = await self._deduplicator.register_or_get_in_flight(
                messages, model or "default", temperature
            )
            if not is_primary:
                in_flight_response = await self._deduplicator.get_in_flight_response(
                    signature
                )
                if in_flight_response is not None:
                    logger.info("In-flight deduplication hit")
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    await self._record_metrics(
                        LLMCallMetrics(
                            model=in_flight_response.model,
                            latency_ms=latency_ms,
                            tokens_used=in_flight_response.tokens_used,
                            cost=0.0,  # deduplicated -> no additional provider cost
                            cache_hit=False,
                            deduplicated=True,
                            dedup_type="in_flight",
                        )
                    )
                    self._deduplicator.record_deduplication("in_flight")
                    return in_flight_response
                # Primary failed/timed out -> claim primary ownership ourselves.
                signature, _ = await self._deduplicator.register_or_get_in_flight(
                    messages, model or "default", temperature
                )

        # Step 3: Call LLM (primary path)
        try:
            response = await self._router.chat(messages, tools)

            # Step 4: Cache response
            if use_cache and response:
                await self._cache_manager.cache_response(
                    messages, response, model or "default", temperature
                )

            # Step 5: Resolve in-flight requests so followers can return
            if use_dedup and signature is not None:
                await self._deduplicator.resolve_in_flight(signature, response)

            # Record metrics
            latency_ms = (time.perf_counter() - start_time) * 1000
            metrics = LLMCallMetrics(
                model=response.model,
                latency_ms=latency_ms,
                tokens_used=response.tokens_used,
                cost=response.cost,
                cache_hit=False,
                deduplicated=False,
                dedup_type=None,
            )
            await self._record_metrics(metrics)

            logger.info(
                f"LLM call completed: model={response.model}, "
                f"latency={latency_ms:.0f}ms, cost=${response.cost:.4f}, "
                f"cache_hit=False, dedup=False"
            )

            return response

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            # Unblock any followers awaiting this signature instead of letting
            # them hang until the in-flight timeout.
            if use_dedup and signature is not None:
                await self._deduplicator.fail_in_flight(signature, e)
            raise

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """Stream chat response.

        Note: Streaming responses are not cached.
        """
        if self._router is None:
            raise RuntimeError("LLM router not configured")

        tools = tools or []

        try:
            # For streaming, we don't use cache or dedup
            async for chunk in self._router._backends[0].stream_chat(messages, tools):
                yield chunk
        except Exception as e:
            logger.error(f"Stream chat failed: {e}")
            raise

    async def _record_metrics(self, metrics: LLMCallMetrics) -> None:
        """Record call metrics."""
        async with self._lock:
            self._metrics.append(metrics)

            # Keep only last 10000 metrics
            if len(self._metrics) > 10000:
                self._metrics = self._metrics[-10000:]

    def get_metrics(self) -> dict[str, Any]:
        """Get aggregated metrics."""
        # Snapshot once (list() copy 在 GIL 下原子)，避免多次 sum() 期间 _metrics 被并发改（B6）。
        metrics_snapshot = list(self._metrics)
        if not metrics_snapshot:
            return {
                "total_calls": 0,
                "cache_hits": 0,
                "cache_hit_rate": 0.0,
                "dedup_hits": 0,
                "dedup_rate": 0.0,
                "total_cost": 0.0,
                "total_tokens": 0,
                "average_latency_ms": 0.0,
            }

        total_calls = len(metrics_snapshot)
        cache_hits = sum(1 for m in metrics_snapshot if m.cache_hit)
        dedup_hits = sum(1 for m in metrics_snapshot if m.deduplicated)
        total_cost = sum(m.cost for m in metrics_snapshot)
        total_tokens = sum(m.tokens_used for m in metrics_snapshot)
        avg_latency = sum(m.latency_ms for m in metrics_snapshot) / total_calls

        return {
            "total_calls": total_calls,
            "cache_hits": cache_hits,
            "cache_hit_rate": (cache_hits / total_calls * 100) if total_calls > 0 else 0.0,
            "dedup_hits": dedup_hits,
            "dedup_rate": (dedup_hits / total_calls * 100) if total_calls > 0 else 0.0,
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "average_latency_ms": avg_latency,
            "cost_savings": self._cache_manager.get_stats()["total_cost_saved"],
            "tokens_saved": self._cache_manager.get_stats()["total_tokens_saved"],
        }

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self._cache_manager.get_stats()

    def get_dedup_stats(self) -> dict[str, Any]:
        """Get deduplication statistics."""
        return self._deduplicator.get_stats()

    async def clear_cache(self) -> None:
        """Clear all caches."""
        await self._cache_manager.invalidate_response_cache()
        await self._deduplicator.clear_cache()
        logger.info("All caches cleared")

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self._deduplicator.cleanup_in_flight()
        logger.info("Cleanup completed")

    def setup_prompt_optimization_workflow(
        self,
        template_name: str,
        template_content: str,
        test_cases: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Set up a complete prompt optimization workflow."""
        # Create template
        template = self.prompt_engineering.create_template(
            name=template_name,
            content=template_content,
            prompt_type=PromptType.USER,
            tags=["optimization"],
        )

        # Create evaluation dataset
        dataset = self.evaluation.create_dataset(
            name=f"{template_name}_test_set",
            description=f"Test cases for {template_name}",
        )

        for test_case in test_cases:
            self.evaluation.add_test_case(
                dataset.dataset_id,
                test_case.get("prompt", ""),
                test_case.get("expected_output", ""),
            )

        return {
            "template_id": template.template_id,
            "dataset_id": dataset.dataset_id,
            "template": template,
            "dataset": dataset,
        }

    def setup_ab_test_for_prompts(
        self,
        experiment_name: str,
        template_id: str,
        variant_configs: list[dict[str, Any]],
        duration_days: int = 7,
    ) -> dict[str, Any]:
        """Set up an A/B test for different prompt versions."""
        # Create experiment
        experiment = self.ab_testing.create_experiment(
            name=experiment_name,
            objective="improve_prompt_quality",
            description=f"A/B test for {template_id}",
            duration_days=duration_days,
            traffic_strategy=TrafficAllocationStrategy.EQUAL,
        )

        # Add variants
        for i, config in enumerate(variant_configs):
            variant_type = VariantType.CONTROL if i == 0 else VariantType.TREATMENT
            experiment.add_variant(
                name=config.get("name", f"Variant {i}"),
                variant_type=variant_type,
                config=config,
                traffic_weight=1.0 / len(variant_configs),
                description=config.get("description", ""),
            )

        return {
            "experiment_id": experiment.experiment_id,
            "experiment": experiment,
        }

    def run_evaluation_on_dataset(
        self,
        dataset_id: str,
        model_name: str,
        provider: str,
        responses: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Run evaluation on a dataset."""
        # Create evaluation run
        run = self.evaluation.create_evaluation_run(
            dataset_id=dataset_id,
            model_name=model_name,
            provider=provider,
        )

        if not run:
            return {}

        # Record responses and evaluate
        for response_data in responses:
            llm_response = self.evaluation.record_response(
                prompt=response_data.get("prompt", ""),
                response=response_data.get("response", ""),
                model_name=model_name,
                provider=provider,
            )

            evaluation = self.evaluation.evaluate_response(
                llm_response.response_id,
                method=EvaluationMethod.AUTOMATED,
            )

            if evaluation:
                self.evaluation.add_evaluation_to_run(run.run_id, evaluation)

        # Complete run
        self.evaluation.complete_run(run.run_id)

        return {
            "run_id": run.run_id,
            "report": self.evaluation.get_evaluation_report(run.run_id),
        }

    def setup_monitoring_alerts(self) -> dict[str, Any]:
        """Set up default monitoring alerts."""
        alerts = []

        # High latency alert
        alert1 = self.monitoring.create_alert_rule(
            name="High Latency",
            metric_type=MetricType.LATENCY,
            condition="greater_than",
            threshold=5000.0,  # 5 seconds
            severity=AlertSeverity.WARNING,
            description="Alert when latency exceeds 5 seconds",
        )
        alerts.append(alert1)

        # High error rate alert
        alert2 = self.monitoring.create_alert_rule(
            name="High Error Rate",
            metric_type=MetricType.ERROR_RATE,
            condition="greater_than",
            threshold=0.1,  # 10%
            severity=AlertSeverity.CRITICAL,
            description="Alert when error rate exceeds 10%",
        )
        alerts.append(alert2)

        # High cost alert
        alert3 = self.monitoring.create_alert_rule(
            name="High Cost",
            metric_type=MetricType.COST,
            condition="greater_than",
            threshold=100.0,  # $100
            severity=AlertSeverity.WARNING,
            description="Alert when hourly cost exceeds $100",
        )
        alerts.append(alert3)

        # Low cache hit rate alert
        alert4 = self.monitoring.create_alert_rule(
            name="Low Cache Hit Rate",
            metric_type=MetricType.CACHE_HIT_RATE,
            condition="less_than",
            threshold=0.5,  # 50%
            severity=AlertSeverity.INFO,
            description="Alert when cache hit rate drops below 50%",
        )
        alerts.append(alert4)

        return {
            "alerts": alerts,
            "count": len(alerts),
        }

    def get_comprehensive_report(self) -> dict[str, Any]:
        """Get a comprehensive report of all systems."""
        return {
            "prompt_engineering": {
                "templates": len(self.prompt_engineering._templates),
                "total_versions": sum(len(v) for v in self.prompt_engineering._versions.values()),
                "total_examples": sum(len(e) for e in self.prompt_engineering._examples.values()),
            },
            "ab_testing": {
                "experiments": len(self.ab_testing._experiments),
                "running": len([e for e in self.ab_testing._experiments.values() if e.is_running()]),
                "completed": len(
                    [e for e in self.ab_testing._experiments.values() if e.status == ExperimentStatus.COMPLETED]
                ),
            },
            "monitoring": {
                "metrics_recorded": len(self.monitoring._metrics),
                "costs_tracked": len(self.monitoring._costs),
                "alerts_triggered": len(self.monitoring._alerts),
                "active_alerts": len([a for a in self.monitoring._alerts if not a.is_resolved]),
                "performance": self.monitoring.get_performance_summary(hours=24),
                "cost_summary": self.monitoring.get_cost_summary(hours=24),
            },
            "evaluation": {
                "responses_evaluated": len(self.evaluation._responses),
                "datasets": len(self.evaluation._datasets),
                "evaluation_runs": len(self.evaluation._runs),
                "completed_runs": len([r for r in self.evaluation._runs.values() if r.status == "completed"]),
            },
        }

    def export_metrics_for_dashboard(self) -> dict[str, Any]:
        """Export metrics suitable for dashboard visualization."""
        perf_summary = self.monitoring.get_performance_summary(hours=24)
        cost_summary = self.monitoring.get_cost_summary(hours=24)

        # Get recent alerts
        recent_alerts = self.monitoring.get_alerts(resolved=False, hours=24)

        # Get experiment status
        running_experiments = [e for e in self.ab_testing._experiments.values() if e.is_running()]

        # Get evaluation metrics
        completed_runs = [r for r in self.evaluation._runs.values() if r.status == "completed"]
        avg_eval_score = 0.0
        if completed_runs:
            scores = [r.metrics_summary.get("overall", 0.0) for r in completed_runs]
            avg_eval_score = sum(scores) / len(scores)

        return {
            "performance": {
                "latency_ms": perf_summary.get("avg_latency_ms", 0.0),
                "error_rate": perf_summary.get("error_rate", 0.0),
                "throughput_rps": perf_summary.get("throughput_rps", 0.0),
                "cache_hit_rate": perf_summary.get("cache_hit_rate", 0.0),
            },
            "costs": {
                "total_usd": cost_summary.get("total_cost_usd", 0.0),
                "total_tokens": cost_summary.get("total_tokens", 0),
                "avg_cost_per_token": cost_summary.get("avg_cost_per_token", 0.0),
                "by_provider": cost_summary.get("by_provider", {}),
            },
            "alerts": {
                "active_count": len(recent_alerts),
                "recent": [
                    {
                        "id": a.alert_id,
                        "severity": a.severity,
                        "message": a.message,
                        "triggered_at": a.triggered_at.isoformat(),
                    }
                    for a in recent_alerts[:5]
                ],
            },
            "experiments": {
                "running_count": len(running_experiments),
                "running": [
                    {
                        "id": e.experiment_id,
                        "name": e.name,
                        "objective": e.objective,
                        "variants": len(e.variants),
                    }
                    for e in running_experiments
                ],
            },
            "evaluation": {
                "avg_score": avg_eval_score,
                "completed_runs": len(completed_runs),
            },
        }

    def get_optimization_recommendations(self) -> list[dict[str, Any]]:
        """Get recommendations for optimization."""
        recommendations = []

        # Check performance metrics
        perf = self.monitoring.get_performance_summary(hours=24)
        if perf.get("avg_latency_ms", 0) > 3000:
            recommendations.append(
                {
                    "type": "performance",
                    "priority": "high",
                    "message": "High latency detected. Consider optimizing prompts or using faster models.",
                    "metric": "latency_ms",
                    "value": perf.get("avg_latency_ms"),
                }
            )

        if perf.get("error_rate", 0) > 0.05:
            recommendations.append(
                {
                    "type": "quality",
                    "priority": "critical",
                    "message": "High error rate detected. Review prompt quality and error handling.",
                    "metric": "error_rate",
                    "value": perf.get("error_rate"),
                }
            )

        # Check cost efficiency
        cost = self.monitoring.get_cost_summary(hours=24)
        if cost.get("total_cost_usd", 0) > 500:
            recommendations.append(
                {
                    "type": "cost",
                    "priority": "medium",
                    "message": "High costs detected. Consider using cheaper models or caching.",
                    "metric": "cost_usd",
                    "value": cost.get("total_cost_usd"),
                }
            )

        # Check cache hit rate
        if perf.get("cache_hit_rate", 0) < 0.3:
            recommendations.append(
                {
                    "type": "efficiency",
                    "priority": "medium",
                    "message": "Low cache hit rate. Consider implementing better caching strategies.",
                    "metric": "cache_hit_rate",
                    "value": perf.get("cache_hit_rate"),
                }
            )

        return recommendations


# Global LLM manager instance
_llm_manager: Optional[LLMManager] = None


def get_llm_manager(router: Optional[LLMRouter] = None) -> LLMManager:
    """Get or create the global LLM manager."""
    global _llm_manager
    if _llm_manager is None:
        if router is None:
            from backend.app.core.llm import LLMRouter, MockLLMBackend
            router = LLMRouter(backend=MockLLMBackend())
        _llm_manager = LLMManager(router)
    return _llm_manager


    def setup_prompt_optimization_workflow(
        self,
        template_name: str,
        template_content: str,
        test_cases: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Set up a complete prompt optimization workflow."""
        # Create template
        template = self.prompt_engineering.create_template(
            name=template_name,
            content=template_content,
            prompt_type=PromptType.USER,
            tags=["optimization"],
        )

        # Create evaluation dataset
        dataset = self.evaluation.create_dataset(
            name=f"{template_name}_test_set",
            description=f"Test cases for {template_name}",
        )

        for test_case in test_cases:
            self.evaluation.add_test_case(
                dataset.dataset_id,
                test_case.get("prompt", ""),
                test_case.get("expected_output", ""),
            )

        return {
            "template_id": template.template_id,
            "dataset_id": dataset.dataset_id,
            "template": template,
            "dataset": dataset,
        }

    def setup_ab_test_for_prompts(
        self,
        experiment_name: str,
        template_id: str,
        variant_configs: list[dict[str, Any]],
        duration_days: int = 7,
    ) -> dict[str, Any]:
        """Set up an A/B test for different prompt versions."""
        # Create experiment
        experiment = self.ab_testing.create_experiment(
            name=experiment_name,
            objective="improve_prompt_quality",
            description=f"A/B test for {template_id}",
            duration_days=duration_days,
            traffic_strategy=TrafficAllocationStrategy.EQUAL,
        )

        # Add variants
        for i, config in enumerate(variant_configs):
            variant_type = VariantType.CONTROL if i == 0 else VariantType.TREATMENT
            experiment.add_variant(
                name=config.get("name", f"Variant {i}"),
                variant_type=variant_type,
                config=config,
                traffic_weight=1.0 / len(variant_configs),
                description=config.get("description", ""),
            )

        return {
            "experiment_id": experiment.experiment_id,
            "experiment": experiment,
        }

    def run_evaluation_on_dataset(
        self,
        dataset_id: str,
        model_name: str,
        provider: str,
        responses: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Run evaluation on a dataset."""
        # Create evaluation run
        run = self.evaluation.create_evaluation_run(
            dataset_id=dataset_id,
            model_name=model_name,
            provider=provider,
        )

        if not run:
            return {}

        # Record responses and evaluate
        for response_data in responses:
            llm_response = self.evaluation.record_response(
                prompt=response_data.get("prompt", ""),
                response=response_data.get("response", ""),
                model_name=model_name,
                provider=provider,
            )

            evaluation = self.evaluation.evaluate_response(
                llm_response.response_id,
                method=EvaluationMethod.AUTOMATED,
            )

            if evaluation:
                self.evaluation.add_evaluation_to_run(run.run_id, evaluation)

        # Complete run
        self.evaluation.complete_run(run.run_id)

        return {
            "run_id": run.run_id,
            "report": self.evaluation.get_evaluation_report(run.run_id),
        }

    def setup_monitoring_alerts(self) -> dict[str, Any]:
        """Set up default monitoring alerts."""
        alerts = []

        # High latency alert
        alert1 = self.monitoring.create_alert_rule(
            name="High Latency",
            metric_type=MetricType.LATENCY,
            condition="greater_than",
            threshold=5000.0,  # 5 seconds
            severity=AlertSeverity.WARNING,
            description="Alert when latency exceeds 5 seconds",
        )
        alerts.append(alert1)

        # High error rate alert
        alert2 = self.monitoring.create_alert_rule(
            name="High Error Rate",
            metric_type=MetricType.ERROR_RATE,
            condition="greater_than",
            threshold=0.1,  # 10%
            severity=AlertSeverity.CRITICAL,
            description="Alert when error rate exceeds 10%",
        )
        alerts.append(alert2)

        # High cost alert
        alert3 = self.monitoring.create_alert_rule(
            name="High Cost",
            metric_type=MetricType.COST,
            condition="greater_than",
            threshold=100.0,  # $100
            severity=AlertSeverity.WARNING,
            description="Alert when hourly cost exceeds $100",
        )
        alerts.append(alert3)

        # Low cache hit rate alert
        alert4 = self.monitoring.create_alert_rule(
            name="Low Cache Hit Rate",
            metric_type=MetricType.CACHE_HIT_RATE,
            condition="less_than",
            threshold=0.5,  # 50%
            severity=AlertSeverity.INFO,
            description="Alert when cache hit rate drops below 50%",
        )
        alerts.append(alert4)

        return {
            "alerts": alerts,
            "count": len(alerts),
        }

    def get_comprehensive_report(self) -> dict[str, Any]:
        """Get a comprehensive report of all systems."""
        return {
            "prompt_engineering": {
                "templates": len(self.prompt_engineering._templates),
                "total_versions": sum(len(v) for v in self.prompt_engineering._versions.values()),
                "total_examples": sum(len(e) for e in self.prompt_engineering._examples.values()),
            },
            "ab_testing": {
                "experiments": len(self.ab_testing._experiments),
                "running": len([e for e in self.ab_testing._experiments.values() if e.is_running()]),
                "completed": len(
                    [e for e in self.ab_testing._experiments.values() if e.status == ExperimentStatus.COMPLETED]
                ),
            },
            "monitoring": {
                "metrics_recorded": len(self.monitoring._metrics),
                "costs_tracked": len(self.monitoring._costs),
                "alerts_triggered": len(self.monitoring._alerts),
                "active_alerts": len([a for a in self.monitoring._alerts if not a.is_resolved]),
                "performance": self.monitoring.get_performance_summary(hours=24),
                "cost_summary": self.monitoring.get_cost_summary(hours=24),
            },
            "evaluation": {
                "responses_evaluated": len(self.evaluation._responses),
                "datasets": len(self.evaluation._datasets),
                "evaluation_runs": len(self.evaluation._runs),
                "completed_runs": len([r for r in self.evaluation._runs.values() if r.status == "completed"]),
            },
        }

    def export_metrics_for_dashboard(self) -> dict[str, Any]:
        """Export metrics suitable for dashboard visualization."""
        perf_summary = self.monitoring.get_performance_summary(hours=24)
        cost_summary = self.monitoring.get_cost_summary(hours=24)

        # Get recent alerts
        recent_alerts = self.monitoring.get_alerts(resolved=False, hours=24)

        # Get experiment status
        running_experiments = [e for e in self.ab_testing._experiments.values() if e.is_running()]

        # Get evaluation metrics
        completed_runs = [r for r in self.evaluation._runs.values() if r.status == "completed"]
        avg_eval_score = 0.0
        if completed_runs:
            scores = [r.metrics_summary.get("overall", 0.0) for r in completed_runs]
            avg_eval_score = sum(scores) / len(scores)

        return {
            "performance": {
                "latency_ms": perf_summary.get("avg_latency_ms", 0.0),
                "error_rate": perf_summary.get("error_rate", 0.0),
                "throughput_rps": perf_summary.get("throughput_rps", 0.0),
                "cache_hit_rate": perf_summary.get("cache_hit_rate", 0.0),
            },
            "costs": {
                "total_usd": cost_summary.get("total_cost_usd", 0.0),
                "total_tokens": cost_summary.get("total_tokens", 0),
                "avg_cost_per_token": cost_summary.get("avg_cost_per_token", 0.0),
                "by_provider": cost_summary.get("by_provider", {}),
            },
            "alerts": {
                "active_count": len(recent_alerts),
                "recent": [
                    {
                        "id": a.alert_id,
                        "severity": a.severity,
                        "message": a.message,
                        "triggered_at": a.triggered_at.isoformat(),
                    }
                    for a in recent_alerts[:5]
                ],
            },
            "experiments": {
                "running_count": len(running_experiments),
                "running": [
                    {
                        "id": e.experiment_id,
                        "name": e.name,
                        "objective": e.objective,
                        "variants": len(e.variants),
                    }
                    for e in running_experiments
                ],
            },
            "evaluation": {
                "avg_score": avg_eval_score,
                "completed_runs": len(completed_runs),
            },
        }

    def get_optimization_recommendations(self) -> list[dict[str, Any]]:
        """Get recommendations for optimization."""
        recommendations = []

        # Check performance metrics
        perf = self.monitoring.get_performance_summary(hours=24)
        if perf.get("avg_latency_ms", 0) > 3000:
            recommendations.append(
                {
                    "type": "performance",
                    "priority": "high",
                    "message": "High latency detected. Consider optimizing prompts or using faster models.",
                    "metric": "latency_ms",
                    "value": perf.get("avg_latency_ms"),
                }
            )

        if perf.get("error_rate", 0) > 0.05:
            recommendations.append(
                {
                    "type": "quality",
                    "priority": "critical",
                    "message": "High error rate detected. Review prompt quality and error handling.",
                    "metric": "error_rate",
                    "value": perf.get("error_rate"),
                }
            )

        # Check cost efficiency
        cost = self.monitoring.get_cost_summary(hours=24)
        if cost.get("total_cost_usd", 0) > 500:
            recommendations.append(
                {
                    "type": "cost",
                    "priority": "medium",
                    "message": "High costs detected. Consider using cheaper models or caching.",
                    "metric": "cost_usd",
                    "value": cost.get("total_cost_usd"),
                }
            )

        # Check cache hit rate
        if perf.get("cache_hit_rate", 0) < 0.3:
            recommendations.append(
                {
                    "type": "efficiency",
                    "priority": "medium",
                    "message": "Low cache hit rate. Consider implementing better caching strategies.",
                    "metric": "cache_hit_rate",
                    "value": perf.get("cache_hit_rate"),
                }
            )

        return recommendations
