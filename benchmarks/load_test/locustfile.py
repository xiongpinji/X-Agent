"""X-Agent Load Test — validates API performance under concurrent load.

Usage:
    locust -f benchmarks/load_test/locustfile.py --host=http://localhost:8000

Or headless:
    locust -f benchmarks/load_test/locustfile.py --host=http://localhost:8000 \
        --users 50 --spawn-rate 5 --run-time 60s --headless

Profiles (via run_load_test.py):
    python benchmarks/load_test/run_load_test.py --profile smoke
    python benchmarks/load_test/run_load_test.py --profile stress
"""
from __future__ import annotations

import json
import random
import string
import time

from locust import HttpUser, task, between, events, tag


# ---------------------------------------------------------------------------
# Event listeners for observability
# ---------------------------------------------------------------------------

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Log test start metadata."""
    print("\n" + "=" * 70)
    print("  X-AGENT LOAD TEST STARTED")
    print("=" * 70)
    print(f"  Target host : {environment.host}")
    runner = environment.runner
    if hasattr(runner, "target_user_count"):
        print(f"  Users       : {runner.target_user_count}")
    if hasattr(runner, "spawn_rate"):
        print(f"  Spawn rate  : {runner.spawn_rate}")
    print("=" * 70 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print summary statistics at test end."""
    stats = environment.stats
    total = stats.total
    print("\n" + "=" * 70)
    print("  X-AGENT LOAD TEST COMPLETED")
    print("=" * 70)
    print(f"  Total requests   : {total.num_requests}")
    print(f"  Total failures   : {total.num_failures}")
    print(f"  Failure rate     : {total.fail_ratio:.2%}")
    print(f"  Avg response     : {total.avg_response_time:.1f} ms")
    print(f"  Median response  : {total.median_response_time:.1f} ms")
    p95 = total.get_response_time_percentile(0.95)
    p99 = total.get_response_time_percentile(0.99)
    print(f"  P95 response     : {p95:.1f} ms")
    print(f"  P99 response     : {p99:.1f} ms")
    print(f"  Max response     : {total.max_response_time:.1f} ms")
    print(f"  Requests/sec     : {total.total_rps:.1f}")
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _random_suffix(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


# ---------------------------------------------------------------------------
# User classes
# ---------------------------------------------------------------------------

class XAgentUser(HttpUser):
    """Simulates a typical X-Agent API user."""

    wait_time = between(0.5, 2.0)
    weight = 5  # Majority of traffic

    def on_start(self):
        """Setup: authenticate and prepare state."""
        self.goal_id: str | None = None
        self.auth_token: str | None = None
        self._login()

    def _login(self):
        """Attempt login; tolerate failure for unauthenticated endpoints."""
        try:
            resp = self.client.post(
                "/api/v1/auth/login",
                json={"email": "loadtest@example.com", "password": "LoadTest123!"},
                name="/api/v1/auth/login",
            )
            if resp.status_code == 200:
                data = resp.json()
                self.auth_token = data.get("access_token") or data.get("token")
        except Exception:
            pass

    def _headers(self) -> dict:
        if self.auth_token:
            return {"Authorization": f"Bearer {self.auth_token}"}
        return {}

    # -- Tasks ---------------------------------------------------------------

    @tag("core", "read")
    @task(5)
    def health_check(self):
        self.client.get("/health", name="/health")

    @tag("core", "read")
    @task(3)
    def list_goals(self):
        self.client.get(
            "/api/v1/goals",
            headers=self._headers(),
            name="/api/v1/goals [LIST]",
        )

    @tag("core", "write")
    @task(2)
    def create_goal(self):
        resp = self.client.post(
            "/api/v1/goals",
            headers=self._headers(),
            json={"objective": f"Load test goal {_random_suffix()}"},
            name="/api/v1/goals [CREATE]",
        )
        if resp.status_code in (200, 201):
            try:
                self.goal_id = resp.json().get("id")
            except Exception:
                pass

    @tag("core", "write")
    @task(1)
    def complete_goal(self):
        if self.goal_id:
            self.client.post(
                f"/api/v1/goals/{self.goal_id}/complete",
                headers=self._headers(),
                name="/api/v1/goals/{id}/complete",
            )

    @tag("tools", "read")
    @task(2)
    def list_tools(self):
        self.client.get(
            "/api/v1/tools",
            headers=self._headers(),
            name="/api/v1/tools",
        )

    @tag("sso", "read")
    @task(1)
    def sso_status(self):
        self.client.get(
            "/api/v1/sso/status",
            headers=self._headers(),
            name="/api/v1/sso/status",
        )

    @tag("evolution", "read")
    @task(1)
    def evolution_stats(self):
        self.client.get(
            "/api/v1/evolution/stats",
            headers=self._headers(),
            name="/api/v1/evolution/stats",
        )


class XAgentPowerUser(HttpUser):
    """Simulates a power user doing code reviews and workflow operations."""

    wait_time = between(1.0, 3.0)
    weight = 2  # Fewer power users

    def on_start(self):
        self.auth_token: str | None = None
        self._login()

    def _login(self):
        try:
            resp = self.client.post(
                "/api/v1/auth/login",
                json={"email": "poweruser@example.com", "password": "PowerTest123!"},
                name="/api/v1/auth/login",
            )
            if resp.status_code == 200:
                data = resp.json()
                self.auth_token = data.get("access_token") or data.get("token")
        except Exception:
            pass

    def _headers(self) -> dict:
        if self.auth_token:
            return {"Authorization": f"Bearer {self.auth_token}"}
        return {}

    @tag("code-review", "write")
    @task(2)
    def code_review(self):
        self.client.post(
            "/api/v1/code-review/file",
            headers=self._headers(),
            json={
                "file_path": f"test_{_random_suffix()}.py",
                "content": "def hello():\n    print('world')\n",
                "language": "python",
            },
            name="/api/v1/code-review/file",
        )

    @tag("workflows", "read")
    @task(1)
    def list_workflows(self):
        self.client.get(
            "/api/v1/workflows",
            headers=self._headers(),
            name="/api/v1/workflows",
        )

    @tag("agents", "read")
    @task(1)
    def list_agents(self):
        self.client.get(
            "/api/v1/agents",
            headers=self._headers(),
            name="/api/v1/agents",
        )

    @tag("workflows", "write")
    @task(1)
    def create_workflow(self):
        self.client.post(
            "/api/v1/workflows",
            headers=self._headers(),
            json={
                "name": f"load-wf-{_random_suffix()}",
                "description": "Load test workflow",
            },
            name="/api/v1/workflows [CREATE]",
        )
