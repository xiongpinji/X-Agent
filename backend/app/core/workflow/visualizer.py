"""Workflow Visualization

Implements workflow visualization:
- Flow diagram generation
- Execution state visualization
- Dependency graphs
- Export to image/PDF
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from datetime import UTC, datetime


@dataclass
class DiagramNode:
    """Node in diagram"""
    id: str
    label: str
    node_type: str
    x: float = 0.0
    y: float = 0.0
    width: float = 100.0
    height: float = 60.0
    color: str = "#4A90E2"
    status: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagramEdge:
    """Edge in diagram"""
    source: str
    target: str
    label: str = ""
    condition: str | None = None
    style: str = "solid"
    color: str = "#333333"


class FlowDiagramGenerator:
    """Generates flow diagrams"""

    # Node type colors
    NODE_COLORS = {
        "input": "#4CAF50",
        "output": "#2196F3",
        "transform": "#FF9800",
        "tool": "#9C27B0",
        "agent": "#F44336",
        "condition": "#FFC107",
        "wait": "#00BCD4",
        "approval": "#E91E63",
        "if_else": "#FFC107",
        "switch": "#FFC107",
        "for_loop": "#00BCD4",
        "while_loop": "#00BCD4",
        "parallel": "#9C27B0",
        "subworkflow": "#673AB7",
    }

    # Status colors
    STATUS_COLORS = {
        "pending": "#CCCCCC",
        "running": "#4CAF50",
        "completed": "#2196F3",
        "failed": "#F44336",
        "paused": "#FF9800",
        "skipped": "#9E9E9E",
    }

    def __init__(self):
        self.nodes: list[DiagramNode] = []
        self.edges: list[DiagramEdge] = []

    def add_node(
        self,
        node_id: str,
        label: str,
        node_type: str,
        status: str = "pending",
        metadata: dict[str, Any] | None = None,
    ) -> DiagramNode:
        """Add node to diagram"""
        color = self.NODE_COLORS.get(node_type, "#4A90E2")
        if status in self.STATUS_COLORS:
            color = self.STATUS_COLORS[status]

        node = DiagramNode(
            id=node_id,
            label=label,
            node_type=node_type,
            color=color,
            status=status,
            metadata=metadata or {},
        )
        self.nodes.append(node)
        return node

    def add_edge(
        self,
        source: str,
        target: str,
        label: str = "",
        condition: str | None = None,
    ) -> DiagramEdge:
        """Add edge to diagram"""
        edge = DiagramEdge(
            source=source,
            target=target,
            label=label,
            condition=condition,
        )
        self.edges.append(edge)
        return edge

    def layout_hierarchical(self) -> None:
        """Apply hierarchical layout"""
        # Build adjacency list
        adjacency = {node.id: [] for node in self.nodes}
        for edge in self.edges:
            adjacency[edge.source].append(edge.target)

        # Topological sort
        visited = set()
        levels = {}

        def visit(node_id: str, level: int) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            levels[node_id] = max(levels.get(node_id, 0), level)
            for target in adjacency.get(node_id, []):
                visit(target, level + 1)

        for node in self.nodes:
            visit(node.id, 0)

        # Position nodes
        level_nodes = {}
        for node_id, level in levels.items():
            if level not in level_nodes:
                level_nodes[level] = []
            level_nodes[level].append(node_id)

        for node in self.nodes:
            level = levels.get(node.id, 0)
            index = level_nodes[level].index(node.id)
            node.x = (index + 1) * 150
            node.y = (level + 1) * 100

    def layout_circular(self) -> None:
        """Apply circular layout"""
        import math
        n = len(self.nodes)
        radius = 200

        for i, node in enumerate(self.nodes):
            angle = 2 * math.pi * i / n
            node.x = 300 + radius * math.cos(angle)
            node.y = 300 + radius * math.sin(angle)

    def to_svg(self) -> str:
        """Generate SVG representation"""
        # Calculate bounds
        if not self.nodes:
            return '<svg></svg>'

        min_x = min(n.x for n in self.nodes) - 50
        min_y = min(n.y for n in self.nodes) - 50
        max_x = max(n.x + n.width for n in self.nodes) + 50
        max_y = max(n.y + n.height for n in self.nodes) + 50

        width = max_x - min_x
        height = max_y - min_y

        svg_parts = [
            f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
            '<defs>',
            '<marker id="arrowhead" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">',
            '<polygon points="0 0, 10 3, 0 6" fill="#333" />',
            '</marker>',
            '</defs>',
        ]

        # Draw edges
        for edge in self.edges:
            source_node = next((n for n in self.nodes if n.id == edge.source), None)
            target_node = next((n for n in self.nodes if n.id == edge.target), None)

            if source_node and target_node:
                x1 = source_node.x + source_node.width / 2 - min_x
                y1 = source_node.y + source_node.height / 2 - min_y
                x2 = target_node.x + target_node.width / 2 - min_x
                y2 = target_node.y + target_node.height / 2 - min_y

                svg_parts.append(
                    f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                    f'stroke="{edge.color}" stroke-width="2" marker-end="url(#arrowhead)" />'
                )

                if edge.label:
                    mid_x = (x1 + x2) / 2
                    mid_y = (y1 + y2) / 2
                    svg_parts.append(
                        f'<text x="{mid_x}" y="{mid_y}" font-size="12" fill="#333">{edge.label}</text>'
                    )

        # Draw nodes
        for node in self.nodes:
            x = node.x - min_x
            y = node.y - min_y

            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="{node.width}" height="{node.height}" '
                f'fill="{node.color}" stroke="#333" stroke-width="2" rx="5" />'
            )

            svg_parts.append(
                f'<text x="{x + node.width / 2}" y="{y + node.height / 2}" '
                f'text-anchor="middle" dominant-baseline="middle" font-size="12" fill="white">'
                f'{node.label}</text>'
            )

        svg_parts.append('</svg>')
        return '\n'.join(svg_parts)

    def to_mermaid(self) -> str:
        """Generate Mermaid diagram syntax"""
        mermaid_parts = ["graph TD"]

        # Add nodes
        for node in self.nodes:
            shape = self._get_mermaid_shape(node.node_type)
            mermaid_parts.append(f'    {node.id}{shape}')

        # Add edges
        for edge in self.edges:
            if edge.condition:
                mermaid_parts.append(f'    {edge.source} -->|{edge.condition}| {edge.target}')
            else:
                mermaid_parts.append(f'    {edge.source} --> {edge.target}')

        return '\n'.join(mermaid_parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "type": n.node_type,
                    "x": n.x,
                    "y": n.y,
                    "color": n.color,
                    "status": n.status,
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "label": e.label,
                    "condition": e.condition,
                }
                for e in self.edges
            ],
        }

    @staticmethod
    def _get_mermaid_shape(node_type: str) -> str:
        """Get Mermaid shape for node type"""
        shapes = {
            "condition": "{condition}",
            "if_else": "{if/else}",
            "switch": "{switch}",
            "for_loop": "([for loop])",
            "while_loop": "([while loop])",
            "parallel": "{{parallel}}",
            "approval": "([approval])",
        }
        return shapes.get(node_type, "[node]")


class WorkflowVisualizer:
    """Visualizes workflows"""

    def __init__(self):
        self.diagram_generator = FlowDiagramGenerator()

    def visualize_workflow(
        self,
        workflow_definition: dict[str, Any],
        execution_state: dict[str, Any] | None = None,
    ) -> FlowDiagramGenerator:
        """Visualize workflow definition"""
        nodes = workflow_definition.get("nodes", [])
        edges = workflow_definition.get("edges", [])

        # Add nodes
        for node in nodes:
            node_id = node.get("id", "")
            node_type = node.get("type", "")
            label = node.get("config", {}).get("label", node_id)

            # Get status from execution state
            status = "pending"
            if execution_state:
                for result in execution_state.get("node_results", []):
                    if result.get("node_id") == node_id:
                        status = result.get("status", "pending")
                        break

            self.diagram_generator.add_node(node_id, label, node_type, status)

        # Add edges
        for edge in edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            condition = edge.get("condition")
            self.diagram_generator.add_edge(source, target, condition=condition)

        # Apply layout
        self.diagram_generator.layout_hierarchical()

        return self.diagram_generator

    def get_execution_timeline(
        self,
        execution_state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Get execution timeline"""
        timeline = []
        for result in execution_state.get("node_results", []):
            timeline.append({
                "node_id": result.get("node_id"),
                "status": result.get("status"),
                "started_at": result.get("started_at"),
                "completed_at": result.get("completed_at"),
                "duration_ms": (
                    (datetime.fromisoformat(result.get("completed_at")) -
                     datetime.fromisoformat(result.get("started_at"))).total_seconds() * 1000
                    if result.get("started_at") and result.get("completed_at")
                    else 0
                ),
            })
        return timeline

    def get_dependency_graph(
        self,
        workflow_definition: dict[str, Any],
    ) -> dict[str, Any]:
        """Get dependency graph"""
        nodes = {n["id"]: n for n in workflow_definition.get("nodes", [])}
        edges = workflow_definition.get("edges", [])

        dependencies = {}
        for node_id in nodes:
            dependencies[node_id] = {
                "depends_on": [],
                "depended_by": [],
            }

        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source and target:
                dependencies[target]["depends_on"].append(source)
                dependencies[source]["depended_by"].append(target)

        return dependencies

    def export_svg(self, output_path: str) -> None:
        """Export diagram as SVG"""
        svg_content = self.diagram_generator.to_svg()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

    def export_mermaid(self, output_path: str) -> None:
        """Export diagram as Mermaid"""
        mermaid_content = self.diagram_generator.to_mermaid()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(mermaid_content)
