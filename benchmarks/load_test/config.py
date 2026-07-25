"""Load test profiles and SLO targets for X-Agent.

Usage:
    from benchmarks.load_test.config import PROFILES, SLO

    profile = PROFILES["normal"]
    # -> {"users": 50, "spawn_rate": 5, "duration": "60s"}
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Load test profiles
# ---------------------------------------------------------------------------

PROFILES: dict[str, dict[str, int | str]] = {
    "smoke": {
        "users": 5,
        "spawn_rate": 1,
        "duration": "30s",
        "description": "Quick sanity check — minimal load",
    },
    "normal": {
        "users": 50,
        "spawn_rate": 5,
        "duration": "60s",
        "description": "Typical production traffic simulation",
    },
    "stress": {
        "users": 200,
        "spawn_rate": 20,
        "duration": "120s",
        "description": "High sustained load to find breaking point",
    },
    "spike": {
        "users": 500,
        "spawn_rate": 100,
        "duration": "30s",
        "description": "Sudden traffic burst to test elasticity",
    },
}


# ---------------------------------------------------------------------------
# SLO targets — test fails if any threshold is breached
# ---------------------------------------------------------------------------

SLO: dict[str, float] = {
    "p95_latency_ms": 200.0,
    "p99_latency_ms": 1000.0,
    "error_rate_percent": 1.0,
    "min_throughput_rps": 100.0,
}


# ---------------------------------------------------------------------------
# Per-endpoint SLO overrides (optional, falls back to global SLO)
# ---------------------------------------------------------------------------

ENDPOINT_SLO: dict[str, dict[str, float]] = {
    "/health": {
        "p95_latency_ms": 50.0,
        "p99_latency_ms": 150.0,
    },
    "/api/v1/goals [LIST]": {
        "p95_latency_ms": 300.0,
    },
}


# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------

DEFAULT_HOST = "http://localhost:8000"
DEFAULT_PROFILE = "normal"
LOCUSTFILE_PATH = "benchmarks/load_test/locustfile.py"
CSV_OUTPUT_DIR = "benchmarks/load_test/results"


@dataclass
class LoadTestResult:
    """Structured result from a load test run."""

    profile: str
    total_requests: int = 0
    total_failures: int = 0
    error_rate_percent: float = 0.0
    avg_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0
    max_response_time_ms: float = 0.0
    requests_per_second: float = 0.0
    slo_passed: bool = False
    slo_violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "profile": self.profile,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "error_rate_percent": round(self.error_rate_percent, 3),
            "avg_response_time_ms": round(self.avg_response_time_ms, 1),
            "p95_response_time_ms": round(self.p95_response_time_ms, 1),
            "p99_response_time_ms": round(self.p99_response_time_ms, 1),
            "max_response_time_ms": round(self.max_response_time_ms, 1),
            "requests_per_second": round(self.requests_per_second, 1),
            "slo_passed": self.slo_passed,
            "slo_violations": self.slo_violations,
        }
