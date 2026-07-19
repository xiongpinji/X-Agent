"""
Performance Monitoring and Reporting Module.

Tracks API performance metrics and generates reports.
Integrates with monitoring systems.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class APIMetric:
    """Single API metric data point."""

    endpoint: str
    method: str
    status_code: int
    response_time: float
    timestamp: float = field(default_factory=time.time)
    request_size: int = 0
    response_size: int = 0
    cache_hit: bool = False
    db_queries: int = 0
    db_time: float = 0.0
    error: str | None = None


@dataclass
class PerformanceReport:
    """Performance report for an endpoint."""

    endpoint: str
    method: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    min_response_time: float = float("inf")
    max_response_time: float = 0.0
    p50_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    cache_hit_rate: float = 0.0
    avg_db_queries: float = 0.0
    avg_db_time: float = 0.0
    throughput: float = 0.0  # requests per second
    error_rate: float = 0.0
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class PerformanceMonitor:
    """Monitors API performance metrics."""

    def __init__(self, window_size: int = 1000) -> None:
        self.window_size = window_size
        self.metrics: dict[str, list[APIMetric]] = {}
        self.start_time = time.time()

    def record_metric(self, metric: APIMetric) -> None:
        """Record API metric."""
        key = f"{metric.method} {metric.endpoint}"

        if key not in self.metrics:
            self.metrics[key] = []

        self.metrics[key].append(metric)

        # Keep only recent metrics (sliding window)
        if len(self.metrics[key]) > self.window_size:
            self.metrics[key] = self.metrics[key][-self.window_size :]

    def get_report(self, endpoint: str, method: str = "GET") -> PerformanceReport:
        """Generate performance report for endpoint."""
        key = f"{method} {endpoint}"

        if key not in self.metrics or not self.metrics[key]:
            return PerformanceReport(endpoint=endpoint, method=method)

        metrics = self.metrics[key]
        response_times = [m.response_time for m in metrics]
        db_times = [m.db_time for m in metrics]
        db_queries = [m.db_queries for m in metrics]

        successful = sum(1 for m in metrics if 200 <= m.status_code < 300)
        failed = len(metrics) - successful
        cache_hits = sum(1 for m in metrics if m.cache_hit)

        # Calculate percentiles
        sorted_times = sorted(response_times)
        p50_idx = len(sorted_times) // 2
        p95_idx = int(len(sorted_times) * 0.95)
        p99_idx = int(len(sorted_times) * 0.99)

        uptime = time.time() - self.start_time

        return PerformanceReport(
            endpoint=endpoint,
            method=method,
            total_requests=len(metrics),
            successful_requests=successful,
            failed_requests=failed,
            avg_response_time=sum(response_times) / len(response_times),
            min_response_time=min(response_times),
            max_response_time=max(response_times),
            p50_response_time=sorted_times[p50_idx],
            p95_response_time=sorted_times[p95_idx],
            p99_response_time=sorted_times[p99_idx],
            cache_hit_rate=(cache_hits / len(metrics)) * 100 if metrics else 0.0,
            avg_db_queries=sum(db_queries) / len(db_queries) if db_queries else 0.0,
            avg_db_time=sum(db_times) / len(db_times) if db_times else 0.0,
            throughput=len(metrics) / uptime if uptime > 0 else 0.0,
            error_rate=(failed / len(metrics)) * 100 if metrics else 0.0,
        )

    def get_all_reports(self) -> dict[str, PerformanceReport]:
        """Get reports for all endpoints."""
        reports = {}
        for key in self.metrics.keys():
            method, endpoint = key.split(" ", 1)
            reports[key] = self.get_report(endpoint, method)
        return reports

    def generate_html_report(self) -> str:
        """Generate HTML performance report."""
        reports = self.get_all_reports()

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>API Performance Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #4CAF50; color: white; }
                tr:nth-child(even) { background-color: #f2f2f2; }
                .good { color: green; }
                .warning { color: orange; }
                .bad { color: red; }
            </style>
        </head>
        <body>
            <h1>API Performance Report</h1>
            <p>Generated: {}</p>
            <table>
                <tr>
                    <th>Endpoint</th>
                    <th>Total Requests</th>
                    <th>Success Rate</th>
                    <th>Avg Response Time</th>
                    <th>P95 Response Time</th>
                    <th>P99 Response Time</th>
                    <th>Cache Hit Rate</th>
                    <th>Throughput (req/s)</th>
                </tr>
        """.format(datetime.utcnow().isoformat())

        for key, report in reports.items():
            success_rate = 100 - report.error_rate
            success_class = "good" if success_rate >= 99 else "warning" if success_rate >= 95 else "bad"

            html += f"""
                <tr>
                    <td>{report.method} {report.endpoint}</td>
                    <td>{report.total_requests}</td>
                    <td class="{success_class}">{success_rate:.2f}%</td>
                    <td>{report.avg_response_time:.4f}s</td>
                    <td>{report.p95_response_time:.4f}s</td>
                    <td>{report.p99_response_time:.4f}s</td>
                    <td>{report.cache_hit_rate:.2f}%</td>
                    <td>{report.throughput:.2f}</td>
                </tr>
            """

        html += """
            </table>
        </body>
        </html>
        """

        return html

    def generate_json_report(self) -> str:
        """Generate JSON performance report."""
        reports = self.get_all_reports()
        report_dicts = {key: report.to_dict() for key, report in reports.items()}
        return json.dumps(report_dicts, indent=2)


class PerformanceAlert:
    """Triggers alerts based on performance thresholds."""

    def __init__(
        self,
        response_time_threshold: float = 1.0,
        error_rate_threshold: float = 5.0,
        cache_hit_threshold: float = 50.0,
    ) -> None:
        self.response_time_threshold = response_time_threshold
        self.error_rate_threshold = error_rate_threshold
        self.cache_hit_threshold = cache_hit_threshold
        self.alerts: list[str] = []

    def check_report(self, report: PerformanceReport) -> list[str]:
        """Check report against thresholds and generate alerts."""
        alerts = []

        if report.avg_response_time > self.response_time_threshold:
            alerts.append(
                f"ALERT: {report.method} {report.endpoint} "
                f"avg response time {report.avg_response_time:.4f}s "
                f"exceeds threshold {self.response_time_threshold}s"
            )

        if report.error_rate > self.error_rate_threshold:
            alerts.append(
                f"ALERT: {report.method} {report.endpoint} "
                f"error rate {report.error_rate:.2f}% "
                f"exceeds threshold {self.error_rate_threshold}%"
            )

        if report.cache_hit_rate < self.cache_hit_threshold:
            alerts.append(
                f"ALERT: {report.method} {report.endpoint} "
                f"cache hit rate {report.cache_hit_rate:.2f}% "
                f"below threshold {self.cache_hit_threshold}%"
            )

        self.alerts.extend(alerts)
        return alerts

    def get_alerts(self) -> list[str]:
        """Get all alerts."""
        return self.alerts

    def clear_alerts(self) -> None:
        """Clear alerts."""
        self.alerts.clear()


# Global performance monitor instance
_monitor = PerformanceMonitor()


def get_monitor() -> PerformanceMonitor:
    """Get global performance monitor."""
    return _monitor


def record_metric(metric: APIMetric) -> None:
    """Record API metric."""
    _monitor.record_metric(metric)


def get_report(endpoint: str, method: str = "GET") -> PerformanceReport:
    """Get performance report for endpoint."""
    return _monitor.get_report(endpoint, method)


def get_all_reports() -> dict[str, PerformanceReport]:
    """Get all performance reports."""
    return _monitor.get_all_reports()
