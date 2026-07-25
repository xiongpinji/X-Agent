"""Neo4j Graph Memory — async knowledge-graph tier for X-Agent memory system.

Provides entity/relation storage, LLM-based relation extraction, and graph
neighbourhood search backed by a Neo4j database. When ``neo4j_enabled=False``
all methods degrade honestly: they return empty results and emit a debug log.

Dependency: ``neo4j>=5.0.0`` (declared in pyproject.toml / requirements.txt).
Uses the **async** driver API (``neo4j.AsyncGraphDatabase``).
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency guard
# ---------------------------------------------------------------------------
try:
    from neo4j import AsyncGraphDatabase  # type: ignore[import-untyped]

    NEO4J_ASYNC_AVAILABLE = True
except ImportError:  # pragma: no cover
    AsyncGraphDatabase = None  # type: ignore[assignment,misc]
    NEO4J_ASYNC_AVAILABLE = False


class Neo4jGraphMemory:
    """Async Neo4j-backed graph memory for entity/relation knowledge graphs.

    Usage::

        graph_mem = Neo4jGraphMemory(
            url="bolt://localhost:7687",
            user="neo4j",
            password="secret",
            enabled=True,
        )
        await graph_mem.connect()
        await graph_mem.store_entity("Python", "language", {"paradigm": "multi"})
        await graph_mem.close()

    When *enabled* is ``False`` (default), every public method returns an
    empty/no-op result with a debug-level log — honest degradation.
    """

    def __init__(
        self,
        url: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "",
        database: str = "neo4j",
        enabled: bool = False,
    ) -> None:
        self._url = url
        self._user = user
        self._password = password
        self._database = database
        self._enabled = enabled
        self._driver: Any = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Establish async connection to Neo4j (no-op when disabled)."""
        if not self._enabled:
            logger.debug("Neo4jGraphMemory: disabled — skipping connection.")
            return

        if not NEO4J_ASYNC_AVAILABLE:
            logger.warning(
                "Neo4jGraphMemory: neo4j package not installed; "
                "graph memory tier unavailable. Install with: pip install neo4j"
            )
            self._enabled = False
            return

        try:
            self._driver = AsyncGraphDatabase.driver(
                self._url,
                auth=(self._user, self._password),
            )
            # Verify connectivity
            await self._driver.verify_connectivity()
            logger.info("Neo4jGraphMemory: connected to %s", self._url)
        except Exception as exc:
            logger.warning(
                "Neo4jGraphMemory: connection failed (%s); degrading to no-op mode.",
                exc,
            )
            self._driver = None
            self._enabled = False

    async def close(self) -> None:
        """Close the Neo4j driver gracefully."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            logger.debug("Neo4jGraphMemory: connection closed.")

    @property
    def available(self) -> bool:
        """True when a live Neo4j driver is backing this instance."""
        return self._enabled and self._driver is not None

    # ------------------------------------------------------------------
    # Entity / Relation storage
    # ------------------------------------------------------------------

    async def store_entity(
        self,
        entity: str,
        entity_type: str,
        properties: dict | None = None,
    ) -> bool:
        """Store (MERGE) an entity node in the knowledge graph.

        Args:
            entity: Entity name/label (e.g. "Python", "FastAPI").
            entity_type: Node label category (e.g. "language", "framework").
            properties: Additional node properties.

        Returns:
            True if stored successfully, False otherwise.
        """
        if not self.available:
            logger.debug("store_entity: neo4j disabled — no-op for entity=%r", entity)
            return False

        props = properties or {}
        try:
            async with self._driver.session(database=self._database) as session:
                await session.run(
                    """
                    MERGE (e:Entity {name: $name, entity_type: $entity_type})
                    SET e += $props, e.updated_at = datetime()
                    RETURN e
                    """,
                    name=entity,
                    entity_type=entity_type,
                    props=props,
                )
            logger.debug("store_entity: stored %r (%s)", entity, entity_type)
            return True
        except Exception as exc:
            logger.error("store_entity failed for %r: %s", entity, exc)
            return False

    async def store_relation(
        self,
        source: str,
        relation: str,
        target: str,
        properties: dict | None = None,
    ) -> bool:
        """Store a relationship between two entity nodes.

        Creates the relationship using a dynamic type derived from *relation*
        (sanitised to a valid Cypher identifier).

        Args:
            source: Source entity name.
            relation: Relationship type (e.g. "uses", "depends_on").
            target: Target entity name.
            properties: Additional relationship properties.

        Returns:
            True if stored successfully, False otherwise.
        """
        if not self.available:
            logger.debug(
                "store_relation: neo4j disabled — no-op for %r-[%s]->%r",
                source, relation, target,
            )
            return False

        # Sanitise relation type to a valid Cypher identifier
        safe_relation = self._sanitize_relation_type(relation)
        props = properties or {}

        try:
            async with self._driver.session(database=self._database) as session:
                await session.run(
                    f"""
                    MATCH (a:Entity {{name: $source}})
                    MATCH (b:Entity {{name: $target}})
                    MERGE (a)-[r:{safe_relation}]->(b)
                    SET r += $props, r.updated_at = datetime()
                    RETURN r
                    """,
                    source=source,
                    target=target,
                    props=props,
                )
            logger.debug("store_relation: %r -[%s]-> %r", source, safe_relation, target)
            return True
        except Exception as exc:
            logger.error(
                "store_relation failed for %r->%r: %s", source, target, exc
            )
            return False

    # ------------------------------------------------------------------
    # LLM-based relation extraction
    # ------------------------------------------------------------------

    async def extract_relations(self, text: str) -> list[tuple]:
        """Extract entity relations from text using LLM.

        Attempts to use the project's LLM backend to extract
        (subject, relation, object) triples from the given text.
        Falls back to a simple regex heuristic when LLM is unavailable.

        Args:
            text: Input text to extract relations from.

        Returns:
            List of (subject, relation, object) tuples.
        """
        if not self._enabled:
            logger.debug("extract_relations: neo4j disabled — returning empty.")
            return []

        # Try LLM-based extraction
        try:
            triples = await self._llm_extract(text)
            if triples:
                return triples
        except Exception as exc:
            logger.debug("LLM extraction failed (%s); using heuristic fallback.", exc)

        # Heuristic fallback: simple pattern matching
        return self._heuristic_extract(text)

    async def _llm_extract(self, text: str) -> list[tuple]:
        """Use the project LLM backend to extract relation triples."""
        try:
            from backend.app.core.llm import build_llm_router
            from backend.app.settings import get_settings

            settings = get_settings()
            router = build_llm_router(
                llm_backend=settings.llm_backend,
                fallback_order=getattr(settings, "llm_fallback_order", ""),
            )
        except Exception:
            return []

        if router is None:
            return []

        prompt = (
            "Extract entity relationships from the following text. "
            "Return ONLY a JSON array of [subject, relation, object] triples. "
            'Example: [["Python", "is_a", "language"], ["FastAPI", "uses", "Python"]]\n\n'
            f"Text:\n{text[:2000]}"
        )

        try:
            response = await router.chat(
                messages=[{"role": "user", "content": prompt}],
                tools=[],
            )
            content = getattr(response, "content", "") or ""
            # Parse JSON array from response
            content = content.strip()
            if content.startswith("```"):
                # Strip markdown code fences
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
            triples_raw = json.loads(content)
            return [
                (str(t[0]), str(t[1]), str(t[2]))
                for t in triples_raw
                if isinstance(t, (list, tuple)) and len(t) >= 3
            ]
        except Exception as exc:
            logger.debug("_llm_extract parse error: %s", exc)
            return []

    @staticmethod
    def _heuristic_extract(text: str) -> list[tuple]:
        """Simple regex-based relation extraction as fallback."""
        import re

        triples: list[tuple] = []
        # Pattern: "X is/uses/depends on/requires Y"
        patterns = [
            (r"(\w[\w\s]{0,30}?)\s+(?:is a|is an|is)\s+(\w[\w\s]{0,30})", "is_a"),
            (r"(\w[\w\s]{0,30}?)\s+(?:uses|utilizes|leverages)\s+(\w[\w\s]{0,30})", "uses"),
            (r"(\w[\w\s]{0,30}?)\s+(?:depends on|requires)\s+(\w[\w\s]{0,30})", "depends_on"),
            (r"(\w[\w\s]{0,30}?)\s+(?:contains|includes|has)\s+(\w[\w\s]{0,30})", "contains"),
        ]
        for pattern, relation in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                subj = match.group(1).strip()
                obj = match.group(2).strip()
                if subj and obj and len(subj) > 1 and len(obj) > 1:
                    triples.append((subj, relation, obj))
        return triples[:20]  # Cap results

    # ------------------------------------------------------------------
    # Graph search
    # ------------------------------------------------------------------

    async def graph_search(self, query: str, depth: int = 2) -> list[dict]:
        """Search the graph neighbourhood around entities matching *query*.

        Finds entity nodes whose name contains the query string, then
        expands outward up to *depth* hops collecting neighbours.

        Args:
            query: Search string to match entity names.
            depth: Maximum traversal depth (1-5).

        Returns:
            List of dicts with entity info and relationship context.
        """
        if not self.available:
            logger.debug("graph_search: neo4j disabled — returning empty.")
            return []

        depth = min(max(int(depth), 1), 5)

        try:
            async with self._driver.session(database=self._database) as session:
                result = await session.run(
                    f"""
                    MATCH (e:Entity)
                    WHERE toLower(e.name) CONTAINS toLower($query)
                    MATCH path = (e)-[*1..{depth}]-(related:Entity)
                    RETURN DISTINCT related.name AS name,
                           related.entity_type AS entity_type,
                           length(path) AS distance,
                           properties(related) AS props
                    ORDER BY distance ASC
                    LIMIT 50
                    """,
                    query=query,
                )
                records = await result.data()
                return [
                    {
                        "name": rec.get("name", ""),
                        "entity_type": rec.get("entity_type", ""),
                        "distance": rec.get("distance", 0),
                        "properties": rec.get("props", {}),
                    }
                    for rec in records
                ]
        except Exception as exc:
            logger.error("graph_search failed for query=%r: %s", query, exc)
            return []

    async def get_related_memories(self, memory_id: str) -> list[dict]:
        """Find memories related to *memory_id* via the knowledge graph.

        Looks up a Memory node by id, then traverses entity links to find
        other Memory nodes sharing entities.

        Args:
            memory_id: The memory ID to find relations for.

        Returns:
            List of dicts describing related memories.
        """
        if not self.available:
            logger.debug("get_related_memories: neo4j disabled — returning empty.")
            return []

        try:
            async with self._driver.session(database=self._database) as session:
                result = await session.run(
                    """
                    MATCH (m:Memory {id: $memory_id})-[:MENTIONS]->(e:Entity)
                    MATCH (e)<-[:MENTIONS]-(other:Memory)
                    WHERE other.id <> $memory_id
                    RETURN DISTINCT other.id AS memory_id,
                           other.content AS content,
                           other.category AS category,
                           collect(DISTINCT e.name) AS shared_entities
                    LIMIT 20
                    """,
                    memory_id=memory_id,
                )
                records = await result.data()
                return [
                    {
                        "memory_id": rec.get("memory_id", ""),
                        "content": rec.get("content", ""),
                        "category": rec.get("category", ""),
                        "shared_entities": rec.get("shared_entities", []),
                    }
                    for rec in records
                ]
        except Exception as exc:
            logger.error("get_related_memories failed for %r: %s", memory_id, exc)
            return []

    # ------------------------------------------------------------------
    # Memory-to-graph linking (used during memory store)
    # ------------------------------------------------------------------

    async def index_memory(
        self,
        memory_id: str,
        content: str,
        category: str = "reference",
    ) -> int:
        """Extract entities/relations from memory content and index in graph.

        Creates a Memory node, extracts entity triples via LLM/heuristic,
        stores entities, and links them to the memory with MENTIONS edges.

        Args:
            memory_id: Unique memory identifier.
            content: Memory text content.
            category: Memory category label.

        Returns:
            Number of entity relations indexed.
        """
        if not self.available:
            logger.debug("index_memory: neo4j disabled — skipping for %r", memory_id)
            return 0

        try:
            # 1. Create/update the Memory node
            async with self._driver.session(database=self._database) as session:
                await session.run(
                    """
                    MERGE (m:Memory {id: $memory_id})
                    SET m.content = $content,
                        m.category = $category,
                        m.updated_at = datetime()
                    RETURN m
                    """,
                    memory_id=memory_id,
                    content=content[:1000],
                    category=category,
                )

            # 2. Extract relations
            triples = await self.extract_relations(content)
            if not triples:
                return 0

            # 3. Store entities and link to memory
            indexed = 0
            async with self._driver.session(database=self._database) as session:
                for subject, relation, obj in triples:
                    # Store entities
                    await session.run(
                        """
                        MERGE (e:Entity {name: $name, entity_type: "extracted"})
                        SET e.updated_at = datetime()
                        """,
                        name=subject,
                    )
                    await session.run(
                        """
                        MERGE (e:Entity {name: $name, entity_type: "extracted"})
                        SET e.updated_at = datetime()
                        """,
                        name=obj,
                    )
                    # Link memory -> entity
                    await session.run(
                        """
                        MATCH (m:Memory {id: $memory_id})
                        MATCH (e:Entity {name: $name})
                        MERGE (m)-[:MENTIONS]->(e)
                        """,
                        memory_id=memory_id,
                        name=subject,
                    )
                    await session.run(
                        """
                        MATCH (m:Memory {id: $memory_id})
                        MATCH (e:Entity {name: $name})
                        MERGE (m)-[:MENTIONS]->(e)
                        """,
                        memory_id=memory_id,
                        name=obj,
                    )
                    # Store entity-to-entity relation
                    safe_rel = self._sanitize_relation_type(relation)
                    await session.run(
                        f"""
                        MATCH (a:Entity {{name: $source}})
                        MATCH (b:Entity {{name: $target}})
                        MERGE (a)-[r:{safe_rel}]->(b)
                        SET r.updated_at = datetime()
                        """,
                        source=subject,
                        target=obj,
                    )
                    indexed += 1

            logger.info(
                "index_memory: indexed %d relations for memory %r", indexed, memory_id
            )
            return indexed

        except Exception as exc:
            logger.error("index_memory failed for %r: %s", memory_id, exc)
            return 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_relation_type(relation: str) -> str:
        """Sanitize a relation string into a valid Cypher relationship type.

        Cypher relationship types must be valid identifiers. We normalise
        spaces/special chars to underscores and enforce an identifier pattern.
        """
        import re

        # Replace non-alphanumeric with underscore
        safe = re.sub(r"[^A-Za-z0-9_]", "_", relation.strip())
        # Ensure starts with a letter
        if not safe or not safe[0].isalpha():
            safe = "rel_" + safe
        # Cap length
        return safe[:64]


# ---------------------------------------------------------------------------
# Module-level singleton (lazy-initialised via get_neo4j_graph_memory)
# ---------------------------------------------------------------------------
_instance: Neo4jGraphMemory | None = None


def get_neo4j_graph_memory() -> Neo4jGraphMemory:
    """Get or create the module-level Neo4jGraphMemory singleton.

    Reads settings from the application config. Returns a disabled instance
    when neo4j_enabled=False (honest degradation).
    """
    global _instance
    if _instance is not None:
        return _instance

    try:
        from backend.app.settings import get_settings

        settings = get_settings()
        _instance = Neo4jGraphMemory(
            url=settings.neo4j_url,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            database=getattr(settings, "neo4j_database", "neo4j"),
            enabled=settings.neo4j_enabled,
        )
    except Exception as exc:
        logger.debug("get_neo4j_graph_memory: settings unavailable (%s); disabled.", exc)
        _instance = Neo4jGraphMemory(enabled=False)

    return _instance
