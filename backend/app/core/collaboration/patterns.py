"""Collaboration patterns for different multi-agent scenarios."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class PatternContext:
    """Context for pattern execution."""

    pattern_id: str
    agents: dict[str, Any]
    initial_data: Any
    result: Any = None
    error: Optional[str] = None


class CollaborationPattern(ABC):
    """Base class for collaboration patterns."""

    @abstractmethod
    async def execute(self, context: PatternContext) -> Any:
        """Execute the pattern.

        Args:
            context: Pattern execution context

        Returns:
            Final result
        """
        raise NotImplementedError


class PipelinePattern(CollaborationPattern):
    """Pipeline pattern: sequential execution through agents.

    Each agent processes output of previous agent.
    """

    def __init__(self, agent_sequence: list[str]) -> None:
        """Initialize pipeline pattern.

        Args:
            agent_sequence: Ordered list of agent IDs
        """
        self.agent_sequence = agent_sequence

    async def execute(self, context: PatternContext) -> Any:
        """Execute pipeline pattern."""
        current_data = context.initial_data

        for agent_id in self.agent_sequence:
            if agent_id not in context.agents:
                logger.warning(f"Agent {agent_id} not found in context")
                continue

            agent = context.agents[agent_id]
            logger.info(f"Pipeline: executing agent {agent_id}")

            try:
                current_data = await agent.process(current_data)
            except Exception as e:
                context.error = str(e)
                logger.error(f"Pipeline error in agent {agent_id}: {e}")
                raise

        context.result = current_data
        return current_data


class MapReducePattern(CollaborationPattern):
    """MapReduce pattern: parallel execution with result aggregation.

    Map phase: distribute work to agents
    Reduce phase: aggregate results
    """

    def __init__(
        self,
        map_agents: list[str],
        reducer: Optional[Callable] = None,
    ) -> None:
        """Initialize MapReduce pattern.

        Args:
            map_agents: List of agent IDs for map phase
            reducer: Custom reducer function
        """
        self.map_agents = map_agents
        self.reducer = reducer

    async def execute(self, context: PatternContext) -> Any:
        """Execute MapReduce pattern."""
        # Map phase: distribute work
        tasks = []
        for agent_id in self.map_agents:
            if agent_id not in context.agents:
                logger.warning(f"Agent {agent_id} not found in context")
                continue

            agent = context.agents[agent_id]
            logger.info(f"MapReduce: mapping to agent {agent_id}")
            tasks.append(agent.process(context.initial_data))

        # Execute all map tasks in parallel
        try:
            map_results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            context.error = str(e)
            logger.error(f"MapReduce error during map phase: {e}")
            raise

        # Reduce phase: aggregate results
        if self.reducer:
            try:
                context.result = await self.reducer(map_results)
            except Exception as e:
                context.error = str(e)
                logger.error(f"MapReduce error during reduce phase: {e}")
                raise
        else:
            context.result = self._default_reduce(map_results)

        return context.result

    def _default_reduce(self, results: list[Any]) -> Any:
        """Default reduce function: merge results."""
        merged = {}
        for i, result in enumerate(results):
            if isinstance(result, dict):
                merged.update(result)
            else:
                merged[f"result_{i}"] = result
        return merged


class MasterWorkerPattern(CollaborationPattern):
    """Master-Worker pattern: master coordinates worker agents.

    Master distributes tasks and collects results from workers.
    """

    def __init__(
        self,
        master_agent_id: str,
        worker_agent_ids: list[str],
    ) -> None:
        """Initialize Master-Worker pattern.

        Args:
            master_agent_id: ID of master agent
            worker_agent_ids: List of worker agent IDs
        """
        self.master_agent_id = master_agent_id
        self.worker_agent_ids = worker_agent_ids

    async def execute(self, context: PatternContext) -> Any:
        """Execute Master-Worker pattern."""
        if self.master_agent_id not in context.agents:
            raise ValueError(f"Master agent {self.master_agent_id} not found")

        master = context.agents[self.master_agent_id]
        logger.info(f"MasterWorker: master agent {self.master_agent_id} starting")

        try:
            # Master decomposes task
            subtasks = await master.decompose(context.initial_data)
        except Exception as e:
            context.error = str(e)
            logger.error(f"MasterWorker error during decomposition: {e}")
            raise

        # Distribute to workers
        worker_tasks = []
        for i, worker_id in enumerate(self.worker_agent_ids):
            if worker_id not in context.agents:
                logger.warning(f"Worker {worker_id} not found in context")
                continue

            worker = context.agents[worker_id]
            subtask = subtasks[i] if i < len(subtasks) else subtasks[-1]
            logger.info(f"MasterWorker: assigning subtask to worker {worker_id}")
            worker_tasks.append(worker.process(subtask))

        # Collect results
        try:
            worker_results = await asyncio.gather(*worker_tasks, return_exceptions=True)
        except Exception as e:
            context.error = str(e)
            logger.error(f"MasterWorker error during worker execution: {e}")
            raise

        # Master aggregates results
        try:
            context.result = await master.aggregate(worker_results)
        except Exception as e:
            context.error = str(e)
            logger.error(f"MasterWorker error during aggregation: {e}")
            raise

        return context.result


class PeerToPeerPattern(CollaborationPattern):
    """Peer-to-Peer pattern: agents collaborate as equals.

    Each agent can communicate with any other agent.
    """

    def __init__(self, agent_ids: list[str]) -> None:
        """Initialize P2P pattern.

        Args:
            agent_ids: List of peer agent IDs
        """
        self.agent_ids = agent_ids

    async def execute(self, context: PatternContext) -> Any:
        """Execute P2P pattern."""
        logger.info(f"P2P: starting collaboration with {len(self.agent_ids)} peers")

        # Initialize all peers
        peer_tasks = []
        for agent_id in self.agent_ids:
            if agent_id not in context.agents:
                logger.warning(f"Peer {agent_id} not found in context")
                continue

            agent = context.agents[agent_id]
            logger.info(f"P2P: initializing peer {agent_id}")
            peer_tasks.append(agent.collaborate(context.initial_data, self.agent_ids))

        # Execute all peers in parallel
        try:
            peer_results = await asyncio.gather(*peer_tasks, return_exceptions=True)
        except Exception as e:
            context.error = str(e)
            logger.error(f"P2P error during collaboration: {e}")
            raise

        # Aggregate peer results
        context.result = self._aggregate_peer_results(peer_results)
        return context.result

    def _aggregate_peer_results(self, results: list[Any]) -> Any:
        """Aggregate results from all peers."""
        merged = {}
        for i, result in enumerate(results):
            if isinstance(result, dict):
                merged.update(result)
            else:
                merged[f"peer_{i}"] = result
        return merged


class HierarchicalPattern(CollaborationPattern):
    """Hierarchical pattern: tree-structured agent collaboration.

    Parent agents coordinate child agents.
    """

    def __init__(self, hierarchy: dict[str, list[str]]) -> None:
        """Initialize hierarchical pattern.

        Args:
            hierarchy: Dict mapping parent agent IDs to lists of child agent IDs
        """
        self.hierarchy = hierarchy

    async def execute(self, context: PatternContext) -> Any:
        """Execute hierarchical pattern."""
        logger.info(f"Hierarchical: starting with {len(self.hierarchy)} parent agents")

        # Find root agents (those not in any child list)
        all_children = set()
        for children in self.hierarchy.values():
            all_children.update(children)

        root_agents = [aid for aid in self.hierarchy.keys() if aid not in all_children]

        # Execute from roots
        root_tasks = []
        for root_id in root_agents:
            root_tasks.append(self._execute_node(root_id, context))

        try:
            results = await asyncio.gather(*root_tasks, return_exceptions=True)
        except Exception as e:
            context.error = str(e)
            logger.error(f"Hierarchical error: {e}")
            raise

        context.result = self._aggregate_hierarchical_results(results)
        return context.result

    async def _execute_node(self, agent_id: str, context: PatternContext) -> Any:
        """Execute a node and its children."""
        if agent_id not in context.agents:
            return None

        agent = context.agents[agent_id]
        children = self.hierarchy.get(agent_id, [])

        # Execute children in parallel
        child_tasks = [self._execute_node(child_id, context) for child_id in children]
        child_results = await asyncio.gather(*child_tasks, return_exceptions=True)

        # Execute parent with child results
        logger.info(f"Hierarchical: executing agent {agent_id} with {len(child_results)} child results")
        return await agent.process_with_children(context.initial_data, child_results)

    def _aggregate_hierarchical_results(self, results: list[Any]) -> Any:
        """Aggregate hierarchical results."""
        merged = {}
        for i, result in enumerate(results):
            if isinstance(result, dict):
                merged.update(result)
            else:
                merged[f"root_{i}"] = result
        return merged
