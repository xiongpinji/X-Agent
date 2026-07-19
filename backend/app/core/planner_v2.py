"""
Advanced planner for hierarchical and adaptive planning.

This module provides sophisticated planning capabilities including hierarchical
planning, adaptive planning, and multi-agent coordination.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class PlanStatus(Enum):
    """Status of a plan."""
    CREATED = "created"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(Enum):
    """Status of a task."""
    PENDING = "pending"
    READY = "ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanTask:
    """A task in a plan."""
    task_id: str
    name: str
    description: str
    priority: int = 0
    estimated_duration: float = 0.0
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    """A plan for achieving a goal."""
    plan_id: str
    goal: str
    tasks: List[PlanTask] = field(default_factory=list)
    status: PlanStatus = PlanStatus.CREATED
    priority: int = 0
    estimated_total_duration: float = 0.0
    actual_duration: float = 0.0
    success_rate: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HierarchicalPlan:
    """A hierarchical plan with multiple levels."""
    plan_id: str
    goal: str
    levels: List[List[PlanTask]] = field(default_factory=list)
    current_level: int = 0
    status: PlanStatus = PlanStatus.CREATED
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Agent:
    """An agent that can execute tasks."""
    agent_id: str
    name: str
    capabilities: List[str]
    current_task: Optional[str] = None
    available: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MultiAgentPlan:
    """A plan for multi-agent coordination."""
    plan_id: str
    goal: str
    agents: List[Agent] = field(default_factory=list)
    tasks: List[PlanTask] = field(default_factory=list)
    task_assignments: Dict[str, str] = field(default_factory=dict)  # task_id -> agent_id
    status: PlanStatus = PlanStatus.CREATED
    metadata: Dict[str, Any] = field(default_factory=dict)


class AdvancedPlanner:
    """Advanced planner for complex planning scenarios."""

    def __init__(self, llm_client=None):
        """Initialize advanced planner.

        Args:
            llm_client: LLM client for planning assistance.
        """
        self.llm_client = llm_client
        self.plans: Dict[str, Plan] = {}
        self.hierarchical_plans: Dict[str, HierarchicalPlan] = {}
        self.multi_agent_plans: Dict[str, MultiAgentPlan] = {}
        self.planning_history: List[Dict[str, Any]] = []

    async def hierarchical_planning(
        self,
        goal: str,
        num_levels: int = 3,
    ) -> HierarchicalPlan:
        """Create a hierarchical plan for a goal.

        Args:
            goal: The goal to achieve.
            num_levels: Number of hierarchical levels.

        Returns:
            HierarchicalPlan with multiple levels of abstraction.
        """
        logger.info(f"Creating hierarchical plan for goal: {goal}")

        plan = HierarchicalPlan(
            plan_id=f"hier_{len(self.hierarchical_plans)}",
            goal=goal,
        )

        # Generate tasks for each level
        for level in range(num_levels):
            level_tasks = await self._generate_level_tasks(goal, level, num_levels)
            plan.levels.append(level_tasks)

        self.hierarchical_plans[plan.plan_id] = plan
        logger.info(f"Created hierarchical plan with {num_levels} levels")

        return plan

    async def adaptive_planning(
        self,
        plan: Plan,
        feedback: Dict[str, Any],
    ) -> Plan:
        """Adapt a plan based on feedback.

        Args:
            plan: The original plan.
            feedback: Feedback on plan execution.

        Returns:
            Adapted plan.
        """
        logger.info(f"Adapting plan {plan.plan_id} based on feedback")

        # Analyze feedback
        issues = self._analyze_feedback(feedback)

        # Identify affected tasks
        affected_tasks = self._identify_affected_tasks(plan, issues)

        # Replan affected tasks
        for task_id in affected_tasks:
            task = next((t for t in plan.tasks if t.task_id == task_id), None)
            if task:
                # Generate alternative approaches
                alternatives = await self._generate_alternatives(task)

                # Select best alternative
                best_alternative = self._select_best_alternative(alternatives, feedback)

                # Update task
                task.description = best_alternative["description"]
                task.metadata["alternatives"] = alternatives

        plan.status = PlanStatus.CREATED  # Reset to allow re-execution

        logger.info(f"Adapted plan with {len(affected_tasks)} changes")

        return plan

    async def multi_agent_planning(
        self,
        goal: str,
        agents: List[Agent],
    ) -> MultiAgentPlan:
        """Create a plan for multi-agent coordination.

        Args:
            goal: The goal to achieve.
            agents: List of available agents.

        Returns:
            MultiAgentPlan with task assignments.
        """
        logger.info(f"Creating multi-agent plan for goal: {goal}")

        plan = MultiAgentPlan(
            plan_id=f"multi_{len(self.multi_agent_plans)}",
            goal=goal,
            agents=agents,
        )

        # Generate tasks
        tasks = await self._generate_tasks(goal)
        plan.tasks = tasks

        # Assign tasks to agents
        plan.task_assignments = await self._assign_tasks_to_agents(tasks, agents)

        self.multi_agent_plans[plan.plan_id] = plan
        logger.info(f"Created multi-agent plan with {len(tasks)} tasks")

        return plan

    async def create_plan(
        self,
        goal: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Plan:
        """Create a plan for a goal.

        Args:
            goal: The goal to achieve.
            constraints: Optional constraints on the plan.

        Returns:
            Plan for achieving the goal.
        """
        logger.info(f"Creating plan for goal: {goal}")

        plan = Plan(
            plan_id=f"plan_{len(self.plans)}",
            goal=goal,
        )

        # Generate tasks
        tasks = await self._generate_tasks(goal)
        plan.tasks = tasks

        # Apply constraints
        if constraints:
            plan = self._apply_constraints(plan, constraints)

        # Calculate estimated duration
        plan.estimated_total_duration = sum(t.estimated_duration for t in plan.tasks)

        self.plans[plan.plan_id] = plan
        logger.info(f"Created plan with {len(plan.tasks)} tasks")

        return plan

    async def execute_plan(self, plan: Plan) -> Plan:
        """Execute a plan.

        Args:
            plan: The plan to execute.

        Returns:
            Executed plan with results.
        """
        logger.info(f"Executing plan {plan.plan_id}")

        plan.status = PlanStatus.EXECUTING

        # Execute tasks in order
        for task in plan.tasks:
            # Check dependencies
            if not self._dependencies_satisfied(task, plan.tasks):
                logger.debug(f"Skipping task {task.task_id} (dependencies not satisfied)")
                task.status = TaskStatus.SKIPPED
                continue

            # Execute task
            task.status = TaskStatus.EXECUTING
            try:
                result = await self._execute_task(task)
                task.result = result
                task.status = TaskStatus.COMPLETED
            except Exception as e:
                logger.error(f"Task {task.task_id} failed: {str(e)}")
                task.error = str(e)
                task.status = TaskStatus.FAILED

        # Calculate success rate
        completed = sum(1 for t in plan.tasks if t.status == TaskStatus.COMPLETED)
        plan.success_rate = completed / len(plan.tasks) if plan.tasks else 0.0

        # Set final status
        if plan.success_rate == 1.0:
            plan.status = PlanStatus.COMPLETED
        elif plan.success_rate > 0:
            plan.status = PlanStatus.COMPLETED  # Partial success
        else:
            plan.status = PlanStatus.FAILED

        logger.info(f"Plan execution completed (success rate: {plan.success_rate:.2%})")

        return plan

    async def replan(
        self,
        plan: Plan,
        reason: str,
    ) -> Plan:
        """Replan when current plan fails.

        Args:
            plan: The failed plan.
            reason: Reason for replanning.

        Returns:
            New plan.
        """
        logger.info(f"Replanning due to: {reason}")

        # Analyze failure
        failed_tasks = [t for t in plan.tasks if t.status == TaskStatus.FAILED]

        # Generate new plan
        new_plan = await self.create_plan(plan.goal)

        # Incorporate lessons from failed plan
        for failed_task in failed_tasks:
            # Find corresponding task in new plan
            new_task = next((t for t in new_plan.tasks if t.name == failed_task.name), None)
            if new_task:
                # Mark as high priority for alternative approach
                new_task.priority = 10
                new_task.metadata["previous_failure"] = failed_task.error

        logger.info(f"Created new plan with {len(new_plan.tasks)} tasks")

        return new_plan

    # Helper methods

    async def _generate_level_tasks(
        self,
        goal: str,
        level: int,
        num_levels: int,
    ) -> List[PlanTask]:
        """Generate tasks for a specific hierarchical level.

        Args:
            goal: The goal.
            level: The level (0 = most abstract, num_levels-1 = most concrete).
            num_levels: Total number of levels.

        Returns:
            List of tasks for this level.
        """
        # Placeholder implementation
        tasks = []

        if level == 0:
            # Most abstract level
            tasks.append(PlanTask(
                task_id=f"task_0_0",
                name="Analyze Goal",
                description=f"Analyze the goal: {goal}",
                priority=10,
            ))
        elif level == num_levels - 1:
            # Most concrete level
            for i in range(3):
                tasks.append(PlanTask(
                    task_id=f"task_{level}_{i}",
                    name=f"Concrete Task {i+1}",
                    description=f"Execute concrete task {i+1}",
                    priority=5,
                ))
        else:
            # Intermediate levels
            for i in range(2):
                tasks.append(PlanTask(
                    task_id=f"task_{level}_{i}",
                    name=f"Intermediate Task {i+1}",
                    description=f"Execute intermediate task {i+1}",
                    priority=7,
                ))

        return tasks

    async def _generate_tasks(self, goal: str) -> List[PlanTask]:
        """Generate tasks for a goal.

        Args:
            goal: The goal.

        Returns:
            List of tasks.
        """
        # Placeholder implementation
        tasks = [
            PlanTask(
                task_id="task_1",
                name="Understand Goal",
                description=f"Understand the goal: {goal}",
                priority=10,
                estimated_duration=1.0,
            ),
            PlanTask(
                task_id="task_2",
                name="Plan Approach",
                description="Plan the approach to achieve the goal",
                priority=9,
                estimated_duration=2.0,
                dependencies=["task_1"],
            ),
            PlanTask(
                task_id="task_3",
                name="Execute Plan",
                description="Execute the planned approach",
                priority=8,
                estimated_duration=5.0,
                dependencies=["task_2"],
            ),
            PlanTask(
                task_id="task_4",
                name="Verify Results",
                description="Verify that the goal has been achieved",
                priority=7,
                estimated_duration=1.0,
                dependencies=["task_3"],
            ),
        ]

        return tasks

    async def _assign_tasks_to_agents(
        self,
        tasks: List[PlanTask],
        agents: List[Agent],
    ) -> Dict[str, str]:
        """Assign tasks to agents.

        Args:
            tasks: List of tasks.
            agents: List of agents.

        Returns:
            Dictionary mapping task IDs to agent IDs.
        """
        assignments = {}

        for task in tasks:
            # Find best agent for this task
            best_agent = None
            best_score = -1

            for agent in agents:
                if not agent.available:
                    continue

                # Score agent based on capabilities
                score = self._score_agent_for_task(agent, task)

                if score > best_score:
                    best_score = score
                    best_agent = agent

            if best_agent:
                assignments[task.task_id] = best_agent.agent_id
                best_agent.current_task = task.task_id

        return assignments

    def _score_agent_for_task(self, agent: Agent, task: PlanTask) -> float:
        """Score an agent for a task.

        Args:
            agent: The agent.
            task: The task.

        Returns:
            Score between 0 and 1.
        """
        # Simple scoring based on capability match
        score = 0.5  # Base score

        # Check if agent has relevant capabilities
        task_keywords = set(task.description.lower().split())
        for capability in agent.capabilities:
            if capability.lower() in task_keywords:
                score += 0.25

        return min(score, 1.0)

    def _analyze_feedback(self, feedback: Dict[str, Any]) -> List[str]:
        """Analyze feedback to identify issues.

        Args:
            feedback: Feedback dictionary.

        Returns:
            List of identified issues.
        """
        issues = []

        if feedback.get("success", False) is False:
            issues.append("Plan execution failed")

        if feedback.get("delays"):
            issues.append("Plan execution delayed")

        if feedback.get("errors"):
            issues.extend(feedback["errors"])

        return issues

    def _identify_affected_tasks(
        self,
        plan: Plan,
        issues: List[str],
    ) -> Set[str]:
        """Identify tasks affected by issues.

        Args:
            plan: The plan.
            issues: List of issues.

        Returns:
            Set of affected task IDs.
        """
        affected = set()

        for issue in issues:
            # Find tasks related to this issue
            for task in plan.tasks:
                if issue.lower() in task.description.lower():
                    affected.add(task.task_id)

        return affected

    async def _generate_alternatives(self, task: PlanTask) -> List[Dict[str, Any]]:
        """Generate alternative approaches for a task.

        Args:
            task: The task.

        Returns:
            List of alternative approaches.
        """
        # Placeholder implementation
        alternatives = [
            {
                "description": f"Alternative approach 1 for {task.name}",
                "estimated_duration": task.estimated_duration * 0.8,
                "confidence": 0.7,
            },
            {
                "description": f"Alternative approach 2 for {task.name}",
                "estimated_duration": task.estimated_duration * 1.2,
                "confidence": 0.8,
            },
        ]

        return alternatives

    def _select_best_alternative(
        self,
        alternatives: List[Dict[str, Any]],
        feedback: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Select the best alternative.

        Args:
            alternatives: List of alternatives.
            feedback: Feedback to guide selection.

        Returns:
            Selected alternative.
        """
        # Simple selection: choose highest confidence
        return max(alternatives, key=lambda x: x.get("confidence", 0))

    def _apply_constraints(
        self,
        plan: Plan,
        constraints: Dict[str, Any],
    ) -> Plan:
        """Apply constraints to a plan.

        Args:
            plan: The plan.
            constraints: Constraints to apply.

        Returns:
            Constrained plan.
        """
        if "max_duration" in constraints:
            max_duration = constraints["max_duration"]
            # Adjust tasks to fit within max duration
            total_duration = sum(t.estimated_duration for t in plan.tasks)
            if total_duration > max_duration:
                scale_factor = max_duration / total_duration
                for task in plan.tasks:
                    task.estimated_duration *= scale_factor

        if "priority_tasks" in constraints:
            # Mark priority tasks
            priority_names = constraints["priority_tasks"]
            for task in plan.tasks:
                if task.name in priority_names:
                    task.priority = 10

        return plan

    def _dependencies_satisfied(
        self,
        task: PlanTask,
        all_tasks: List[PlanTask],
    ) -> bool:
        """Check if task dependencies are satisfied.

        Args:
            task: The task.
            all_tasks: All tasks in the plan.

        Returns:
            True if dependencies are satisfied.
        """
        for dep_id in task.dependencies:
            dep_task = next((t for t in all_tasks if t.task_id == dep_id), None)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False

        return True

    async def _execute_task(self, task: PlanTask) -> str:
        """Execute a task.

        Args:
            task: The task to execute.

        Returns:
            Task result.
        """
        logger.info(f"Executing task: {task.name}")

        # Placeholder implementation
        result = f"Completed: {task.description}"

        return result

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get a plan by ID.

        Args:
            plan_id: The plan ID.

        Returns:
            The plan, or None if not found.
        """
        return self.plans.get(plan_id)

    def get_all_plans(self) -> List[Plan]:
        """Get all plans.

        Returns:
            List of all plans.
        """
        return list(self.plans.values())

    def get_planning_stats(self) -> Dict[str, Any]:
        """Get planning statistics.

        Returns:
            Planning statistics.
        """
        return {
            "total_plans": len(self.plans),
            "hierarchical_plans": len(self.hierarchical_plans),
            "multi_agent_plans": len(self.multi_agent_plans),
            "completed_plans": sum(1 for p in self.plans.values() if p.status == PlanStatus.COMPLETED),
            "failed_plans": sum(1 for p in self.plans.values() if p.status == PlanStatus.FAILED),
        }
