"""LLM monitoring system for tracking quality, cost, and performance metrics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class MetricType(StrEnum):
    """Types of metrics to monitor."""
    LATENCY = "latency"
    TOKEN_USAGE = "token_usage"
    COST = "cost"
    ERROR_RATE = "error_rate"
    QUALITY = "quality"
    THROUGHPUT = "throughput"
    CACHE_HIT_RATE = "cache_hit_rate"


class AlertSeverity(StrEnum):
    """Severity levels for alerts."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class LLMMetric(BaseModel):
    """A single LLM metric data point."""

    metric_id: str = Field(default_factory=lambda: str(uuid4()))
    metric_type: MetricType
    value: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    model_name: str = ""
    provider: str = ""
    user_id: str | None = None
    request_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MetricAggregation(BaseModel):
    """Aggregated metrics over a time period."""

    aggregation_id: str = Field(default_factory=lambda: str(uuid4()))
    metric_type: MetricType
    period: str = "1h"  # 1h, 1d, 1w
    start_time: datetime
    end_time: datetime
    count: int = 0
    min_value: float = 0.0
    max_value: float = 0.0
    avg_value: float = 0.0
    p50_value: float = 0.0
    p95_value: float = 0.0
    p99_value: float = 0.0
    model_name: str = ""
    provider: str = ""


class CostTracker(BaseModel):
    """Track costs for LLM API calls."""

    cost_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    model_name: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    user_id: str | None = None
    request_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def calculate_cost(self, input_price_per_1k: float, output_price_per_1k: float) -> float:
        """Calculate cost based on token prices."""
        input_cost = (self.input_tokens / 1000) * input_price_per_1k
        output_cost = (self.output_tokens / 1000) * output_price_per_1k
        self.cost_usd = input_cost + output_cost
        return self.cost_usd


class Alert(BaseModel):
    """An alert for metric anomalies."""

    alert_id: str = Field(default_factory=lambda: str(uuid4()))
    severity: AlertSeverity
    metric_type: MetricType
    message: str
    threshold: float
    current_value: float
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    is_resolved: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    def resolve(self) -> None:
        """Mark alert as resolved."""
        self.is_resolved = True
        self.resolved_at = datetime.now(UTC)


