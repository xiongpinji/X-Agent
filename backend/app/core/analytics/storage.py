"""Analytics data storage."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Optional

import asyncpg

from .models import (
    APICallMetric,
    TokenUsageMetric,
    ToolUsageMetric,
    ErrorMetric,
    PerformanceMetric,
    AggregatedMetric,
    AggregationLevel,
    MetricType,
)


class AnalyticsStorage:
    """Stores analytics data in PostgreSQL."""

    def __init__(self, database_url: str):
        """Initialize storage.

        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self) -> None:
        """Initialize database connection pool and create tables."""
        self.pool = await asyncpg.create_pool(self.database_url, min_size=5, max_size=20)
        await self._create_tables()

    async def close(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()

    async def _create_tables(self) -> None:
        """Create analytics tables."""
        async with self.pool.acquire() as conn:
            # API call metrics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS analytics_api_calls (
                    id BIGSERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    tenant_id VARCHAR(255) NOT NULL,
                    user_id VARCHAR(255) NOT NULL,
                    endpoint VARCHAR(255) NOT NULL,
                    method VARCHAR(10) NOT NULL,
                    status_code INT NOT NULL,
                    response_time_ms FLOAT NOT NULL,
                    request_size_bytes INT,
                    response_size_bytes INT,
                    error_message TEXT,
                    tags JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_api_calls_tenant_timestamp
                    ON analytics_api_calls(tenant_id, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_api_calls_endpoint
                    ON analytics_api_calls(endpoint);
            """)

            # Token usage metrics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS analytics_token_usage (
                    id BIGSERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    tenant_id VARCHAR(255) NOT NULL,
                    user_id VARCHAR(255) NOT NULL,
                    model VARCHAR(255) NOT NULL,
                    input_tokens INT NOT NULL,
                    output_tokens INT NOT NULL,
                    total_tokens INT NOT NULL,
                    cost_usd DECIMAL(10, 6) NOT NULL,
                    tags JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_token_usage_tenant_timestamp
                    ON analytics_token_usage(tenant_id, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_token_usage_model
                    ON analytics_token_usage(model);
            """)

            # Tool usage metrics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS analytics_tool_usage (
                    id BIGSERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    tenant_id VARCHAR(255) NOT NULL,
                    user_id VARCHAR(255) NOT NULL,
                    tool_name VARCHAR(255) NOT NULL,
                    tool_type VARCHAR(255) NOT NULL,
                    execution_time_ms FLOAT NOT NULL,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    tags JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_tool_usage_tenant_timestamp
                    ON analytics_tool_usage(tenant_id, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_tool_usage_tool_name
                    ON analytics_tool_usage(tool_name);
            """)

            # Error metrics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS analytics_errors (
                    id BIGSERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    tenant_id VARCHAR(255) NOT NULL,
                    user_id VARCHAR(255) NOT NULL,
                    error_type VARCHAR(255) NOT NULL,
                    error_message TEXT NOT NULL,
                    endpoint VARCHAR(255),
                    stack_trace TEXT,
                    tags JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_errors_tenant_timestamp
                    ON analytics_errors(tenant_id, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_errors_type
                    ON analytics_errors(error_type);
            """)

            # Performance metrics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS analytics_performance (
                    id BIGSERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    tenant_id VARCHAR(255) NOT NULL,
                    metric_name VARCHAR(255) NOT NULL,
                    value FLOAT NOT NULL,
                    unit VARCHAR(50) NOT NULL,
                    tags JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_performance_tenant_timestamp
                    ON analytics_performance(tenant_id, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_performance_metric_name
                    ON analytics_performance(metric_name);
            """)

            # Aggregated metrics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS analytics_aggregated (
                    id BIGSERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    aggregation_level VARCHAR(50) NOT NULL,
                    metric_type VARCHAR(50) NOT NULL,
                    tenant_id VARCHAR(255) NOT NULL,
                    metric_name VARCHAR(255) NOT NULL,
                    count INT NOT NULL,
                    sum_value FLOAT NOT NULL,
                    avg_value FLOAT NOT NULL,
                    min_value FLOAT NOT NULL,
                    max_value FLOAT NOT NULL,
                    p50_value FLOAT NOT NULL,
                    p95_value FLOAT NOT NULL,
                    p99_value FLOAT NOT NULL,
                    tags JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_aggregated_tenant_timestamp
                    ON analytics_aggregated(tenant_id, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_aggregated_metric_type
                    ON analytics_aggregated(metric_type);
            """)

    async def store_api_call(self, metric: APICallMetric) -> None:
        """Store API call metric."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO analytics_api_calls
                (timestamp, tenant_id, user_id, endpoint, method, status_code,
                 response_time_ms, request_size_bytes, response_size_bytes,
                 error_message, tags)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """, metric.timestamp, metric.tenant_id, metric.user_id, metric.endpoint,
                metric.method, metric.status_code, metric.response_time_ms,
                metric.request_size_bytes, metric.response_size_bytes,
                metric.error_message, json.dumps(metric.tags))

    async def store_token_usage(self, metric: TokenUsageMetric) -> None:
        """Store token usage metric."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO analytics_token_usage
                (timestamp, tenant_id, user_id, model, input_tokens, output_tokens,
                 total_tokens, cost_usd, tags)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, metric.timestamp, metric.tenant_id, metric.user_id, metric.model,
                metric.input_tokens, metric.output_tokens, metric.total_tokens,
                metric.cost_usd, json.dumps(metric.tags))

    async def store_tool_usage(self, metric: ToolUsageMetric) -> None:
        """Store tool usage metric."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO analytics_tool_usage
                (timestamp, tenant_id, user_id, tool_name, tool_type,
                 execution_time_ms, success, error_message, tags)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, metric.timestamp, metric.tenant_id, metric.user_id, metric.tool_name,
                metric.tool_type, metric.execution_time_ms, metric.success,
                metric.error_message, json.dumps(metric.tags))

    async def store_error(self, metric: ErrorMetric) -> None:
        """Store error metric."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO analytics_errors
                (timestamp, tenant_id, user_id, error_type, error_message,
                 endpoint, stack_trace, tags)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, metric.timestamp, metric.tenant_id, metric.user_id, metric.error_type,
                metric.error_message, metric.endpoint, metric.stack_trace,
                json.dumps(metric.tags))

    async def store_performance(self, metric: PerformanceMetric) -> None:
        """Store performance metric."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO analytics_performance
                (timestamp, tenant_id, metric_name, value, unit, tags)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, metric.timestamp, metric.tenant_id, metric.metric_name,
                metric.value, metric.unit, json.dumps(metric.tags))

    async def store_aggregated(self, metric: AggregatedMetric) -> None:
        """Store aggregated metric."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO analytics_aggregated
                (timestamp, aggregation_level, metric_type, tenant_id, metric_name,
                 count, sum_value, avg_value, min_value, max_value,
                 p50_value, p95_value, p99_value, tags)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            """, metric.timestamp, metric.aggregation_level.value, metric.metric_type.value,
                metric.tenant_id, metric.metric_name, metric.count, metric.sum_value,
                metric.avg_value, metric.min_value, metric.max_value,
                metric.p50_value, metric.p95_value, metric.p99_value,
                json.dumps(metric.tags))

    async def get_api_calls(
        self,
        tenant_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get API call metrics."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM analytics_api_calls
                WHERE tenant_id = $1 AND timestamp BETWEEN $2 AND $3
                ORDER BY timestamp DESC
                LIMIT $4
            """, tenant_id, start_time, end_time, limit)
            return [dict(row) for row in rows]

    async def get_token_usage(
        self,
        tenant_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get token usage metrics."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM analytics_token_usage
                WHERE tenant_id = $1 AND timestamp BETWEEN $2 AND $3
                ORDER BY timestamp DESC
                LIMIT $4
            """, tenant_id, start_time, end_time, limit)
            return [dict(row) for row in rows]

    async def cleanup_old_data(self, retention_days: int = 30) -> int:
        """Clean up old raw metrics data.

        Args:
            retention_days: Number of days to retain raw data

        Returns:
            Number of rows deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        async with self.pool.acquire() as conn:
            # Delete old raw metrics
            deleted = 0
            for table in [
                "analytics_api_calls",
                "analytics_token_usage",
                "analytics_tool_usage",
                "analytics_errors",
                "analytics_performance",
            ]:
                result = await conn.execute(f"""
                    DELETE FROM {table}
                    WHERE timestamp < $1
                """, cutoff_date)
                deleted += int(result.split()[-1])
            return deleted
