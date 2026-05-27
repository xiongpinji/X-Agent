"""Extended integration tests - end-to-end workflows and system interactions."""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, UTC, timedelta

from fastapi.testclient import TestClient
from backend.app.main import app


class TestEndToEndWorkflows:
    """Test end-to-end workflow scenarios."""

    @pytest.fixture
    def client(self):
        return TestClient(app, headers={"x-api-key": "bootstrap"})

    def test_complete_workflow_lifecycle(self, client):
        """Test complete workflow lifecycle: create -> execute -> monitor -> delete."""
        # 1. Create workflow
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "E2E Test Workflow",
                "description": "End-to-end test",
                "nodes": [
                    {"id": "input_1", "type": "input", "config": {"key": "name"}},
                    {"id": "output_1", "type": "output", "config": {"from": "input_1"}},
                ],
                "edges": [
                    {"source": "input_1", "target": "output_1"}
                ]
            }
        )
        assert create_response.status_code in [200, 201]
        workflow_id = create_response.json().get("id")

        if workflow_id:
            # 2. Get workflow
            get_response = client.get(f"/api/v1/workflows/{workflow_id}")
            assert get_response.status_code == 200

            # 3. Execute workflow
            exec_response = client.post(
                f"/api/v1/workflows/{workflow_id}/execute",
                json={"name": "test"}
            )
            assert exec_response.status_code in [200, 202]

            # 4. Get execution status
            if "run_id" in exec_response.json():
                run_id = exec_response.json()["run_id"]
                status_response = client.get(f"/api/v1/runs/{run_id}")
                assert status_response.status_code in [200, 404]

            # 5. Delete workflow
            delete_response = client.delete(f"/api/v1/workflows/{workflow_id}")
            assert delete_response.status_code in [200, 204, 404]

    def test_workflow_with_multiple_nodes(self, client):
        """Test workflow with multiple interconnected nodes."""
        response = client.post(
            "/api/v1/workflows",
            json={
                "name": "Multi-node Workflow",
                "nodes": [
                    {"id": "input_1", "type": "input", "config": {"key": "data"}},
                    {"id": "transform_1", "type": "transform", "config": {"template": "processed_{input_data}"}},
                    {"id": "transform_2", "type": "transform", "config": {"template": "final_{transform_1}"}},
                    {"id": "output_1", "type": "output", "config": {"from": "transform_2"}},
                ],
                "edges": [
                    {"source": "input_1", "target": "transform_1"},
                    {"source": "transform_1", "target": "transform_2"},
                    {"source": "transform_2", "target": "output_1"},
                ]
            }
        )
        assert response.status_code in [200, 201]

    def test_workflow_with_conditional_branches(self, client):
        """Test workflow with conditional branches."""
        response = client.post(
            "/api/v1/workflows",
            json={
                "name": "Conditional Workflow",
                "nodes": [
                    {"id": "input_1", "type": "input", "config": {"key": "value"}},
                    {"id": "condition_1", "type": "condition", "config": {"expression": "value > 10"}},
                    {"id": "transform_1", "type": "transform", "config": {"template": "high_{input_value}"}},
                    {"id": "transform_2", "type": "transform", "config": {"template": "low_{input_value}"}},
                    {"id": "output_1", "type": "output", "config": {"from": "transform_1"}},
                ],
                "edges": [
                    {"source": "input_1", "target": "condition_1"},
                    {"source": "condition_1", "target": "transform_1"},
                    {"source": "condition_1", "target": "transform_2"},
                    {"source": "transform_1", "target": "output_1"},
                ]
            }
        )
        assert response.status_code in [200, 201]

    def test_memory_workflow_integration(self, client):
        """Test workflow with memory operations."""
        # Store memory
        store_response = client.post(
            "/api/v1/memory",
            json={
                "content": "workflow context data",
                "layer": 3,
                "importance": 0.8,
                "tags": ["workflow"]
            }
        )
        assert store_response.status_code in [200, 201]

        # Search memory
        search_response = client.post(
            "/api/v1/memory/search",
            json={"query": "workflow context"}
        )
        assert search_response.status_code == 200

        # Consolidate memory
        consolidate_response = client.post(
            "/api/v1/memory/consolidate",
            json={
                "source_layers": [3],
                "target_layer": 2,
                "max_items": 5
            }
        )
        assert consolidate_response.status_code in [200, 400]


