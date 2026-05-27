"""X-Agent Enhanced Workflow System - Usage Guide and Best Practices

Complete guide for using the enhanced workflow orchestration system.
"""

# X-Agent Enhanced Workflow System

## Overview

The enhanced workflow system provides advanced orchestration capabilities for complex business processes:

- **Control Flow**: If/else, switch, loops, parallel execution, subworkflows
- **Data Flow**: Variable scoping, transformations, expression evaluation
- **Error Handling**: Retry policies, compensation strategies, error notifications
- **Templates**: Reusable workflow templates with parameters
- **Versioning**: Version control, deployment strategies, rollback
- **Debugging**: Breakpoints, execution tracing, performance analysis
- **Visualization**: Flow diagrams, execution timelines, dependency graphs

## Quick Start

### 1. Basic Workflow Definition

```python
from backend.app.core.workflows import WorkflowDefinition, WorkflowNode, WorkflowEdge

# Define workflow
workflow = WorkflowDefinition(
    name="Data Processing Pipeline",
    description="Process and transform data",
    nodes=[
        WorkflowNode(id="input", type="input", config={"key": "data"}),
        WorkflowNode(id="transform", type="transform", config={"template": "Process: {input_data}"}),
        WorkflowNode(id="output", type="output", config={"from": "transform"}),
    ],
    edges=[
        WorkflowEdge(source="input", target="transform"),
        WorkflowEdge(source="transform", target="output"),
    ],
)
```

### 2. Control Flow - If/Else

```python
from backend.app.core.workflow.control_flow import IfElseNode

if_node = IfElseNode(
    id="check_value",
    condition="$value > 100",
    then_node_id="high_value_handler",
    else_node_id="low_value_handler",
)
```

### 3. Control Flow - Loops

```python
from backend.app.core.workflow.control_flow import ForLoopNode

loop_node = ForLoopNode(
    id="process_items",
    iterable_expr="$items",
    item_var="current_item",
    body_node_id="process_single_item",
    max_iterations=1000,
)
```

### 4. Parallel Execution

```python
from backend.app.core.workflow.control_flow import ParallelNode

parallel_node = ParallelNode(
    id="parallel_processing",
    branches=["branch1", "branch2", "branch3"],
    join_strategy="all",  # all, any, first, race
    timeout_ms=30000,
)
```

### 5. Data Flow Management

```python
from backend.app.core.workflow.data_flow import DataFlowManager, ExpressionEvaluator

# Create data flow manager
manager = DataFlowManager()

# Set variables
manager.set_variable("user_id", 123)
manager.set_variable("action", "create")

# Evaluate expressions
result = manager.evaluate_expression("$user_id > 100")

# Render templates
output = manager.render_template("User {user_id} performed {action}")

# Transform data
transformed = manager.transform_data(
    [1, 2, 3, 4, 5],
    {"type": "filter", "predicate": "$item > 2"}
)
```

### 6. Error Handling

```python
from backend.app.core.workflow.error_handling import (
    ErrorHandler,
    RetryPolicy,
    CompensationStrategy,
    RetryStrategy,
    CompensationType,
)

# Create error handler with retry policy
handler = ErrorHandler(
    retry_policy=RetryPolicy(
        max_attempts=3,
        initial_delay_ms=100,
        strategy=RetryStrategy.EXPONENTIAL,
        backoff_multiplier=2.0,
    ),
    compensation_strategy=CompensationStrategy(
        type=CompensationType.ROLLBACK,
        notify_channels=["slack", "email"],
    ),
)

# Handle error
try:
    # Execute node
    pass
except Exception as e:
    result = await handler.handle_error(
        error=e,
        node_id="node1",
        workflow_id="workflow1",
        attempt=1,
    )
```

### 7. Workflow Templates

