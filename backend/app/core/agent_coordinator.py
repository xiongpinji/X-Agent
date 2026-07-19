"""
Agent coordinator module for X-Agent.

Coordinates multiple agents and aggregates their results.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Any, Dict, List

logger = logging.getLogger(__name__)


class CoordinationStrategy(str, Enum):
    """Strategy for coordinating agents."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"
    CONSENSUS = "consensus"


class AggregationStrategy(str, Enum):
    """Strategy for aggregating results."""

    FIRST = "first"
    LAST = "last"
    ALL = "all"
    MAJORITY = "majority"
    CUSTOM = "custom"


@dataclass
class AgentResult:
    """Result from an agent."""

    agent_id: str
    status: str
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class AggregatedResult:
    """Aggregated result from multiple agents."""

    coordination_id: str
    strategy: CoordinationStrategy
    agent_results: List[AgentResult] = field(default_factory=list)
    aggregated_output: Any = None
    aggregation_strategy: AggregationStrategy = AggregationStrategy.ALL
    completed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentCoordinator:
    """
    Coordinates execution of multiple agents.

    Handles different coordination strategies and result aggregation.
    """

    def __init__(self):
        """Initialize the agent coordinator."""
        self.logger = logger
        self.coordination_history: Dict[str, AggregatedResult] = {}

    async def coordinate_agents(
        self,
        agents: List[Any],
        strategy: CoordinationStrategy = CoordinationStrategy.PARALLEL,
        task: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AggregatedResult:
        """
        Coordinate execution of multiple agents.

        Args:
            agents: List of agent instances
            strategy: Coordination strategy
            task: Task for agents to execute
            context: Context data

        Returns:
            Aggregated result
        """
        import uuid
        coordination_id = f"coord_{uuid.uuid4().hex[:12]}"
        context = context or {}

        self.logger.info(
            f"Starting coordination {coordination_id} with {len(agents)} agents "
            f"using {strategy.value} strategy"
        )

        try:
            if strategy == CoordinationStrategy.SEQUENTIAL:
                results = await self._coordinate_sequential(agents, task, context)
            elif strategy == CoordinationStrategy.PARALLEL:
                results = await self._coordinate_parallel(agents, task, context)
            elif strategy == CoordinationStrategy.HIERARCHICAL:
                results = await self._coordinate_hierarchical(agents, task, context)
            elif strategy == CoordinationStrategy.CONSENSUS:
                results = await self._coordinate_consensus(agents, task, context)
            else:
                raise ValueError(f"Unknown strategy: {strategy}")

            aggregated = AggregatedResult(
                coordination_id=coordination_id,
                strategy=strategy,
                agent_results=results,
            )

            self.coordination_history[coordination_id] = aggregated
            return aggregated

        except Exception as e:
            self.logger.error(f"Coordination {coordination_id} failed: {e}")
            raise

    async def _coordinate_sequential(
        self,
        agents: List[Any],
        task: Optional[str],
        context: Dict[str, Any],
    ) -> List[AgentResult]:
        """
        Execute agents sequentially.

        Args:
            agents: List of agents
            task: Task to execute
            context: Context data

        Returns:
            List of agent results
        """
        results = []

        for agent in agents:
            try:
                # Execute agent
                output = await self._execute_agent(agent, task, context)

                result = AgentResult(
                    agent_id=getattr(agent, "agent_id", "unknown"),
                    status="completed",
                    output=output,
                )
                results.append(result)

                # Pass output to next agent as context
                context["previous_output"] = output

            except Exception as e:
                result = AgentResult(
                    agent_id=getattr(agent, "agent_id", "unknown"),
                    status="failed",
                    error=str(e),
                )
                results.append(result)

        return results

    async def _coordinate_parallel(
        self,
        agents: List[Any],
        task: Optional[str],
        context: Dict[str, Any],
    ) -> List[AgentResult]:
        """
        Execute agents in parallel.

        Args:
            agents: List of agents
            task: Task to execute
            context: Context data

        Returns:
            List of agent results
        """
        tasks = [
            self._execute_agent_safe(agent, task, context)
            for agent in agents
        ]

        results = await asyncio.gather(*tasks, return_exceptions=False)
        return results

    async def _coordinate_hierarchical(
        self,
        agents: List[Any],
        task: Optional[str],
        context: Dict[str, Any],
    ) -> List[AgentResult]:
        """
        Execute agents in hierarchical manner.

        Args:
            agents: List of agents
            task: Task to execute
            context: Context data

        Returns:
            List of agent results
        """
        # First agent is coordinator
        if not agents:
            return []

        coordinator = agents[0]
        workers = agents[1:]

        results = []

        try:
            # Coordinator prepares task
            coord_output = await self._execute_agent(coordinator, task, context)
            results.append(
                AgentResult(
                    agent_id=getattr(coordinator, "agent_id", "unknown"),
                    status="completed",
                    output=coord_output,
                )
            )

            # Workers execute in parallel
            worker_context = {**context, "coordinator_output": coord_output}
            worker_tasks = [
                self._execute_agent_safe(worker, task, worker_context)
                for worker in workers
            ]

            worker_results = await asyncio.gather(*worker_tasks, return_exceptions=False)
            results.extend(worker_results)

        except Exception as e:
            self.logger.error(f"Hierarchical coordination failed: {e}")
            raise

        return results

    async def _coordinate_consensus(
        self,
        agents: List[Any],
        task: Optional[str],
        context: Dict[str, Any],
    ) -> List[AgentResult]:
        """
        Execute agents and reach consensus.

        Args:
            agents: List of agents
            task: Task to execute
            context: Context data

        Returns:
            List of agent results
        """
        # Execute all agents in parallel
        tasks = [
            self._execute_agent_safe(agent, task, context)
            for agent in agents
        ]

        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Analyze consensus
        outputs = [r.output for r in results if r.status == "completed"]
        if outputs:
            # Simple consensus: most common output
            from collections import Counter
            consensus = Counter(str(o) for o in outputs).most_common(1)[0][0]
            self.logger.info(f"Consensus reached: {consensus}")

        return results

    async def _execute_agent(
        self,
        agent: Any,
        task: Optional[str],
        context: Dict[str, Any],
    ) -> Any:
        """
        Execute a single agent.

        Args:
            agent: Agent to execute
            task: Task to execute
            context: Context data

        Returns:
            Agent output
        """
        # Execute via the real AgentLoop engine (惰性导入避免循环依赖)。
        from backend.app.dependencies import get_agent
        from backend.app.core.contracts import RunContext

        agent_id = ""
        if isinstance(agent, dict):
            agent_id = str(agent.get("agent_id", ""))
        else:
            agent_id = str(getattr(agent, "agent_id", "") or "")

        ctx_data = dict(context or {})
        run_context = RunContext(
            tenant_id=str(ctx_data.get("tenant_id", "default")),
            user_id=str(ctx_data.get("user_id", "system")),
            agent_id=agent_id or "coordinator-agent",
            request_id=str(ctx_data.get("request_id", agent_id or "coordinator")),
            trace_id=str(ctx_data.get("trace_id", agent_id or "coordinator")),
            permission_scope=list(ctx_data.get("permission_scope", []) or []),
        )

        agent_loop = get_agent()
        response = await agent_loop.run(run_context, task or "", ctx_data)

        status_value = getattr(getattr(response, "status", None), "value", None) or str(
            getattr(response, "status", "completed")
        )
        return {
            "status": status_value,
            "task": task,
            "answer": getattr(response, "answer", ""),
            "iterations": getattr(response, "iterations", 0),
            "trace_id": getattr(response, "trace_id", run_context.trace_id),
            "error": getattr(response, "error", None),
        }

    async def _execute_agent_safe(
        self,
        agent: Any,
        task: Optional[str],
        context: Dict[str, Any],
    ) -> AgentResult:
        """
        Execute a single agent safely.

        Args:
            agent: Agent to execute
            task: Task to execute
            context: Context data

        Returns:
            Agent result
        """
        try:
            output = await self._execute_agent(agent, task, context)
            return AgentResult(
                agent_id=getattr(agent, "agent_id", "unknown"),
                status="completed",
                output=output,
            )
        except Exception as e:
            return AgentResult(
                agent_id=getattr(agent, "agent_id", "unknown"),
                status="failed",
                error=str(e),
            )

    async def aggregate_results(
        self,
        results: List[AgentResult],
        strategy: AggregationStrategy = AggregationStrategy.ALL,
    ) -> Any:
        """
        Aggregate results from multiple agents.

        Args:
            results: List of agent results
            strategy: Aggregation strategy

        Returns:
            Aggregated output
        """
        if strategy == AggregationStrategy.FIRST:
            return results[0].output if results else None

        elif strategy == AggregationStrategy.LAST:
            return results[-1].output if results else None

        elif strategy == AggregationStrategy.ALL:
            return [r.output for r in results]

        elif strategy == AggregationStrategy.MAJORITY:
            from collections import Counter
            outputs = [r.output for r in results if r.status == "completed"]
            if outputs:
                return Counter(outputs).most_common(1)[0][0]
            return None

        else:
            return None

    def get_coordination_history(
        self,
        limit: int = 10,
    ) -> List[AggregatedResult]:
        """
        Get coordination history.

        Args:
            limit: Maximum number of records

        Returns:
            List of aggregated results
        """
        items = list(self.coordination_history.values())
        items.sort(key=lambda x: x.completed_at, reverse=True)
        return items[:limit]

    def get_coordination_stats(self) -> Dict[str, Any]:
        """
        Get coordination statistics.

        Returns:
            Statistics dict
        """
        total = len(self.coordination_history)
        strategies = {}

        for result in self.coordination_history.values():
            strategy = result.strategy.value
            strategies[strategy] = strategies.get(strategy, 0) + 1

        return {
            "total_coordinations": total,
            "strategy_breakdown": strategies,
        }


# Global instance
agent_coordinator = AgentCoordinator()
