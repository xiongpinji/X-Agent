"""Comprehensive tests for core modules - Memory, Browser, Observability."""
import pytest
from datetime import datetime, UTC
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from backend.app.core.contracts import RiskLevel, RunContext


class TestMemoryGraphEdgeCases:
    """Test memory graph edge cases and boundary conditions."""

    def test_empty_memory_graph(self):
        """Test empty memory graph initialization."""
        from backend.app.core.memory_graph import MemoryGraph

        graph = MemoryGraph()
        # MemoryGraph is a co-occurrence graph with _edges dict, no .nodes/.edges attrs
        assert graph._edges == {}

    def test_add_text_to_graph(self):
        """Test adding text to graph."""
        from backend.app.core.memory_graph import MemoryGraph

        graph = MemoryGraph()
        graph.add_text("test node data value")
        # Should extract terms and build co-occurrence edges
        assert len(graph._edges) > 0

    def test_add_multiple_texts(self):
        """Test adding multiple texts."""
        from backend.app.core.memory_graph import MemoryGraph

        graph = MemoryGraph()
        for i in range(10):
            graph.add_text(f"node index {i}")
        assert len(graph._edges) > 0

    def test_related_terms_basic(self):
        """Test retrieving related terms."""
        from backend.app.core.memory_graph import MemoryGraph

        graph = MemoryGraph()
        graph.add_text("test node data value")
        related = graph.related_terms({"test"}, limit=5)
        # Should return related terms or empty set
        assert isinstance(related, set)

    def test_related_terms_nonexistent(self):
        """Test related terms for nonexistent term."""
        from backend.app.core.memory_graph import MemoryGraph

        graph = MemoryGraph()
        graph.add_text("test node data")
        # Query for term not in graph
        related = graph.related_terms({"nonexistent"}, limit=5)
        assert related == set()

    def test_extract_terms_basic(self):
        """Test term extraction."""
        from backend.app.core.memory_graph import MemoryGraph

        terms = MemoryGraph.extract_terms("test node data value")
        assert "test" in terms
        assert "node" in terms

    def test_extract_terms_with_cjk(self):
        """Test term extraction with CJK characters."""
        from backend.app.core.memory_graph import MemoryGraph

        terms = MemoryGraph.extract_terms("测试 node 数据")
        # Should extract both CJK and ASCII terms
        assert len(terms) > 0

    def test_large_text_processing(self):
        """Test processing large text."""
        from backend.app.core.memory_graph import MemoryGraph

        graph = MemoryGraph()
        large_text = "word " * 10000
        graph.add_text(large_text)
        # Should handle large text without error
        assert len(graph._edges) > 0


@pytest.mark.skip(
    reason="Aspirational API: backend.app.services.browser.session_manager does "
    "not exist (the only SessionManager is core/session.py, a DB-session "
    "manager — wrong domain). These mock-theater tests assert nothing about "
    "real behaviour; re-enable once the browser session manager exists."
)
class TestBrowserSessionManagement:
    """Test browser session management."""

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test creating browser session."""
        from backend.app.services.browser.session_manager import SessionManager

        manager = SessionManager()
        session = await manager.create_session()
        assert session is not None
        assert session.id is not None

    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test getting browser session."""
        from backend.app.services.browser.session_manager import SessionManager

        manager = SessionManager()
        created = await manager.create_session()
        retrieved = await manager.get_session(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self):
        """Test getting nonexistent session."""
        from backend.app.services.browser.session_manager import SessionManager

        manager = SessionManager()
        session = await manager.get_session("nonexistent_id")
        assert session is None

    @pytest.mark.asyncio
    async def test_close_session(self):
        """Test closing browser session."""
        from backend.app.services.browser.session_manager import SessionManager

        manager = SessionManager()
        session = await manager.create_session()
        await manager.close_session(session.id)
        # Session should be closed
        retrieved = await manager.get_session(session.id)
        assert retrieved is None or retrieved.closed

    @pytest.mark.asyncio
    async def test_multiple_sessions(self):
        """Test managing multiple sessions."""
        from backend.app.services.browser.session_manager import SessionManager

        manager = SessionManager()
        sessions = []
        for _ in range(5):
            session = await manager.create_session()
            sessions.append(session)
        assert len(sessions) == 5
        for session in sessions:
            assert session.id is not None

    @pytest.mark.asyncio
    async def test_session_timeout(self):
        """Test session timeout."""
        from backend.app.services.browser.session_manager import SessionManager

        manager = SessionManager(timeout_seconds=1)
        session = await manager.create_session()
        await asyncio.sleep(1.5)
        # Session should be expired
        retrieved = await manager.get_session(session.id)
        assert retrieved is None or retrieved.expired


