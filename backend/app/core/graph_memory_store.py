"""Graph memory store using Neo4j for relationship management.

Features:
- Memory node creation and management
- Relationship management between memories
- Graph traversal and path finding
- Related memory expansion
- Knowledge graph queries
"""

from __future__ import annotations

import re
from typing import Any

from backend.app.core.hybrid_memory_system import Memory

# Whitelist of relationship types allowed in Cypher MERGE clauses.
# Relationship types cannot be parameterized in Cypher, so only these
# fixed identifiers may be interpolated into the query text.
ALLOWED_RELATION_TYPES: frozenset[str] = frozenset(
    {
        "related_to",
        "depends_on",
        "references",
        "supersedes",
        "part_of",
        "caused_by",
        "derived_from",
        "supports",
        "contradicts",
        "duplicates",
    }
)
_RELATION_TYPE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")


class GraphPath(Memory):
    """Represents a path through the memory graph."""

    path_length: int = 0
    path_nodes: list[str] = []


class GraphMemoryStore:
    """Neo4j-backed graph memory storage for relationships and knowledge graphs."""

    def __init__(
        self,
        neo4j_driver: Any | None = None,
        database: str = "neo4j",
    ) -> None:
        self.neo4j_driver = neo4j_driver
        self.database = database
        self._node_count = 0

    async def add_node(self, memory: Memory) -> str:
        """Add memory as node in graph.

        Args:
            memory: Memory to add

        Returns:
            Memory ID
        """
        if not self.neo4j_driver:
            return memory.id

        try:
            with self.neo4j_driver.session(database=self.database) as session:
                session.run(
                    """
                    MERGE (m:Memory {id: $id})
                    SET m.content = $content,
                        m.category = $category,
                        m.importance = $importance,
                        m.tags = $tags,
                        m.created_at = $created_at,
                        m.updated_at = $updated_at,
                        m.access_count = $access_count
                    RETURN m
                    """,
                    {
                        "id": memory.id,
                        "content": memory.content[:500],
                        "category": memory.category,
                        "importance": memory.importance,
                        "tags": memory.tags,
                        "created_at": memory.created_at.isoformat(),
                        "updated_at": memory.updated_at.isoformat(),
                        "access_count": memory.access_count,
                    },
                )
            self._node_count += 1
            return memory.id

        except Exception as e:
            raise RuntimeError(f"Failed to add node to graph: {e}")

    async def add_relation(
        self,
        from_id: str,
        to_id: str,
        relation: str,
    ) -> bool:
        """Add relationship between two memories.

        Args:
            from_id: Source memory ID
            to_id: Target memory ID
            relation: Relationship type

        Returns:
            Success status
        """
        if not self.neo4j_driver:
            return False

        # Cypher relationship types cannot be parameterized; enforce a strict
        # whitelist (plus identifier-shape check) before interpolation.
        if relation not in ALLOWED_RELATION_TYPES or not _RELATION_TYPE_RE.match(relation):
            raise ValueError(f"Unsupported relation type: {relation!r}")

        try:
            with self.neo4j_driver.session(database=self.database) as session:
                session.run(
                    f"""
                    MATCH (m1:Memory {{id: $from_id}}), (m2:Memory {{id: $to_id}})
                    MERGE (m1)-[r:{relation}]->(m2)
                    SET r.created_at = $created_at
                    RETURN r
                    """,
                    {
                        "from_id": from_id,
                        "to_id": to_id,
                        "created_at": self._now_iso(),
                    },
                )
            return True

        except Exception as e:
            raise RuntimeError(f"Failed to add relation: {e}")

    async def find_related(
        self,
        memory_id: str,
        depth: int = 2,
    ) -> list[Memory]:
        """Find related memories via graph traversal.

        Args:
            memory_id: Starting memory ID
            depth: Maximum traversal depth

        Returns:
            List of related memories
        """
        if not self.neo4j_driver:
            return []

        # Depth is interpolated into Cypher (variable-length bounds cannot be
        # parameterized); coerce to a bounded int so it is always a literal.
        depth = min(max(int(depth), 1), 5)

        try:
            with self.neo4j_driver.session(database=self.database) as session:
                result = session.run(
                    f"""
                    MATCH (m:Memory {{id: $id}})-[*1..{depth}]-(related:Memory)
                    RETURN DISTINCT related
                    ORDER BY related.importance DESC
                    LIMIT 20
                    """,
                    {"id": memory_id},
                )

                memories: list[Memory] = []
                for record in result:
                    node = record["related"]
                    memory = self._node_to_memory(node)
                    if memory:
                        memories.append(memory)

                return memories

        except Exception as e:
            raise RuntimeError(f"Failed to find related memories: {e}")

    async def find_path(
        self,
        from_id: str,
        to_id: str,
    ) -> list[GraphPath]:
        """Find paths between two memories.

        Args:
            from_id: Source memory ID
            to_id: Target memory ID

        Returns:
            List of paths
        """
        if not self.neo4j_driver:
            return []

        try:
            with self.neo4j_driver.session(database=self.database) as session:
                result = session.run(
                    """
                    MATCH path = shortestPath(
                        (m1:Memory {id: $from_id})-[*]-(m2:Memory {id: $to_id})
                    )
                    RETURN path
                    LIMIT 5
                    """,
                    {"from_id": from_id, "to_id": to_id},
                )

                paths: list[GraphPath] = []
                for record in result:
                    path = record["path"]
                    graph_path = self._path_to_graph_path(path)
                    if graph_path:
                        paths.append(graph_path)

                return paths

        except Exception as e:
            raise RuntimeError(f"Failed to find path: {e}")

    async def get_node(self, memory_id: str) -> Memory | None:
        """Get memory node from graph.

        Args:
            memory_id: Memory ID

        Returns:
            Memory object or None
        """
        if not self.neo4j_driver:
            return None

        try:
            with self.neo4j_driver.session(database=self.database) as session:
                result = session.run(
                    "MATCH (m:Memory {id: $id}) RETURN m",
                    {"id": memory_id},
                )

                record = result.single()
                if record:
                    return self._node_to_memory(record["m"])

                return None

        except Exception:
            return None

    async def delete_node(self, memory_id: str) -> bool:
        """Delete memory node from graph.

        Args:
            memory_id: Memory ID to delete

        Returns:
            Success status
        """
        if not self.neo4j_driver:
            return False

        try:
            with self.neo4j_driver.session(database=self.database) as session:
                session.run(
                    "MATCH (m:Memory {id: $id}) DETACH DELETE m",
                    {"id": memory_id},
                )
            self._node_count = max(0, self._node_count - 1)
            return True

        except Exception as e:
            raise RuntimeError(f"Failed to delete node: {e}")

    async def count(self) -> int:
        """Get total node count in graph.

        Returns:
            Number of memory nodes
        """
        if not self.neo4j_driver:
            return 0

        try:
            with self.neo4j_driver.session(database=self.database) as session:
                result = session.run("MATCH (m:Memory) RETURN count(m) as count")
                record = result.single()
                if record:
                    return record["count"]
                return 0

        except Exception:
            return self._node_count

    async def get_stats(self) -> dict[str, Any]:
        """Get graph statistics.

        Returns:
            Statistics dictionary
        """
        if not self.neo4j_driver:
            return {}

        try:
            with self.neo4j_driver.session(database=self.database) as session:
                # Node count
                node_result = session.run("MATCH (m:Memory) RETURN count(m) as count")
                node_count = node_result.single()["count"] if node_result.single() else 0

                # Relationship count
                rel_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
                rel_count = rel_result.single()["count"] if rel_result.single() else 0

                # Average importance
                avg_result = session.run(
                    "MATCH (m:Memory) RETURN avg(m.importance) as avg"
                )
                avg_importance = avg_result.single()["avg"] if avg_result.single() else 0

                return {
                    "node_count": node_count,
                    "relationship_count": rel_count,
                    "avg_importance": avg_importance,
                    "timestamp": self._now_iso(),
                }

        except Exception:
            return {}

    def _node_to_memory(self, node: Any) -> Memory | None:
        """Convert Neo4j node to Memory object.

        Args:
            node: Neo4j node

        Returns:
            Memory object or None
        """
        try:
            from datetime import UTC, datetime

            props = dict(node)
            return Memory(
                id=props.get("id", ""),
                content=props.get("content", ""),
                category=props.get("category", "reference"),
                importance=float(props.get("importance", 0.5)),
                tier="graph",
                tags=props.get("tags", []),
                created_at=self._parse_datetime(props.get("created_at")),
                updated_at=self._parse_datetime(props.get("updated_at")),
                access_count=int(props.get("access_count", 0)),
            )

        except Exception:
            return None

    def _path_to_graph_path(self, path: Any) -> GraphPath | None:
        """Convert Neo4j path to GraphPath object.

        Args:
            path: Neo4j path

        Returns:
            GraphPath object or None
        """
        try:
            from datetime import UTC, datetime

            nodes = path.nodes
            if not nodes:
                return None

            start_node = nodes[0]
            props = dict(start_node)

            path_nodes = [dict(node).get("id", "") for node in nodes]

            return GraphPath(
                id=props.get("id", ""),
                content=props.get("content", ""),
                category=props.get("category", "reference"),
                importance=float(props.get("importance", 0.5)),
                tier="graph",
                tags=props.get("tags", []),
                created_at=self._parse_datetime(props.get("created_at")),
                updated_at=self._parse_datetime(props.get("updated_at")),
                path_length=len(nodes),
                path_nodes=path_nodes,
            )

        except Exception:
            return None

    @staticmethod
    def _parse_datetime(datetime_str: str | None) -> Any:
        """Parse ISO datetime string.

        Args:
            datetime_str: ISO format datetime string

        Returns:
            Datetime object or current time
        """
        if not datetime_str:
            from datetime import UTC, datetime
            return datetime.now(UTC)

        try:
            from datetime import datetime
            return datetime.fromisoformat(datetime_str)
        except (ValueError, TypeError):
            from datetime import UTC, datetime
            return datetime.now(UTC)

    @staticmethod
    def _now_iso() -> str:
        """Get current time in ISO format."""
        from datetime import UTC, datetime
        return datetime.now(UTC).isoformat()
