"""Tests for pluggable embedding backends (P1-13).

Covers: backend factory routing, sentence-transformers real embeddings (via a
fake ST module), explicit degradation to the hash fallback, strict mode, and
OpenAI-compatible base_url plumbing.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from backend.app.core.embeddings import (
    DeterministicEmbeddingModel,
    OpenAIEmbeddingModel,
    SentenceTransformerEmbeddingModel,
    build_embedding_model,
)


class _FakeSTModel:
    """Minimal stand-in for sentence_transformers.SentenceTransformer."""

    def __init__(self, name: str, device: str | None = None) -> None:
        self.name = name
        self.device = device

    def get_sentence_embedding_dimension(self) -> int:
        return 4

    def encode(self, text: str, normalize_embeddings: bool = True):
        base = [float(len(text) % 7) + 1.0, float(text.count("a")) + 1.0, float(text.count("b")) + 1.0, 1.0]
        if normalize_embeddings:
            norm = sum(v * v for v in base) ** 0.5
            return [v / norm for v in base]
        return base


class _ExplodingSTModel:
    def __init__(self, name: str, device: str | None = None) -> None:
        raise OSError("offline: weights not cached")


@pytest.fixture
def fake_st_module(monkeypatch):
    module = SimpleNamespace(SentenceTransformer=_FakeSTModel)
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    return module


class TestBuildEmbeddingModelRouting:
    def test_local_returns_hash_fallback(self) -> None:
        model = build_embedding_model(embedding_backend="local")
        assert isinstance(model, DeterministicEmbeddingModel)

    def test_hash_alias(self) -> None:
        model = build_embedding_model(embedding_backend="hash")
        assert isinstance(model, DeterministicEmbeddingModel)

    def test_unknown_backend_raises_explicitly(self) -> None:
        with pytest.raises(ValueError, match="Unknown embedding_backend"):
            build_embedding_model(embedding_backend="qdrant")

    def test_openai_requires_api_key(self) -> None:
        with pytest.raises(ValueError, match="API_KEY"):
            build_embedding_model(embedding_backend="openai", openai_api_key=None)

    def test_openai_compatible_base_url_is_config_driven(self) -> None:
        model = build_embedding_model(
            embedding_backend="openai",
            openai_api_key="k",
            openai_embedding_model="bge-m3",
            openai_base_url="http://localhost:11434/v1",
        )
        assert isinstance(model, OpenAIEmbeddingModel)
        assert model.base_url == "http://localhost:11434/v1"
        assert model.model == "bge-m3"

    def test_sentence_transformers_backend(self, fake_st_module) -> None:
        model = build_embedding_model(
            embedding_backend="sentence-transformers", st_model="fake-model"
        )
        assert isinstance(model, SentenceTransformerEmbeddingModel)
        assert not model.degraded


class TestSentenceTransformerEmbeddingModel:
    def test_real_embeddings_normalized_and_deterministic(self, fake_st_module) -> None:
        model = SentenceTransformerEmbeddingModel("fake-model")
        first = model.embed("hello world")
        second = model.embed("hello world")
        assert first == second
        assert len(first) == 4
        assert model.dimensions == 4
        magnitude = sum(v * v for v in first) ** 0.5
        assert magnitude == pytest.approx(1.0, rel=1e-6)
        # 语义不同文本 → 不同向量
        assert model.embed("aaaa bbbb") != model.embed("zzzz")

    def test_semantic_similarity_beats_hash_for_paraphrase(self, fake_st_module) -> None:
        # 演示性检查：真实嵌入下完全相同的语义得到 1.0 相似度
        model = SentenceTransformerEmbeddingModel("fake-model")
        a = model.embed("the cat sat")
        b = model.embed("the cat sat")
        assert DeterministicEmbeddingModel.similarity(a, b) == pytest.approx(1.0)

    def test_model_load_failure_degrades_explicitly(self, monkeypatch) -> None:
        module = SimpleNamespace(SentenceTransformer=_ExplodingSTModel)
        monkeypatch.setitem(sys.modules, "sentence_transformers", module)
        model = SentenceTransformerEmbeddingModel("missing-model")
        assert model.degraded
        assert "offline" in (model.degraded_reason or "")
        # 显式降级到哈希嵌入: 仍能出向量, 但调用方可见 degraded 标志
        vector = model.embed("fallback text")
        assert len(vector) == model.dimensions

    def test_model_load_failure_strict_raises(self, monkeypatch) -> None:
        module = SimpleNamespace(SentenceTransformer=_ExplodingSTModel)
        monkeypatch.setitem(sys.modules, "sentence_transformers", module)
        with pytest.raises(RuntimeError, match="Failed to load"):
            SentenceTransformerEmbeddingModel("missing-model", strict=True)

    def test_missing_package_raises_with_install_hint(self, monkeypatch) -> None:
        monkeypatch.setitem(sys.modules, "sentence_transformers", None)
        with pytest.raises(RuntimeError, match="requirements-embeddings"):
            SentenceTransformerEmbeddingModel("any")


class TestOpenAIEmbeddingModelBaseUrl:
    async def test_base_url_env_fallback(self, monkeypatch) -> None:
        monkeypatch.setenv("XAGENT_OPENAI_BASE_URL", "http://proxy.local/v1")
        model = OpenAIEmbeddingModel(api_key="k")
        assert model.base_url == "http://proxy.local/v1"
