"""Analytics aggregation and analysis."""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timedelta
from typing import Any

from .models import (
    AggregatedMetric,
    AggregationLevel,
    CostAnalysis,
    MetricType,
    PerformanceAnalysis,
    RealtimeStats,
    TrendData,
)
from .storage import AnalyticsStorage


class AnalyticsAggregator:
    """Aggregates analytics data."""

    def __init__(self, storage: AnalyticsStorage):
        """Initialize aggregator.

        Args:
            storage: Analytics storage instance
        """
        self.storage = storage

    async def aggregate_api_calls(
        self,
        tenant_id: str,
        start_time: datetime,
        end_time: datetime,
        level: AggregationLevel,
    ) -> list[AggregatedMetric]:
        """Aggregate API call metrics.

        Args:
            tenant_id: Tenant identifier
            start_time: Start time
            end_time: End time
            level: Aggregation level

        Returns:
            List of aggregated metrics
        """
        api_calls = await self.storage.get_api_calls(
            tenant_id, start_time, end_time, limit=100000
        )

        if not api_calls:
            return []

        # Group by endpoint and aggregation period
        grouped = self._group_by_period(api_calls, level)
        aggregated = []

        for period_key, calls in grouped.items():
            response_times = [c["response_time_ms"] for c in calls]
            [c["status_code"] for c in calls]
            errors = sum(1 for c in calls if c["status_code"] >= 400)

            metric = AggregatedMetric(
                timestamp=period_key,
                aggregation_level=level,
                metric_type=MetricType.API_CALL,
                tenant_id=tenant_id,
                metric_name="api_calls",
                count=len(calls),
                sum_value=sum(response_times),
                avg_value=statistics.mean(response_times),
                min_value=min(response_times),
                max_value=max(response_times),
                p50_value=self._percentile(response_times, 50),
                p95_value=self._percentile(response_times, 95),
                p99_value=self._percentile(response_times, 99),
                tags={
                    "error_count": str(errors),
                    "error_rate": f"{errors / len(calls) * 100:.2f}%",
                },
            )
            aggregated.append(metric)

        return aggregated

    async def aggregate_token_usage(
        self,
        tenant_id: str,
        start_time: datetime,
        end_time: datetime,
        level: AggregationLevel,
    ) -> list[AggregatedMetric]:
        """Aggregate token usage metrics.

        Args:
            tenant_id: Tenant identifier
            start_time: Start time
            end_time: End time
            level: Aggregation level

        Returns:
            List of aggregated metrics
        """
        token_usage = await self.storage.get_token_usage(
            tenant_id, start_time, end_time, limit=100000
        )

        if not token_usage:
            return []

        grouped = self._group_by_period(token_usage, level)
        aggregated = []

        for period_key, usages in grouped.items():
            total_tokens = sum(u["total_tokens"] for u in usages)
            total_cost = sum(float(u["cost_usd"]) for u in usages)

            metric = AggregatedMetric(
                timestamp=period_key,
                aggregation_level=level,
                metric_type=MetricType.TOKEN_USAGE,
                tenant_id=tenant_id,
                metric_name="token_usage",
                count=len(usages),
                sum_value=total_tokens,
                avg_value=total_tokens / len(usages),
                min_value=min(u["total_tokens"] for u in usages),
                max_value=max(u["total_tokens"] for u in usages),
                p50_value=self._percentile(
                    [u["total_tokens"] for u in usages], 50
                ),
                p95_value=self._percentile(
                    [u["total_tokens"] for u in usages], 95
                ),
                p99_value=self._percentile(
                    [u["total_tokens"] for u in usages], 99
                ),
                tags={"total_cost_usd": f"{total_cost:.2f}"},
            )
            aggregated.append(metric)

        return aggregated

    async def get_realtime_stats(self, tenant_id: str) -> RealtimeStats:
        """Get real-time statistics.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Real-time statistics
        """
        now = datetime.utcnow()
        one_minute_ago = now - timedelta(minutes=1)
        five_minutes_ago = now - timedelta(minutes=5)

        # Get API calls in last minute
        api_calls_1m = await self.storage.get_api_calls(
            tenant_id, one_minute_ago, now, limit=10000
        )
        api_calls_5m = await self.storage.get_api_calls(
            tenant_id, five_minutes_ago, now, limit=10000
        )

        # Calculate metrics
        api_calls_per_minute = len(api_calls_1m)
        errors = sum(1 for c in api_calls_1m if c["status_code"] >= 400)
        error_rate = errors / len(api_calls_1m) if api_calls_1m else 0

        response_times = [c["response_time_ms"] for c in api_calls_1m]
        avg_response_time = (
            statistics.mean(response_times) if response_times else 0
        )

        throughput = len(api_calls_5m) / 5  # calls per minute

        return RealtimeStats(
            timestamp=now,
            active_users=len({c["user_id"] for c in api_calls_5m}),
            active_sessions=len(api_calls_5m),
            api_calls_per_minute=float(api_calls_per_minute),
            tokens_per_minute=0,  # Would need token data
            error_rate=error_rate,
            avg_response_time_ms=avg_response_time,
            current_throughput=throughput,
        )

    async def get_trend_data(
        self,
        tenant_id: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        level: AggregationLevel,
    ) -> TrendData:
        """Get trend data for a metric.

        Args:
            tenant_id: Tenant identifier
            metric_name: Metric name
            start_time: Start time
            end_time: End time
            level: Aggregation level

        Returns:
            Trend data
        """
        # This would query aggregated metrics from storage
        # For now, return placeholder
        return TrendData(
            metric_name=metric_name,
            aggregation_level=level,
            data_points=[],
            trend_direction="stable",
            trend_percentage=0.0,
        )

    async def get_cost_analysis(
        self,
        tenant_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> CostAnalysis:
        """Get cost analysis.

        Args:
            tenant_id: Tenant identifier
            start_time: Start time
            end_time: End time

        Returns:
            Cost analysis
        """
        token_usage = await self.storage.get_token_usage(
            tenant_id, start_time, end_time, limit=100000
        )

        total_cost = sum(float(u["cost_usd"]) for u in token_usage)
        cost_by_model = {}
        cost_by_user = {}

        for usage in token_usage:
            model = usage["model"]
            user_id = usage["user_id"]
            cost = float(usage["cost_usd"])

            cost_by_model[model] = cost_by_model.get(model, 0) + cost
            cost_by_user[user_id] = cost_by_user.get(user_id, 0) + cost

        return CostAnalysis(
            timestamp=datetime.utcnow(),
            tenant_id=tenant_id,
            period_start=start_time,
            period_end=end_time,
            total_cost_usd=total_cost,
            cost_by_model=cost_by_model,
            cost_by_feature={},
            cost_by_user=cost_by_user,
            cost_trend=0.0,
        )

    async def get_performance_analysis(
        self,
        tenant_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> PerformanceAnalysis:
        """Get performance analysis.

        Args:
            tenant_id: Tenant identifier
            start_time: Start time
            end_time: End time

        Returns:
            Performance analysis
        """
        api_calls = await self.storage.get_api_calls(
            tenant_id, start_time, end_time, limit=100000
        )

        if not api_calls:
            return PerformanceAnalysis(
                timestamp=datetime.utcnow(),
                tenant_id=tenant_id,
                period_start=start_time,
                period_end=end_time,
                avg_response_time_ms=0,
                p95_response_time_ms=0,
                p99_response_time_ms=0,
                error_rate=0,
                success_rate=0,
                throughput_rps=0,
                slow_endpoints=[],
            )

        response_times = [c["response_time_ms"] for c in api_calls]
        errors = sum(1 for c in api_calls if c["status_code"] >= 400)
        duration_seconds = (end_time - start_time).total_seconds()

        # Find slow endpoints
        endpoint_times = {}
        for call in api_calls:
            endpoint = call["endpoint"]
            if endpoint not in endpoint_times:
                endpoint_times[endpoint] = []
            endpoint_times[endpoint].append(call["response_time_ms"])

        slow_endpoints = [
            (endpoint, statistics.mean(times))
            for endpoint, times in endpoint_times.items()
        ]
        slow_endpoints.sort(key=lambda x: x[1], reverse=True)

        return PerformanceAnalysis(
            timestamp=datetime.utcnow(),
            tenant_id=tenant_id,
            period_start=start_time,
            period_end=end_time,
            avg_response_time_ms=statistics.mean(response_times),
            p95_response_time_ms=self._percentile(response_times, 95),
            p99_response_time_ms=self._percentile(response_times, 99),
            error_rate=errors / len(api_calls),
            success_rate=1 - (errors / len(api_calls)),
            throughput_rps=len(api_calls) / duration_seconds,
            slow_endpoints=slow_endpoints[:10],
        )

    def _group_by_period(
        self, items: list[dict[str, Any]], level: AggregationLevel
    ) -> dict[datetime, list[dict[str, Any]]]:
        """Group items by aggregation period.

        Args:
            items: Items to group
            level: Aggregation level

        Returns:
            Dictionary of grouped items
        """
        grouped = {}
        for item in items:
            timestamp = item["timestamp"]
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)

            period_key = self._get_period_key(timestamp, level)
            if period_key not in grouped:
                grouped[period_key] = []
            grouped[period_key].append(item)

        return grouped

    def _get_period_key(self, timestamp: datetime, level: AggregationLevel) -> datetime:
        """Get period key for timestamp.

        Args:
            timestamp: Timestamp
            level: Aggregation level

        Returns:
            Period key
        """
        if level == AggregationLevel.MINUTE:
            return timestamp.replace(second=0, microsecond=0)
        elif level == AggregationLevel.HOUR:
            return timestamp.replace(minute=0, second=0, microsecond=0)
        elif level == AggregationLevel.DAY:
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        elif level == AggregationLevel.WEEK:
            days_since_monday = timestamp.weekday()
            return (timestamp - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif level == AggregationLevel.MONTH:
            return timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return timestamp

    def _percentile(self, data: list[float], percentile: int) -> float:
        """Calculate percentile.

        Args:
            data: Data points
            percentile: Percentile (0-100)

        Returns:
            Percentile value
        """
        if not data:
            return 0
        sorted_data = sorted(data)
        # 最近秩(nearest-rank)百分位:rank = ceil(p/100 * n),取第 rank 个(1-based)。
        # 旧实现用 int(n * p/100) 会偏高一位(P50 of [1..10] 错算成 6,应为 5)。
        n = len(sorted_data)
        rank = math.ceil(percentile / 100 * n)
        index = min(max(rank - 1, 0), n - 1)
        return sorted_data[index]
