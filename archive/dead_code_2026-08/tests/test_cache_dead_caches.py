"""归档自 tests/test_cache.py（2026-08-04 死代码收敛）
测试对象 db_cache/llm_cache/memory_cache 已归档（归档态不可运行）。
"""

class TestMemoryCaching:
    """Test memory system caching."""

    @pytest.mark.asyncio
    async def test_cache_memory_item(self) -> None:
        from backend.app.core.memory import MemoryItem, MemoryScope

        item = MemoryItem(
            tenant_id="test_tenant",
            content="Test memory",
            layer=3,
        )
        await cache_memory_item(item)
        cached = await get_cached_memory_item(item.id)
        assert cached is not None
        assert cached["content"] == "Test memory"

    @pytest.mark.asyncio
    async def test_invalidate_memory_item_cache(self) -> None:
        from backend.app.core.memory import MemoryItem

        item = MemoryItem(
            tenant_id="test_tenant",
            content="Test memory",
            layer=3,
        )
        await cache_memory_item(item)
        await invalidate_memory_item_cache(item.id)
        cached = await get_cached_memory_item(item.id)
        assert cached is None

    @pytest.mark.asyncio
    async def test_cache_search_results(self) -> None:
        from backend.app.core.memory import MemoryItem, MemorySearchHit

        item = MemoryItem(
            tenant_id="test_tenant",
            content="Test memory",
            layer=3,
        )
        hit = MemorySearchHit(item=item, score=0.95)
        results = [hit]
        await cache_search_results("test_tenant", "test query", results)
        cached = await get_cached_search_results("test_tenant", "test query")
        assert cached is not None
        assert len(cached) == 1
        assert cached[0].score == 0.95

    @pytest.mark.asyncio
    async def test_cache_session(self) -> None:
        session_data = {
            "session_id": "test_session",
            "tenant_id": "test_tenant",
            "user_id": "test_user",
        }
        await cache_session("test_session", session_data)
        cached = await get_cached_session("test_session")
        assert cached == session_data

    @pytest.mark.asyncio
    async def test_invalidate_session_cache(self) -> None:
        session_data = {"session_id": "test_session"}
        await cache_session("test_session", session_data)
        await invalidate_session_cache("test_session")
        cached = await get_cached_session("test_session")
        assert cached is None


class TestLLMCaching:
    """Test LLM response caching."""

    @pytest.mark.asyncio
    async def test_cache_llm_response(self) -> None:
        from backend.app.core.llm import LLMResponse

        messages = [{"role": "user", "content": "Hello"}]
        response = LLMResponse(content="Hi there", tokens_used=10)
        await cache_llm_response(messages, response, "gpt-4")
        cached = await get_cached_llm_response(messages, "gpt-4")
        assert cached is not None
        assert cached.content == "Hi there"
        assert cached.tokens_used == 10

    @pytest.mark.asyncio
    async def test_cache_embedding(self) -> None:
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        await cache_embedding("test text", embedding, "text-embedding-3-small")
        cached = await get_cached_embedding("test text", "text-embedding-3-small")
        assert cached == embedding


class TestDatabaseCaching:
    """Test database query caching."""

    @pytest.mark.asyncio
    async def test_cache_user(self) -> None:
        user_data = {"id": "user1", "email": "test@example.com", "name": "Test User"}
        await cache_user("user1", user_data)
        cached = await get_cached_user("user1")
        assert cached == user_data

    @pytest.mark.asyncio
    async def test_invalidate_user_cache(self) -> None:
        user_data = {"id": "user1", "email": "test@example.com"}
        await cache_user("user1", user_data)
        await invalidate_user_cache("user1")
        cached = await get_cached_user("user1")
        assert cached is None

    @pytest.mark.asyncio
    async def test_cache_tenant(self) -> None:
        tenant_data = {"id": "tenant1", "name": "Test Tenant"}
        await cache_tenant("tenant1", tenant_data)
        cached = await get_cached_tenant("tenant1")
        assert cached == tenant_data

    @pytest.mark.asyncio
    async def test_cache_api_key(self) -> None:
        key_data = {"id": "key1", "user_id": "user1", "key": "secret"}
        await cache_api_key("key1", key_data)
        cached = await get_cached_api_key("key1")
        assert cached == key_data

    @pytest.mark.asyncio
    async def test_generic_query_cache(self) -> None:
        result = {"count": 42, "items": []}
        await cache_query("custom_query", result, ttl=300, param1="value1")
        cached = await get_cached_query("custom_query", param1="value1")
        assert cached == result

    @pytest.mark.asyncio
    async def test_cache_query_signature(self) -> None:
        """Test cache_query with correct keyword-only ttl."""
        result = {"data": "test"}
        await cache_query("query_type", result, ttl=600, key="value")
        cached = await get_cached_query("query_type", key="value")
        assert cached == result