```python
from backend.app.core.workflow.templates import (
    WorkflowTemplate,
    TemplateParameter,
    TemplateLibrary,
    TemplateRegistry,
)

# Create custom template
template = WorkflowTemplate(
    name="Data Processing",
    description="Process data through pipeline",
    parameters=[
        TemplateParameter(
            name="input_source",
            type="string",
            description="Input data source",
            required=True,
        ),
        TemplateParameter(
            name="output_format",
            type="string",
            description="Output format",
            default="json",
            enum_values=["json", "csv", "parquet"],
        ),
    ],
    nodes=[
        {"id": "input", "type": "input", "config": {"source": "${input_source}"}},
        {"id": "output", "type": "output", "config": {"format": "${output_format}"}},
    ],
    edges=[{"source": "input", "target": "output"}],
)

# Instantiate template
workflow = template.instantiate({
    "input_source": "database",
    "output_format": "json",
})

# Use template library
registry = TemplateRegistry()
for template in TemplateLibrary.get_all_templates():
    registry.register(template)

# Search templates
results = registry.search("data processing")
```

### 8. Version Management

```python
from backend.app.core.workflow.versioning import (
    VersionManager,
    DeploymentStrategy,
)

manager = VersionManager()

# Create version
version = manager.create_version(
    workflow_id="wf1",
    nodes=[{"id": "node1", "type": "input"}],
    edges=[],
    changelog="Initial version",
    author="user@example.com",
)

# Publish version
published = manager.publish_version(
    workflow_id="wf1",
    version_id=version.id,
    deployment_strategy=DeploymentStrategy.CANARY,
    canary_percentage=10,
)

# Compare versions
diff = manager.compare_versions("wf1", version1_id, version2_id)
print(f"Breaking changes: {diff.breaking_changes}")
print(f"Compatibility: {diff.compatibility_score}")

# Rollback
manager.rollback("wf1", previous_version_id)
```

### 9. Debugging

```python
from backend.app.core.workflow.debugger import WorkflowDebugger

debugger = WorkflowDebugger()

# Add breakpoint
bp = debugger.breakpoint_manager.add_breakpoint(
    node_id="node1",
    condition="$value > 100",
)

# Add watch expression
watch = debugger.add_watch("$counter")

# Evaluate watches
watches = debugger.evaluate_watches({"counter": 5})

# Get debug info
debug_info = debugger.get_debug_info()
print(f"State: {debug_info['state']}")
print(f"Call stack: {debug_info['call_stack']}")

# Performance report
perf = debugger.get_performance_report()
print(f"Slowest nodes: {perf['slowest_nodes']}")
```

### 10. Visualization

```python
from backend.app.core.workflow.visualizer import WorkflowVisualizer

visualizer = WorkflowVisualizer()

# Visualize workflow
diagram = visualizer.visualize_workflow(
    workflow_definition=workflow_def,
    execution_state=execution_state,
)

# Export to SVG
visualizer.export_svg("workflow.svg")

# Export to Mermaid
visualizer.export_mermaid("workflow.md")

# Get execution timeline
timeline = visualizer.get_execution_timeline(execution_state)

# Get dependency graph
deps = visualizer.get_dependency_graph(workflow_def)
```

## Best Practices

### 1. Workflow Design

- **Keep workflows simple**: Break complex workflows into smaller subworkflows
- **Use meaningful node IDs**: Use descriptive IDs like "validate_input" instead of "node1"
- **Document workflows**: Add descriptions and comments to nodes
- **Avoid deep nesting**: Limit nesting depth to improve readability

### 2. Error Handling

- **Use appropriate retry strategies**: 
  - FIXED: For simple retries
  - EXPONENTIAL: For transient failures
  - FIBONACCI: For rate-limited APIs
- **Set reasonable timeouts**: Prevent workflows from hanging
- **Implement compensation**: Always have a rollback strategy
- **Monitor errors**: Track error patterns and adjust strategies

### 3. Data Flow

- **Use variable scoping**: Keep variables in appropriate scopes
- **Validate inputs**: Check data types and ranges
- **Transform early**: Apply transformations close to data source
- **Use templates**: Avoid hardcoding values

### 4. Performance

- **Use parallel execution**: Process independent tasks concurrently
- **Batch operations**: Group similar operations together
- **Cache results**: Avoid redundant computations
- **Monitor performance**: Use debugger to identify bottlenecks

### 5. Versioning

- **Use semantic versioning**: MAJOR.MINOR.PATCH
- **Document changes**: Write clear changelogs
- **Test before publishing**: Validate new versions
- **Use canary deployments**: Roll out changes gradually

### 6. Debugging

- **Add strategic breakpoints**: Focus on critical nodes
- **Use watch expressions**: Monitor important variables
- **Review execution traces**: Understand execution flow
- **Analyze performance**: Identify slow operations

