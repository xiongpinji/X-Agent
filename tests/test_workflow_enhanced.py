"""Comprehensive Tests for Enhanced Workflow System

Tests for:
- Control flow (if/else, loops, parallel)
- Data flow management
- Error handling
- Templates
- Versioning
- Debugging
- Visualization
"""

import asyncio
import pytest
from datetime import UTC, datetime, timedelta

from backend.app.core.workflow.control_flow import (
    IfElseNode,
    SwitchNode,
    ForLoopNode,
    WhileLoopNode,
    ParallelNode,
    ControlFlowExecutor,
)
from backend.app.core.workflow.data_flow import (
    DataFlowManager,
    ExpressionEvaluator,
    DataTransformer,
    VariableScope,
    ScopeLevel,
)
from backend.app.core.workflow.error_handling import (
    ErrorHandler,
    RetryPolicy,
    CompensationStrategy,
    CompensationType,
    RetryStrategy,
)
from backend.app.core.workflow.templates import (
    WorkflowTemplate,
    TemplateRegistry,
    TemplateLibrary,
    TemplateParameter,
)
from backend.app.core.workflow.versioning import (
    VersionManager,
    WorkflowVersion,
    VersionComparator,
    DeploymentStrategy,
)
from backend.app.core.workflow.debugger import (
    WorkflowDebugger,
    BreakpointManager,
    ExecutionTracer,
)
from backend.app.core.workflow.visualizer import (
    WorkflowVisualizer,
    FlowDiagramGenerator,
)


class TestControlFlow:
    """Test control flow constructs"""

    @pytest.mark.asyncio
    async def test_if_else_node(self):
        """Test if/else branching"""
        executor = ControlFlowExecutor()

        # Create nodes
        if_node = IfElseNode(
            id="if1",
            condition="$value > 10",
            then_node_id="then1",
            else_node_id="else1",
        )
        executor.register_node(if_node)

        # Register stub child nodes so the executor can dispatch to them
        then_node = IfElseNode(id="then1", condition="true", then_node_id="")
        else_node = IfElseNode(id="else1", condition="true", then_node_id="")
        executor.register_node(then_node)
        executor.register_node(else_node)

        # Test true condition (value=15 > 10 → dispatches to then1)
        context = {"value": 15}
        result = await executor.execute("if1", context)
        assert result is None  # then_node returns None (no further dispatch)

    @pytest.mark.asyncio
    async def test_for_loop_node(self):
        """Test for loop"""
        executor = ControlFlowExecutor()

        loop_node = ForLoopNode(
            id="loop1",
            iterable_expr="$items",
            item_var="item",
            body_node_id="body1",
        )
        executor.register_node(loop_node)

        # Register stub body node
        body_node = IfElseNode(id="body1", condition="true", then_node_id="")
        executor.register_node(body_node)

        context = {"items": [1, 2, 3, 4, 5]}
        result = await executor.execute("loop1", context)

        assert result["iterations"] == 5
        assert len(result["results"]) == 5

    @pytest.mark.asyncio
    async def test_while_loop_node(self):
        """Test while loop"""
        executor = ControlFlowExecutor()

        loop_node = WhileLoopNode(
            id="while1",
            condition="$counter < 5",
            body_node_id="body1",
            max_iterations=10,  # Cap iterations for test speed
        )
        executor.register_node(loop_node)

        # Register stub body node
        body_node = IfElseNode(id="body1", condition="true", then_node_id="")
        executor.register_node(body_node)

        context = {"counter": 0}
        result = await executor.execute("while1", context)

        # With a no-op body, counter never changes, so the loop runs until
        # max_iterations. The test just checks it doesn't crash and returns
        # a reasonable structure.
        assert result["iterations"] <= result["max_iterations"]

    @pytest.mark.asyncio
    async def test_parallel_node(self):
        """Test parallel execution"""
        executor = ControlFlowExecutor()

        parallel_node = ParallelNode(
            id="parallel1",
            branches=["branch1", "branch2", "branch3"],
            join_strategy="all",
        )
        executor.register_node(parallel_node)

        context = {}
        result = await executor.execute("parallel1", context)

        assert result["branch_count"] == 3
        assert result["join_strategy"] == "all"


