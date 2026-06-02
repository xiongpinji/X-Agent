"""Configuration for analytics system."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnalyticsConfig:
    """Analytics system configuration."""

    # Collector settings
    collector_buffer_size: int = 10000
    collector_flush_interval_seconds: int = 60

    # Storage settings
    database_url: str = "postgresql://localhost/xagent"
    storage_pool_min_size: int = 5
    storage_pool_max_size: int = 20

    # Aggregation settings
    enable_auto_aggregation: bool = True
    aggregation_interval_seconds: int = 300  # 5 minutes

    # Data retention settings
    raw_data_retention_days: int = 30
    minute_aggregation_retention_days: int = 7
    hour_aggregation_retention_days: int = 90
    day_aggregation_retention_days: int = 365

    # Performance settings
    max_query_results: int = 100000
    query_timeout_seconds: int = 30

    # Feature flags
    enable_realtime_stats: bool = True
    enable_cost_analysis: bool = True
    enable_performance_analysis: bool = True
    enable_user_behavior_analysis: bool = True

    # Alerting settings
    enable_alerting: bool = False
    alert_webhook_url: Optional[str] = None

    # Export settings
    enable_json_export: bool = True
    enable_csv_export: bool = True
    enable_pdf_export: bool = False

    # Dashboard settings
    dashboard_refresh_interval_seconds: int = 5
    dashboard_max_data_points: int = 1000


# Default configuration
DEFAULT_ANALYTICS_CONFIG = AnalyticsConfig()