class TestBrowserAutomation:
    """Test browser automation."""

    @pytest.mark.asyncio
    async def test_navigate_to_url(self):
        """Test navigating to URL."""
        from backend.app.services.browser.automation import BrowserAutomation

        automation = BrowserAutomation()
        # Mock the actual navigation
        with patch.object(automation, "navigate") as mock_nav:
            mock_nav.return_value = None
            await automation.navigate("https://example.com")
            mock_nav.assert_called_once()

    @pytest.mark.asyncio
    async def test_click_element(self):
        """Test clicking element."""
        from backend.app.services.browser.automation import BrowserAutomation

        automation = BrowserAutomation()
        with patch.object(automation, "click") as mock_click:
            mock_click.return_value = None
            await automation.click("button#submit")
            mock_click.assert_called_once()

    @pytest.mark.asyncio
    async def test_type_text(self):
        """Test typing text."""
        from backend.app.services.browser.automation import BrowserAutomation

        automation = BrowserAutomation()
        with patch.object(automation, "type_text") as mock_type:
            mock_type.return_value = None
            await automation.type_text("input#search", "test query")
            mock_type.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_page_content(self):
        """Test getting page content."""
        from backend.app.services.browser.automation import BrowserAutomation

        automation = BrowserAutomation()
        with patch.object(automation, "get_content") as mock_get:
            mock_get.return_value = "<html><body>Test</body></html>"
            content = await automation.get_content()
            assert "Test" in content

    @pytest.mark.asyncio
    async def test_take_screenshot(self):
        """Test taking screenshot."""
        from backend.app.services.browser.automation import BrowserAutomation

        automation = BrowserAutomation()
        with patch.object(automation, "screenshot") as mock_screenshot:
            mock_screenshot.return_value = b"fake_image_data"
            image = await automation.screenshot()
            assert image is not None


class TestObservabilityEventExporter:
    """Test observability event exporter."""

    @pytest.mark.asyncio
    async def test_export_event_basic(self):
        """Test exporting basic event."""
        from backend.app.services.observability.event_exporter import EventExporter

        exporter = EventExporter()
        event = {
            "type": "tool_execution",
            "tool_name": "read_file",
            "status": "success",
            "timestamp": datetime.now(UTC),
        }
        await exporter.export([event])
        # Should not raise

    @pytest.mark.asyncio
    async def test_export_multiple_events(self):
        """Test exporting multiple events."""
        from backend.app.services.observability.event_exporter import EventExporter

        exporter = EventExporter()
        events = [
            {
                "type": "event",
                "index": i,
                "timestamp": datetime.now(UTC),
            }
            for i in range(10)
        ]
        await exporter.export(events)
        # Should handle all events

    @pytest.mark.asyncio
    async def test_export_event_with_error(self):
        """Test exporting event with error."""
        from backend.app.services.observability.event_exporter import EventExporter

        exporter = EventExporter()
        event = {
            "type": "error",
            "error": "Test error",
            "stack_trace": "line 1\nline 2",
            "timestamp": datetime.now(UTC),
        }
        await exporter.export([event])
        # Should handle error events

    @pytest.mark.asyncio
    async def test_export_event_with_large_payload(self):
        """Test exporting event with large payload."""
        from backend.app.services.observability.event_exporter import EventExporter

        exporter = EventExporter()
        event = {
            "type": "data",
            "payload": "x" * 100000,
            "timestamp": datetime.now(UTC),
        }
        await exporter.export([event])
        # Should handle large payloads


