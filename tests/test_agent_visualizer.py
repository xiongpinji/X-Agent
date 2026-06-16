"""Tests for agent execution visualizer."""

import pytest
from datetime import datetime, timedelta
from backend.app.core.agent_visualizer import (
    ExecutionVisualizer,
    ExecutionEvent,
    ToolCall,
    AgentTransition,
    MermaidSequenceDiagram,
    MermaidFlowchart,
    MermaidGanttChart,
    generate_execution_diagram,
    generate_workflow_diagram,
    generate_agent_collaboration_diagram,
)


class TestMermaidSequenceDiagram:
    """Test Mermaid sequence diagram generation."""

    def test_create_diagram(self):
        """Test creating a basic sequence diagram."""
        diagram = MermaidSequenceDiagram("Test Sequence")
        assert "sequenceDiagram" in diagram.render()
        assert "title Test Sequence" in diagram.render()

    def test_add_actors(self):
        """Test adding actors to diagram."""
        diagram = MermaidSequenceDiagram()
        diagram.add_actor("Agent1")
        diagram.add_actor("Agent2")
        rendered = diagram.render()
        assert "Agent1" in rendered
        assert "Agent2" in rendered

    def test_add_message(self):
        """Test adding messages between actors."""
        diagram = MermaidSequenceDiagram()
        diagram.add_actor("Agent1")
        diagram.add_actor("Agent2")
        diagram.add_message("Agent1", "Agent2", "Process request")
        rendered = diagram.render()
        assert "Agent1->Agent2: Process request" in rendered

    def test_add_note(self):
        """Test adding notes to actors."""
        diagram = MermaidSequenceDiagram()
        diagram.add_actor("Agent1")
        diagram.add_note("Agent1", "Processing task")
        rendered = diagram.render()
        assert "Note right of Agent1: Processing task" in rendered

    def test_add_loop(self):
        """Test adding loop blocks."""
        diagram = MermaidSequenceDiagram()
        diagram.add_loop("repeat task")
        diagram.add_end()
        rendered = diagram.render()
        assert "loop repeat task" in rendered
        assert "end" in rendered


class TestMermaidFlowchart:
    """Test Mermaid flowchart generation."""

    def test_create_flowchart(self):
        """Test creating a basic flowchart."""
        diagram = MermaidFlowchart("Test Flow")
        assert "flowchart TD" in diagram.render()

    def test_add_nodes(self):
        """Test adding nodes to flowchart."""
        diagram = MermaidFlowchart()
        diagram.add_node("start", "Start", shape="circle")
        diagram.add_node("process", "Process", shape="square")
        diagram.add_node("end", "End", shape="circle")

        rendered = diagram.render()
        assert "((Start))" in rendered
        assert "[Process]" in rendered

    def test_add_edges(self):
        """Test adding edges between nodes."""
        diagram = MermaidFlowchart()
        diagram.add_node("start", "Start")
        diagram.add_node("end", "End")
        diagram.add_edge("start", "end", label="Next")

        rendered = diagram.render()
        assert "start -->|Next| end" in rendered

    def test_add_decision(self):
        """Test adding decision nodes."""
        diagram = MermaidFlowchart()
        diagram.add_decision("check", "Check condition", "yes_node", "no_node")

        rendered = diagram.render()
        assert "check{Check condition}" in rendered
        assert "check -->|Yes|" in rendered
        assert "check -->|No|" in rendered


class TestMermaidGanttChart:
    """Test Mermaid Gantt chart generation."""

    def test_create_gantt(self):
        """Test creating a basic Gantt chart."""
        diagram = MermaidGanttChart("Test Timeline")
        assert "gantt" in diagram.render()
        assert "title Test Timeline" in diagram.render()

    def test_add_tasks(self):
        """Test adding tasks to Gantt chart."""
        diagram = MermaidGanttChart()
        start = datetime(2024, 1, 1, 10, 0, 0)

        diagram.add_task("task1", "Task 1", start, 1000)
        diagram.add_task("task2", "Task 2", start + timedelta(seconds=1), 500)

        rendered = diagram.render()
        assert "task1(Task 1)" in rendered
        assert "task2(Task 2)" in rendered

    def test_task_dependencies(self):
        """Test task dependencies in Gantt chart."""
        diagram = MermaidGanttChart()
        start = datetime(2024, 1, 1, 10, 0, 0)

        diagram.add_task("task1", "Task 1", start, 1000)
        diagram.add_task("task2", "Task 2", start, 1000, depends_on="task1")

        rendered = diagram.render()
        assert "after task1" in rendered


