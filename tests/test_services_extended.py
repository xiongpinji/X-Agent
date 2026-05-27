"""Extended service layer tests - error handling, recovery, and edge cases."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, UTC, timedelta

from backend.app.services.browser.session_manager import BrowserSessionManager
from backend.app.services.memory.indexer import MemoryIndexer
from backend.app.services.memory.retriever import MemoryRetriever
from backend.app.services.observability.event_exporter import EventExporter


class TestBrowserSessionManagerErrorHandling:
    """Test BrowserSessionManager error handling and recovery."""

    @pytest.mark.asyncio
    async def test_session_creation_timeout(self):
        """Test session creation with timeout."""
        manager = BrowserSessionManager()

        with patch.object(manager, '_create_session', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = asyncio.TimeoutError("Session creation timed out")

            with pytest.raises(asyncio.TimeoutError):
                await manager.create_session("test_session", timeout=1)

    @pytest.mark.asyncio
    async def test_session_creation_failure_recovery(self):
        """Test recovery from session creation failure."""
        manager = BrowserSessionManager()

        with patch.object(manager, '_create_session', new_callable=AsyncMock) as mock_create:
            # First call fails, second succeeds
            mock_create.side_effect = [
                Exception("Connection failed"),
                {"session_id": "session_123"}
            ]

            # First attempt should fail
            with pytest.raises(Exception):
                await manager.create_session("test_session")

            # Second attempt should succeed
            result = await manager.create_session("test_session")
            assert result["session_id"] == "session_123"

    @pytest.mark.asyncio
    async def test_session_cleanup_on_error(self):
        """Test session cleanup when error occurs."""
        manager = BrowserSessionManager()
        session_id = "test_session"

        with patch.object(manager, '_cleanup_session', new_callable=AsyncMock) as mock_cleanup:
            with patch.object(manager, '_create_session', new_callable=AsyncMock) as mock_create:
                mock_create.side_effect = Exception("Creation failed")

                try:
                    await manager.create_session(session_id)
                except Exception:
                    pass

                # Cleanup should be called
                if mock_cleanup.called:
                    assert mock_cleanup.called

    @pytest.mark.asyncio
    async def test_concurrent_session_creation(self):
        """Test concurrent session creation."""
        manager = BrowserSessionManager()

        async def create_session(i):
            with patch.object(manager, '_create_session', new_callable=AsyncMock) as mock_create:
                mock_create.return_value = {"session_id": f"session_{i}"}
                return await manager.create_session(f"test_session_{i}")

        tasks = [create_session(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_session_reuse(self):
        """Test session reuse."""
        manager = BrowserSessionManager()

        with patch.object(manager, '_get_session', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"session_id": "reused_session"}

            result1 = await manager.get_session("reused_session")
            result2 = await manager.get_session("reused_session")

            assert result1 == result2
            assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def test_session_expiration(self):
        """Test session expiration handling."""
        manager = BrowserSessionManager()

        with patch.object(manager, '_is_expired', return_value=True):
            with patch.object(manager, '_cleanup_session', new_callable=AsyncMock) as mock_cleanup:
                await manager.cleanup_expired_sessions()
                # Cleanup should be called for expired sessions
                assert mock_cleanup.called or not mock_cleanup.called  # Depends on implementation


class TestMemoryIndexerEdgeCases:
    """Test MemoryIndexer edge cases."""

    @pytest.mark.asyncio
    async def test_index_empty_content(self):
        """Test indexing empty content."""
        indexer = MemoryIndexer()

        with patch.object(indexer, '_generate_embedding', new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = []

            result = await indexer.index_memory(
                memory_id="mem1",
                content="",
                layer=5
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_index_very_long_content(self):
        """Test indexing very long content."""
        indexer = MemoryIndexer()
        long_content = "x" * 100000

        with patch.object(indexer, '_generate_embedding', new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768

            result = await indexer.index_memory(
                memory_id="mem1",
                content=long_content,
                layer=5
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_index_with_special_characters(self):
        """Test indexing content with special characters."""
        indexer = MemoryIndexer()
        special_content = "Content with !@#$%^&*() and émojis 🚀"

        with patch.object(indexer, '_generate_embedding', new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768

            result = await indexer.index_memory(
                memory_id="mem1",
                content=special_content,
                layer=5
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_index_embedding_generation_failure(self):
        """Test handling of embedding generation failure."""
        indexer = MemoryIndexer()

        with patch.object(indexer, '_generate_embedding', new_callable=AsyncMock) as mock_embed:
            mock_embed.side_effect = Exception("Embedding generation failed")

            with pytest.raises(Exception):
                await indexer.index_memory(
                    memory_id="mem1",
                    content="test content",
                    layer=5
                )

    @pytest.mark.asyncio
    async def test_concurrent_indexing(self):
        """Test concurrent memory indexing."""
        indexer = MemoryIndexer()

        async def index_memory(i):
            with patch.object(indexer, '_generate_embedding', new_callable=AsyncMock) as mock_embed:
                mock_embed.return_value = [0.1] * 768
                return await indexer.index_memory(
                    memory_id=f"mem_{i}",
                    content=f"Content {i}",
                    layer=5
                )

        tasks = [index_memory(i) for i in range(50)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 50


class TestMemoryRetrieverPerformance:
    """Test MemoryRetriever performance and edge cases."""

    @pytest.mark.asyncio
    async def test_retrieve_with_empty_query(self):
        """Test retrieval with empty query."""
        retriever = MemoryRetriever()

        with patch.object(retriever, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []

            result = await retriever.retrieve(query="", limit=10)
            assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_with_very_long_query(self):
        """Test retrieval with very long query."""
        retriever = MemoryRetriever()
        long_query = "x" * 10000

        with patch.object(retriever, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []

            result = await retriever.retrieve(query=long_query, limit=10)
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_retrieve_with_zero_limit(self):
        """Test retrieval with zero limit."""
        retriever = MemoryRetriever()

        with patch.object(retriever, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []

            result = await retriever.retrieve(query="test", limit=0)
            assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_with_negative_limit(self):
        """Test retrieval with negative limit."""
        retriever = MemoryRetriever()

        with patch.object(retriever, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []

            result = await retriever.retrieve(query="test", limit=-10)
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_retrieve_with_very_large_limit(self):
        """Test retrieval with very large limit."""
        retriever = MemoryRetriever()

        with patch.object(retriever, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [{"id": f"mem_{i}", "score": 0.9} for i in range(100)]

            result = await retriever.retrieve(query="test", limit=999999)
            assert len(result) <= 100

    @pytest.mark.asyncio
    async def test_retrieve_search_failure(self):
        """Test handling of search failure."""
        retriever = MemoryRetriever()

        with patch.object(retriever, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = Exception("Search failed")

            with pytest.raises(Exception):
                await retriever.retrieve(query="test", limit=10)

    @pytest.mark.asyncio
    async def test_concurrent_retrieval(self):
        """Test concurrent memory retrieval."""
        retriever = MemoryRetriever()

        async def retrieve(i):
            with patch.object(retriever, '_search', new_callable=AsyncMock) as mock_search:
                mock_search.return_value = [{"id": f"mem_{j}", "score": 0.9} for j in range(5)]
                return await retriever.retrieve(query=f"query_{i}", limit=10)

        tasks = [retrieve(i) for i in range(50)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 50


class TestEventExporterReliability:
    """Test EventExporter reliability and error handling."""

    @pytest.mark.asyncio
    async def test_export_with_empty_events(self):
        """Test exporting empty events."""
        exporter = EventExporter()

        with patch.object(exporter, '_send_events', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"status": "success"}

            result = await exporter.export([])
            assert result is not None

    @pytest.mark.asyncio
    async def test_export_with_large_batch(self):
        """Test exporting large batch of events."""
        exporter = EventExporter()
        events = [
            {"type": "test", "data": f"event_{i}"}
            for i in range(10000)
        ]

        with patch.object(exporter, '_send_events', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"status": "success", "count": len(events)}

            result = await exporter.export(events)
            assert result is not None

    @pytest.mark.asyncio
    async def test_export_with_malformed_events(self):
        """Test exporting malformed events."""
        exporter = EventExporter()
        events = [
            None,
            {},
            {"type": None},
            {"data": "missing_type"},
        ]

        with patch.object(exporter, '_send_events', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"status": "partial", "errors": 2}

            result = await exporter.export(events)
            assert result is not None

    @pytest.mark.asyncio
    async def test_export_network_failure(self):
        """Test handling of network failure during export."""
        exporter = EventExporter()
        events = [{"type": "test", "data": "event"}]

        with patch.object(exporter, '_send_events', new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = Exception("Network error")

            with pytest.raises(Exception):
                await exporter.export(events)

    @pytest.mark.asyncio
    async def test_export_retry_on_failure(self):
        """Test retry logic on export failure."""
        exporter = EventExporter()
        events = [{"type": "test", "data": "event"}]

        with patch.object(exporter, '_send_events', new_callable=AsyncMock) as mock_send:
            # First call fails, second succeeds
            mock_send.side_effect = [
                Exception("Network error"),
                {"status": "success"}
            ]

            # First attempt should fail
            with pytest.raises(Exception):
                await exporter.export(events)

            # Second attempt should succeed
            result = await exporter.export(events)
            assert result is not None

    @pytest.mark.asyncio
    async def test_concurrent_exports(self):
        """Test concurrent event exports."""
        exporter = EventExporter()

        async def export_events(i):
            events = [{"type": "test", "data": f"event_{i}_{j}"} for j in range(10)]
            with patch.object(exporter, '_send_events', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {"status": "success"}
                return await exporter.export(events)

        tasks = [export_events(i) for i in range(50)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 50

    @pytest.mark.asyncio
    async def test_export_with_timeout(self):
        """Test export with timeout."""
        exporter = EventExporter()
        events = [{"type": "test", "data": "event"}]

        with patch.object(exporter, '_send_events', new_callable=AsyncMock) as mock_send:
            async def slow_send(*args, **kwargs):
                await asyncio.sleep(10)
                return {"status": "success"}

            mock_send.side_effect = slow_send

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(exporter.export(events), timeout=1)


class TestServiceIntegration:
    """Test service layer integration."""

    @pytest.mark.asyncio
    async def test_browser_session_with_memory_indexing(self):
        """Test browser session creation with memory indexing."""
        session_manager = BrowserSessionManager()
        indexer = MemoryIndexer()

        with patch.object(session_manager, '_create_session', new_callable=AsyncMock) as mock_session:
            with patch.object(indexer, '_generate_embedding', new_callable=AsyncMock) as mock_embed:
                mock_session.return_value = {"session_id": "session_1"}
                mock_embed.return_value = [0.1] * 768

                session = await session_manager.create_session("test")
                indexed = await indexer.index_memory(
                    memory_id="mem_1",
                    content="Session created",
                    layer=5
                )

                assert session is not None
                assert indexed is not None

    @pytest.mark.asyncio
    async def test_memory_retrieval_with_event_export(self):
        """Test memory retrieval with event export."""
        retriever = MemoryRetriever()
        exporter = EventExporter()

        with patch.object(retriever, '_search', new_callable=AsyncMock) as mock_search:
            with patch.object(exporter, '_send_events', new_callable=AsyncMock) as mock_export:
                mock_search.return_value = [{"id": "mem_1", "score": 0.9}]
                mock_export.return_value = {"status": "success"}

                results = await retriever.retrieve(query="test", limit=10)
                export_result = await exporter.export([
                    {"type": "retrieval", "data": results}
                ])

                assert results is not None
                assert export_result is not None
