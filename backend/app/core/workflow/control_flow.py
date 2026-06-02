"""Control Flow Management for Workflows

Implements advanced control flow constructs:
- If/Else conditional branching
- Switch multi-branch selection
- For/While loops with break/continue
- Parallel execution
- Subworkflow invocation
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Callable, Awaitable
from uuid import uuid4


class ControlFlowType(StrEnum):
    IF_ELSE = "if_else"
    SWITCH = "switch"
    FOR_LOOP = "for_loop"
    WHILE_LOOP = "while_loop"
    PARALLEL = "parallel"
    SUBWORKFLOW = "subworkflow"
    BREAK = "break"
    CONTINUE = "continue"


class LoopControlSignal(Exception):
    """Signal for loop control (break/continue)"""
    pass


class BreakSignal(LoopControlSignal):
    """Signal to break out of loop"""
    def __init__(self, value: Any = None):
        self.value = value
        super().__init__()


class ContinueSignal(LoopControlSignal):
    """Signal to continue to next iteration"""
    pass


@dataclass
class ControlFlowNode(ABC):
    """Base class for control flow nodes"""
    id: str = field(default_factory=lambda: str(uuid4()))
    type: ControlFlowType = field(init=False)
    config: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @abstractmethod
    async def execute(
        self,
        context: dict[str, Any],
        executor: Callable[[str, dict[str, Any]], Awaitable[Any]],
    ) -> Any:
        """Execute the control flow node"""
        pass


@dataclass
class IfElseNode(ControlFlowNode):
    """If/Else conditional branching"""
    type: ControlFlowType = field(default=ControlFlowType.IF_ELSE, init=False)
    condition: str = ""
    then_node_id: str = ""
    else_node_id: str | None = None

    async def execute(
        self,
        context: dict[str, Any],
        executor: Callable[[str, dict[str, Any]], Awaitable[Any]],
    ) -> Any:
        """Execute if/else branching"""
        from .data_flow import ExpressionEvaluator

        evaluator = ExpressionEvaluator()
        condition_result = evaluator.evaluate(self.condition, context)

        if condition_result:
            return await executor(self.then_node_id, context)
        elif self.else_node_id:
            return await executor(self.else_node_id, context)
        return None


@dataclass
class SwitchNode(ControlFlowNode):
    """Switch multi-branch selection"""
    type: ControlFlowType = field(default=ControlFlowType.SWITCH, init=False)
    expression: str = ""
    cases: dict[str, str] = field(default_factory=dict)  # value -> node_id
    default_node_id: str | None = None

    async def execute(
        self,
        context: dict[str, Any],
        executor: Callable[[str, dict[str, Any]], Awaitable[Any]],
    ) -> Any:
        """Execute switch branching"""
        from .data_flow import ExpressionEvaluator

        evaluator = ExpressionEvaluator()
        value = evaluator.evaluate(self.expression, context)
        value_str = str(value)

        if value_str in self.cases:
            return await executor(self.cases[value_str], context)
        elif self.default_node_id:
            return await executor(self.default_node_id, context)
        return None


@dataclass
class ForLoopNode(ControlFlowNode):
    """For loop with iteration"""
    type: ControlFlowType = field(default=ControlFlowType.FOR_LOOP, init=False)
    iterable_expr: str = ""
    item_var: str = "item"
    index_var: str = "index"
    body_node_id: str = ""
    max_iterations: int = 1000

    async def execute(
        self,
        context: dict[str, Any],
        executor: Callable[[str, dict[str, Any]], Awaitable[Any]],
    ) -> Any:
        """Execute for loop"""
        from .data_flow import ExpressionEvaluator

        evaluator = ExpressionEvaluator()
        iterable = evaluator.evaluate(self.iterable_expr, context)

        if not hasattr(iterable, '__iter__') or isinstance(iterable, (str, dict)):
            iterable = [iterable]

        results = []
        loop_context = context.copy()

        for index, item in enumerate(iterable):
            if index >= self.max_iterations:
                break

            loop_context[self.item_var] = item
            loop_context[self.index_var] = index
            loop_context["_loop_index"] = index
            loop_context["_loop_item"] = item

            try:
                result = await executor(self.body_node_id, loop_context)
                results.append(result)
            except BreakSignal as e:
                results.append(e.value)
                break
            except ContinueSignal:
                continue

        return {
            "results": results,
            "iterations": len(results),
            "max_iterations": self.max_iterations,
        }


@dataclass
class WhileLoopNode(ControlFlowNode):
    """While loop with condition"""
    type: ControlFlowType = field(default=ControlFlowType.WHILE_LOOP, init=False)
    condition: str = ""
    body_node_id: str = ""
    max_iterations: int = 1000

    async def execute(
        self,
        context: dict[str, Any],
        executor: Callable[[str, dict[str, Any]], Awaitable[Any]],
    ) -> Any:
        """Execute while loop"""
        from .data_flow import ExpressionEvaluator

        evaluator = ExpressionEvaluator()
        results = []
        loop_context = context.copy()
        iterations = 0

        while iterations < self.max_iterations:
            condition_result = evaluator.evaluate(self.condition, loop_context)
            if not condition_result:
                break

            try:
                result = await executor(self.body_node_id, loop_context)
                results.append(result)
            except BreakSignal as e:
                results.append(e.value)
                break
            except ContinueSignal:
                iterations += 1
                continue

            iterations += 1

        return {
            "results": results,
            "iterations": iterations,
            "max_iterations": self.max_iterations,
            "condition_final": evaluator.evaluate(self.condition, loop_context),
        }


@dataclass
class ParallelNode(ControlFlowNode):
    """Parallel execution of multiple branches"""
    type: ControlFlowType = field(default=ControlFlowType.PARALLEL, init=False)
    branches: list[str] = field(default_factory=list)  # node_ids
    join_strategy: str = "all"  # all, any, first, race
    timeout_ms: int = 0

    async def execute(
        self,
        context: dict[str, Any],
        executor: Callable[[str, dict[str, Any]], Awaitable[Any]],
    ) -> Any:
        """Execute branches in parallel"""
        tasks = [
            asyncio.create_task(executor(node_id, context.copy()))
            for node_id in self.branches
        ]

        try:
            timeout = self.timeout_ms / 1000 if self.timeout_ms > 0 else None

            if self.join_strategy == "all":
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=timeout,
                )
            elif self.join_strategy == "any":
                done, pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=timeout,
                )
                results = [task.result() for task in done]
                for task in pending:
                    task.cancel()
            elif self.join_strategy == "first":
                result = await asyncio.wait_for(
                    asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED),
                    timeout=timeout,
                )
                results = [result]
            elif self.join_strategy == "race":
                result = await asyncio.wait_for(
                    asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED),
                    timeout=timeout,
                )
                results = [result]
            else:
                results = await asyncio.gather(*tasks, return_exceptions=True)

            return {
                "results": results,
                "branch_count": len(self.branches),
                "join_strategy": self.join_strategy,
                "completed": len([r for r in results if not isinstance(r, Exception)]),
                "failed": len([r for r in results if isinstance(r, Exception)]),
            }
        except asyncio.TimeoutError:
            for task in tasks:
                task.cancel()
            raise


@dataclass
class SubworkflowNode(ControlFlowNode):
    """Invoke another workflow as a subworkflow"""
    type: ControlFlowType = field(default=ControlFlowType.SUBWORKFLOW, init=False)
    workflow_id: str = ""
    input_mapping: dict[str, str] = field(default_factory=dict)
    output_mapping: dict[str, str] = field(default_factory=dict)
    timeout_ms: int = 0

    async def execute(
        self,
        context: dict[str, Any],
        executor: Callable[[str, dict[str, Any]], Awaitable[Any]],
    ) -> Any:
        """Execute subworkflow"""
        from .data_flow import ExpressionEvaluator

        evaluator = ExpressionEvaluator()

        # Map inputs
        subworkflow_inputs = {}
        for target_key, source_expr in self.input_mapping.items():
            subworkflow_inputs[target_key] = evaluator.evaluate(source_expr, context)

        # Execute subworkflow
        timeout = self.timeout_ms / 1000 if self.timeout_ms > 0 else None

        try:
            result = await asyncio.wait_for(
                executor(self.workflow_id, subworkflow_inputs),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Subworkflow {self.workflow_id} timed out")

        # Map outputs
        mapped_output = {}
        if isinstance(result, dict):
            for target_key, source_key in self.output_mapping.items():
                mapped_output[target_key] = result.get(source_key)

        return {
            "workflow_id": self.workflow_id,
            "result": result,
            "mapped_output": mapped_output,
        }


class ControlFlowExecutor:
    """Executor for control flow nodes"""

    def __init__(self):
        self.nodes: dict[str, ControlFlowNode] = {}
        self.execution_history: list[dict[str, Any]] = []

    def register_node(self, node: ControlFlowNode) -> None:
        """Register a control flow node"""
        self.nodes[node.id] = node

    async def execute(
        self,
        node_id: str,
        context: dict[str, Any],
        executor: Callable[[str, dict[str, Any]], Awaitable[Any]] | None = None,
    ) -> Any:
        """Execute a control flow node"""
        # An empty/None dispatch target means a branch terminates with no
        # downstream node (e.g. an if-branch or loop body that does nothing).
        # Treat it as a safe no-op rather than a hard error. A genuinely
        # missing (non-empty) node_id still raises below.
        if not node_id:
            return None

        node = self.nodes.get(node_id)
        if node is None:
            raise ValueError(f"Node not found: {node_id}")

        if executor is None:
            executor = self.execute

        start_time = datetime.now(UTC)
        try:
            result = await node.execute(context, executor)
            self.execution_history.append({
                "node_id": node_id,
                "type": node.type,
                "status": "completed",
                "result": result,
                "duration_ms": (datetime.now(UTC) - start_time).total_seconds() * 1000,
            })
            return result
        except Exception as e:
            self.execution_history.append({
                "node_id": node_id,
                "type": node.type,
                "status": "failed",
                "error": str(e),
                "duration_ms": (datetime.now(UTC) - start_time).total_seconds() * 1000,
            })
            raise