class TestExecutionVisualizer:
    """Test execution visualizer."""

    def test_add_events(self):
        """Test adding events to visualizer."""
        visualizer = ExecutionVisualizer()
        event = ExecutionEvent(
            timestamp=datetime.now(),
            event_type="tool_call",
            agent_id="agent-1",
            action="search",
            details={"query": "test"},
            duration_ms=100,
            status="success"
        )
        visualizer.add_event(event)
        assert len(visualizer.events) == 1
        assert visualizer.events[0].agent_id == "agent-1"

    def test_add_tool_calls(self):
        """Test adding tool calls."""
        visualizer = ExecutionVisualizer()
        tool_call = ToolCall(
            tool_name="search",
            agent_id="agent-1",
            timestamp=datetime.now(),
            duration_ms=100,
            status="success",
            input_args={"query": "test"},
            output={"results": []}
        )
        visualizer.add_tool_call(tool_call)
        assert len(visualizer.tool_calls) == 1

    def test_add_transitions(self):
        """Test adding agent transitions."""
        visualizer = ExecutionVisualizer()
        transition = AgentTransition(
            from_agent="agent-1",
            to_agent="agent-2",
            timestamp=datetime.now(),
            reason="handoff",
            data_passed={"context": "data"}
        )
        visualizer.add_transition(transition)
        assert len(visualizer.transitions) == 1

    def test_generate_sequence_diagram(self):
        """Test generating sequence diagram."""
        visualizer = ExecutionVisualizer()

        for i in range(3):
            event = ExecutionEvent(
                timestamp=datetime.now(),
                event_type="tool_call" if i % 2 == 0 else "tool_result",
                agent_id=f"agent-{i}",
                action="test_action",
                details={},
                duration_ms=100,
                status="success"
            )
            visualizer.add_event(event)

        diagram = visualizer.generate_sequence_diagram()
        assert "sequenceDiagram" in diagram
        assert "agent-0" in diagram

    def test_generate_workflow_diagram(self):
        """Test generating workflow diagram."""
        visualizer = ExecutionVisualizer()

        for i in range(3):
            event = ExecutionEvent(
                timestamp=datetime.now(),
                event_type="step",
                agent_id="agent-1",
                action=f"step_{i}",
                details={},
                duration_ms=100,
                status="success"
            )
            visualizer.add_event(event)

        diagram = visualizer.generate_workflow_diagram()
        assert "flowchart" in diagram
        assert "Start" in diagram

    def test_generate_timeline_diagram(self):
        """Test generating timeline (Gantt) diagram."""
        visualizer = ExecutionVisualizer()

        base_time = datetime.now()
        for i in range(3):
            event = ExecutionEvent(
                timestamp=base_time + timedelta(seconds=i),
                event_type="execution",
                agent_id="agent-1",
                action=f"task_{i}",
                details={},
                duration_ms=1000,
                status="success"
            )
            visualizer.add_event(event)

        diagram = visualizer.generate_timeline_diagram()
        assert "gantt" in diagram
        assert "Execution Timeline" in diagram

    def test_generate_collaboration_diagram(self):
        """Test generating multi-agent collaboration diagram."""
        visualizer = ExecutionVisualizer()

        transition = AgentTransition(
            from_agent="agent-1",
            to_agent="agent-2",
            timestamp=datetime.now(),
            reason="handoff",
            data_passed={"key": "value"}
        )
        visualizer.add_transition(transition)

        diagram = visualizer.generate_collaboration_diagram()
        assert "sequenceDiagram" in diagram
        assert "agent-1" in diagram


class TestGenerationFunctions:
    """Test top-level diagram generation functions."""

    def test_generate_execution_diagram(self):
        """Test generate_execution_diagram function."""
        events = [
            {
                "timestamp": datetime.now().isoformat(),
                "event_type": "tool_call",
                "agent_id": "agent-1",
                "action": "search",
                "details": {"query": "test"},
                "duration_ms": 100,
                "status": "success"
            }
        ]

        diagram = generate_execution_diagram("run-123", events, diagram_type="sequence")
        assert "sequenceDiagram" in diagram

    def test_generate_execution_diagram_flowchart(self):
        """Test generate_execution_diagram with flowchart type."""
        events = [
            {
                "timestamp": datetime.now().isoformat(),
                "event_type": "step",
                "agent_id": "agent-1",
                "action": "process",
                "details": {},
                "duration_ms": 100,
                "status": "success"
            }
        ]

        diagram = generate_execution_diagram("run-123", events, diagram_type="flowchart")
        assert "flowchart" in diagram

    def test_generate_workflow_diagram(self):
        """Test generate_workflow_diagram function."""
        steps = [
            {"name": "Initialize", "type": "action"},
            {"name": "Check", "type": "decision"},
            {"name": "Execute", "type": "action"}
        ]

        diagram = generate_workflow_diagram("wf-123", steps)
        assert "flowchart" in diagram
        assert "Initialize" in diagram
        assert "Check{Check}" in diagram

    def test_generate_agent_collaboration_diagram(self):
        """Test generate_agent_collaboration_diagram function."""
        run_ids = ["run-1", "run-2", "run-3"]
        diagram = generate_agent_collaboration_diagram(run_ids)

        assert "sequenceDiagram" in diagram
        assert "Agent-1" in diagram
        assert "Agent-2" in diagram

    def test_invalid_diagram_type(self):
        """Test error handling for invalid diagram type."""
        events = []
        with pytest.raises(ValueError):
            generate_execution_diagram("run-123", events, diagram_type="invalid")


class TestDiagramContent:
    """Test specific diagram content."""

    def test_sequence_diagram_has_autonumber(self):
        """Test that sequence diagrams have autonumbering."""
        diagram = MermaidSequenceDiagram()
        rendered = diagram.render()
        assert "autonumber" in rendered

    def test_flowchart_has_direction(self):
        """Test that flowchart has correct direction."""
        diagram = MermaidFlowchart(direction="LR")
        rendered = diagram.render()
        assert "flowchart LR" in rendered

    def test_gantt_has_dateformat(self):
        """Test that Gantt chart has date format."""
        diagram = MermaidGanttChart()
        rendered = diagram.render()
        assert "dateFormat" in rendered

    def test_complex_sequence_diagram(self):
        """Test complex sequence diagram with multiple elements."""
        diagram = MermaidSequenceDiagram("Complex Sequence")

        for i in range(3):
            diagram.add_actor(f"Agent{i}")

        diagram.add_message("Agent0", "Agent1", "Start process")
        diagram.add_loop("while not complete")
        diagram.add_message("Agent1", "Agent2", "Do work")
        diagram.add_message("Agent2", "Agent1", "Result", is_response=True)
        diagram.add_end()
        diagram.add_message("Agent1", "Agent0", "Done", is_response=True)

        rendered = diagram.render()
        assert "loop while not complete" in rendered
        assert "Agent0->Agent1" in rendered
        assert "Agent1-->Agent0" in rendered
