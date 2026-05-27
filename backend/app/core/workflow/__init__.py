"""X-Agent Workflow Orchestration System

Enhanced workflow system with:
- Advanced control flow (if/else, switch, loops, parallel execution)
- Data flow management (variables, scoping, transformations)
- Error handling (try/catch/finally, retry, compensation)
- Workflow templates and versioning
- Debugging and visualization capabilities
"""

from .control_flow import (
    ControlFlowNode,
    IfElseNode,
    SwitchNode,
    ForLoopNode,
    WhileLoopNode,
    ParallelNode,
    SubworkflowNode,
)
from .data_flow import (
    DataFlowManager,
    VariableScope,
    DataTransformer,
    ExpressionEvaluator,
)
from .error_handling import (
    ErrorHandler,
    RetryPolicy,
    CompensationStrategy,
    ErrorNotifier,
)
from .templates import (
    WorkflowTemplate,
    TemplateLibrary,
    TemplateRegistry,
)
from .versioning import (
    WorkflowVersion,
    VersionManager,
    VersionComparator,
)
from .debugger import (
    WorkflowDebugger,
    BreakpointManager,
    ExecutionTracer,
)
from .visualizer import (
    WorkflowVisualizer,
    FlowDiagramGenerator,
)

__all__ = [
    "ControlFlowNode",
    "IfElseNode",
    "SwitchNode",
    "ForLoopNode",
    "WhileLoopNode",
    "ParallelNode",
    "SubworkflowNode",
    "DataFlowManager",
    "VariableScope",
    "DataTransformer",
    "ExpressionEvaluator",
    "ErrorHandler",
    "RetryPolicy",
    "CompensationStrategy",
    "ErrorNotifier",
    "WorkflowTemplate",
    "TemplateLibrary",
    "TemplateRegistry",
    "WorkflowVersion",
    "VersionManager",
    "VersionComparator",
    "WorkflowDebugger",
    "BreakpointManager",
    "ExecutionTracer",
    "WorkflowVisualizer",
    "FlowDiagramGenerator",
]
