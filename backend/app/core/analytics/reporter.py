"""Analytics reporting."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from .models import (
    Report,
    AggregationLevel,
    CostAnalysis,
    PerformanceAnalysis,
    UserBehaviorAnalysis,
)
from .aggregator import AnalyticsAggregator


class AnalyticsReporter:
    """Generates analytics reports."""

    def __init__(self, aggregator: AnalyticsAggregator):
        """Initialize reporter.

        Args:
            aggregator: Analytics aggregator instance
        """
        self.aggregator = aggregator

    async def generate_daily_report(
        self,
        tenant_id: str,
        date: datetime,
    ) -> Report:
        """Generate daily report.

        Args:
            tenant_id: Tenant identifier
            date: Report date

        Returns:
            Generated report
        """
        start_time = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time.replace(hour=23, minute=59, second=59)

        cost_analysis = await self.aggregator.get_cost_analysis(
            tenant_id, start_time, end_time
        )
        perf_analysis = await self.aggregator.get_performance_analysis(
            tenant_id, start_time, end_time
        )

        return Report(
            id=str(uuid4()),
            tenant_id=tenant_id,
            report_type="daily",
            period_start=start_time,
            period_end=end_time,
            generated_at=datetime.utcnow(),
            data={
                "cost_analysis": self._serialize_cost_analysis(cost_analysis),
                "performance_analysis": self._serialize_perf_analysis(perf_analysis),
            },
        )

    async def generate_weekly_report(
        self,
        tenant_id: str,
        start_date: datetime,
    ) -> Report:
        """Generate weekly report.

        Args:
            tenant_id: Tenant identifier
            start_date: Week start date

        Returns:
            Generated report
        """
        start_time = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = (start_time + __import__("datetime").timedelta(days=7)).replace(
            hour=23, minute=59, second=59
        )

        cost_analysis = await self.aggregator.get_cost_analysis(
            tenant_id, start_time, end_time
        )
        perf_analysis = await self.aggregator.get_performance_analysis(
            tenant_id, start_time, end_time
        )

        return Report(
            id=str(uuid4()),
            tenant_id=tenant_id,
            report_type="weekly",
            period_start=start_time,
            period_end=end_time,
            generated_at=datetime.utcnow(),
            data={
                "cost_analysis": self._serialize_cost_analysis(cost_analysis),
                "performance_analysis": self._serialize_perf_analysis(perf_analysis),
            },
        )

    async def generate_monthly_report(
        self,
        tenant_id: str,
        year: int,
        month: int,
    ) -> Report:
        """Generate monthly report.

        Args:
            tenant_id: Tenant identifier
            year: Year
            month: Month

        Returns:
            Generated report
        """
        start_time = datetime(year, month, 1)
        if month == 12:
            end_time = datetime(year + 1, 1, 1)
        else:
            end_time = datetime(year, month + 1, 1)
        end_time = end_time.replace(hour=23, minute=59, second=59)

        cost_analysis = await self.aggregator.get_cost_analysis(
            tenant_id, start_time, end_time
        )
        perf_analysis = await self.aggregator.get_performance_analysis(
            tenant_id, start_time, end_time
        )

        return Report(
            id=str(uuid4()),
            tenant_id=tenant_id,
            report_type="monthly",
            period_start=start_time,
            period_end=end_time,
            generated_at=datetime.utcnow(),
            data={
                "cost_analysis": self._serialize_cost_analysis(cost_analysis),
                "performance_analysis": self._serialize_perf_analysis(perf_analysis),
            },
        )

    async def generate_custom_report(
        self,
        tenant_id: str,
        start_time: datetime,
        end_time: datetime,
        metrics: list[str],
    ) -> Report:
        """Generate custom report.

        Args:
            tenant_id: Tenant identifier
            start_time: Start time
            end_time: End time
            metrics: List of metrics to include

        Returns:
            Generated report
        """
        data = {}

        if "cost" in metrics:
            cost_analysis = await self.aggregator.get_cost_analysis(
                tenant_id, start_time, end_time
            )
            data["cost_analysis"] = self._serialize_cost_analysis(cost_analysis)

        if "performance" in metrics:
            perf_analysis = await self.aggregator.get_performance_analysis(
                tenant_id, start_time, end_time
            )
            data["performance_analysis"] = self._serialize_perf_analysis(perf_analysis)

        return Report(
            id=str(uuid4()),
            tenant_id=tenant_id,
            report_type="custom",
            period_start=start_time,
            period_end=end_time,
            generated_at=datetime.utcnow(),
            data=data,
        )

    def export_to_json(self, report: Report) -> str:
        """Export report to JSON.

        Args:
            report: Report to export

        Returns:
            JSON string
        """
        return json.dumps(
            {
                "id": report.id,
                "tenant_id": report.tenant_id,
                "report_type": report.report_type,
                "period_start": report.period_start.isoformat(),
                "period_end": report.period_end.isoformat(),
                "generated_at": report.generated_at.isoformat(),
                "data": report.data,
            },
            indent=2,
        )

    def export_to_csv(self, report: Report) -> str:
        """Export report to CSV.

        Args:
            report: Report to export

        Returns:
            CSV string
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(
            [
                "Report Type",
                "Period Start",
                "Period End",
                "Generated At",
            ]
        )

        # Write data
        writer.writerow(
            [
                report.report_type,
                report.period_start.isoformat(),
                report.period_end.isoformat(),
                report.generated_at.isoformat(),
            ]
        )

        # Write metrics
        writer.writerow([])
        writer.writerow(["Metric", "Value"])

        for key, value in report.data.items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    writer.writerow([f"{key}.{subkey}", str(subvalue)])
            else:
                writer.writerow([key, str(value)])

        return output.getvalue()

    def _serialize_cost_analysis(self, analysis: CostAnalysis) -> dict[str, Any]:
        """Serialize cost analysis.

        Args:
            analysis: Cost analysis

        Returns:
            Serialized data
        """
        return {
            "total_cost_usd": analysis.total_cost_usd,
            "cost_by_model": analysis.cost_by_model,
            "cost_by_feature": analysis.cost_by_feature,
            "cost_by_user": analysis.cost_by_user,
            "cost_trend": analysis.cost_trend,
        }

    def _serialize_perf_analysis(self, analysis: PerformanceAnalysis) -> dict[str, Any]:
        """Serialize performance analysis.

        Args:
            analysis: Performance analysis

        Returns:
            Serialized data
        """
        return {
            "avg_response_time_ms": analysis.avg_response_time_ms,
            "p95_response_time_ms": analysis.p95_response_time_ms,
            "p99_response_time_ms": analysis.p99_response_time_ms,
            "error_rate": analysis.error_rate,
            "success_rate": analysis.success_rate,
            "throughput_rps": analysis.throughput_rps,
            "slow_endpoints": [
                {"endpoint": ep, "avg_time_ms": time} for ep, time in analysis.slow_endpoints
            ],
        }
