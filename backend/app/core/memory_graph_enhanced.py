"""
Enhanced memory graph module for X-Agent.

Implements advanced graph-based memory relationships, reasoning,
and path tracing capabilities using Neo4j.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MemoryNode:
    """Represents a node in the memory graph."""

    id: str
    content: str
    node_type: str = "memory"
    created_at: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class MemoryRelation:
    """Represents a relationship between memory nodes."""

    source_id: str
    target_id: str
    relation_type: str
    strength: float = 1.0
    metadata: dict = field(default_factory=dict)


@dataclass
class MemoryPath:
    """Represents a path through the memory graph."""

    path_nodes: list[str]
    path_relations: list[MemoryRelation]
    total_strength: float
    path_length: int


class EnhancedMemoryGraph:
    """
    Enhanced memory graph with relationship reasoning and path tracing.

    Manages memory nodes and relationships, supports advanced queries
    like finding related memories and tracing memory paths.
    """

    def __init__(self, max_path_length: int = 5):
        """
        Initialize the enhanced memory graph.

        Args:
            max_path_length: Maximum length of paths to trace
        """
        self.max_path_length = max_path_length
        self.nodes: dict[str, MemoryNode] = {}
        self.relations: dict[str, list[MemoryRelation]] = defaultdict(list)
        self.reverse_relations: dict[str, list[MemoryRelation]] = defaultdict(list)
        self.logger = logger

    def add_node(self, node: MemoryNode) -> None:
        """Add a memory node to the graph."""
        self.nodes[node.id] = node
        self.logger.debug(f"Added node: {node.id}")

    def add_relation(self, relation: MemoryRelation) -> None:
        """Add a relationship between two memory nodes."""
        if relation.source_id not in self.nodes or relation.target_id not in self.nodes:
            self.logger.warning(
                f"Cannot add relation: nodes not found "
                f"({relation.source_id}, {relation.target_id})"
            )
            return

        self.relations[relation.source_id].append(relation)
        self.reverse_relations[relation.target_id].append(relation)
        self.logger.debug(
            f"Added relation: {relation.source_id} -> {relation.target_id} "
            f"({relation.relation_type})"
        )

    def find_related_memories(
        self,
        memory_id: str,
        depth: int = 2,
        relation_types: list[str] | None = None,
        limit: int = 20,
    ) -> list[tuple[str, float]]:
        """
        Find memories related to a given memory.

        Args:
            memory_id: ID of the source memory
            depth: Maximum depth to search
            relation_types: Filter by specific relation types
            limit: Maximum number of results

        Returns:
            List of (memory_id, relevance_score) tuples
        """
        if memory_id not in self.nodes:
            self.logger.warning(f"Memory not found: {memory_id}")
            return []

        visited = set()
        related = {}
        queue = deque([(memory_id, 0, 1.0)])  # (node_id, current_depth, strength)

        while queue:
            current_id, current_depth, current_strength = queue.popleft()

            if current_id in visited or current_depth >= depth:
                continue

            visited.add(current_id)

            # Get outgoing relations
            for relation in self.relations.get(current_id, []):
                if relation_types and relation.relation_type not in relation_types:
                    continue

                target_id = relation.target_id
                if target_id == memory_id:
                    continue

                # Calculate cumulative strength
                cumulative_strength = current_strength * relation.strength

                if target_id not in related or related[target_id] < cumulative_strength:
                    related[target_id] = cumulative_strength

                # Add to queue for further exploration
                if current_depth + 1 < depth:
                    queue.append((target_id, current_depth + 1, cumulative_strength))

        # Sort by strength and return top results
        sorted_related = sorted(related.items(), key=lambda x: x[1], reverse=True)
        return sorted_related[:limit]

    def trace_memory_path(
        self,
        source_id: str,
        target_id: str,
        relation_types: list[str] | None = None,
    ) -> MemoryPath | None:
        """
        Trace a path between two memories.

        Args:
            source_id: ID of source memory
            target_id: ID of target memory
            relation_types: Filter by specific relation types

        Returns:
            MemoryPath if path exists, None otherwise
        """
        if source_id not in self.nodes or target_id not in self.nodes:
            self.logger.warning("Source or target memory not found")
            return None

        # BFS to find shortest path
        queue = deque([(source_id, [source_id], [], 1.0)])
        visited = set()

        while queue:
            current_id, path_nodes, path_relations, total_strength = queue.popleft()

            if current_id in visited:
                continue

            visited.add(current_id)

            if current_id == target_id:
                return MemoryPath(
                    path_nodes=path_nodes,
                    path_relations=path_relations,
                    total_strength=total_strength,
                    path_length=len(path_nodes) - 1,
                )

            if len(path_nodes) >= self.max_path_length:
                continue

            # Explore neighbors
            for relation in self.relations.get(current_id, []):
                if relation_types and relation.relation_type not in relation_types:
                    continue

                next_id = relation.target_id
                if next_id not in visited:
                    new_strength = total_strength * relation.strength
                    queue.append(
                        (
                            next_id,
                            [*path_nodes, next_id],
                            [*path_relations, relation],
                            new_strength,
                        )
                    )

        return None

    def get_memory_context(
        self,
        memory_id: str,
        context_depth: int = 2,
    ) -> dict:
        """
        Get rich context for a memory including related memories and paths.

        Args:
            memory_id: ID of the memory
            context_depth: Depth of context to retrieve

        Returns:
            Dictionary containing memory context
        """
        if memory_id not in self.nodes:
            return {}

        node = self.nodes[memory_id]
        related = self.find_related_memories(memory_id, depth=context_depth)

        # Get incoming relations
        incoming = self.reverse_relations.get(memory_id, [])
        outgoing = self.relations.get(memory_id, [])

        return {
            "memory": {
                "id": node.id,
                "content": node.content,
                "type": node.node_type,
                "metadata": node.metadata,
            },
            "related_memories": related,
            "incoming_relations": [
                {
                    "source_id": r.source_id,
                    "relation_type": r.relation_type,
                    "strength": r.strength,
                }
                for r in incoming
            ],
            "outgoing_relations": [
                {
                    "target_id": r.target_id,
                    "relation_type": r.relation_type,
                    "strength": r.strength,
                }
                for r in outgoing
            ],
        }

    def infer_relations(
        self,
        memory_id: str,
        similarity_threshold: float = 0.7,
    ) -> list[MemoryRelation]:
        """
        Infer new relations for a memory based on content similarity.

        Args:
            memory_id: ID of the memory
            similarity_threshold: Minimum similarity to create relation

        Returns:
            List of inferred relations
        """
        if memory_id not in self.nodes:
            return []

        source_node = self.nodes[memory_id]
        inferred = []

        for target_id, target_node in self.nodes.items():
            if target_id == memory_id:
                continue

            # Calculate similarity (simplified)
            similarity = self._calculate_similarity(
                source_node.content,
                target_node.content,
            )

            if similarity >= similarity_threshold:
                relation = MemoryRelation(
                    source_id=memory_id,
                    target_id=target_id,
                    relation_type="inferred_similarity",
                    strength=similarity,
                )
                inferred.append(relation)

        return inferred

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (simplified)."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def get_graph_stats(self) -> dict:
        """Get statistics about the memory graph."""
        total_relations = sum(len(rels) for rels in self.relations.values())

        return {
            "total_nodes": len(self.nodes),
            "total_relations": total_relations,
            "avg_relations_per_node": (
                total_relations / len(self.nodes) if self.nodes else 0
            ),
            "relation_types": self._get_relation_types(),
        }

    def _get_relation_types(self) -> dict[str, int]:
        """Get count of each relation type."""
        type_counts = defaultdict(int)
        for relations in self.relations.values():
            for relation in relations:
                type_counts[relation.relation_type] += 1

        return dict(type_counts)

    def export_graph(self) -> dict:
        """Export graph as dictionary for serialization."""
        return {
            "nodes": [
                {
                    "id": node.id,
                    "content": node.content,
                    "type": node.node_type,
                    "metadata": node.metadata,
                }
                for node in self.nodes.values()
            ],
            "relations": [
                {
                    "source_id": rel.source_id,
                    "target_id": rel.target_id,
                    "type": rel.relation_type,
                    "strength": rel.strength,
                    "metadata": rel.metadata,
                }
                for rels in self.relations.values()
                for rel in rels
            ],
        }

    def import_graph(self, graph_data: dict) -> None:
        """Import graph from dictionary."""
        # Clear existing graph
        self.nodes.clear()
        self.relations.clear()
        self.reverse_relations.clear()

        # Import nodes
        for node_data in graph_data.get("nodes", []):
            node = MemoryNode(
                id=node_data["id"],
                content=node_data["content"],
                node_type=node_data.get("type", "memory"),
                metadata=node_data.get("metadata", {}),
            )
            self.add_node(node)

        # Import relations
        for rel_data in graph_data.get("relations", []):
            relation = MemoryRelation(
                source_id=rel_data["source_id"],
                target_id=rel_data["target_id"],
                relation_type=rel_data["type"],
                strength=rel_data.get("strength", 1.0),
                metadata=rel_data.get("metadata", {}),
            )
            self.add_relation(relation)


# Global instance
enhanced_memory_graph = EnhancedMemoryGraph()
