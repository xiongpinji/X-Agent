from __future__ import annotations

import hashlib
import logging
import math
import os
import re
from collections import Counter
from collections.abc import Awaitable
from hashlib import sha256
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# 默认本地句向量模型: 多语言(含中文)MiniLM, 384 维, ~470MB, CPU 可跑。
# 实测(2026-07-20): 中文改写对 cos=0.71 vs 无关对 0.16; 英文改写对 0.77。
# 纯英文场景可换更快的 all-MiniLM-L6-v2 (~90MB, 但不支持中文语义)。
DEFAULT_SENTENCE_TRANSFORMER_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


class EmbeddingModel(Protocol):
    def embed(self, text: str) -> list[float] | Awaitable[list[float]]:
        """Return a vector for retrieval."""


class DeterministicEmbeddingModel:
    """Dependency-free **offline fallback** embedding (feature-hashing over tokens).

    WARNING: this is a hash-based pseudo-embedding. It is NOT semantic and must
    only be used as an explicit offline/degraded fallback for local tests and
    offline development. Production semantic retrieval should use
    ``SentenceTransformerEmbeddingModel`` (local) or ``OpenAIEmbeddingModel``
    (OpenAI-compatible API) via ``build_embedding_model``.

    It gives the memory layer a stable vector contract that can be backed by a
    real provider without changing callers.
    """

    def __init__(self, dimensions: int = 128) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token, count in Counter(self._tokens(text)).items():
            digest = sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign * (1.0 + math.log(count))
        return self._normalize(vector)

    @staticmethod
    def similarity(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        return sum(a * b for a, b in zip(left, right, strict=True))

    @staticmethod
    def _normalize(vector: list[float]) -> list[float]:
        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            return vector
        return [value / magnitude for value in vector]

    @staticmethod
    def _tokens(text: str) -> list[str]:
        normalized = text.casefold()
        words = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", normalized)
        bigrams = [f"{words[index]} {words[index + 1]}" for index in range(len(words) - 1)]
        return words + bigrams


class SentenceTransformerEmbeddingModel:
    """Real local embeddings via the optional ``sentence-transformers`` package.

    Install with ``pip install -r requirements-embeddings.txt`` (pulls torch).

    Explicit degradation semantics (no silent fake-success):
    - Package not installed -> ``RuntimeError`` at construction with install hint.
    - Model weights unavailable (e.g. offline, HuggingFace unreachable):
      * ``strict=True``  -> ``RuntimeError``.
      * ``strict=False`` -> fall back to ``fallback`` model (default:
        :class:`DeterministicEmbeddingModel`), set ``degraded=True`` /
        ``degraded_reason`` and log a warning. Callers can inspect the flags.
    """

    def __init__(
        self,
        model_name: str | None = None,
        *,
        device: str | None = None,
        fallback: EmbeddingModel | None = None,
        strict: bool = False,
    ) -> None:
        self.model_name = model_name or os.getenv(
            "XAGENT_ST_MODEL", DEFAULT_SENTENCE_TRANSFORMER_MODEL
        )
        self.device = device or os.getenv("XAGENT_ST_DEVICE") or None
        self.degraded = False
        self.degraded_reason: str | None = None
        self._fallback = fallback if fallback is not None else DeterministicEmbeddingModel()
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed; install real local "
                "embeddings via `pip install -r requirements-embeddings.txt`, "
                "or use embedding_backend='local' (hash fallback) / 'openai'."
            ) from exc
        try:
            self._model = SentenceTransformer(self.model_name, device=self.device)
        except Exception as exc:  # offline / weights missing / OOM ...
            if strict:
                raise RuntimeError(
                    f"Failed to load sentence-transformers model {self.model_name!r}: {exc}"
                ) from exc
            self._model = None
            self.degraded = True
            self.degraded_reason = f"model load failed: {exc}"
            logger.warning(
                "SentenceTransformerEmbeddingModel degraded: cannot load %r (%s); "
                "falling back to %s (hash-based, non-semantic).",
                self.model_name,
                exc,
                type(self._fallback).__name__,
            )

    @property
    def dimensions(self) -> int:
        if self._model is not None:
            dim = self._model.get_sentence_embedding_dimension()
            if dim:
                return int(dim)
        return getattr(self._fallback, "dimensions", 0) or 0

    def embed(self, text: str) -> list[float]:
        if self._model is None:
            result = self._fallback.embed(text)
            if hasattr(result, "__await__"):
                raise RuntimeError("async fallback models are not supported here")
            return list(result)  # type: ignore[arg-type]
        vector = self._model.encode(text, normalize_embeddings=True)
        return [float(value) for value in vector]


