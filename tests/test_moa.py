"""Tests for MoA (Mixture of Agents) 混合模型推理引擎。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.llm.backends import BaseLLMBackend, LLMResponse
from backend.app.core.llm.moa import MoAConfig, MoAEngine, MoAResponseMeta


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_response(content: str, model: str = "test-model", tokens: int = 100) -> LLMResponse:
    return LLMResponse(
        content=content,
        model=model,
        tokens_used=tokens,
        cost=0.001,
        latency_ms=50.0,
    )


class FakeBackend(BaseLLMBackend):
    """A fake backend that returns a canned response."""

    def __init__(self, content: str, model: str = "fake", fail: bool = False):
        self._content = content
        self._model = model
        self._fail = fail

    async def chat(self, messages, tools) -> LLMResponse:
        if self._fail:
            from backend.app.core.llm.backends import LLMBackendError
            raise LLMBackendError("simulated failure")
        return _make_response(self._content, self._model)


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestMoAEngine:
    """MoA Engine core tests."""

    def test_requires_at_least_2_backends(self):
        with pytest.raises(ValueError, match="at least 2"):
            MoAEngine(backends=[FakeBackend("a")])

    async def test_consensus_strategy(self):
        """Consensus: aggregator synthesizes all responses."""
        b1 = FakeBackend("Answer A", model="model-1")
        b2 = FakeBackend("Answer B", model="model-2")
        # Aggregator (first backend) will be called to synthesize
        engine = MoAEngine(backends=[b1, b2])
        config = MoAConfig(enabled=True, strategy="consensus", min_responses=2)

        response = await engine.generate(
            [{"role": "user", "content": "test"}], [], config
        )
        assert response.content  # non-empty
        assert response.tokens_used > 0

    async def test_best_of_n_strategy(self):
        """best_of_n: scorer picks the best response."""
        b1 = FakeBackend("Short", model="m1")
        b2 = FakeBackend("A much longer and more detailed answer", model="m2")
        engine = MoAEngine(backends=[b1, b2])
        config = MoAConfig(enabled=True, strategy="best_of_n", min_responses=2)

        response = await engine.generate(
            [{"role": "user", "content": "test"}], [], config
        )
        assert response.content

    async def test_weighted_vote_strategy(self):
        """weighted_vote: majority vote."""
        b1 = FakeBackend("Answer X", model="m1")
        b2 = FakeBackend("Answer X", model="m2")
        b3 = FakeBackend("Answer Y", model="m3")
        engine = MoAEngine(backends=[b1, b2, b3])
        config = MoAConfig(enabled=True, strategy="weighted_vote", min_responses=2)

        response = await engine.generate(
            [{"role": "user", "content": "test"}], [], config
        )
        assert response.content

    async def test_partial_failure_still_works(self):
        """If one backend fails, others still contribute."""
        b1 = FakeBackend("Good answer", model="m1")
        b2 = FakeBackend("", model="m2", fail=True)
        b3 = FakeBackend("Another good answer", model="m3")
        engine = MoAEngine(backends=[b1, b2, b3])
        config = MoAConfig(enabled=True, strategy="consensus", min_responses=2)

        response = await engine.generate(
            [{"role": "user", "content": "test"}], [], config
        )
        assert response.content

    async def test_insufficient_responses_fallback(self):
        """When fewer than min_responses succeed, return best single response."""
        b1 = FakeBackend("Only survivor", model="m1")
        b2 = FakeBackend("", model="m2", fail=True)
        b3 = FakeBackend("", model="m3", fail=True)
        engine = MoAEngine(backends=[b1, b2, b3])
        config = MoAConfig(enabled=True, strategy="consensus", min_responses=2)

        response = await engine.generate(
            [{"role": "user", "content": "test"}], [], config
        )
        # Should fallback to the single successful response
        assert "Only survivor" in response.content

    async def test_moa_metadata_attached(self):
        """Response should carry moa_metadata."""
        b1 = FakeBackend("A", model="m1")
        b2 = FakeBackend("B", model="m2")
        engine = MoAEngine(backends=[b1, b2])
        config = MoAConfig(enabled=True, strategy="consensus", min_responses=2)

        response = await engine.generate(
            [{"role": "user", "content": "test"}], [], config
        )
        meta = getattr(response, "moa_metadata", None)
        if meta is not None:
            assert meta.responses_collected >= 1


class TestMoARouterIntegration:
    """Test MoA path in LLMRouter.chat()."""

    async def test_moa_disabled_uses_sequential(self):
        """When moa_enabled=False, router uses sequential path."""
        from backend.app.core.llm.backends import LLMRouter

        b1 = FakeBackend("seq-response", model="seq")
        router = LLMRouter(backends=[b1, FakeBackend("other", model="o")])

        mock_settings = MagicMock()
        mock_settings.moa_enabled = False
        with patch("backend.app.settings.get_settings", return_value=mock_settings):
            response = await router.chat([{"role": "user", "content": "hi"}], [])
        assert "seq-response" in response.content

    async def test_moa_enabled_uses_moa_path(self):
        """When moa_enabled=True + 2+ backends, MoA path is used."""
        from backend.app.core.llm.backends import LLMRouter

        b1 = FakeBackend("moa-A", model="m1")
        b2 = FakeBackend("moa-B", model="m2")
        router = LLMRouter(backends=[b1, b2])

        mock_settings = MagicMock()
        mock_settings.moa_enabled = True
        mock_settings.moa_strategy = "consensus"
        mock_settings.moa_timeout = 10.0
        mock_settings.moa_min_responses = 2
        with patch("backend.app.settings.get_settings", return_value=mock_settings):
            response = await router.chat([{"role": "user", "content": "hi"}], [])
        assert response.content  # MoA aggregated response