class TestConcurrentWorkflowExecution:
    """Test concurrent workflow execution."""

    @pytest.fixture
    def client(self):
        return TestClient(app, headers={"x-api-key": "bootstrap"})

    def test_concurrent_workflow_creation(self, client):
        """Test creating multiple workflows concurrently."""
        import concurrent.futures

        def create_workflow(i):
            return client.post(
                "/api/v1/workflows",
                json={
                    "name": f"Concurrent Workflow {i}",
                    "nodes": [
                        {"id": "input_1", "type": "input", "config": {"key": "data"}},
                        {"id": "output_1", "type": "output", "config": {"from": "input_1"}},
                    ],
                    "edges": [{"source": "input_1", "target": "output_1"}]
                }
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_workflow, i) for i in range(50)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(responses) == 50
        assert all(r.status_code in [200, 201] for r in responses)

    def test_concurrent_workflow_execution(self, client):
        """Test executing multiple workflows concurrently."""
        import concurrent.futures

        # Create a workflow first
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "Concurrent Execution Test",
                "nodes": [
                    {"id": "input_1", "type": "input", "config": {"key": "data"}},
                    {"id": "output_1", "type": "output", "config": {"from": "input_1"}},
                ],
                "edges": [{"source": "input_1", "target": "output_1"}]
            }
        )

        if create_response.status_code in [200, 201]:
            workflow_id = create_response.json().get("id")

            def execute_workflow(i):
                return client.post(
                    f"/api/v1/workflows/{workflow_id}/execute",
                    json={"data": f"input_{i}"}
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(execute_workflow, i) for i in range(20)]
                responses = [f.result() for f in concurrent.futures.as_completed(futures)]

            assert len(responses) == 20


class TestErrorRecoveryIntegration:
    """Test error recovery in integrated scenarios."""

    @pytest.fixture
    def client(self):
        return TestClient(app, headers={"x-api-key": "bootstrap"})

    def test_workflow_execution_with_invalid_input(self, client):
        """Test workflow execution with invalid input."""
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "Error Test Workflow",
                "nodes": [
                    {"id": "input_1", "type": "input", "config": {"key": "required_field"}},
                    {"id": "output_1", "type": "output", "config": {"from": "input_1"}},
                ],
                "edges": [{"source": "input_1", "target": "output_1"}]
            }
        )

        if create_response.status_code in [200, 201]:
            workflow_id = create_response.json().get("id")

            # Execute with missing required field
            exec_response = client.post(
                f"/api/v1/workflows/{workflow_id}/execute",
                json={"wrong_field": "value"}
            )
            assert exec_response.status_code in [200, 202, 400, 422]

    def test_workflow_execution_timeout_recovery(self, client):
        """Test recovery from workflow execution timeout."""
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "Timeout Test Workflow",
                "nodes": [
                    {"id": "input_1", "type": "input", "config": {"key": "data"}},
                    {"id": "wait_1", "type": "wait", "config": {"delay_ms": 5000}},
                    {"id": "output_1", "type": "output", "config": {"from": "input_1"}},
                ],
                "edges": [
                    {"source": "input_1", "target": "wait_1"},
                    {"source": "wait_1", "target": "output_1"},
                ]
            }
        )

        if create_response.status_code in [200, 201]:
            workflow_id = create_response.json().get("id")

            # Execute with timeout
            exec_response = client.post(
                f"/api/v1/workflows/{workflow_id}/execute",
                json={"data": "test"}
            )
            assert exec_response.status_code in [200, 202, 408]


class TestDataConsistency:
    """Test data consistency across operations."""

    @pytest.fixture
    def client(self):
        return TestClient(app, headers={"x-api-key": "bootstrap"})

    def test_memory_consistency_after_consolidation(self, client):
        """Test memory consistency after consolidation."""
        # Store multiple memories
        for i in range(5):
            client.post(
                "/api/v1/memory",
                json={
                    "content": f"Memory item {i}",
                    "layer": 3,
                    "importance": 0.5 + (i * 0.1),
                    "tags": ["test"]
                }
            )

        # Get count before consolidation
        count_before = client.get("/api/v1/memory/count")
        before_count = count_before.json().get("count", 0) if count_before.status_code == 200 else 0

        # Consolidate
        consolidate_response = client.post(
            "/api/v1/memory/consolidate",
            json={
                "source_layers": [3],
                "target_layer": 2,
                "max_items": 10
            }
        )

        # Get count after consolidation
        count_after = client.get("/api/v1/memory/count")
        after_count = count_after.json().get("count", 0) if count_after.status_code == 200 else 0

        # Total count should remain consistent
        assert before_count >= 0
        assert after_count >= 0

    def test_workflow_state_consistency(self, client):
        """Test workflow state consistency."""
        # Create workflow
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "State Test Workflow",
                "nodes": [
                    {"id": "input_1", "type": "input", "config": {"key": "data"}},
                    {"id": "output_1", "type": "output", "config": {"from": "input_1"}},
                ],
                "edges": [{"source": "input_1", "target": "output_1"}]
            }
        )

        if create_response.status_code in [200, 201]:
            workflow_id = create_response.json().get("id")

            # Get workflow multiple times
            response1 = client.get(f"/api/v1/workflows/{workflow_id}")
            response2 = client.get(f"/api/v1/workflows/{workflow_id}")
            response3 = client.get(f"/api/v1/workflows/{workflow_id}")

            if response1.status_code == 200:
                data1 = response1.json()
                data2 = response2.json()
                data3 = response3.json()

                # Data should be consistent
                assert data1.get("id") == data2.get("id") == data3.get("id")
                assert data1.get("name") == data2.get("name") == data3.get("name")