### 7. Templates

- **Create reusable templates**: Reduce duplication
- **Parameterize templates**: Make templates flexible
- **Document parameters**: Explain what each parameter does
- **Version templates**: Track template changes

## Common Patterns

### Pattern 1: Retry with Exponential Backoff

```python
handler = ErrorHandler(
    retry_policy=RetryPolicy(
        max_attempts=5,
        initial_delay_ms=100,
        max_delay_ms=30000,
        strategy=RetryStrategy.EXPONENTIAL,
        backoff_multiplier=2.0,
    ),
)
```

### Pattern 2: Parallel Processing with Timeout

```python
parallel_node = ParallelNode(
    id="parallel_process",
    branches=["process_1", "process_2", "process_3"],
    join_strategy="all",
    timeout_ms=60000,  # 60 seconds
)
```

### Pattern 3: Conditional Branching

```python
if_node = IfElseNode(
    id="check_status",
    condition="$status == 'approved'",
    then_node_id="execute_action",
    else_node_id="send_notification",
)
```

### Pattern 4: Data Transformation Pipeline

```python
transformations = [
    {"type": "filter", "predicate": "$item.active == true"},
    {"type": "map", "mapping": {"id": "id", "name": "full_name"}},
    {"type": "sort", "key": "$name", "reverse": False},
]

for transform in transformations:
    data = manager.transform_data(data, transform)
```

### Pattern 5: Approval Workflow

```python
approval_node = WorkflowNode(
    id="approval",
    type="approval",
    config={
        "risk_level": "HIGH",
        "reason": "High-value transaction",
        "approvers": ["admin@example.com"],
    },
)
```

## Troubleshooting

### Issue: Workflow hangs

**Solution**: Add timeouts to nodes and use execution tracing to identify where it's stuck.

```python
node.config["timeout_ms"] = 30000  # 30 seconds
```

### Issue: High memory usage

**Solution**: Use streaming for large datasets and clean up intermediate results.

```python
# Process in batches
for batch in batches:
    result = process_batch(batch)
    # Clean up
    del batch
```

### Issue: Slow performance

**Solution**: Use parallel execution and optimize data transformations.

```python
# Profile with debugger
perf_report = debugger.get_performance_report()
print(perf_report["slowest_nodes"])
```

### Issue: Errors not being caught

**Solution**: Ensure error handlers are registered and compensation strategies are defined.

```python
handler.register_error_handler(
    "TimeoutError",
    async_handler_function,
)
```

## Advanced Topics

### Custom Node Types

Extend the workflow system with custom node types:

```python
from backend.app.core.workflow.control_flow import ControlFlowNode

class CustomNode(ControlFlowNode):
    async def execute(self, context, executor):
        # Custom logic
        return result
```

### Custom Transformations

Add custom data transformations:

```python
class CustomTransformer(DataTransformer):
    @staticmethod
    def custom_transform(data, config):
        # Custom transformation logic
        return transformed_data
```

### Integration with External Systems

Connect workflows to external APIs:

```python
node = WorkflowNode(
    id="api_call",
    type="tool",
    config={
        "tool_name": "http_request",
        "url": "${api_url}",
        "method": "POST",
        "body": "${request_body}",
    },
)
```

## Performance Metrics

Monitor workflow performance:

```python
metrics = {
    "total_workflows": manager.repository.definition_count(),
    "total_runs": manager.repository.run_count(),
    "average_duration": calculate_average_duration(),
    "success_rate": calculate_success_rate(),
    "error_rate": calculate_error_rate(),
}
```

## Security Considerations

- **Validate all inputs**: Prevent injection attacks
- **Use permission scopes**: Restrict node access
- **Encrypt sensitive data**: Protect credentials
- **Audit workflows**: Track all changes
- **Rate limit**: Prevent abuse

## References

- Control Flow: `backend.app.core.workflow.control_flow`
- Data Flow: `backend.app.core.workflow.data_flow`
- Error Handling: `backend.app.core.workflow.error_handling`
- Templates: `backend.app.core.workflow.templates`
- Versioning: `backend.app.core.workflow.versioning`
- Debugging: `backend.app.core.workflow.debugger`
- Visualization: `backend.app.core.workflow.visualizer`
