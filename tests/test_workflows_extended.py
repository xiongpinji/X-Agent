"""Extended test coverage for workflows module."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

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


class TestWorkflowDefinition:
    """Test WorkflowDefinition model."""

    def test_workflow_definition_creation(self) -> None:
        """Test creating a workflow definition."""
        nodes = [
            WorkflowNode(id="input_1", type=WorkflowNodeType.INPUT, config={"key": "name"}),
            WorkflowNode(id="output_1", type=WorkflowNodeType.OUTPUT, config={"from": "input_1"}),
        ]
        edges = [WorkflowEdge(source="input_1", target="output_1")]

        workflow = WorkflowDefinition(
            name="Test Workflow",
            description="A test workflow",
            nodes=nodes,
            edges=edges,
        )

        assert workflow.name == "Test Workflow"
        assert workflow.description == "A test workflow"
        assert len(workflow.nodes) == 2
        assert len(workflow.edges) == 1
        assert workflow.id is not None
        assert workflow.created_at is not None
        assert workflow.updated_at is not None

    def test_workflow_definition_default_id(self) -> None:
        """Test workflow definition generates unique IDs."""
        workflow1 = WorkflowDefinition(name="Workflow 1", nodes=[])
        workflow2 = WorkflowDefinition(name="Workflow 2", nodes=[])

        assert workflow1.id != workflow2.id

    def test_workflow_definition_timestamps(self) -> None:
        """Test workflow definition timestamps."""
        workflow = WorkflowDefinition(name="Test", nodes=[])

        assert isinstance(workflow.created_at, datetime)
        assert isinstance(workflow.updated_at, datetime)
        assert workflow.created_at.tzinfo is not None


class TestWorkflowNode:
    """Test WorkflowNode model."""

    def test_workflow_node_creation(self) -> None:
        """Test creating workflow nodes."""
        node = WorkflowNode(
            id="node_1",
            type=WorkflowNodeType.TRANSFORM,
            config={"template": "Hello {name}"},
        )

        assert node.id == "node_1"
        assert node.type == WorkflowNodeType.TRANSFORM
        assert node.config == {"template": "Hello {name}"}

    def test_workflow_node_types(self) -> None:
        """Test all workflow node types."""
        node_types = [
            WorkflowNodeType.INPUT,
            WorkflowNodeType.TRANSFORM,
            WorkflowNodeType.TOOL,
            WorkflowNodeType.AGENT,
            WorkflowNodeType.CONDITION,
            WorkflowNodeType.WAIT,
            WorkflowNodeType.APPROVAL,
            WorkflowNodeType.OUTPUT,
        ]

        for node_type in node_types:
            node = WorkflowNode(id="test", type=node_type)
            assert node.type == node_type

    def test_workflow_node_empty_config(self) -> None:
        """Test workflow node with empty config."""
        node = WorkflowNode(id="node_1", type=WorkflowNodeType.INPUT)
        assert node.config == {}


class TestWorkflowEdge:
    """Test WorkflowEdge model."""

    def test_workflow_edge_creation(self) -> None:
        """Test creating workflow edges."""
        edge = WorkflowEdge(source="node_1", target="node_2")

        assert edge.source == "node_1"
        assert edge.target == "node_2"
        assert edge.condition is None

    def test_workflow_edge_with_condition(self) -> None:
        """Test workflow edge with condition."""
        edge = WorkflowEdge(
            source="node_1",
            target="node_2",
            condition="output.status == 'success'",
        )

        assert edge.source == "node_1"
        assert edge.target == "node_2"
        assert edge.condition == "output.status == 'success'"


class TestWorkflowNodeResult:
    """Test WorkflowNodeResult model."""

    def test_workflow_node_result_creation(self) -> None:
        """Test creating workflow node results."""
        result = WorkflowNodeResult(
            node_id="node_1",
            node_type=WorkflowNodeType.TRANSFORM,
            status=WorkflowRunStatus.COMPLETED,
            output={"greeting": "Hello World"},
        )

        assert result.node_id == "node_1"
        assert result.node_type == WorkflowNodeType.TRANSFORM
        assert result.status == WorkflowRunStatus.COMPLETED
        assert result.output == {"greeting": "Hello World"}
        assert result.attempts == 1
        assert result.error is None
        assert result.compensated is False

    def test_workflow_node_result_with_error(self) -> None:
        """Test workflow node result with error."""
        result = WorkflowNodeResult(
            node_id="node_1",
            node_type=WorkflowNodeType.TOOL,
            status=WorkflowRunStatus.FAILED,
            error="Tool execution failed",
        )

        assert result.status == WorkflowRunStatus.FAILED
        assert result.error == "Tool execution failed"

    def test_workflow_node_result_with_compensation(self) -> None:
        """Test workflow node result with compensation."""
        result = WorkflowNodeResult(
            node_id="node_1",
            node_type=WorkflowNodeType.AGENT,
            status=WorkflowRunStatus.COMPLETED,
            compensated=True,
            compensation_output={"rollback": "success"},
        )

        assert result.compensated is True
        assert result.compensation_output == {"rollback": "success"}

    def test_workflow_node_result_timestamps(self) -> None:
        """Test workflow node result timestamps."""
        result = WorkflowNodeResult(
            node_id="node_1",
            node_type=WorkflowNodeType.INPUT,
            status=WorkflowRunStatus.COMPLETED,
        )

        assert isinstance(result.started_at, datetime)
        assert isinstance(result.completed_at, datetime)


class TestWorkflowRunRecord:
    """Test WorkflowRunRecord model."""

    def test_workflow_run_record_creation(self) -> None:
        """Test creating workflow run records."""
        record = WorkflowRunRecord(
            workflow_id="wf_1",
            workflow_name="Test Workflow",
            status=WorkflowRunStatus.RUNNING,
            inputs={"name": "Alice"},
        )

        assert record.workflow_id == "wf_1"
        assert record.workflow_name == "Test Workflow"
        assert record.status == WorkflowRunStatus.RUNNING
        assert record.inputs == {"name": "Alice"}
        assert record.run_id is not None
        assert record.tenant_id == "default"
        assert record.user_id == "anonymous"

    def test_workflow_run_record_statuses(self) -> None:
        """Test all workflow run statuses."""
        statuses = [
            WorkflowRunStatus.DRAFT,
            WorkflowRunStatus.RUNNING,
            WorkflowRunStatus.COMPLETED,
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.CANCELED,
            WorkflowRunStatus.PAUSED,
            WorkflowRunStatus.NEEDS_APPROVAL,
        ]

        for status in statuses:
            record = WorkflowRunRecord(
                workflow_id="wf_1",
                workflow_name="Test",
                status=status,
            )
            assert record.status == status

    def test_workflow_run_record_with_results(self) -> None:
        """Test workflow run record with node results."""
        node_results = [
            WorkflowNodeResult(
                node_id="node_1",
                node_type=WorkflowNodeType.INPUT,
                status=WorkflowRunStatus.COMPLETED,
                output={"name": "Alice"},
            ),
            WorkflowNodeResult(
                node_id="node_2",
                node_type=WorkflowNodeType.OUTPUT,
                status=WorkflowRunStatus.COMPLETED,
                output={"greeting": "Hello Alice"},
            ),
        ]

        record = WorkflowRunRecord(
            workflow_id="wf_1",
            workflow_name="Test",
            status=WorkflowRunStatus.COMPLETED,
            node_results=node_results,
        )

        assert len(record.node_results) == 2
        assert record.node_results[0].output == {"name": "Alice"}

    def test_workflow_run_record_unique_ids(self) -> None:
        """Test workflow run records have unique IDs."""
        record1 = WorkflowRunRecord(workflow_id="wf_1", workflow_name="Test", status=WorkflowRunStatus.DRAFT)
        record2 = WorkflowRunRecord(workflow_id="wf_1", workflow_name="Test", status=WorkflowRunStatus.DRAFT)

        assert record1.run_id != record2.run_id

    def test_workflow_run_record_timestamps(self) -> None:
        """Test workflow run record timestamps."""
        record = WorkflowRunRecord(
            workflow_id="wf_1",
            workflow_name="Test",
            status=WorkflowRunStatus.RUNNING,
        )

        assert isinstance(record.started_at, datetime)
        assert record.started_at.tzinfo is not None


class TestWorkflowScheduleStatus:
    """Test WorkflowScheduleStatus enum."""

    def test_schedule_statuses(self) -> None:
        """Test all schedule statuses."""
        statuses = [
            WorkflowScheduleStatus.PENDING,
            WorkflowScheduleStatus.TRIGGERED,
            WorkflowScheduleStatus.CANCELED,
            WorkflowScheduleStatus.FAILED,
        ]

        for status in statuses:
            assert isinstance(status, WorkflowScheduleStatus)
