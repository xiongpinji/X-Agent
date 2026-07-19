"""Load testing and performance benchmarking for X-Agent."""

from locust import HttpUser, task, between, events
from locust.contrib.fasthttp import FastHttpUser
import random
import json
import logging

logger = logging.getLogger(__name__)


class XAgentUser(FastHttpUser):
    """Simulated X-Agent user for load testing."""

    wait_time = between(1, 3)

    def on_start(self):
        """Initialize user session."""
        self.api_key = "test-api-key"
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        self.agent_id = None
        self.workflow_id = None

    @task(3)
    def health_check(self):
        """Health check endpoint."""
        with self.client.get("/health", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(2)
    def list_agents(self):
        """List available agents."""
        with self.client.get("/api/agents", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                try:
                    agents = response.json()
                    if agents and isinstance(agents, list):
                        self.agent_id = agents[0].get('id')
                except:
                    pass
            else:
                response.failure(f"List agents failed: {response.status_code}")

    @task(2)
    def list_workflows(self):
        """List available workflows."""
        with self.client.get("/api/workflows", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                try:
                    workflows = response.json()
                    if workflows and isinstance(workflows, list):
                        self.workflow_id = workflows[0].get('id')
                except:
                    pass
            else:
                response.failure(f"List workflows failed: {response.status_code}")

    @task(5)
    def create_agent_run(self):
        """Create and execute an agent run."""
        if not self.agent_id:
            return

        payload = {
            "agent_id": self.agent_id,
            "input": f"Test query {random.randint(1, 1000)}",
            "parameters": {
                "max_iterations": 5,
                "timeout": 30
            }
        }

        with self.client.post(
            "/api/agents/run",
            json=payload,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [200, 201]:
                response.success()
            else:
                response.failure(f"Create agent run failed: {response.status_code}")

    @task(3)
    def create_workflow_run(self):
        """Create and execute a workflow run."""
        if not self.workflow_id:
            return

        payload = {
            "workflow_id": self.workflow_id,
            "input": {
                "query": f"Test workflow {random.randint(1, 1000)}"
            }
        }

        with self.client.post(
            "/api/workflows/run",
            json=payload,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [200, 201]:
                response.success()
            else:
                response.failure(f"Create workflow run failed: {response.status_code}")

    @task(2)
    def get_memory(self):
        """Retrieve memory entries."""
        with self.client.get(
            "/api/memory?limit=10",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Get memory failed: {response.status_code}")

    @task(1)
    def search_memory(self):
        """Search memory entries."""
        query = f"test query {random.randint(1, 100)}"
        with self.client.get(
            f"/api/memory/search?q={query}",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Search memory failed: {response.status_code}")

    @task(2)
    def get_metrics(self):
        """Get system metrics."""
        with self.client.get("/metrics", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Get metrics failed: {response.status_code}")


class AdminUser(FastHttpUser):
    """Admin user for testing admin endpoints."""

    wait_time = between(2, 5)

    def on_start(self):
        """Initialize admin session."""
        self.admin_key = "admin-api-key"
        self.headers = {
            "X-API-Key": self.admin_key,
            "Content-Type": "application/json"
        }

    @task(1)
    def get_system_stats(self):
        """Get system statistics."""
        with self.client.get("/api/admin/stats", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Get system stats failed: {response.status_code}")

    @task(1)
    def get_audit_logs(self):
        """Get audit logs."""
        with self.client.get("/api/admin/audit?limit=100", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Get audit logs failed: {response.status_code}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts."""
    logger.info("Load test started")
    logger.info(f"Target: {environment.host}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops."""
    logger.info("Load test stopped")

    # Print summary statistics
    stats = environment.stats
    logger.info("\n=== Load Test Summary ===")
    logger.info(f"Total requests: {stats.total.num_requests}")
    logger.info(f"Total failures: {stats.total.num_failures}")
    logger.info(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    logger.info(f"Min response time: {stats.total.min_response_time:.2f}ms")
    logger.info(f"Max response time: {stats.total.max_response_time:.2f}ms")
    logger.info(f"Requests/sec: {stats.total.total_rps:.2f}")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Called for each request."""
    if exception:
        logger.error(f"Request failed: {name} - {exception}")
