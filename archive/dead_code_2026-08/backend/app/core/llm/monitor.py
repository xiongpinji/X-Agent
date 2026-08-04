"""Performance monitoring for LLM models."""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class ModelMetrics:
    """Metrics for a single model."""

    model_name: str
    provider: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    latencies_ms: list[float] = field(default_factory=list)
    quality_scores: list[float] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)

    def get_success_rate(self) -> float:
        """Get success rate."""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    def get_average_latency_ms(self) -> float:
        """Get average latency."""
        if not self.latencies_ms:
            return 0.0
        return statistics.mean(self.latencies_ms)

    def get_p95_latency_ms(self) -> float:
        """Get 95th percentile latency."""
        if len(self.latencies_ms) < 20:
            return self.get_average_latency_ms()
        return statistics.quantiles(self.latencies_ms, n=20)[18]  # 95th percentile

    def get_p99_latency_ms(self) -> float:
        """Get 99th percentile latency."""
        if len(self.latencies_ms) < 100:
            return self.get_average_latency_ms()
        return statistics.quantiles(self.latencies_ms, n=100)[98]  # 99th percentile

    def get_average_quality_score(self) -> float:
        """Get average quality score."""
        if not self.quality_scores:
            return 0.0
        return statistics.mean(self.quality_scores)

    def get_cost_per_token(self) -> float:
        """Get cost per token."""
        if self.total_tokens == 0:
            return 0.0
        return (self.total_cost_usd / self.total_tokens) * 1000  # Cost per 1K tokens

    def get_summary(self) -> dict[str, Any]:
        """Get summary of metrics."""
        return {
            "model": self.model_name,
            "provider": self.provider,
            "total_requests": self.total_requests,
            "success_rate": self.get_success_rate(),
            "average_latency_ms": self.get_average_latency_ms(),
            "p95_latency_ms": self.get_p95_latency_ms(),
            "p99_latency_ms": self.get_p99_latency_ms(),
            "average_quality_score": self.get_average_quality_score(),
            "cost_per_1k_tokens": self.get_cost_per_token(),
            "total_cost_usd": self.total_cost_usd,
        }