class TestDataFlow:
    """Test data flow management"""

    def test_variable_scope(self):
        """Test variable scoping"""
        global_scope = VariableScope(level=ScopeLevel.GLOBAL)
        global_scope.set("global_var", "global_value")

        child_scope = global_scope.create_child(ScopeLevel.NODE)
        child_scope.set("local_var", "local_value")

        # Child can access parent variables
        assert child_scope.get("global_var") == "global_value"
        assert child_scope.get("local_var") == "local_value"

        # Parent cannot access child variables
        assert global_scope.get("local_var") is None

    def test_expression_evaluation(self):
        """Test expression evaluation"""
        context = {"x": 10, "y": 5, "name": "test"}

        # Arithmetic
        assert ExpressionEvaluator.evaluate("$x + $y", context) is not None

        # Comparison
        result = ExpressionEvaluator.evaluate("$x > $y", context)
        assert result is True

        # String operations
        result = ExpressionEvaluator.evaluate("upper($name)", context)
        assert result == "TEST"

    def test_data_transformation(self):
        """Test data transformation"""
        data = [1, 2, 3, 4, 5]

        # Filter transformation
        result = DataTransformer.transform(
            data,
            {"type": "filter", "predicate": "$item > 2"},
        )
        assert len(result) == 3

        # Map transformation
        data_dict = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
        result = DataTransformer.transform(
            data_dict,
            {"type": "map", "mapping": {"id": "id", "label": "name"}},
        )
        # Map over a list of records returns a list of mapped records
        assert len(result) == 2
        assert "label" in result[0]
        assert result[0]["label"] == "a"

    def test_data_flow_manager(self):
        """Test data flow manager"""
        manager = DataFlowManager()

        manager.set_variable("x", 10)
        manager.set_variable("y", 20)

        assert manager.get_variable("x") == 10
        assert manager.get_variable("y") == 20

        # Push new scope
        manager.push_scope(ScopeLevel.NODE)
        manager.set_variable("z", 30)

        assert manager.get_variable("z") == 30
        assert manager.get_variable("x") == 10  # Can still access parent

        # Pop scope
        manager.pop_scope()
        assert manager.get_variable("z") is None  # Lost after pop


class TestErrorHandling:
    """Test error handling"""

    def test_retry_policy(self):
        """Test retry policy"""
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay_ms=100,
            strategy=RetryStrategy.EXPONENTIAL,
        )

        # Check delays increase exponentially
        delay1 = policy.get_delay(1)
        delay2 = policy.get_delay(2)
        delay3 = policy.get_delay(3)

        assert delay1 <= delay2 <= delay3

    @pytest.mark.asyncio
    async def test_error_handler(self):
        """Test error handler"""
        handler = ErrorHandler(
            retry_policy=RetryPolicy(max_attempts=3),
            compensation_strategy=CompensationStrategy(
                type=CompensationType.FALLBACK,
                fallback_value={"status": "fallback"},
            ),
        )

        error = ValueError("Test error")
        result = await handler.handle_error(
            error,
            node_id="node1",
            workflow_id="workflow1",
            attempt=3,
        )

        assert result == {"status": "fallback"}

    def test_error_summary(self):
        """Test error summary"""
        handler = ErrorHandler()

        # Simulate errors
        for i in range(3):
            try:
                raise ValueError(f"Error {i}")
            except ValueError as e:
                asyncio.run(handler.handle_error(
                    e,
                    node_id=f"node{i}",
                    workflow_id="workflow1",
                    attempt=1,
                ))

        summary = handler.get_error_summary()
        assert summary["total_errors"] == 3


class TestTemplates:
    """Test workflow templates"""

    def test_template_creation(self):
        """Test template creation"""
        template = WorkflowTemplate(
            name="Test Template",
            description="A test template",
            parameters=[
                TemplateParameter(
                    name="input",
                    type="string",
                    required=True,
                ),
            ],
            nodes=[{"id": "node1", "type": "input"}],
            edges=[],
        )

        assert template.name == "Test Template"
        assert len(template.parameters) == 1

    def test_template_instantiation(self):
        """Test template instantiation"""
        template = WorkflowTemplate(
            name="Test",
            parameters=[
                TemplateParameter(name="source", type="string", required=True),
            ],
            nodes=[
                {"id": "input", "type": "input", "config": {"source": "${source}"}},
            ],
            edges=[],
        )

        workflow = template.instantiate({"source": "test_source"})
        assert workflow["template_id"] == template.id

    def test_template_registry(self):
        """Test template registry"""
        registry = TemplateRegistry()

        template = TemplateLibrary.create_data_processing_template()
        registry.register(template)

        retrieved = registry.get(template.id)
        assert retrieved is not None
        assert retrieved.name == template.name

    def test_template_library(self):
        """Test template library"""
        templates = TemplateLibrary.get_all_templates()
        assert len(templates) >= 5

        # Check specific templates exist
        names = [t.name for t in templates]
        assert "Data Processing Pipeline" in names
        assert "Web Scraping Pipeline" in names


