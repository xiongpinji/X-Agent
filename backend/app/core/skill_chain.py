"""
X-Agent 技能链系统 - 支持技能组合、链式执行、并行执行、条件执行和循环
"""

from __future__ import annotations

import logging
import asyncio
import uuid
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
import json

from .skill_system_v2 import (
    SkillExecutionContext,
    SkillExecutionResult,
    ExecutionStatus,
    get_skill_executor,
    get_skill_registry,
)

logger = logging.getLogger(__name__)


class ChainType(str, Enum):
    """链类型"""
    SEQUENTIAL = "sequential"  # 顺序执行
    PARALLEL = "parallel"  # 并行执行
    CONDITIONAL = "conditional"  # 条件执行
    LOOP = "loop"  # 循环执行


class LoopType(str, Enum):
    """循环类型"""
    FOR = "for"  # 固定次数循环
    WHILE = "while"  # 条件循环
    FOREACH = "foreach"  # 遍历循环


@dataclass
class ChainStep:
    """链步骤"""
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    skill_name: str = ""
    input_mapping: Dict[str, str] = field(default_factory=dict)  # 输入映射
    output_mapping: Dict[str, str] = field(default_factory=dict)  # 输出映射
    retry_count: int = 0
    retry_delay_ms: int = 1000
    timeout_seconds: int = 300
    skip_on_error: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "step_id": self.step_id,
            "name": self.name,
            "skill_name": self.skill_name,
            "input_mapping": self.input_mapping,
            "output_mapping": self.output_mapping,
            "retry_count": self.retry_count,
            "retry_delay_ms": self.retry_delay_ms,
            "timeout_seconds": self.timeout_seconds,
            "skip_on_error": self.skip_on_error,
            "metadata": self.metadata,
        }


@dataclass
class ConditionalStep:
    """条件步骤"""
    condition: str  # 条件表达式，如 "result.success == true"
    then_steps: List[ChainStep] = field(default_factory=list)
    else_steps: List[ChainStep] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "condition": self.condition,
            "then_steps": [s.to_dict() for s in self.then_steps],
            "else_steps": [s.to_dict() for s in self.else_steps],
        }


@dataclass
class LoopStep:
    """循环步骤"""
    loop_type: LoopType = LoopType.FOR
    loop_count: int = 1  # FOR循环次数
    loop_condition: str = ""  # WHILE循环条件
    loop_variable: str = "item"  # FOREACH循环变量
    loop_items: str = ""  # FOREACH循环项目来源
    steps: List[ChainStep] = field(default_factory=list)
    break_on_error: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "loop_type": self.loop_type.value,
            "loop_count": self.loop_count,
            "loop_condition": self.loop_condition,
            "loop_variable": self.loop_variable,
            "loop_items": self.loop_items,
            "steps": [s.to_dict() for s in self.steps],
            "break_on_error": self.break_on_error,
        }