class OpenAIEmbeddingModel:
    """Embeddings via any OpenAI-compatible embeddings API.

    ``base_url`` makes it config-driven for compatible providers (vLLM, Ollama,
    SiliconFlow, Azure proxies, ...). Defaults to the official OpenAI endpoint.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: int | None = None,
        base_url: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.base_url = base_url or os.getenv("XAGENT_OPENAI_BASE_URL") or None
        self._client = client

    async def embed(self, text: str) -> list[float]:
        client = self._client
        if client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:  # pragma: no cover - dependency exists in project deps
                raise RuntimeError("openai package is not installed") from exc
            kwargs: dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            client = AsyncOpenAI(**kwargs)

        request: dict[str, Any] = {"model": self.model, "input": text}
        if self.dimensions is not None:
            request["dimensions"] = self.dimensions
        response = await client.embeddings.create(**request)
        return list(response.data[0].embedding)


def build_embedding_model(
    *,
    embedding_backend: str = "auto",
    openai_api_key: str | None = None,
    openai_embedding_model: str = "text-embedding-3-small",
    openai_embedding_dimensions: int | None = None,
    openai_base_url: str | None = None,
    st_model: str | None = None,
    st_device: str | None = None,
    strict: bool = False,
) -> EmbeddingModel:
    """Build an embedding model for the given backend.

    Backends:
    - ``"auto"``: try OpenAI (if API key set) → sentence-transformers (if
      installed) → deterministic hash fallback. Never raises for missing
      optional deps; degradation is logged.
    - ``"local"`` / ``"hash"``: deterministic hash pseudo-embedding (OFFLINE
      FALLBACK, non-semantic). Kept for tests and offline development.
    - ``"sentence-transformers"`` (aliases ``"sentence_transformers"``,
      ``"st"``, ``"local-st"``): real local embeddings; needs the optional
      ``sentence-transformers`` package. When weights cannot be loaded it
      degrades explicitly (see :class:`SentenceTransformerEmbeddingModel`).
    - ``"openai"``: OpenAI-compatible embeddings API; requires an API key and
      honors ``openai_base_url`` / ``XAGENT_OPENAI_BASE_URL``.

    Unknown backends raise ``ValueError`` (never silently fall through).
    """
    backend = (embedding_backend or "auto").strip().lower()
    if backend == "auto":
        return _build_auto_embedding_model(
            openai_api_key=openai_api_key,
            openai_embedding_model=openai_embedding_model,
            openai_embedding_dimensions=openai_embedding_dimensions,
            openai_base_url=openai_base_url,
            st_model=st_model,
            st_device=st_device,
        )
    if backend in {"local", "hash", "deterministic"}:
        if backend == "local":
            logger.info(
                "embedding_backend='local' -> DeterministicEmbeddingModel "
                "(hash-based OFFLINE fallback, non-semantic)."
            )
        return DeterministicEmbeddingModel()
    if backend in {"sentence-transformers", "sentence_transformers", "st", "local-st"}:
        return SentenceTransformerEmbeddingModel(
            model_name=st_model,
            device=st_device,
            strict=strict,
        )
    if backend == "openai":
        if not openai_api_key:
            raise ValueError("XAGENT_OPENAI_API_KEY or OPENAI_API_KEY is required for embeddings.")
        return OpenAIEmbeddingModel(
            api_key=openai_api_key,
            model=openai_embedding_model,
            dimensions=openai_embedding_dimensions,
            base_url=openai_base_url,
        )
    raise ValueError(
        f"Unknown embedding_backend: {embedding_backend!r}. "
        "Valid backends: 'auto', 'local' (hash fallback), 'sentence-transformers', 'openai'."
    )


def _build_auto_embedding_model(
    *,
    openai_api_key: str | None = None,
    openai_embedding_model: str = "text-embedding-3-small",
    openai_embedding_dimensions: int | None = None,
    openai_base_url: str | None = None,
    st_model: str | None = None,
    st_device: str | None = None,
) -> EmbeddingModel:
    """Auto-detect the best available embedding backend.

    Priority: OpenAI (if key set) → sentence-transformers (if installed) →
    deterministic hash fallback. Degradation is always logged, never silent.
    """
    # 1. Try OpenAI if API key is available
    api_key = openai_api_key or os.getenv("XAGENT_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if api_key:
        logger.info(
            "embedding_backend='auto' -> OpenAI embeddings (model=%s).",
            openai_embedding_model,
        )
        return OpenAIEmbeddingModel(
            api_key=api_key,
            model=openai_embedding_model,
            dimensions=openai_embedding_dimensions,
            base_url=openai_base_url,
        )

    # 2. Try sentence-transformers if installed
    try:
        import sentence_transformers  # noqa: F401

        logger.info(
            "embedding_backend='auto' -> sentence-transformers (local semantic)."
        )
        return SentenceTransformerEmbeddingModel(
            model_name=st_model,
            device=st_device,
            strict=False,
        )
    except ImportError:
        pass

    # 3. Fallback to deterministic hash
    logger.info(
        "embedding_backend='auto' -> DeterministicEmbeddingModel "
        "(hash-based fallback; no OpenAI key, sentence-transformers not installed)."
    )
    return DeterministicEmbeddingModel()


# ---------------------------------------------------------------------------
# EmbeddingProvider — unified async interface with batch support (P1-13)
# ---------------------------------------------------------------------------


class EmbeddingProvider:
    """Unified embedding provider with auto-detection and batch support.

    Wraps the backend-specific models behind a single async interface.
    Supports:
    - ``"openai"`` → OpenAI embeddings API
    - ``"local"`` / ``"sentence-transformers"`` → local sentence-transformers
    - ``"hash"`` → deterministic hash-based pseudo-embedding (offline fallback)
    - ``"auto"`` → try openai if key set, else local, else hash

    Usage::

        provider = EmbeddingProvider(backend="auto")
        vec = await provider.embed("hello world")
        vecs = await provider.embed_batch(["hello", "world"])
    """

    def __init__(
        self,
        backend: str = "auto",
        *,
        model: str | None = None,
        dimensions: int | None = None,
        openai_api_key: str | None = None,
        openai_base_url: str | None = None,
        batch_size: int = 32,
    ) -> None:
        self.backend = backend
        self.model_name = model or os.getenv(
            "XAGENT_EMBEDDING_MODEL", "text-embedding-3-small"
        )
        self.dimensions = dimensions or int(
            os.getenv("XAGENT_EMBEDDING_DIM", "384")
        )
        self.batch_size = batch_size
        self._openai_api_key = openai_api_key
        self._openai_base_url = openai_base_url
        self._model: EmbeddingModel | None = None
        self._resolved_backend: str = "unknown"

    @property
    def resolved_backend(self) -> str:
        """The actual backend in use after auto-resolution."""
        if self._model is None:
            self._resolve()
        return self._resolved_backend

    def _resolve(self) -> None:
        """Lazily resolve the backend model."""
        if self._model is not None:
            return
        openai_dims = self.dimensions if self.model_name.startswith("text-embedding-3") else None
        self._model = build_embedding_model(
            embedding_backend=self.backend,
            openai_api_key=self._openai_api_key,
            openai_embedding_model=self.model_name,
            openai_embedding_dimensions=openai_dims,
            openai_base_url=self._openai_base_url,
        )
        # Track what was actually resolved
        if isinstance(self._model, OpenAIEmbeddingModel):
            self._resolved_backend = "openai"
        elif isinstance(self._model, SentenceTransformerEmbeddingModel):
            self._resolved_backend = "sentence-transformers"
        else:
            self._resolved_backend = "hash"

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string into a vector."""
        self._resolve()
        assert self._model is not None
        result = self._model.embed(text)
        if isinstance(result, list):
            return result
        return await result  # type: ignore[misc]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts, respecting batch_size for API backends."""
        if not texts:
            return []
        self._resolve()
        assert self._model is not None

        # For OpenAI backend, use native batch API
        if isinstance(self._model, OpenAIEmbeddingModel):
            return await self._openai_batch_embed(texts)

        # For local/hash backends, process sequentially (or in parallel for ST)
        results: list[list[float]] = []
        for text in texts:
            result = self._model.embed(text)
            if isinstance(result, list):
                results.append(result)
            else:
                results.append(await result)  # type: ignore[misc]
        return results

    async def _openai_batch_embed(self, texts: list[str]) -> list[list[float]]:
        """Batch embed via OpenAI API with chunking."""
        model = self._model
        assert isinstance(model, OpenAIEmbeddingModel)

        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed") from exc

        kwargs: dict[str, Any] = {"api_key": model.api_key}
        if model.base_url:
            kwargs["base_url"] = model.base_url
        client = AsyncOpenAI(**kwargs)

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            chunk = texts[i : i + self.batch_size]
            request: dict[str, Any] = {"model": model.model, "input": chunk}
            if model.dimensions is not None:
                request["dimensions"] = model.dimensions
            response = await client.embeddings.create(**request)
            # Sort by index to preserve order
            sorted_data = sorted(response.data, key=lambda d: d.index)
            all_embeddings.extend([list(d.embedding) for d in sorted_data])
        return all_embeddings

    def _hash_embedding(self, text: str, dim: int | None = None) -> list[float]:
        """Deterministic pseudo-embedding from text hash (fallback only).

        Same text ALWAYS produces the same vector. This is critical for
        consistency when no real embedding service is available.
        """
        dim = dim or self.dimensions
        h = hashlib.sha256(text.encode("utf-8")).digest()
        # Expand hash to fill dim dimensions deterministically
        vector: list[float] = []
        block_idx = 0
        while len(vector) < dim:
            block = hashlib.sha256(h + block_idx.to_bytes(4, "big")).digest()
            for byte in block:
                if len(vector) >= dim:
                    break
                # Map byte [0,255] to [-1.0, 1.0]
                vector.append((byte / 127.5) - 1.0)
            block_idx += 1
        # L2 normalize
        magnitude = math.sqrt(sum(v * v for v in vector))
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        return vector


# Module-level singleton (lazily initialized)
_default_provider: EmbeddingProvider | None = None


def get_embedding_provider(
    backend: str | None = None,
    model: str | None = None,
    dimensions: int | None = None,
) -> EmbeddingProvider:
    """Get or create the module-level EmbeddingProvider singleton.

    Reads defaults from environment:
    - XAGENT_EMBEDDING_BACKEND (default: "auto")
    - XAGENT_EMBEDDING_MODEL (default: "text-embedding-3-small")
    - XAGENT_EMBEDDING_DIM (default: 384)
    """
    global _default_provider
    if _default_provider is None or backend is not None:
        _default_provider = EmbeddingProvider(
            backend=backend or os.getenv("XAGENT_EMBEDDING_BACKEND", "auto"),
            model=model,
            dimensions=dimensions,
        )
    return _default_provider
