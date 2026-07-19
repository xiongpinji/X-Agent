"""Tests for analytics system."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from backend.app.core.analytics.collector import AnalyticsCollector
from backend.app.core.analytics.aggregator import AnalyticsAggregator
from backend.app.core.analytics.reporter import AnalyticsReporter
from backend.app.core.analytics.models import (
    APICallMetric,
    TokenUsageMetric,
    ToolUsageMetric,
    ErrorMetric,
    PerformanceMetric,
    AggregationLevel,
)


@pytest.mark.asyncio
async def test_collector_record_api_call():
    """Test recording API call metric."""
    collector = AnalyticsCollector()
    await collector.start()

    await collector.record_api_call(
        tenant_id="tenant1",
        user_id="user1",
        endpoint="/api/test",
        method="GET",
        status_code=200,
        response_time_ms=100.5,
        request_size_bytes=1024,
        response_size_bytes=2048,
    )

    metrics = await collector.flush()
    assert len(metrics) == 1
    assert isinstance(metrics[0], APICallMetric)
    assert metrics[0].endpoint == "/api/test"
    assert metrics[0].status_code == 200

    await collector.stop()


@pytest.mark.asyncio
async def test_collector_record_token_usage():
    """Test recording token usage metric."""
    collector = AnalyticsCollector()
    await collector.start()

    await collector.record_token_usage(
        tenant_id="tenant1",
        user_id="user1",
        model="gpt-4",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.15,
    )

    metrics = await collector.flush()
    assert len(metrics) == 1
    assert isinstance(metrics[0], TokenUsageMetric)
    assert metrics[0].total_tokens == 150
    assert metrics[0].cost_usd == 0.15

    await collector.stop()


@pytest.mark.asyncio
async def test_collector_record_tool_usage():
    """Test recording tool usage metric."""
    collector = AnalyticsCollector()
    await collector.start()

    await collector.record_tool_usage(
        tenant_id="tenant1",
        user_id="user1",
        tool_name="web_search",
        tool_type="search",
        execution_time_ms=500.0,
        success=True,
    )

    metrics = await collector.flush()
    assert len(metrics) == 1
    assert isinstance(metrics[0], ToolUsageMetric)
    assert metrics[0].tool_name == "web_search"
    assert metrics[0].success is True

    await collector.stop()


@pytest.mark.asyncio
async def test_collector_record_error():
    """Test recording error metric."""
    collector = AnalyticsCollector()
    await collector.start()

    await collector.record_error(
        tenant_id="tenant1",
        user_id="user1",
        error_type="ValueError",
        error_message="Invalid input",
        endpoint="/api/test",
    )

    metrics = await collector.flush()
    assert len(metrics) == 1
    assert isinstance(metrics[0], ErrorMetric)
    assert metrics[0].error_type == "ValueError"

    await collector.stop()


@pytest.mark.asyncio
async def test_aggregator_percentile():
    """Test percentile calculation."""
    storage = AsyncMock()
    aggregator = AnalyticsAggregator(storage)

    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    p50 = aggregator._percentile(data, 50)
    p95 = aggregator._percentile(data, 95)
    p99 = aggregator._percentile(data, 99)

    assert p50 == 5
    assert p95 == 10
    assert p99 == 10


@pytest.mark.asyncio
async def test_aggregator_group_by_period():
    """Test grouping by period."""
    storage = AsyncMock()
    aggregator = AnalyticsAggregator(storage)

    now = datetime.utcnow()
    items = [
        {"timestamp": now, "value": 1},
        {"timestamp": now + timedelta(minutes=1), "value": 2},
        {"timestamp": now + timedelta(hours=1), "value": 3},
    ]

    grouped = aggregator._group_by_period(items, AggregationLevel.HOUR)
    assert len(grouped) == 2  # Two different hours


@pytest.mark.asyncio
async def test_reporter_export_to_json():
    """Test exporting report to JSON."""
    storage = AsyncMock()
    aggregator = AnalyticsAggregator(storage)
    reporter = AnalyticsReporter(aggregator)

    from backend.app.core.analytics.models import Report

    report = Report(
        id="report1",
        tenant_id="tenant1",
        report_type="daily",
        period_start=datetime.utcnow(),
        period_end=datetime.utcnow(),
        generated_at=datetime.utcnow(),
        data={"test": "data"},
    )

    json_str = reporter.export_to_json(report)
    assert "report1" in json_str
    assert "daily" in json_str


@pytest.mark.asyncio
async def test_reporter_export_to_csv():
    """Test exporting report to CSV."""
    storage = AsyncMock()
    aggregator = AnalyticsAggregator(storage)
    reporter = AnalyticsReporter(aggregator)

    from backend.app.core.analytics.models import Report

    report = Report(
        id="report1",
        tenant_id="tenant1",
        report_type="daily",
        period_start=datetime.utcnow(),
        period_end=datetime.utcnow(),
        generated_at=datetime.utcnow(),
        data={"metric1": 100, "metric2": 200},
    )

    csv_str = reporter.export_to_csv(report)
    assert "Report Type" in csv_str
    assert "daily" in csv_str
    assert "metric1" in csv_str


@pytest.mark.asyncio
async def test_collector_buffer_flush():
    """Test automatic buffer flushing."""
    collector = AnalyticsCollector(buffer_size=2)
    await collector.start()

    # Add metrics
    await collector.record_api_call(
        tenant_id="tenant1",
        user_id="user1",
        endpoint="/api/test1",
        method="GET",
        status_code=200,
        response_time_ms=100.0,
    )

    await collector.record_api_call(
        tenant_id="tenant1",
        user_id="user1",
        endpoint="/api/test2",
        method="POST",
        status_code=201,
        response_time_ms=150.0,
    )

    # Buffer should be flushed automatically
    await collector.stop()


@pytest.mark.asyncio
async def test_aggregator_get_realtime_stats():
    """Test getting real-time statistics."""
    storage = AsyncMock()
    aggregator = AnalyticsAggregator(storage)

    # Mock storage response
    now = datetime.utcnow()
    storage.get_api_calls.return_value = [
        {
            "timestamp": now,
            "user_id": "user1",
            "status_code": 200,
            "response_time_ms": 100.0,
        },
        {
            "timestamp": now,
            "user_id": "user2",
            "status_code": 200,
            "response_time_ms": 150.0,
        },
    ]

    stats = await aggregator.get_realtime_stats("tenant1")
    assert stats.active_users == 2
    assert stats.api_calls_per_minute == 2
    assert stats.error_rate == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