@dataclass
class SkillChain:
    """技能链定义"""
    chain_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    chain_type: ChainType = ChainType.SEQUENTIAL
    steps: List[Union[ChainStep, ConditionalStep, LoopStep]] = field(default_factory=list)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 3600
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "chain_id": self.chain_id,
            "name": self.name,
            "description": self.description,
            "chain_type": self.chain_type.value,
            "steps": [
                s.to_dict() if isinstance(s, ChainStep)
                else s.to_dict() if isinstance(s, ConditionalStep)
                else s.to_dict()
                for s in self.steps
            ],
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ChainExecutionContext:
    """链执行上下文"""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    chain_id: str = ""
    chain_name: str = ""
    user_id: str = ""
    tenant_id: str = ""
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, SkillExecutionResult] = field(default_factory=dict)
    status: ExecutionStatus = ExecutionStatus.PENDING
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get_duration_ms(self) -> float:
        """获取执行时长（毫秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "execution_id": self.execution_id,
            "chain_id": self.chain_id,
            "chain_name": self.chain_name,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "step_results": {k: v.to_dict() for k, v in self.step_results.items()},
            "status": self.status.value,
            "error": self.error,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "created_at": self.created_at.isoformat(),
            "duration_ms": self.get_duration_ms(),
        }


class SkillChainExecutor:
    """技能链执行引擎"""

    def __init__(self):
        self.executor = get_skill_executor()
        self.registry = get_skill_registry()
        self._execution_history: Dict[str, ChainExecutionContext] = {}

    async def execute_chain(
        self,
        chain: SkillChain,
        input_data: Dict[str, Any],
        user_id: str = "",
        tenant_id: str = "",
    ) -> ChainExecutionContext:
        """
        执行技能链

        Args:
            chain: 技能链定义
            input_data: 输入数据
            user_id: 用户ID
            tenant_id: 租户ID

        Returns:
            ChainExecutionContext: 执行上下文
        """
        context = ChainExecutionContext(
            chain_id=chain.chain_id,
            chain_name=chain.name,
            user_id=user_id,
            tenant_id=tenant_id,
            input_data=input_data,
        )

        try:
            context.status = ExecutionStatus.RUNNING
            context.start_time = datetime.now(UTC)

            # Execute based on chain type
            if chain.chain_type == ChainType.SEQUENTIAL:
                await self._execute_sequential(chain, context)
            elif chain.chain_type == ChainType.PARALLEL:
                await self._execute_parallel(chain, context)
            elif chain.chain_type == ChainType.CONDITIONAL:
                await self._execute_conditional(chain, context)
            elif chain.chain_type == ChainType.LOOP:
                await self._execute_loop(chain, context)

            context.status = ExecutionStatus.SUCCESS

        except Exception as e:
            context.status = ExecutionStatus.FAILED
            context.error = str(e)
            logger.error(f"Chain execution failed: {str(e)}", exc_info=True)

        finally:
            context.end_time = datetime.now(UTC)
            self._execution_history[context.execution_id] = context

        return context

    async def _execute_sequential(
        self, chain: SkillChain, context: ChainExecutionContext
    ) -> None:
        """顺序执行链"""
        current_data = context.input_data.copy()

        for step in chain.steps:
            if isinstance(step, ChainStep):
                result = await self._execute_step(step, current_data, context)
                context.step_results[step.step_id] = result

                if result.success:
                    # 应用输出映射
                    current_data = self._apply_output_mapping(
                        step.output_mapping, result.data, current_data
                    )
                else:
                    if not step.skip_on_error:
                        raise Exception(f"Step '{step.name}' failed: {result.error}")

            elif isinstance(step, ConditionalStep):
                await self._execute_conditional_step(step, current_data, context)

            elif isinstance(step, LoopStep):
                await self._execute_loop_step(step, current_data, context)

        context.output_data = current_data

    async def _execute_parallel(
        self, chain: SkillChain, context: ChainExecutionContext
    ) -> None:
        """并行执行链"""
        tasks = []

        for step in chain.steps:
            if isinstance(step, ChainStep):
                task = self._execute_step(step, context.input_data, context)
                tasks.append((step.step_id, task))

        results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

        for (step_id, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                context.step_results[step_id] = SkillExecutionResult(
                    success=False,
                    error=str(result),
                    error_type=type(result).__name__,
                )
            else:
                context.step_results[step_id] = result

        # Merge results
        merged_data = context.input_data.copy()
        for result in context.step_results.values():
            if result.success:
                merged_data.update(result.data)

        context.output_data = merged_data

    async def _execute_conditional(
        self, chain: SkillChain, context: ChainExecutionContext
    ) -> None:
        """条件执行链"""
        for step in chain.steps:
            if isinstance(step, ConditionalStep):
                await self._execute_conditional_step(step, context.input_data, context)

    async def _execute_loop(
        self, chain: SkillChain, context: ChainExecutionContext
    ) -> None:
        """循环执行链"""
        for step in chain.steps:
            if isinstance(step, LoopStep):
                await self._execute_loop_step(step, context.input_data, context)

    async def _execute_step(
        self,
        step: ChainStep,
        input_data: Dict[str, Any],
        context: ChainExecutionContext,
    ) -> SkillExecutionResult:
        """执行单个步骤"""
        # 应用输入映射
        mapped_input = self._apply_input_mapping(step.input_mapping, input_data)

        # 执行技能
        result = await self.executor.execute(
            skill_name=step.skill_name,
            input_data=mapped_input,
            user_id=context.user_id,
            tenant_id=context.tenant_id,
            timeout_seconds=step.timeout_seconds,
        )

        return result

    async def _execute_conditional_step(
        self,
        step: ConditionalStep,
        input_data: Dict[str, Any],
        context: ChainExecutionContext,
    ) -> None:
        """执行条件步骤"""
        # 评估条件
        condition_result = self._evaluate_condition(step.condition, input_data)

        if condition_result:
            for s in step.then_steps:
                result = await self._execute_step(s, input_data, context)
                context.step_results[s.step_id] = result
        else:
            for s in step.else_steps:
                result = await self._execute_step(s, input_data, context)
                context.step_results[s.step_id] = result

    async def _execute_loop_step(
        self,
        step: LoopStep,
        input_data: Dict[str, Any],
        context: ChainExecutionContext,
    ) -> None:
        """执行循环步骤"""
        if step.loop_type == LoopType.FOR:
            for i in range(step.loop_count):
                loop_data = input_data.copy()
                loop_data["_loop_index"] = i
                for s in step.steps:
                    result = await self._execute_step(s, loop_data, context)
                    context.step_results[f"{s.step_id}_loop_{i}"] = result
                    if not result.success and step.break_on_error:
                        break

        elif step.loop_type == LoopType.WHILE:
            iteration = 0
            while self._evaluate_condition(step.loop_condition, input_data):
                loop_data = input_data.copy()
                loop_data["_loop_iteration"] = iteration
                for s in step.steps:
                    result = await self._execute_step(s, loop_data, context)
                    context.step_results[f"{s.step_id}_loop_{iteration}"] = result
                    if not result.success and step.break_on_error:
                        break
                iteration += 1

        elif step.loop_type == LoopType.FOREACH:
            items = self._get_loop_items(step.loop_items, input_data)
            for idx, item in enumerate(items):
                loop_data = input_data.copy()
                loop_data[step.loop_variable] = item
                loop_data["_loop_index"] = idx
                for s in step.steps:
                    result = await self._execute_step(s, loop_data, context)
                    context.step_results[f"{s.step_id}_loop_{idx}"] = result
                    if not result.success and step.break_on_error:
                        break

    def _apply_input_mapping(
        self, mapping: Dict[str, str], input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """应用输入映射"""
        result = {}
        for target, source in mapping.items():
            if source in input_data:
                result[target] = input_data[source]
        return result

    def _apply_output_mapping(
        self,
        mapping: Dict[str, str],
        output_data: Dict[str, Any],
        current_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """应用输出映射"""
        result = current_data.copy()
        for target, source in mapping.items():
            if source in output_data:
                result[target] = output_data[source]
        return result

    def _evaluate_condition(
        self, condition: str, data: Dict[str, Any]
    ) -> bool:
        """评估条件表达式"""
        try:
            # 简单的条件评估，支持基本的比较操作
            # 例如: "result.success == true", "data.count > 10"
            return eval(condition, {"__builtins__": {}}, data)
        except Exception as e:
            logger.error(f"Condition evaluation failed: {str(e)}")
            return False

    def _get_loop_items(
        self, loop_items: str, data: Dict[str, Any]
    ) -> List[Any]:
        """获取循环项目"""
        try:
            # 支持从数据中获取循环项目
            # 例如: "data.items", "result.list"
            parts = loop_items.split(".")
            value = data
            for part in parts:
                value = value[part]
            return value if isinstance(value, list) else [value]
        except Exception as e:
            logger.error(f"Failed to get loop items: {str(e)}")
            return []

    async def get_execution_history(
        self, execution_id: str
    ) -> Optional[ChainExecutionContext]:
        """获取执行历史"""
        return self._execution_history.get(execution_id)

    async def list_execution_history(
        self, chain_id: str, limit: int = 100
    ) -> List[ChainExecutionContext]:
        """列出执行历史"""
        results = []
        for context in self._execution_history.values():
            if context.chain_id == chain_id:
                results.append(context)
        return sorted(results, key=lambda x: x.created_at, reverse=True)[:limit]


# Global instance
_chain_executor: Optional[SkillChainExecutor] = None


def get_skill_chain_executor() -> SkillChainExecutor:
    """获取全局技能链执行引擎"""
    global _chain_executor
    if _chain_executor is None:
        _chain_executor = SkillChainExecutor()
    return _chain_executor


__all__ = [
    "ChainType",
    "LoopType",
    "ChainStep",
    "ConditionalStep",
    "LoopStep",
    "SkillChain",
    "ChainExecutionContext",
    "SkillChainExecutor",
    "get_skill_chain_executor",
]