@pytest.mark.skip(
    reason="TraceMapper.map_trace/calculate_duration/find_critical_path not in prod API; "
    "only .map(event_type, **payload) exists"
)
class TestTraceMapper:
    """Test trace mapper."""

    def test_map_trace_basic(self):
        """Test basic trace mapping."""
        from backend.app.services.observability.trace_mapper import TraceMapper

        mapper = TraceMapper()
        trace = {
            "id": "trace1",
            "spans": [
                {"id": "span1", "name": "operation1", "duration": 100},
                {"id": "span2", "name": "operation2", "duration": 200},
            ],
        }
        mapped = mapper.map_trace(trace)
        assert mapped is not None

    def test_map_nested_spans(self):
        """Test mapping nested spans."""
        from backend.app.services.observability.trace_mapper import TraceMapper

        mapper = TraceMapper()
        trace = {
            "id": "trace1",
            "spans": [
                {
                    "id": "span1",
                    "name": "parent",
                    "children": [
                        {"id": "span2", "name": "child1"},
                        {"id": "span3", "name": "child2"},
                    ],
                }
            ],
        }
        mapped = mapper.map_trace(trace)
        assert mapped is not None

    def test_calculate_trace_duration(self):
        """Test calculating trace duration."""
        from backend.app.services.observability.trace_mapper import TraceMapper

        mapper = TraceMapper()
        trace = {
            "id": "trace1",
            "spans": [
                {"id": "span1", "start": 0, "end": 100},
                {"id": "span2", "start": 100, "end": 300},
            ],
        }
        duration = mapper.calculate_duration(trace)
        assert duration is not None

    def test_identify_critical_path(self):
        """Test identifying critical path in trace."""
        from backend.app.services.observability.trace_mapper import TraceMapper

        mapper = TraceMapper()
        trace = {
            "id": "trace1",
            "spans": [
                {"id": "span1", "duration": 100},
                {"id": "span2", "duration": 500},
                {"id": "span3", "duration": 200},
            ],
        }
        critical = mapper.find_critical_path(trace)
        assert critical is not None


class TestMemoryIndexer:
    """Test memory indexer."""

    def test_index_document(self):
        """Test indexing document (sync method)."""
        from backend.app.services.memory.indexer import MemoryIndexer
        from unittest.mock import patch

        indexer = MemoryIndexer()
        # index() is sync, requires tenant_id and text as keyword args
        with patch("backend.app.services.memory.indexer.vector_client") as mock_vc:
            mock_vc.upsert.return_value = type('Record', (), {'id': 'doc1'})()
            result = indexer.index(tenant_id="tenant1", text="Test document content", doc_id="doc1")
            assert result is not None

    def test_index_multiple_documents(self):
        """Test indexing multiple documents."""
        from backend.app.services.memory.indexer import MemoryIndexer
        from unittest.mock import patch

        indexer = MemoryIndexer()
        with patch("backend.app.services.memory.indexer.vector_client") as mock_vc:
            mock_vc.upsert.return_value = type('Record', (), {'id': 'doc1'})()
            for i in range(10):
                result = indexer.index(tenant_id="tenant1", text=f"Document {i}", doc_id=f"doc{i}")
                assert result is not None

    def test_index_document_with_embeddings(self):
        """Test indexing document with embeddings."""
        from backend.app.services.memory.indexer import MemoryIndexer
        from unittest.mock import patch

        indexer = MemoryIndexer()
        with patch("backend.app.services.memory.indexer.vector_client") as mock_vc:
            mock_vc.upsert.return_value = type('Record', (), {'id': 'doc1'})()
            result = indexer.index(
                tenant_id="tenant1",
                text="Test content",
                embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
                doc_id="doc1"
            )
            assert result is not None

    def test_index_with_payload(self):
        """Test indexing with additional payload."""
        from backend.app.services.memory.indexer import MemoryIndexer
        from unittest.mock import patch

        indexer = MemoryIndexer()
        with patch("backend.app.services.memory.indexer.vector_client") as mock_vc:
            mock_vc.upsert.return_value = type('Record', (), {'id': 'doc1'})()
            result = indexer.index(
                tenant_id="tenant1",
                text="Test",
                doc_id="doc1",
                metadata_type="note"
            )
            assert result is not None

    def test_index_empty_text(self):
        """Test indexing empty text."""
        from backend.app.services.memory.indexer import MemoryIndexer
        from unittest.mock import patch

        indexer = MemoryIndexer()
        with patch("backend.app.services.memory.indexer.vector_client") as mock_vc:
            mock_vc.upsert.return_value = type('Record', (), {'id': 'doc1'})()
            result = indexer.index(tenant_id="tenant1", text="", doc_id="doc1")
            assert result is not None


