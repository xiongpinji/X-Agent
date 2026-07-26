"""Analytics API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.app.core.security import Principal
from backend.app.dependencies import (
    enforce_scope,
    get_current_principal,
)

from backend.app.core.analytics.aggregator import AnalyticsAggregator
from backend.app.core.analytics.collector import AnalyticsCollector
from backend.app.core.analytics.models import AggregationLevel
from backend.app.core.analytics.reporter import AnalyticsReporter
from backend.app.core.analytics.storage import AnalyticsStorage


# Pydantic models for API
class RealtimeStatsResponse(BaseModel):
    """Real-time statistics response."""

    timestamp: datetime
    active_users: int
    active_sessions: int
    api_calls_per_minute: float
    tokens_per_minute: int
    error_rate: float
    avg_response_time_ms: float
    current_throughput: float


class CostAnalysisResponse(BaseModel):
    """Cost analysis response."""

    total_cost_usd: float
    cost_by_model: dict[str, float]
    cost_by_feature: dict[str, float]
    cost_by_user: dict[str, float]
    cost_trend: float


class PerformanceAnalysisResponse(BaseModel):
    """Performance analysis response."""

    avg_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    error_rate: float
    success_rate: float
    throughput_rps: float
    slow_endpoints: list[dict[str, float]]


class TrendDataResponse(BaseModel):
    """Trend data response."""

    metric_name: str
    aggregation_level: str
    data_points: list[tuple[datetime, float]]
    trend_direction: str
    trend_percentage: float


class ReportResponse(BaseModel):
    """Report response."""

    id: str
    report_type: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    data: dict


# Global instances (would be injected in production)
_collector: AnalyticsCollector | None = None
_storage: AnalyticsStorage | None = None
_aggregator: AnalyticsAggregator | None = None
_reporter: AnalyticsReporter | None = None


def get_collector() -> AnalyticsCollector:
    """Get analytics collector."""
    global _collector
    if _collector is None:
        _collector = AnalyticsCollector()
    return _collector


def get_storage() -> AnalyticsStorage:
    """Get analytics storage."""
    global _storage
    if _storage is None:
        from backend.app.settings import get_settings

        settings = get_settings()
        _storage = AnalyticsStorage(settings.database_url)
    return _storage


def get_aggregator() -> AnalyticsAggregator:
    """Get analytics aggregator."""
    global _aggregator
    if _aggregator is None:
        _aggregator = AnalyticsAggregator(get_storage())
    return _aggregator


def get_reporter() -> AnalyticsReporter:
    """Get analytics reporter."""
    global _reporter
    if _reporter is None:
        _reporter = AnalyticsReporter(get_aggregator())
    return _reporter


# Router
router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
CollectorDependency = Annotated[AnalyticsCollector, Depends(get_collector)]
StorageDependency = Annotated[AnalyticsStorage, Depends(get_storage)]
AggregatorDependency = Annotated[AnalyticsAggregator, Depends(get_aggregator)]
ReporterDependency = Annotated[AnalyticsReporter, Depends(get_reporter)]


@router.get("/realtime", response_model=RealtimeStatsResponse)
async def get_realtime_stats(
    principal: PrincipalDependency,
    aggregator: AggregatorDependency,
) -> RealtimeStatsResponse:
    """Get real-time statistics.

    Args:
        principal: Current principal
        aggregator: Analytics aggregator

    Returns:
        Real-time statistics
    """
    enforce_scope(principal, "analytics:read")
    tenant_id = principal.tenant_id
    stats = await aggregator.get_realtime_stats(tenant_id)
    return RealtimeStatsResponse(**vars(stats))


@router.get("/trends", response_model=TrendDataResponse)
async def get_trends(
    principal: PrincipalDependency,
    aggregator: AggregatorDependency,
    metric_name: str = Query(...),
    level: AggregationLevel = Query(AggregationLevel.HOUR),
    days: int = Query(7, ge=1, le=90),
) -> TrendDataResponse:
    """Get trend data.

    Args:
        principal: Current principal
        aggregator: Analytics aggregator
        metric_name: Metric name
        level: Aggregation level
        days: Number of days to retrieve

    Returns:
        Trend data
    """
    enforce_scope(principal, "analytics:read")
    tenant_id = principal.tenant_id
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)

    trend = await aggregator.get_trend_data(
        tenant_id, metric_name, start_time, end_time, level
    )
    return TrendDataResponse(**vars(trend))


@router.get("/costs", response_model=CostAnalysisResponse)
async def get_costs(
    principal: PrincipalDependency,
    aggregator: AggregatorDependency,
    days: int = Query(30, ge=1, le=365),
) -> CostAnalysisResponse:
    """Get cost analysis.

    Args:
        principal: Current principal
        aggregator: Analytics aggregator
        days: Number of days to analyze

    Returns:
        Cost analysis
    """
    enforce_scope(principal, "analytics:read")
    tenant_id = principal.tenant_id
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)

    analysis = await aggregator.get_cost_analysis(tenant_id, start_time, end_time)
    return CostAnalysisResponse(**vars(analysis))


@router.get("/performance", response_model=PerformanceAnalysisResponse)
async def get_performance(
    principal: PrincipalDependency,
    aggregator: AggregatorDependency,
    days: int = Query(7, ge=1, le=90),
) -> PerformanceAnalysisResponse:
    """Get performance analysis.

    Args:
        principal: Current principal
        aggregator: Analytics aggregator
        days: Number of days to analyze

    Returns:
        Performance analysis
    """
    enforce_scope(principal, "analytics:read")
    tenant_id = principal.tenant_id
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)

    analysis = await aggregator.get_performance_analysis(
        tenant_id, start_time, end_time
    )
    return PerformanceAnalysisResponse(**vars(analysis))


@router.post("/reports/daily", response_model=ReportResponse)
async def generate_daily_report(
    principal: PrincipalDependency,
    reporter: ReporterDependency,
    date: datetime | None = Query(None),
) -> ReportResponse:
    """Generate daily report.

    Args:
        principal: Current principal
        reporter: Analytics reporter
        date: Report date (defaults to today)

    Returns:
        Generated report
    """
    enforce_scope(principal, "analytics:read")
    tenant_id = principal.tenant_id
    if date is None:
        date = datetime.utcnow()

    report = await reporter.generate_daily_report(tenant_id, date)
    return ReportResponse(**vars(report))


@router.post("/reports/weekly", response_model=ReportResponse)
async def generate_weekly_report(
    principal: PrincipalDependency,
    reporter: ReporterDependency,
    start_date: datetime | None = Query(None),
) -> ReportResponse:
    """Generate weekly report.

    Args:
        principal: Current principal
        reporter: Analytics reporter
        start_date: Week start date (defaults to this week)

    Returns:
        Generated report
    """
    enforce_scope(principal, "analytics:read")
    tenant_id = principal.tenant_id
    if start_date is None:
        start_date = datetime.utcnow()

    report = await reporter.generate_weekly_report(tenant_id, start_date)
    return ReportResponse(**vars(report))


@router.post("/reports/monthly", response_model=ReportResponse)
async def generate_monthly_report(
    principal: PrincipalDependency,
    reporter: ReporterDependency,
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
) -> ReportResponse:
    """Generate monthly report.

    Args:
        principal: Current principal
        reporter: Analytics reporter
        year: Year
        month: Month

    Returns:
        Generated report
    """
    enforce_scope(principal, "analytics:read")
    tenant_id = principal.tenant_id
    report = await reporter.generate_monthly_report(tenant_id, year, month)
    return ReportResponse(**vars(report))


@router.post("/reports/custom", response_model=ReportResponse)
async def generate_custom_report(
    principal: PrincipalDependency,
    reporter: ReporterDependency,
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    metrics: list[str] = Query(["cost", "performance"]),
) -> ReportResponse:
    """Generate custom report.

    Args:
        principal: Current principal
        reporter: Analytics reporter
        start_time: Start time
        end_time: End time
        metrics: Metrics to include

    Returns:
        Generated report
    """
    enforce_scope(principal, "analytics:read")
    tenant_id = principal.tenant_id
    report = await reporter.generate_custom_report(
        tenant_id, start_time, end_time, metrics
    )
    return ReportResponse(**vars(report))


@router.get("/reports/{report_id}")
async def get_report(
    principal: PrincipalDependency,
    report_id: str,
    format: str = Query("json", pattern="^(json|csv|pdf)$"),
) -> dict | str:
    """Get report.

    Args:
        principal: Current principal
        report_id: Report ID
        format: Export format

    Returns:
        Report data
    """
    enforce_scope(principal, "analytics:read")
    # In production, would fetch from storage
    return {"id": report_id, "format": format}
