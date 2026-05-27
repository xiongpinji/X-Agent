"""
Locust Load Testing Script for X-Agent

This script provides load testing capabilities using Locust framework.
Run with: locust -f locustfile.py --host=http://localhost:8000
"""

import random
import string
from locust import HttpUser, task, between, events
from locust.contrib.fasthttp import FastHttpUser


class XAgentUser(HttpUser):
    """Simulates X-Agent user behavior."""

    wait_time = between(1, 3)
    auth_token = None

    def on_start(self):
        """Called when a simulated user starts."""
        self.login()

    def on_stop(self):
        """Called when a simulated user stops."""
        pass

    def login(self):
        """Authenticate and get access token."""
        try:
            response = self.client.post(
                "/api/v1/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "Test1234"
                },
                name="/api/v1/auth/login"
            )
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token") or data.get("token")
        except Exception as e:
            print(f"Login failed: {e}")

    def get_headers(self):
        """Get request headers with authentication."""
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    @task(5)
    def health_check(self):
        """Health check endpoint - high frequency."""
        self.client.get("/health", name="/health")

    @task(3)
    def list_workflows(self):
        """List workflows."""
        self.client.get(
            "/api/v1/workflows",
            headers=self.get_headers(),
            name="/api/v1/workflows"
        )

    @task(2)
    def create_workflow(self):
        """Create a new workflow."""
        workflow_name = f"perf-test-{random.randint(1000, 9999)}"
        self.client.post(
            "/api/v1/workflows",
            headers=self.get_headers(),
            json={
                "name": workflow_name,
                "description": "Performance test workflow"
            },
            name="/api/v1/workflows [POST]"
        )

    @task(2)
    def list_agents(self):
        """List agents."""
        self.client.get(
            "/api/v1/agents",
            headers=self.get_headers(),
            name="/api/v1/agents"
        )

    @task(1)
    def create_agent(self):
        """Create a new agent."""
        agent_name = f"perf-agent-{random.randint(1000, 9999)}"
        self.client.post(
            "/api/v1/agents",
            headers=self.get_headers(),
            json={
                "name": agent_name,
                "description": "Performance test agent"
            },
            name="/api/v1/agents [POST]"
        )

    @task(1)
    def get_overview(self):
        """Get system overview."""
        self.client.get(
            "/api/v1/overview",
            headers=self.get_headers(),
            name="/api/v1/overview"
        )


class XAgentFastUser(FastHttpUser):
    """Fast HTTP user for high-performance load testing."""

    wait_time = between(0.5, 2)
    auth_token = None

    def on_start(self):
        """Called when a simulated user starts."""
        self.login()

    def login(self):
        """Authenticate and get access token."""
        try:
            response = self.client.post(
                "/api/v1/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "Test1234"
                }
            )
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token") or data.get("token")
        except Exception as e:
            print(f"Login failed: {e}")

    def get_headers(self):
        """Get request headers with authentication."""
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    @task(10)
    def health_check(self):
        """Health check endpoint."""
        self.client.get("/health")

    @task(5)
    def list_workflows(self):
        """List workflows."""
        self.client.get(
            "/api/v1/workflows",
            headers=self.get_headers()
        )

    @task(3)
    def list_agents(self):
        """List agents."""
        self.client.get(
            "/api/v1/agents",
            headers=self.get_headers()
        )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts."""
    print("\n" + "=" * 60)
    print("X-AGENT LOAD TEST STARTED")
    print("=" * 60)
    print(f"Target: {environment.host}")
    print(f"Users: {environment.runner.target_user_count}")
    print(f"Spawn rate: {environment.runner.spawn_rate}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops."""
    print("\n" + "=" * 60)
    print("X-AGENT LOAD TEST COMPLETED")
    print("=" * 60)

    # Print statistics
    stats = environment.stats
    print(f"\nTotal requests: {stats.total.num_requests}")
    print(f"Total failures: {stats.total.num_failures}")
    print(f"Failure rate: {stats.total.fail_ratio:.2%}")
    print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    print(f"Min response time: {stats.total.min_response_time:.2f}ms")
    print(f"Max response time: {stats.total.max_response_time:.2f}ms")
    print(f"Median response time: {stats.total.median_response_time:.2f}ms")
    print(f"95th percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"99th percentile: {stats.total.get_response_time_percentile(0.99):.2f}ms")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Called for each request."""
    if exception:
        print(f"Request failed: {name} - {exception}")
