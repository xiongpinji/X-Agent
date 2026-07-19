"""Comprehensive tests for workflow system components.

Tests cover:
- WorkflowNodeType enum
- WorkflowRunStatus enum
- WorkflowNode creation and validation
- WorkflowEdge creation
- WorkflowDefinition lifecycle
- WorkflowNodeResult tracking
- WorkflowRunRecord management
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.app.core.workflows import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeResult,
    WorkflowNodeType,
    WorkflowRunRecord,
    WorkflowRunStatus,
    WorkflowScheduleStatus,
)


class TestWorkflowNodeType:
    """Test WorkflowNodeType enum."""

    def test_node_types_exist(self) -> None:
        assert WorkflowNodeType.INPUT == "input"
        assert WorkflowNodeType.TRANSFORM == "transform"
        assert WorkflowNodeType.TOOL == "tool"
        assert WorkflowNodeType.AGENT == "agent"
        assert WorkflowNodeType.CONDITION == "condition"
        assert WorkflowNodeType.WAIT == "wait"
        assert WorkflowNodeType.APPROVAL == "approval"
        assert WorkflowNodeType.OUTPUT == "output"

    def test_node_type_comparison(self) -> None:
        assert WorkflowNodeType.INPUT == WorkflowNodeType.INPUT
        assert WorkflowNodeType.INPUT != WorkflowNodeType.OUTPUT


class TestWorkflowRunStatus:
    """Test WorkflowRunStatus enum."""

    def test_run_statuses_exist(self) -> None:
        assert WorkflowRunStatus.DRAFT == "draft"
        assert WorkflowRunStatus.RUNNING == "running"
        assert WorkflowRunStatus.COMPLETED == "completed"
        assert WorkflowRunStatus.FAILED == "failed"
        assert WorkflowRunStatus.CANCELED == "canceled"
        assert WorkflowRunStatus.PAUSED == "paused"
        assert WorkflowRunStatus.NEEDS_APPROVAL == "needs_approval"


class TestWorkflowScheduleStatus:
    """Test WorkflowScheduleStatus enum."""

    def test_schedule_statuses_exist(self) -> None:
        assert WorkflowScheduleStatus.PENDING == "pending"
        assert WorkflowScheduleStatus.TRIGGERED == "triggered"
        assert WorkflowScheduleStatus.CANCELED == "canceled"
        assert WorkflowScheduleStatus.FAILED == "failed"


class TestWorkflowNode:
    """Test WorkflowNode model."""

    def test_node_creation(self) -> None:
        node = WorkflowNode(
            id="node-1",
            type=WorkflowNodeType.INPUT,
        )
        assert node.id == "node-1"
        assert node.type == WorkflowNodeType.INPUT
        assert node.config == {}

    def test_node_with_config(self) -> None:
        config = {
            "name": "Input Node",
            "description": "Accepts user input",
            "required_fields": ["name", "email"],
        }
        node = WorkflowNode(
            id="node-1",
            type=WorkflowNodeType.INPUT,
            config=config,
        )
        assert node.config == config
        assert node.config["name"] == "Input Node"

    def test_node_types(self) -> None:
        for node_type in [
            WorkflowNodeType.INPUT,
            WorkflowNodeType.TRANSFORM,
            WorkflowNodeType.TOOL,
            WorkflowNodeType.AGENT,
            WorkflowNodeType.CONDITION,
            WorkflowNodeType.WAIT,
            WorkflowNodeType.APPROVAL,
            WorkflowNodeType.OUTPUT,
        ]:
            node = WorkflowNode(id="node-1", type=node_type)
            assert node.type == node_type


class TestWorkflowEdge:
    """Test WorkflowEdge model."""

    def test_edge_creation(self) -> None:
        edge = WorkflowEdge(source="node-1", target="node-2")
        assert edge.source == "node-1"
        assert edge.target == "node-2"
        assert edge.condition is None

    def test_edge_with_condition(self) -> None:
        edge = WorkflowEdge(
            source="node-1",
            target="node-2",
            condition="status == 'success'",
        )
        assert edge.source == "node-1"
        assert edge.target == "node-2"
        assert edge.condition == "status == 'success'"


class TestWorkflowDefinition:
    """Test WorkflowDefinition model."""

    def test_workflow_creation(self) -> None:
        nodes = [
            WorkflowNode(id="node-1", type=WorkflowNodeType.INPUT),
            WorkflowNode(id="node-2", type=WorkflowNodeType.OUTPUT),
        ]
        workflow = WorkflowDefinition(
            name="Simple Workflow",
            nodes=nodes,
        )
        assert workflow.id is not None
        assert workflow.name == "Simple Workflow"
        assert workflow.description == ""
        assert len(workflow.nodes) == 2
        assert workflow.edges == []

    def test_workflow_with_all_fields(self) -> None:
        now = datetime.now(UTC)
        nodes = [
            WorkflowNode(id="node-1", type=WorkflowNodeType.INPUT),
            WorkflowNode(id="node-2", type=WorkflowNodeType.TOOL),
            WorkflowNode(id="node-3", type=WorkflowNodeType.OUTPUT),
        ]
        edges = [
            WorkflowEdge(source="node-1", target="node-2"),
            WorkflowEdge(source="node-2", target="node-3"),
        ]
        workflow = WorkflowDefinition(
            id="wf-123",
            name="Complex Workflow",
            description="A complex workflow with multiple steps",
            nodes=nodes,
            edges=edges,
            created_at=now,
            updated_at=now,
        )
        assert workflow.id == "wf-123"
        assert workflow.name == "Complex Workflow"
        assert len(workflow.nodes) == 3
        assert len(workflow.edges) == 2

    def test_workflow_with_conditional_edges(self) -> None:
        nodes = [
            WorkflowNode(id="node-1", type=WorkflowNodeType.CONDITION),
            WorkflowNode(id="node-2", type=WorkflowNodeType.OUTPUT),
            WorkflowNode(id="node-3", type=WorkflowNodeType.OUTPUT),
        ]
        edges = [
            WorkflowEdge(source="node-1", target="node-2", condition="result == true"),
            WorkflowEdge(source="node-1", target="node-3", condition="result == false"),
        ]
        workflow = WorkflowDefinition(
            name="Conditional Workflow",
            nodes=nodes,
            edges=edges,
        )
        assert len(workflow.edges) == 2
        assert workflow.edges[0].condition == "result == true"


class TestWorkflowNodeResult:
    """Test WorkflowNodeResult model."""

    def test_node_result_creation(self) -> None:
        result = WorkflowNodeResult(
            node_id="node-1",
            node_type=WorkflowNodeType.TOOL,
            status=WorkflowRunStatus.COMPLETED,
        )
        assert result.node_id == "node-1"
        assert result.node_type == WorkflowNodeType.TOOL
        assert result.status == WorkflowRunStatus.COMPLETED
        assert result.attempts == 1
        assert result.output is None
        assert result.error is None
        assert result.compensated is False

    def test_node_result_with_output(self) -> None:
        result = WorkflowNodeResult(
            node_id="node-1",
            node_type=WorkflowNodeType.TOOL,
            status=WorkflowRunStatus.COMPLETED,
            output={"result": "success", "data": [1, 2, 3]},
        )
        assert result.output == {"result": "success", "data": [1, 2, 3]}

    def test_node_result_with_error(self) -> None:
        result = WorkflowNodeResult(
            node_id="node-1",
            node_type=WorkflowNodeType.TOOL,
            status=WorkflowRunStatus.FAILED,
            error="Tool execution failed",
            attempts=3,
        )
        assert result.status == WorkflowRunStatus.FAILED
        assert result.error == "Tool execution failed"
        assert result.attempts == 3

    def test_node_result_with_compensation(self) -> None:
        result = WorkflowNodeResult(
            node_id="node-1",
            node_type=WorkflowNodeType.TOOL,
            status=WorkflowRunStatus.COMPLETED,
            output={"result": "success"},
            compensated=True,
            compensation_output={"rollback": "success"},
        )
        assert result.compensated is True
        assert result.compensation_output == {"rollback": "success"}

    def test_node_result_timestamps(self) -> None:
        result = WorkflowNodeResult(
            node_id="node-1",
            node_type=WorkflowNodeType.TOOL,
            status=WorkflowRunStatus.COMPLETED,
        )
        assert isinstance(result.started_at, datetime)
        assert isinstance(result.completed_at, datetime)


class TestWorkflowRunRecord:
    """Test WorkflowRunRecord model."""

    def test_run_record_creation(self) -> None:
        record = WorkflowRunRecord(
            workflow_id="wf-1",
            workflow_name="Test Workflow",
            status=WorkflowRunStatus.RUNNING,
        )
        assert record.run_id is not None
        assert record.workflow_id == "wf-1"
        assert record.workflow_name == "Test Workflow"
        assert record.status == WorkflowRunStatus.RUNNING
        assert record.tenant_id == "default"
        assert record.user_id == "anonymous"
        assert record.inputs == {}
        assert record.outputs == {}
        assert record.node_results == []

    def test_run_record_with_all_fields(self) -> None:
        now = datetime.now(UTC)
        node_result = WorkflowNodeResult(
            node_id="node-1",
            node_type=WorkflowNodeType.TOOL,
            status=WorkflowRunStatus.COMPLETED,
            output={"result": "success"},
        )
        record = WorkflowRunRecord(
            run_id="run-123",
            workflow_id="wf-1",
            workflow_name="Test Workflow",
            status=WorkflowRunStatus.COMPLETED,
            tenant_id="tenant-1",
            user_id="user-1",
            inputs={"param1": "value1"},
            outputs={"result": "success"},
            node_results=[node_result],
            started_at=now,
        )
        assert record.run_id == "run-123"
        assert record.tenant_id == "tenant-1"
        assert record.user_id == "user-1"
        assert len(record.node_results) == 1
        assert record.inputs == {"param1": "value1"}
        assert record.outputs == {"result": "success"}

    def test_run_record_status_transitions(self) -> None:
        record = WorkflowRunRecord(
            workflow_id="wf-1",
            workflow_name="Test Workflow",
            status=WorkflowRunStatus.DRAFT,
        )
        assert record.status == WorkflowRunStatus.DRAFT

        # Simulate status transitions
        record.status = WorkflowRunStatus.RUNNING
        assert record.status == WorkflowRunStatus.RUNNING

        record.status = WorkflowRunStatus.COMPLETED
        assert record.status == WorkflowRunStatus.COMPLETED

    def test_run_record_with_multiple_node_results(self) -> None:
        results = [
            WorkflowNodeResult(
                node_id=f"node-{i}",
                node_type=WorkflowNodeType.TOOL,
                status=WorkflowRunStatus.COMPLETED,
                output={"step": i},
            )
            for i in range(5)
        ]
        record = WorkflowRunRecord(
            workflow_id="wf-1",
            workflow_name="Multi-step Workflow",
            status=WorkflowRunStatus.COMPLETED,
            node_results=results,
        )
        assert len(record.node_results) == 5
        for i, result in enumerate(record.node_results):
            assert result.node_id == f"node-{i}"

    def test_run_record_timestamps(self) -> None:
        record = WorkflowRunRecord(
            workflow_id="wf-1",
            workflow_name="Test Workflow",
            status=WorkflowRunStatus.RUNNING,
        )
        assert isinstance(record.started_at, datetime)

    def test_run_record_failed_status(self) -> None:
        record = WorkflowRunRecord(
            workflow_id="wf-1",
            workflow_name="Test Workflow",
            status=WorkflowRunStatus.FAILED,
            node_results=[
                WorkflowNodeResult(
                    node_id="node-1",
                    node_type=WorkflowNodeType.TOOL,
                    status=WorkflowRunStatus.FAILED,
                    error="Tool failed",
                )
            ],
        )
        assert record.status == WorkflowRunStatus.FAILED
        assert record.node_results[0].error == "Tool failed"

    def test_run_record_needs_approval_status(self) -> None:
        record = WorkflowRunRecord(
            workflow_id="wf-1",
            workflow_name="Test Workflow",
            status=WorkflowRunStatus.NEEDS_APPROVAL,
            node_results=[
                WorkflowNodeResult(
                    node_id="approval-node",
                    node_type=WorkflowNodeType.APPROVAL,
                    status=WorkflowRunStatus.NEEDS_APPROVAL,
                )
            ],
        )
        assert record.status == WorkflowRunStatus.NEEDS_APPROVAL

    def test_run_record_canceled_status(self) -> None:
        record = WorkflowRunRecord(
            workflow_id="wf-1",
            workflow_name="Test Workflow",
            status=WorkflowRunStatus.CANCELED,
        )
        assert record.status == WorkflowRunStatus.CANCELED

    def test_run_record_paused_status(self) -> None:
        record = WorkflowRunRecord(
            workflow_id="wf-1",
            workflow_name="Test Workflow",
            status=WorkflowRunStatus.PAUSED,
        )
        assert record.status == WorkflowRunStatus.PAUSED
