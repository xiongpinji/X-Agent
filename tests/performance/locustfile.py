"""X-Agent Performance Load Test using Locust.

Locust-based distributed load testing framework for X-Agent endpoints.
Simulates realistic user patterns with weighted task distribution.

Run:
    locust -f tests/performance/locustfile.py --headless -u 50 -r 10 --run-time 60s --host http://localhost:8000

Performance Targets:
    - /health: 100 RPS, P99 < 50ms
    - /ready: 50 RPS, P99 < 200ms
    - /api/v1/agent/run: 10 RPS, P99 < 500ms (with mock LLM)
    - /api/v1/tools: 20 RPS, P99 < 300ms

Load Profile:
    - 50 concurrent users
    - Ramp-up: 10 users/second
    - Run time: 60 seconds
    - Wait time: 0.1-0.5s between requests per user
"""

from locust import HttpUser, task, between, events
from typing import Optional
import json
import logging
import time

logger = logging.getLogger(__name__)


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Log test start event."""
    logger.info(
        f"Load test starting: target={environment.host}, "
        f"users={environment.runner.target_user_count}"
    )


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Log test stop event and summary."""
    logger.info("Load test completed")
    logger.info(
        f"Total requests: {environment.stats.total.num_requests}, "
        f"Total failures: {environment.stats.total.num_failures}"
    )


class XAgentHealthUser(HttpUser):
    """Health check focused user — high frequency, low latency."""

    wait_time = between(0.05, 0.2)

    @task(15)
    def health_check(self):
        """Check if service is alive (target: 100 RPS, P99 < 50ms)."""
        self.client.get("/health", name="/health")

    @task(5)
    def readiness_check(self):
        """Check if service is ready (target: 50 RPS, P99 < 200ms)."""
        self.client.get("/ready", name="/ready")


class XAgentToolsUser(HttpUser):
    """Tools and catalog access — typical user pattern."""

    wait_time = between(0.1, 0.5)

    @task(8)
    def list_tools(self):
        """List available tools (target: 20 RPS, P99 < 300ms)."""
        self.client.get(
            "/api/v1/tools",
            headers={"X-API-Key": "test-key-perf"},
            name="/api/v1/tools",
        )

    @task(5)
    def get_tool_detail(self):
        """Get details of a specific tool."""
        self.client.get(
            "/api/v1/tools/browser",
            headers={"X-API-Key": "test-key-perf"},
            name="/api/v1/tools/{tool_id}",
        )

    @task(3)
    def list_agents(self):
        """List deployed agents."""
        self.client.get(
            "/api/v1/agents",
            headers={"X-API-Key": "test-key-perf"},
            name="/api/v1/agents",
        )


class XAgentExecutionUser(HttpUser):
    """Agent execution — heavier operations, slower rate."""

    wait_time = between(0.5, 2.0)

    def on_start(self):
        """Initialize user session."""
        self.api_key = "test-key-perf"
        self.agent_id = None

    @task(4)
    def submit_agent_task(self):
        """Submit an agent task (target: 10 RPS, P99 < 500ms)."""
        payload = {
            "prompt": "Analyze the following data and provide insights.",
            "mode": "quick",
            "timeout_seconds": 30,
        }
        self.client.post(
            "/api/v1/agent/run",
            json=payload,
            headers={"X-API-Key": self.api_key},
            name="/api/v1/agent/run",
        )

    @task(2)
    def chat_endpoint(self):
        """Chat with agent (conversational interface)."""
        payload = {"message": "What can you help me with?"}
        self.client.post(
            "/api/v1/chat",
            json=payload,
            headers={"X-API-Key": self.api_key},
            name="/api/v1/chat",
        )

    @task(2)
    def get_execution_status(self):
        """Check status of an execution (if ID available)."""
        self.client.get(
            "/api/v1/executions/mock-execution-id",
            headers={"X-API-Key": self.api_key},
            name="/api/v1/executions/{execution_id}",
        )

    @task(1)
    def get_memory_state(self):
        """Retrieve current memory/context state."""
        self.client.get(
            "/api/v1/memory/state",
            headers={"X-API-Key": self.api_key},
            name="/api/v1/memory/state",
        )


class XAgentCacheUser(HttpUser):
    """Cache and retrieval operations."""

    wait_time = between(0.2, 0.8)

    @task(6)
    def cache_lookup(self):
        """Look up cached results."""
        self.client.get(
            "/api/v1/cache/lookup",
            params={"key": "test-cache-key"},
            headers={"X-API-Key": "test-key-perf"},
            name="/api/v1/cache/lookup",
        )

    @task(2)
    def cache_store(self):
        """Store result in cache."""
        payload = {"key": "test-cache-key", "value": "cached-result", "ttl": 3600}
        self.client.post(
            "/api/v1/cache/store",
            json=payload,
            headers={"X-API-Key": "test-key-perf"},
            name="/api/v1/cache/store",
        )

    @task(1)
    def cache_invalidate(self):
        """Invalidate cache entry."""
        self.client.delete(
            "/api/v1/cache/invalidate",
            params={"key": "test-cache-key"},
            headers={"X-API-Key": "test-key-perf"},
            name="/api/v1/cache/invalidate",
        )


class XAgentMonitoringUser(HttpUser):
    """Monitoring and observability endpoints."""

    wait_time = between(1.0, 3.0)

    @task(5)
    def get_metrics(self):
        """Fetch Prometheus metrics."""
        self.client.get("/metrics", name="/metrics")

    @task(3)
    def get_traces(self):
        """Retrieve execution traces."""
        self.client.get(
            "/api/v1/traces",
            headers={"X-API-Key": "test-key-perf"},
            name="/api/v1/traces",
        )

    @task(2)
    def get_logs(self):
        """Retrieve application logs."""
        self.client.get(
            "/api/v1/logs",
            params={"limit": 100},
            headers={"X-API-Key": "test-key-perf"},
            name="/api/v1/logs",
        )