class TestMemoryRetriever:
    """Test memory retriever."""

    def test_retrieve_by_id(self):
        """Test retrieving memory by ID (sync method)."""
        from backend.app.services.memory.retriever import MemoryRetriever
        from unittest.mock import patch

        retriever = MemoryRetriever()
        # search() is sync, requires query as keyword arg
        with patch("backend.app.services.memory.retriever.vector_client") as mock_vc:
            mock_vc.search.return_value = [{"id": "doc1", "content": "Test"}]
            result = retriever.search(tenant_id="tenant1", query="test")
            assert result is not None

    def test_semantic_search(self):
        """Test semantic search (sync)."""
        from backend.app.services.memory.retriever import MemoryRetriever
        from unittest.mock import patch

        retriever = MemoryRetriever()
        with patch("backend.app.services.memory.retriever.vector_client") as mock_vc:
            mock_vc.search.return_value = [
                {"id": "doc1", "score": 0.9},
                {"id": "doc2", "score": 0.7},
            ]
            results = retriever.search(query="test query", top_k=5)
            assert len(results) == 2

    def test_search_with_top_k(self):
        """Test search with top_k parameter."""
        from backend.app.services.memory.retriever import MemoryRetriever
        from unittest.mock import patch

        retriever = MemoryRetriever()
        with patch("backend.app.services.memory.retriever.vector_client") as mock_vc:
            mock_vc.search.return_value = [{"id": "doc1", "score": 0.9}]
            results = retriever.search(
                query="query",
                top_k=10,
            )
            assert results is not None

    def test_retrieve_similar_documents(self):
        """Test retrieving similar documents."""
        from backend.app.services.memory.retriever import MemoryRetriever
        from unittest.mock import patch

        retriever = MemoryRetriever()
        with patch("backend.app.services.memory.retriever.vector_client") as mock_vc:
            mock_vc.search.return_value = [
                {"id": "doc2", "score": 0.85},
                {"id": "doc3", "score": 0.75},
            ]
            results = retriever.search(query="doc1", top_k=5)
            assert len(results) == 2

    def test_search_empty_query(self):
        """Test search with empty query."""
        from backend.app.services.memory.retriever import MemoryRetriever
        from unittest.mock import patch

        retriever = MemoryRetriever()
        with patch("backend.app.services.memory.retriever.vector_client") as mock_vc:
            mock_vc.search.return_value = []
            results = retriever.search(query="", top_k=5)
            assert results == []

    def test_search_with_tenant(self):
        """Test search with tenant_id."""
        from backend.app.services.memory.retriever import MemoryRetriever
        from unittest.mock import patch

        retriever = MemoryRetriever()
        with patch("backend.app.services.memory.retriever.vector_client") as mock_vc:
            mock_vc.search.return_value = [{"id": "doc1", "score": 0.9}]
            results = retriever.search(tenant_id="tenant1", query="test", top_k=5)
            assert len(results) == 1


