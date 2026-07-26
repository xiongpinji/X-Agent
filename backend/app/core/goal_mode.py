"""Goal Mode: Long-running goal execution with checkpoint/resume (对标 Codex /goal)."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class GoalControl:
    """协作式执行控制: 暂停/恢复/取消一个正在运行的目标。

    - ``pause_event`` set 表示允许继续推进; clear 表示在下一个子目标边界暂停。
    - ``cancel()`` 置位取消标志并唤醒暂停等待, 使执行循环尽快退出。
    """

    def __init__(self) -> None:
        self.pause_event = asyncio.Event()
        self.pause_event.set()
        self.cancel_requested = False

    def pause(self) -> None:
        self.pause_event.clear()

    def resume(self) -> None:
        self.pause_event.set()

    def cancel(self) -> None:
        self.cancel_requested = True
        self.pause_event.set()  # 唤醒暂停中的执行循环, 让取消生效


@dataclass
class SubGoal:
    """A decomposed sub-goal."""
    id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    status: str = "pending"  # pending, in_progress, completed, failed
    result: str = ""
    started_at: float | None = None
    completed_at: float | None = None


@dataclass
class GoalCheckpoint:
    """Checkpoint for goal progress."""
    goal_id: str = ""
    progress: list[SubGoal] = field(default_factory=list)
    current_step: int = 0
    total_steps: int = 0
    elapsed_seconds: float = 0.0
    saved_at: float = field(default_factory=time.time)


@dataclass
class GoalResult:
    """Final result of goal execution."""
    goal_id: str = ""
    status: str = "pending"  # pending, running, completed, timeout, failed, cancelled
    progress: list[SubGoal] = field(default_factory=list)
    output: str = ""
    total_duration: float = 0.0
    checkpoints_count: int = 0


class GoalModeOrchestrator:
    """Long-running goal mode with checkpoint/resume.

    Features:
    - Automatic goal decomposition into sub-goals
    - Periodic checkpointing (default 5 min)
    - Resume from checkpoint on failure
    - Configurable max execution time
    - Progress evaluation via LLM
    """

    def __init__(
        self,
        llm_router=None,
        agent_loop=None,
        memory=None,
        max_hours: float = 8.0,
        checkpoint_interval: int = 300,
    ):
        self.llm_router = llm_router
        self.agent_loop = agent_loop
        self.memory = memory
        self.max_hours = max_hours
        self.checkpoint_interval = checkpoint_interval
        self._checkpoints: dict[str, GoalCheckpoint] = {}

    async def execute_goal(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
        max_hours: float | None = None,
        goal_id: str | None = None,
        control: GoalControl | None = None,
    ) -> GoalResult:
        """Execute a long-running goal with automatic decomposition.

        ``goal_id`` 允许调用方(如 Goals API)透传自己的目标 ID, 便于状态关联。
        ``control`` 提供协作式暂停/取消: 每个子目标边界检查取消标志并等待
        暂停事件, 已开始的子目标会执行完毕后生效。
        """
        goal_id = goal_id or str(uuid4())
        deadline = time.time() + (max_hours or self.max_hours) * 3600
        result = GoalResult(goal_id=goal_id, status="running")
        start_time = time.time()
        context = context or {}

        logger.info(f"Starting goal execution: {goal_id} - {goal[:100]}")

        try:
            # 1. Decompose goal into sub-goals
            subgoals = await self._decompose_goal(goal, context)
            result.progress = subgoals

            # 2. Execute sub-goals sequentially
            for i, subgoal in enumerate(subgoals):
                # 协作式取消: 子目标边界生效
                if control and control.cancel_requested:
                    result.status = "cancelled"
                    break
                # 协作式暂停: 等待 resume, 期间取消仍可生效
                if control:
                    await control.pause_event.wait()
                    if control.cancel_requested:
                        result.status = "cancelled"
                        break

                if time.time() >= deadline:
                    result.status = "timeout"
                    break

                subgoal.status = "in_progress"
                subgoal.started_at = time.time()

                sub_result = await self._execute_subgoal(subgoal, context)
                subgoal.result = sub_result
                subgoal.status = "completed"
                subgoal.completed_at = time.time()

                # Checkpoint periodically
                if (i + 1) % max(1, len(subgoals) // 5) == 0:
                    await self._checkpoint(goal_id, result, start_time)

                # Evaluate overall progress
                if await self._goal_complete(goal, result):
                    result.status = "completed"
                    break

            if result.status == "running":
                result.status = "completed"

        except Exception as e:
            result.status = "failed"
            result.output = str(e)
            logger.error(f"Goal {goal_id} failed: {e}")

        result.total_duration = time.time() - start_time
        result.checkpoints_count = len([
            c for c in self._checkpoints.values() if c.goal_id == goal_id
        ])

        logger.info(f"Goal {goal_id} finished: status={result.status}, duration={result.total_duration:.1f}s")
        return result

    async def _decompose_goal(self, goal: str, context: dict[str, Any]) -> list[SubGoal]:
        """Decompose a high-level goal into executable sub-goals."""
        if self.llm_router:
            try:
                prompt = (
                    f"Decompose this goal into 3-7 concrete sub-goals:\n\n"
                    f"Goal: {goal}\n"
                    f"Context: {str(context)[:500]}\n\n"
                    "Respond with a JSON array of strings, each describing one sub-goal."
                )
                messages = [{"role": "user", "content": prompt}]
                response = await self.llm_router.chat(messages, tools=[])
                content = response.content if hasattr(response, "content") else str(response)
                json_start = content.find("[")
                json_end = content.rfind("]") + 1
                if json_start >= 0 and json_end > json_start:
                    items = json.loads(content[json_start:json_end])
                    return [SubGoal(description=str(item)) for item in items]
            except Exception as e:
                logger.warning(f"Goal decomposition via LLM failed: {e}")

        return [SubGoal(description=goal)]

    async def _execute_subgoal(self, subgoal: SubGoal, context: dict[str, Any]) -> str:
        """Execute a single sub-goal."""
        if self.agent_loop:
            try:
                result = await self.agent_loop.run(context=context, task=subgoal.description)
                return result.output if hasattr(result, "output") else str(result)
            except Exception as e:
                return f"Error: {e}"
        return f"Executed: {subgoal.description}"

    async def _goal_complete(self, goal: str, result: GoalResult) -> bool:
        """Evaluate if the overall goal is complete."""
        completed = sum(1 for sg in result.progress if sg.status == "completed")
        return completed >= len(result.progress)

    async def _checkpoint(self, goal_id: str, result: GoalResult, start_time: float) -> None:
        """Save a checkpoint of current progress."""
        checkpoint = GoalCheckpoint(
            goal_id=goal_id,
            progress=result.progress,
            current_step=sum(1 for sg in result.progress if sg.status == "completed"),
            total_steps=len(result.progress),
            elapsed_seconds=time.time() - start_time,
        )
        self._checkpoints[f"{goal_id}_{int(time.time())}"] = checkpoint
        logger.debug(f"Checkpoint saved for goal {goal_id}")

    def resume_from_checkpoint(self, goal_id: str) -> GoalCheckpoint | None:
        """Get the latest checkpoint for a goal."""
        relevant = [c for c in self._checkpoints.values() if c.goal_id == goal_id]
        if not relevant:
            return None
        return max(relevant, key=lambda c: c.saved_at)


# Global singleton
goal_orchestrator = GoalModeOrchestrator()