class PerformanceMonitor:
    """Monitor performance of LLM models."""

    def __init__(self):
        """Initialize performance monitor."""
        self.metrics: dict[str, ModelMetrics] = {}
        self._request_log: list[dict[str, Any]] = []
        self._alerts: list[dict[str, Any]] = []

    def record_request(
        self,
        model_name: str,
        provider: str,
        success: bool,
        latency_ms: float,
        tokens_used: int,
        cost_usd: float,
        quality_score: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a request."""
        if model_name not in self.metrics:
            self.metrics[model_name] = ModelMetrics(
                model_name=model_name,
                provider=provider,
            )

        metrics = self.metrics[model_name]
        metrics.total_requests += 1

        if success:
            metrics.successful_requests += 1
        else:
            metrics.failed_requests += 1

        metrics.total_tokens += tokens_used
        metrics.total_cost_usd += cost_usd
        metrics.latencies_ms.append(latency_ms)

        if quality_score is not None:
            metrics.quality_scores.append(quality_score)

        metrics.last_updated = datetime.now()

        # Keep only last 10000 latencies
        if len(metrics.latencies_ms) > 10000:
            metrics.latencies_ms = metrics.latencies_ms[-10000:]

        # Log request
        self._request_log.append({
            "timestamp": datetime.now(),
            "model": model_name,
            "provider": provider,
            "success": success,
            "latency_ms": latency_ms,
            "tokens": tokens_used,
            "cost_usd": cost_usd,
            "quality_score": quality_score,
            "metadata": metadata or {},
        })

        # Keep only last 10000 logs
        if len(self._request_log) > 10000:
            self._request_log = self._request_log[-10000:]

        # Check for alerts
        self._check_alerts(model_name)

    def _check_alerts(self, model_name: str) -> None:
        """Check for performance alerts."""
        metrics = self.metrics[model_name]

        # Alert on low success rate
        if metrics.total_requests >= 10:
            success_rate = metrics.get_success_rate()
            if success_rate < 0.9:
                self._add_alert(
                    model_name,
                    "low_success_rate",
                    f"Success rate is {success_rate*100:.1f}%",
                )

        # Alert on high latency
        if len(metrics.latencies_ms) >= 10:
            avg_latency = metrics.get_average_latency_ms()
            if avg_latency > 5000:  # 5 seconds
                self._add_alert(
                    model_name,
                    "high_latency",
                    f"Average latency is {avg_latency:.0f}ms",
                )

    def _add_alert(self, model_name: str, alert_type: str, message: str) -> None:
        """Add an alert."""
        alert = {
            "timestamp": datetime.now(),
            "model": model_name,
            "type": alert_type,
            "message": message,
        }
        self._alerts.append(alert)

        # Keep only last 1000 alerts
        if len(self._alerts) > 1000:
            self._alerts = self._alerts[-1000:]

    def get_metrics(self, model_name: str) -> ModelMetrics | None:
        """Get metrics for a model."""
        return self.metrics.get(model_name)

    def get_all_metrics(self) -> dict[str, ModelMetrics]:
        """Get metrics for all models."""
        return self.metrics.copy()

    def compare_models(self, model_names: list[str]) -> dict[str, Any]:
        """Compare metrics across models."""
        comparison = {}

        for model_name in model_names:
            if model_name in self.metrics:
                comparison[model_name] = self.metrics[model_name].get_summary()

        return comparison

    def get_best_model_for(self, criteria: str) -> str | None:
        """Get best model for a criteria."""
        if not self.metrics:
            return None

        if criteria == "speed":
            return min(
                self.metrics.items(),
                key=lambda x: x[1].get_average_latency_ms(),
            )[0]

        elif criteria == "quality":
            return max(
                self.metrics.items(),
                key=lambda x: x[1].get_average_quality_score(),
            )[0]

        elif criteria == "cost":
            return min(
                self.metrics.items(),
                key=lambda x: x[1].get_cost_per_token(),
            )[0]

        elif criteria == "reliability":
            return max(
                self.metrics.items(),
                key=lambda x: x[1].get_success_rate(),
            )[0]

        return None

    def get_performance_trend(
        self,
        model_name: str,
        hours: int = 24,
    ) -> dict[str, Any]:
        """Get performance trend for a model."""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_logs = [
            log for log in self._request_log
            if log["model"] == model_name and log["timestamp"] > cutoff
        ]

        if not recent_logs:
            return {}

        # Split into time buckets
        buckets = defaultdict(list)

        for log in recent_logs:
            bucket_key = log["timestamp"].replace(
                minute=0, second=0, microsecond=0
            )
            buckets[bucket_key].append(log)

        trend = {}
        for bucket_time in sorted(buckets.keys()):
            bucket_logs = buckets[bucket_time]
            success_count = sum(1 for log in bucket_logs if log["success"])
            avg_latency = sum(log["latency_ms"] for log in bucket_logs) / len(bucket_logs)

            trend[bucket_time.isoformat()] = {
                "requests": len(bucket_logs),
                "success_rate": success_count / len(bucket_logs),
                "average_latency_ms": avg_latency,
            }

        return trend

    def get_alerts(self, hours: int = 24) -> list[dict[str, Any]]:
        """Get recent alerts."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [a for a in self._alerts if a["timestamp"] > cutoff]

    def get_report(self, hours: int = 24) -> dict[str, Any]:
        """Get comprehensive performance report."""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_logs = [
            log for log in self._request_log
            if log["timestamp"] > cutoff
        ]

        total_requests = len(recent_logs)
        successful_requests = sum(1 for log in recent_logs if log["success"])
        total_tokens = sum(log["tokens"] for log in recent_logs)
        total_cost = sum(log["cost_usd"] for log in recent_logs)

        latencies = [log["latency_ms"] for log in recent_logs]
        avg_latency = statistics.mean(latencies) if latencies else 0.0

        return {
            "period_hours": hours,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "success_rate": successful_requests / total_requests if total_requests > 0 else 1.0,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "average_latency_ms": avg_latency,
            "model_metrics": {
                name: metrics.get_summary()
                for name, metrics in self.metrics.items()
            },
            "alerts": self.get_alerts(hours),
        }