@pytest.mark.skip(
    reason="Mock-theater on wrong target: imports the third-party "
    "qdrant_client.QdrantClient (not the project's QdrantVectorClient wrapper) "
    "and patch.object()s create_collection/upsert/search/delete — but the real "
    "client's surface differs (no `search`, it's `query_points`), so patch fails "
    "with mock-spec AttributeError. Tests assert only that the mock was called, "
    "verifying nothing real. Re-target at QdrantVectorClient to re-enable."
)
class TestQdrantClient:
    """Test Qdrant vector database client."""

    @pytest.mark.asyncio
    async def test_connect_to_qdrant(self):
        """Test connecting to Qdrant."""
        from backend.app.services.memory.qdrant_client import QdrantClient

        client = QdrantClient(url="http://localhost:6333")
        # Should initialize without error
        assert client is not None

    @pytest.mark.asyncio
    async def test_create_collection(self):
        """Test creating collection."""
        from backend.app.services.memory.qdrant_client import QdrantClient

        client = QdrantClient(url="http://localhost:6333")
        with patch.object(client, "create_collection") as mock_create:
            mock_create.return_value = None
            await client.create_collection("test_collection", vector_size=384)
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_vectors(self):
        """Test upserting vectors."""
        from backend.app.services.memory.qdrant_client import QdrantClient

        client = QdrantClient(url="http://localhost:6333")
        with patch.object(client, "upsert") as mock_upsert:
            mock_upsert.return_value = None
            vectors = [
                {"id": 1, "vector": [0.1, 0.2, 0.3]},
                {"id": 2, "vector": [0.4, 0.5, 0.6]},
            ]
            await client.upsert("test_collection", vectors)
            mock_upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_vectors(self):
        """Test searching vectors."""
        from backend.app.services.memory.qdrant_client import QdrantClient

        client = QdrantClient(url="http://localhost:6333")
        with patch.object(client, "search") as mock_search:
            mock_search.return_value = [
                {"id": 1, "score": 0.95},
                {"id": 2, "score": 0.87},
            ]
            results = await client.search(
                "test_collection",
                query_vector=[0.1, 0.2, 0.3],
                limit=10,
            )
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_delete_vectors(self):
        """Test deleting vectors."""
        from backend.app.services.memory.qdrant_client import QdrantClient

        client = QdrantClient(url="http://localhost:6333")
        with patch.object(client, "delete") as mock_delete:
            mock_delete.return_value = None
            await client.delete("test_collection", [1, 2, 3])
            mock_delete.assert_called_once()


@pytest.mark.skip(
    reason="Aspirational API: backend.app.core.embeddings.EmbeddingsService is "
    "not yet implemented. These mock-theater tests patch every method and "
    "assert nothing about real behaviour; re-enable once the module exists."
)
class TestEmbeddingsService:
    """Test embeddings service."""

    @pytest.mark.asyncio
    async def test_embed_text(self):
        """Test embedding text."""
        from backend.app.core.embeddings import EmbeddingsService

        service = EmbeddingsService()
        with patch.object(service, "embed") as mock_embed:
            mock_embed.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]
            embedding = await service.embed("test text")
            assert len(embedding) == 5

    @pytest.mark.asyncio
    async def test_embed_multiple_texts(self):
        """Test embedding multiple texts."""
        from backend.app.core.embeddings import EmbeddingsService

        service = EmbeddingsService()
        with patch.object(service, "embed_batch") as mock_embed:
            mock_embed.return_value = [
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6],
                [0.7, 0.8, 0.9],
            ]
            embeddings = await service.embed_batch(
                ["text1", "text2", "text3"]
            )
            assert len(embeddings) == 3

    @pytest.mark.asyncio
    async def test_embed_empty_text(self):
        """Test embedding empty text."""
        from backend.app.core.embeddings import EmbeddingsService

        service = EmbeddingsService()
        with patch.object(service, "embed") as mock_embed:
            mock_embed.return_value = [0.0] * 384
            embedding = await service.embed("")
            assert embedding is not None

    @pytest.mark.asyncio
    async def test_embed_very_long_text(self):
        """Test embedding very long text."""
        from backend.app.core.embeddings import EmbeddingsService

        service = EmbeddingsService()
        with patch.object(service, "embed") as mock_embed:
            mock_embed.return_value = [0.1] * 384
            long_text = "word " * 10000
            embedding = await service.embed(long_text)
            assert embedding is not None

    @pytest.mark.asyncio
    async def test_similarity_score(self):
        """Test calculating similarity score."""
        from backend.app.core.embeddings import EmbeddingsService

        service = EmbeddingsService()
        with patch.object(service, "similarity") as mock_sim:
            mock_sim.return_value = 0.95
            score = await service.similarity(
                [0.1, 0.2, 0.3],
                [0.1, 0.2, 0.3],
            )
            assert 0 <= score <= 1