class AlertRule(BaseModel):
    """Rule for triggering alerts."""

    rule_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    metric_type: MetricType
    condition: str  # "greater_than", "less_than", "equals"
    threshold: float
    severity: AlertSeverity
    enabled: bool = True
    description: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LLMMonitoring:
    """Main LLM monitoring system."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._metrics: list[LLMMetric] = []
        self._aggregations: dict[str, list[MetricAggregation]] = {}
        self._costs: list[CostTracker] = []
        self._alerts: list[Alert] = []
        self._alert_rules: dict[str, AlertRule] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._load_from_disk()

    def record_metric(
        self,
        metric_type: MetricType,
        value: float,
        model_name: str = "",
        provider: str = "",
        user_id: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LLMMetric:
        """Record a metric."""
        metric = LLMMetric(
            metric_type=metric_type,
            value=value,
            model_name=model_name,
            provider=provider,
            user_id=user_id,
            request_id=request_id,
            metadata=metadata or {},
        )
        self._metrics.append(metric)

        # Check alert rules
        self._check_alert_rules(metric)

        # Aggregate metrics
        self._aggregate_metric(metric)

        self._save_to_disk()
        return metric

    def record_cost(
        self,
        model_name: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        input_price_per_1k: float,
        output_price_per_1k: float,
        user_id: str | None = None,
        request_id: str | None = None,
    ) -> CostTracker:
        """Record a cost for an LLM call."""
        cost = CostTracker(
            model_name=model_name,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            user_id=user_id,
            request_id=request_id,
        )
        cost.calculate_cost(input_price_per_1k, output_price_per_1k)
        self._costs.append(cost)
        self._save_to_disk()
        return cost

    def get_metrics(
        self,
        metric_type: MetricType | None = None,
        model_name: str | None = None,
        hours: int = 24,
    ) -> list[LLMMetric]:
        """Get metrics for a time period."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        metrics = [m for m in self._metrics if m.timestamp >= cutoff]

        if metric_type:
            metrics = [m for m in metrics if m.metric_type == metric_type]
        if model_name:
            metrics = [m for m in metrics if m.model_name == model_name]

        return metrics

    def get_aggregations(
        self,
        metric_type: MetricType,
        period: str = "1h",
    ) -> list[MetricAggregation]:
        """Get aggregated metrics."""
        key = f"{metric_type}:{period}"
        return self._aggregations.get(key, [])

    def get_cost_summary(self, hours: int = 24) -> dict[str, Any]:
        """Get cost summary for a time period."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        costs = [c for c in self._costs if c.timestamp >= cutoff]

        total_cost = sum(c.cost_usd for c in costs)
        total_tokens = sum(c.total_tokens for c in costs)
        avg_cost_per_token = total_cost / max(total_tokens, 1)

        # Group by provider
        by_provider = {}
        for cost in costs:
            if cost.provider not in by_provider:
                by_provider[cost.provider] = {"cost": 0.0, "tokens": 0}
            by_provider[cost.provider]["cost"] += cost.cost_usd
            by_provider[cost.provider]["tokens"] += cost.total_tokens

        # Group by model
        by_model = {}
        for cost in costs:
            if cost.model_name not in by_model:
                by_model[cost.model_name] = {"cost": 0.0, "tokens": 0}
            by_model[cost.model_name]["cost"] += cost.cost_usd
            by_model[cost.model_name]["tokens"] += cost.total_tokens

        return {
            "total_cost_usd": total_cost,
            "total_tokens": total_tokens,
            "avg_cost_per_token": avg_cost_per_token,
            "by_provider": by_provider,
            "by_model": by_model,
            "request_count": len(costs),
        }

    def create_alert_rule(
        self,
        name: str,
        metric_type: MetricType,
        condition: str,
        threshold: float,
        severity: AlertSeverity,
        description: str = "",
    ) -> AlertRule:
        """Create an alert rule."""
        rule = AlertRule(
            name=name,
            metric_type=metric_type,
            condition=condition,
            threshold=threshold,
            severity=severity,
            description=description,
        )
        self._alert_rules[rule.rule_id] = rule
        self._save_to_disk()
        return rule

    def get_alert_rules(self) -> list[AlertRule]:
        """Get all alert rules."""
        return list(self._alert_rules.values())

    def get_alerts(self, resolved: bool | None = None, hours: int = 24) -> list[Alert]:
        """Get alerts."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        alerts = [a for a in self._alerts if a.triggered_at >= cutoff]

        if resolved is not None:
            alerts = [a for a in alerts if a.is_resolved == resolved]

        return alerts

    def resolve_alert(self, alert_id: str) -> Alert | None:
        """Resolve an alert."""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.resolve()
                self._save_to_disk()
                return alert
        return None

    def get_performance_summary(self, hours: int = 24) -> dict[str, Any]:
        """Get performance summary."""
        metrics = self.get_metrics(hours=hours)

        if not metrics:
            return {
                "avg_latency_ms": 0.0,
                "error_rate": 0.0,
                "throughput_rps": 0.0,
                "cache_hit_rate": 0.0,
            }

        latencies = [m.value for m in metrics if m.metric_type == MetricType.LATENCY]
        errors = [m.value for m in metrics if m.metric_type == MetricType.ERROR_RATE]
        cache_hits = [m.value for m in metrics if m.metric_type == MetricType.CACHE_HIT_RATE]

        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        avg_error_rate = sum(errors) / len(errors) if errors else 0.0
        avg_cache_hit = sum(cache_hits) / len(cache_hits) if cache_hits else 0.0

        # Calculate throughput (requests per second)
        time_span_hours = hours
        throughput = len(metrics) / (time_span_hours * 3600)

        return {
            "avg_latency_ms": avg_latency,
            "error_rate": avg_error_rate,
            "throughput_rps": throughput,
            "cache_hit_rate": avg_cache_hit,
            "total_requests": len(metrics),
        }

    def _check_alert_rules(self, metric: LLMMetric) -> None:
        """Check if metric triggers any alert rules."""
        for rule in self._alert_rules.values():
            if not rule.enabled or rule.metric_type != metric.metric_type:
                continue

            should_alert = False
            if rule.condition == "greater_than" and metric.value > rule.threshold:
                should_alert = True
            elif rule.condition == "less_than" and metric.value < rule.threshold:
                should_alert = True
            elif rule.condition == "equals" and metric.value == rule.threshold:
                should_alert = True

            if should_alert:
                alert = Alert(
                    severity=rule.severity,
                    metric_type=metric.metric_type,
                    message=f"Alert: {rule.name} - {metric.metric_type} = {metric.value}",
                    threshold=rule.threshold,
                    current_value=metric.value,
                    metadata={"rule_id": rule.rule_id},
                )
                self._alerts.append(alert)

    def _aggregate_metric(self, metric: LLMMetric) -> None:
        """Aggregate metric into time buckets."""
        # Simple hourly aggregation
        hour_start = metric.timestamp.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)

        key = f"{metric.metric_type}:1h"
        if key not in self._aggregations:
            self._aggregations[key] = []

        # Find or create aggregation for this hour
        agg = None
        for a in self._aggregations[key]:
            if a.start_time == hour_start and a.model_name == metric.model_name:
                agg = a
                break

        if not agg:
            agg = MetricAggregation(
                metric_type=metric.metric_type,
                period="1h",
                start_time=hour_start,
                end_time=hour_end,
                model_name=metric.model_name,
                provider=metric.provider,
            )
            self._aggregations[key].append(agg)

        # Update aggregation
        agg.count += 1
        agg.min_value = min(agg.min_value, metric.value) if agg.count > 1 else metric.value
        agg.max_value = max(agg.max_value, metric.value)
        agg.avg_value = (agg.avg_value * (agg.count - 1) + metric.value) / agg.count

    def _save_to_disk(self) -> None:
        """Save all data to disk."""
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Save metrics
        metrics_file = self._storage_path.parent / "metrics.jsonl"
        with metrics_file.open("w", encoding="utf-8") as f:
            for metric in self._metrics[-10000:]:  # Keep last 10k metrics
                f.write(metric.model_dump_json() + "\n")

        # Save costs
        costs_file = self._storage_path.parent / "costs.jsonl"
        with costs_file.open("w", encoding="utf-8") as f:
            for cost in self._costs[-10000:]:  # Keep last 10k costs
                f.write(cost.model_dump_json() + "\n")

        # Save alerts
        alerts_file = self._storage_path.parent / "alerts.jsonl"
        with alerts_file.open("w", encoding="utf-8") as f:
            for alert in self._alerts[-1000:]:  # Keep last 1k alerts
                f.write(alert.model_dump_json() + "\n")

        # Save alert rules
        rules_file = self._storage_path.parent / "alert_rules.jsonl"
        with rules_file.open("w", encoding="utf-8") as f:
            for rule in self._alert_rules.values():
                f.write(rule.model_dump_json() + "\n")

    def _load_from_disk(self) -> None:
        """Load all data from disk."""
        if self._storage_path is None or not self._storage_path.parent.exists():
            return

        # Load metrics
        metrics_file = self._storage_path.parent / "metrics.jsonl"
        if metrics_file.exists():
            with metrics_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        metric = LLMMetric.model_validate_json(line)
                        self._metrics.append(metric)

        # Load costs
        costs_file = self._storage_path.parent / "costs.jsonl"
        if costs_file.exists():
            with costs_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        cost = CostTracker.model_validate_json(line)
                        self._costs.append(cost)

        # Load alerts
        alerts_file = self._storage_path.parent / "alerts.jsonl"
        if alerts_file.exists():
            with alerts_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        alert = Alert.model_validate_json(line)
                        self._alerts.append(alert)

        # Load alert rules
        rules_file = self._storage_path.parent / "alert_rules.jsonl"
        if rules_file.exists():
            with rules_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        rule = AlertRule.model_validate_json(line)
                        self._alert_rules[rule.rule_id] = rule
