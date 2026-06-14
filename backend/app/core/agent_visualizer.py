"""Agent Execution Visualizer for X-Agent.

Generates Mermaid diagrams from agent execution traces for visual understanding
of multi-agent collaboration, tool call sequences, decision trees, and workflow
execution timelines.

Features:
    - Sequence diagrams for agent collaboration
    - Flowcharts for workflow execution paths
    - Multi-agent interaction diagrams
    - Gantt charts for execution timelines
    - Tool call dependency graphs
    - Decision tree visualization

Usage:
    from backend.app.core.agent_visualizer import generate_execution_diagram

    # Generate sequence diagram
    diagram = generate_execution_diagram(run_id="run-123")
    print(diagram)

    # Generate workflow flowchart
    diagram = generate_workflow_diagram(workflow_id="wf-456")

    # Generate multi-agent collaboration
    diagram = generate_agent_collaboration_diagram(run_ids=["run-1", "run-2"])
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, asdict


class DiagramType(Enum):
    """Types of diagrams that can be generated."""

    SEQUENCE = "sequence"
    FLOWCHART = "flowchart"
    GANTT = "gantt"
    STATE = "state"
    CLASS = "class"


@dataclass
class ExecutionEvent:
    """Represents a single execution event."""

    timestamp: datetime
    event_type: str
    agent_id: str
    action: str
    details: Dict[str, Any]
    duration_ms: Optional[float] = None
    status: str = "success"  # success, warning, error, pending


@dataclass
class ToolCall:
    """Represents a tool call during execution."""

    tool_name: str
    agent_id: str
    timestamp: datetime
    duration_ms: float
    status: str
    input_args: Dict[str, Any]
    output: Any
    error: Optional[str] = None


@dataclass
class AgentTransition:
    """Represents a transition between agents."""

    from_agent: str
    to_agent: str
    timestamp: datetime
    reason: str
    data_passed: Dict[str, Any]


class MermaidSequenceDiagram:
    """Generates Mermaid sequence diagrams."""

    def __init__(self, title: str = "Agent Execution Sequence"):
        self.title = title
        self.lines: List[str] = [
            "sequenceDiagram",
            f"  title {title}",
            "  autonumber"
        ]
        self.actors: set = set()

    def add_actor(self, actor_id: str, actor_type: str = "Agent") -> None:
        """Add an actor to the diagram."""
        if actor_id not in self.actors:
            self.actors.add(actor_id)

    def add_message(
        self,
        from_actor: str,
        to_actor: str,
        message: str,
        is_response: bool = False,
        note: Optional[str] = None
    ) -> None:
        """Add a message between actors."""
        arrow = "-->" if is_response else "->"
        self.lines.append(f"  {from_actor}{arrow}{to_actor}: {message}")

        if note:
            self.lines.append(f"  Note over {from_actor},{to_actor}: {note}")

    def add_loop(self, condition: str) -> None:
        """Add a loop block."""
        self.lines.append(f"  loop {condition}")

    def add_alt(self, condition: str) -> None:
        """Add an alt (alternative) block."""
        self.lines.append(f"  alt {condition}")

    def add_else(self) -> None:
        """Add an else clause."""
        self.lines.append("  else")

    def add_par(self, description: str) -> None:
        """Add parallel execution block."""
        self.lines.append(f"  par {description}")

    def add_end(self) -> None:
        """End the current block (loop, alt, par)."""
        self.lines.append("  end")

    def add_note(self, actor: str, message: str, position: str = "right") -> None:
        """Add a note to an actor."""
        self.lines.append(f"  Note {position} of {actor}: {message}")

    def render(self) -> str:
        """Render the diagram as Mermaid markdown."""
        return "\n".join(self.lines)


class MermaidFlowchart:
    """Generates Mermaid flowcharts."""

    def __init__(self, title: str = "Workflow Execution", direction: str = "TD"):
        self.title = title
        self.direction = direction  # TD, LR, DT, RL
        self.lines: List[str] = [f"flowchart {direction}"]
        self.nodes: Dict[str, Tuple[str, str]] = {}
        self.edges: List[Tuple[str, str, Optional[str]]] = []

    def add_node(
        self,
        node_id: str,
        label: str,
        shape: str = "round",
        style: Optional[str] = None
    ) -> None:
        """Add a node to the flowchart.

        Shapes: round, square, diamond, circle, hexagon
        """
        shape_map = {
            "round": (f"({label})", ""),
            "square": (f"[{label}]", ""),
            "diamond": (f"{{{{{label}}}}}", ""),
            "circle": (f"(({label}))", ""),
            "hexagon": (f"{{{{label}}}}", "")
        }

        node_shape, _ = shape_map.get(shape, (f"[{label}]", ""))
        self.nodes[node_id] = (node_shape, style or "")

    def add_edge(
        self,
        from_node: str,
        to_node: str,
        label: Optional[str] = None,
        style: Optional[str] = None
    ) -> None:
        """Add an edge between nodes."""
        self.edges.append((from_node, to_node, label))

    def add_decision(
        self,
        node_id: str,
        label: str,
        yes_target: str,
        no_target: str
    ) -> None:
        """Add a decision node."""
        self.add_node(node_id, label, shape="diamond")
        self.add_edge(node_id, yes_target, label="Yes")
        self.add_edge(node_id, no_target, label="No")

    def render(self) -> str:
        """Render the flowchart as Mermaid markdown."""
        lines = [f"flowchart {self.direction}", f"  title {self.title}"]

        for node_id, (shape, style) in self.nodes.items():
            line = f"  {node_id}{shape}"
            if style:
                line += f" style {style}"
            lines.append(line)

        for from_node, to_node, label in self.edges:
            if label:
                line = f"  {from_node} -->|{label}| {to_node}"
            else:
                line = f"  {from_node} --> {to_node}"
            lines.append(line)

        return "\n".join(lines)


class MermaidGanttChart:
    """Generates Mermaid Gantt charts for execution timelines."""

    def __init__(self, title: str = "Execution Timeline"):
        self.title = title
        self.lines: List[str] = [
            "gantt",
            f"  title {title}",
            "  dateFormat YYYY-MM-DD HH:mm:ss",
        ]
        self.tasks: Dict[str, Dict[str, Any]] = {}

    def add_task(
        self,
        task_id: str,
        name: str,
        start_time: datetime,
        duration_ms: float,
        category: str = "",
        depends_on: Optional[str] = None
    ) -> None:
        """Add a task to the Gantt chart."""
        end_time = start_time + timedelta(milliseconds=duration_ms)
        task_info = {
            "name": name,
            "start": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "category": category,
            "depends_on": depends_on
        }
        self.tasks[task_id] = task_info

    def render(self) -> str:
        """Render the Gantt chart as Mermaid markdown."""
        lines = self.lines.copy()

        for task_id, info in self.tasks.items():
            depends = f", after {info['depends_on']}" if info['depends_on'] else ""
            line = f"  {task_id}({info['name']}) : {info['start']} , {info['end']}{depends}"
            lines.append(line)

        return "\n".join(lines)


class ExecutionVisualizer:
    """Main class for visualizing agent executions."""

    def __init__(self):
        self.events: List[ExecutionEvent] = []
        self.tool_calls: List[ToolCall] = []
        self.transitions: List[AgentTransition] = []

    def add_event(self, event: ExecutionEvent) -> None:
        """Add an execution event."""
        self.events.append(event)

    def add_tool_call(self, tool_call: ToolCall) -> None:
        """Add a tool call."""
        self.tool_calls.append(tool_call)

    def add_transition(self, transition: AgentTransition) -> None:
        """Add an agent transition."""
        self.transitions.append(transition)

    def generate_sequence_diagram(self) -> str:
        """Generate a sequence diagram from events."""
        diagram = MermaidSequenceDiagram("Agent Execution Sequence")

        # Add unique agents
        agents = set()
        for event in self.events:
            agents.add(event.agent_id)
            diagram.add_actor(event.agent_id, "Agent")

        # Add system actor for external events
        diagram.add_actor("System", "External")

        # Add messages from events
        for i, event in enumerate(self.events):
            if event.event_type == "tool_call":
                diagram.add_message(
                    event.agent_id,
                    "System",
                    f"Call {event.action}",
                    note=f"Duration: {event.duration_ms}ms"
                )
            elif event.event_type == "tool_result":
                diagram.add_message(
                    "System",
                    event.agent_id,
                    f"{event.action} result",
                    is_response=True
                )

        return diagram.render()

    def generate_workflow_diagram(self) -> str:
        """Generate a flowchart from execution flow."""
        diagram = MermaidFlowchart("Workflow Execution Flow")

        # Add start node
        diagram.add_node("start", "Start", shape="circle")

        # Add agent nodes
        for i, event in enumerate(self.events):
            node_id = f"event_{i}"
            color = "success" if event.status == "success" else "danger" \
                if event.status == "error" else "warning"
            diagram.add_node(
                node_id,
                f"{event.agent_id}: {event.action}",
                style=color
            )

        # Add edges
        diagram.add_edge("start", "event_0")
        for i in range(len(self.events) - 1):
            diagram.add_edge(f"event_{i}", f"event_{i+1}")

        # Add end node
        if self.events:
            diagram.add_edge(f"event_{len(self.events)-1}", "end")

        diagram.add_node("end", "End", shape="circle")

        return diagram.render()

    def generate_collaboration_diagram(self) -> str:
        """Generate a multi-agent collaboration diagram."""
        diagram = MermaidSequenceDiagram("Multi-Agent Collaboration")

        # Add all agents as actors
        agents = set()
        for transition in self.transitions:
            agents.add(transition.from_agent)
            agents.add(transition.to_agent)
            diagram.add_actor(transition.from_agent, "Agent")
            diagram.add_actor(transition.to_agent, "Agent")

        # Add transitions as messages
        for transition in self.transitions:
            data_summary = ", ".join(
                f"{k}={v}"
                for k, v in list(transition.data_passed.items())[:2]
            )
            if len(transition.data_passed) > 2:
                data_summary += ", ..."

            diagram.add_message(
                transition.from_agent,
                transition.to_agent,
                transition.reason,
                note=f"Data: {data_summary}"
            )

        return diagram.render()

    def generate_timeline_diagram(self) -> str:
        """Generate a Gantt chart showing execution timeline."""
        diagram = MermaidGanttChart("Execution Timeline")

        # Sort events by timestamp
        sorted_events = sorted(self.events, key=lambda e: e.timestamp)

        # Add tasks from events
        for i, event in enumerate(sorted_events):
            task_id = f"task_{i}"
            duration = event.duration_ms or 100
            depends_on = f"task_{i-1}" if i > 0 else None

            diagram.add_task(
                task_id,
                f"{event.agent_id}: {event.action}",
                event.timestamp,
                duration,
                category=event.agent_id,
                depends_on=depends_on
            )

        return diagram.render()

    def generate_decision_tree(self) -> str:
        """Generate a decision tree from conditional events."""
        diagram = MermaidFlowchart("Decision Tree", direction="TD")

        # Build tree structure from events
        diagram.add_node("root", "Start", shape="circle")

        decision_count = 0
        for i, event in enumerate(self.events):
            if event.event_type == "decision":
                decision_id = f"decision_{decision_count}"
                diagram.add_node(
                    decision_id,
                    event.action,
                    shape="diamond"
                )

                if decision_count == 0:
                    diagram.add_edge("root", decision_id)
                else:
                    diagram.add_edge(f"decision_{decision_count-1}", decision_id)

                # Add outcomes
                outcomes = event.details.get("outcomes", {})
                for outcome_key, outcome_val in outcomes.items():
                    outcome_id = f"outcome_{decision_count}_{outcome_key}"
                    diagram.add_node(
                        outcome_id,
                        str(outcome_val),
                        shape="round"
                    )
                    diagram.add_edge(decision_id, outcome_id, label=outcome_key)

                decision_count += 1

        return diagram.render()


def generate_execution_diagram(
    run_id: str,
    events: List[Dict[str, Any]],
    diagram_type: str = "sequence"
) -> str:
    """Generate an execution diagram from run data.

    Args:
        run_id: The run ID
        events: List of execution events
        diagram_type: Type of diagram (sequence, flowchart, gantt)

    Returns:
        Mermaid diagram markdown
    """
    visualizer = ExecutionVisualizer()

    # Convert event dicts to ExecutionEvent objects
    for evt in events:
        event = ExecutionEvent(
            timestamp=datetime.fromisoformat(evt["timestamp"]),
            event_type=evt["event_type"],
            agent_id=evt["agent_id"],
            action=evt["action"],
            details=evt.get("details", {}),
            duration_ms=evt.get("duration_ms"),
            status=evt.get("status", "success")
        )
        visualizer.add_event(event)

    if diagram_type == "sequence":
        return visualizer.generate_sequence_diagram()
    elif diagram_type == "flowchart":
        return visualizer.generate_workflow_diagram()
    elif diagram_type == "gantt":
        return visualizer.generate_timeline_diagram()
    elif diagram_type == "decision":
        return visualizer.generate_decision_tree()
    else:
        raise ValueError(f"Unknown diagram type: {diagram_type}")


def generate_workflow_diagram(
    workflow_id: str,
    steps: List[Dict[str, Any]]
) -> str:
    """Generate a workflow diagram.

    Args:
        workflow_id: The workflow ID
        steps: List of workflow steps

    Returns:
        Mermaid flowchart markdown
    """
    diagram = MermaidFlowchart(f"Workflow: {workflow_id}", direction="LR")

    diagram.add_node("start", "Start", shape="circle")

    prev_node = "start"
    for i, step in enumerate(steps):
        step_id = f"step_{i}"
        step_name = step.get("name", f"Step {i}")
        step_type = step.get("type", "action")

        shape = "diamond" if step_type == "decision" else "square"
        diagram.add_node(step_id, step_name, shape=shape)
        diagram.add_edge(prev_node, step_id)

        if step_type == "decision":
            yes_target = f"step_{i}_yes"
            no_target = f"step_{i}_no"
            diagram.add_node(yes_target, "Success", shape="round")
            diagram.add_node(no_target, "Retry", shape="round")
            diagram.add_edge(step_id, yes_target, label="Yes")
            diagram.add_edge(step_id, no_target, label="No")

        prev_node = step_id

    diagram.add_node("end", "End", shape="circle")
    diagram.add_edge(prev_node, "end")

    return diagram.render()


def generate_agent_collaboration_diagram(run_ids: List[str]) -> str:
    """Generate a multi-agent collaboration diagram.

    Args:
        run_ids: List of run IDs to visualize collaboration

    Returns:
        Mermaid sequence diagram markdown
    """
    diagram = MermaidSequenceDiagram("Multi-Agent Collaboration")

    for run_id in run_ids:
        agent_id = f"Agent-{run_ids.index(run_id) + 1}"
        diagram.add_actor(agent_id, "Agent")

    # Add example collaborations
    for i in range(len(run_ids) - 1):
        from_agent = f"Agent-{i + 1}"
        to_agent = f"Agent-{i + 2}"
        diagram.add_message(from_agent, to_agent, f"Handoff to {to_agent}")

    return diagram.render()
