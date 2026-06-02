"""Data models for analytics system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class MetricType(str, Enum):
    """Types of metrics."""

    API_CALL = "api_call"
    TOKEN_USAGE = "token_usage"
    TOOL_USAGE = "tool_usage"
    ERROR = "error"
    PERFORMANCE = "performance"
    COST = "cost"


class AggregationLevel(str, Enum):
    """Aggregation levels for metrics."""

    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


@dataclass
class APICallMetric:
    """API call metric."""

    timestamp: datetime
    tenant_id: str
    user_id: str
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    request_size_bytes: int
    response_size_bytes: int
    error_message: Optional[str] = None
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class TokenUsageMetric:
    """Token usage metric."""

    timestamp: datetime
    tenant_id: str
    user_id: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class ToolUsageMetric:
    """Tool usage metric."""

    timestamp: datetime
    tenant_id: str
    user_id: str
    tool_name: str
    tool_type: str
    execution_time_ms: float
    success: bool
    error_message: Optional[str] = None
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class ErrorMetric:
    """Error metric."""

    timestamp: datetime
    tenant_id: str
    user_id: str
    error_type: str
    error_message: str
    endpoint: Optional[str] = None
    stack_trace: Optional[str] = None
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class PerformanceMetric:
    """Performance metric."""

    timestamp: datetime
    tenant_id: str
    metric_name: str
    value: float
    unit: str
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class AggregatedMetric:
    """Aggregated metric."""

    timestamp: datetime
    aggregation_level: AggregationLevel
    metric_type: MetricType
    tenant_id: str
    metric_name: str
    count: int
    sum_value: float
    avg_value: float
    min_value: float
    max_value: float
    p50_value: float
    p95_value: float
    p99_value: float
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class RealtimeStats:
    """Real-time statistics."""

    timestamp: datetime
    active_users: int
    active_sessions: int
    api_calls_per_minute: float
    tokens_per_minute: int
    error_rate: float
    avg_response_time_ms: float
    current_throughput: float


@dataclass
class TrendData:
    """Trend data for analysis."""

    metric_name: str
    aggregation_level: AggregationLevel
    data_points: list[tuple[datetime, float]]
    trend_direction: str  # "up", "down", "stable"
    trend_percentage: float


@dataclass
class CostAnalysis:
    """Cost analysis data."""

    timestamp: datetime
    tenant_id: str
    period_start: datetime
    period_end: datetime
    total_cost_usd: float
    cost_by_model: dict[str, float]
    cost_by_feature: dict[str, float]
    cost_by_user: dict[str, float]
    cost_trend: float  # percentage change from previous period


@dataclass
class PerformanceAnalysis:
    """Performance analysis data."""

    timestamp: datetime
    tenant_id: str
    period_start: datetime
    period_end: datetime
    avg_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    error_rate: float
    success_rate: float
    throughput_rps: float
    slow_endpoints: list[tuple[str, float]]  # (endpoint, avg_time_ms)


@dataclass
class UserBehaviorAnalysis:
    """User behavior analysis."""

    timestamp: datetime
    tenant_id: str
    period_start: datetime
    period_end: datetime
    total_users: int
    active_users: int
    new_users: int
    returning_users: int
    avg_sessions_per_user: float
    avg_api_calls_per_user: float
    most_used_features: list[tuple[str, int]]  # (feature, count)
    usage_patterns: dict[str, Any]


@dataclass
class Report:
    """Analytics report."""

    id: str
    tenant_id: str
    report_type: str  # "daily", "weekly", "monthly", "custom"
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    data: dict[str, Any]
    format: str = "json"  # "json", "csv", "pdf"
