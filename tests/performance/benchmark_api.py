"""
API Performance Benchmark Tests using Locust.

Establishes baseline performance metrics for critical API endpoints.
Tests concurrent load, response times, and throughput.
"""

from __future__ import annotations

import time
from typing import Any

from locust import HttpUser, between, task


class APIPerformanceUser(HttpUser):
    """Simulates API user behavior for performance testing."""

    wait_time = between(1, 3)

    def on_start(self) -> None:
        """Initialize user session."""
        self.auth_token = self._get_auth_token()

    def _get_auth_token(self) -> str:
        """Get authentication token."""
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "test_user", "password": "test_password"},
        )
        if response.status_code == 200:
            return response.json().get("access_token", "")
        return ""

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with auth token."""
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }

    @task(3)
    def list_workflows(self) -> None:
        """Test workflow listing endpoint."""
        with self.client.get(
            "/api/v1/workflows",
            headers=self._get_headers(),
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(2)
    def list_runs(self) -> None:
        """Test runs listing endpoint."""
        with self.client.get(
            "/api/v1/runs?limit=20",
            headers=self._get_headers(),
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(2)
    def get_workflow_status(self) -> None:
        """Test workflow status endpoint."""
        with self.client.get(
            "/api/v1/workflows/status",
            headers=self._get_headers(),
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(1)
    def search_memory(self) -> None:
        """Test memory search endpoint."""
        with self.client.get(
            "/api/v1/memory/search?query=test&top_k=5",
            headers=self._get_headers(),
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(1)
    def get_overview(self) -> None:
        """Test overview endpoint."""
        with self.client.get(
            "/api/v1/overview",
            headers=self._get_headers(),
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")


class HighConcurrencyUser(HttpUser):
    """Simulates high concurrency scenarios."""

    wait_time = between(0.5, 1.5)

    def on_start(self) -> None:
        """Initialize user session."""
        self.auth_token = self._get_auth_token()

    def _get_auth_token(self) -> str:
        """Get authentication token."""
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "test_user", "password": "test_password"},
        )
        if response.status_code == 200:
            return response.json().get("access_token", "")
        return ""

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with auth token."""
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }

    @task
    def concurrent_list_workflows(self) -> None:
        """Test concurrent workflow listing."""
        with self.client.get(
            "/api/v1/workflows",
            headers=self._get_headers(),
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")


class CacheEffectivenessUser(HttpUser):
    """Tests cache effectiveness with repeated requests."""

    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        """Initialize user session."""
        self.auth_token = self._get_auth_token()

    def _get_auth_token(self) -> str:
        """Get authentication token."""
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "test_user", "password": "test_password"},
        )
        if response.status_code == 200:
            return response.json().get("access_token", "")
        return ""

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with auth token."""
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }

    @task
    def repeated_workflow_list(self) -> None:
        """Test repeated requests to same endpoint (cache hits)."""
        with self.client.get(
            "/api/v1/workflows",
            headers=self._get_headers(),
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