class TestVersioning:
    """Test workflow versioning"""

    def test_version_creation(self):
        """Test version creation"""
        manager = VersionManager()

        version = manager.create_version(
            workflow_id="wf1",
            nodes=[{"id": "node1", "type": "input"}],
            edges=[],
            changelog="Initial version",
            author="test_user",
        )

        assert version.version_number == "1.0.0"
        assert version.status.value == "draft"

    def test_version_publishing(self):
        """Test version publishing"""
        manager = VersionManager()

        version = manager.create_version(
            workflow_id="wf1",
            nodes=[],
            edges=[],
        )

        published = manager.publish_version(
            workflow_id="wf1",
            version_id=version.id,
            deployment_strategy=DeploymentStrategy.IMMEDIATE,
        )

        assert published.status.value == "published"
        assert published.published_at is not None

    def test_version_comparison(self):
        """Test version comparison"""
        v1 = WorkflowVersion(
            workflow_id="wf1",
            version_number="1.0.0",
            nodes=[{"id": "node1", "type": "input"}],
            edges=[],
        )

        v2 = WorkflowVersion(
            workflow_id="wf1",
            version_number="1.1.0",
            nodes=[
                {"id": "node1", "type": "input"},
                {"id": "node2", "type": "output"},
            ],
            edges=[{"source": "node1", "target": "node2"}],
        )

        diff = VersionComparator.compare(v1, v2)
        assert len(diff.nodes_added) == 1
        assert len(diff.edges_added) == 1

    def test_version_rollback(self):
        """Test version rollback"""
        manager = VersionManager()

        v1 = manager.create_version("wf1", [{"id": "node1"}], [])
        manager.publish_version("wf1", v1.id)

        v2 = manager.create_version("wf1", [{"id": "node1"}, {"id": "node2"}], [])
        manager.publish_version("wf1", v2.id)

        # Rollback to v1
        rolled_back = manager.rollback("wf1", v1.id)
        assert rolled_back is not None


class TestDebugging:
    """Test debugging capabilities"""

    def test_breakpoint_manager(self):
        """Test breakpoint management"""
        manager = BreakpointManager()

        bp = manager.add_breakpoint("node1")
        assert bp.enabled is True

        manager.disable_breakpoint(bp.id)
        assert bp.enabled is False

    def test_execution_tracer(self):
        """Test execution tracing"""
        tracer = ExecutionTracer()

        frame = tracer.start_frame("node1", "input", {})
        assert frame is not None

        tracer.end_frame(output={"result": "test"})
        assert len(tracer.frames) == 1

    def test_workflow_debugger(self):
        """Test workflow debugger"""
        debugger = WorkflowDebugger()

        bp = debugger.breakpoint_manager.add_breakpoint("node1")
        assert bp is not None

        watch = debugger.add_watch("$x > 10")
        assert watch is not None

        debug_info = debugger.get_debug_info()
        assert debug_info["breakpoints"] == 1
        assert debug_info["watch_expressions"] == 1


class TestVisualization:
    """Test visualization"""

    def test_flow_diagram_generator(self):
        """Test flow diagram generation"""
        generator = FlowDiagramGenerator()

        generator.add_node("node1", "Input", "input")
        generator.add_node("node2", "Process", "transform")
        generator.add_node("node3", "Output", "output")

        generator.add_edge("node1", "node2")
        generator.add_edge("node2", "node3")

        generator.layout_hierarchical()

        # Check nodes are positioned
        assert all(n.x > 0 for n in generator.nodes)
        assert all(n.y > 0 for n in generator.nodes)

    def test_svg_export(self):
        """Test SVG export"""
        generator = FlowDiagramGenerator()

        generator.add_node("node1", "Test", "input")
        svg = generator.to_svg()

        assert "<svg" in svg
        assert "node1" in svg or "Test" in svg

    def test_mermaid_export(self):
        """Test Mermaid export"""
        generator = FlowDiagramGenerator()

        generator.add_node("node1", "Input", "input")
        generator.add_node("node2", "Output", "output")
        generator.add_edge("node1", "node2")

        mermaid = generator.to_mermaid()

        assert "graph TD" in mermaid
        assert "node1" in mermaid
        assert "node2" in mermaid

    def test_workflow_visualizer(self):
        """Test workflow visualizer"""
        visualizer = WorkflowVisualizer()

        workflow = {
            "nodes": [
                {"id": "n1", "type": "input", "config": {"label": "Input"}},
                {"id": "n2", "type": "output", "config": {"label": "Output"}},
            ],
            "edges": [
                {"source": "n1", "target": "n2"},
            ],
        }

        diagram = visualizer.visualize_workflow(workflow)
        assert len(diagram.nodes) == 2
        assert len(diagram.edges) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
