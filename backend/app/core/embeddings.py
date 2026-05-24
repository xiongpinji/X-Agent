from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Awaitable
from hashlib import sha256
from typing import Any, Protocol


class EmbeddingModel(Protocol):
    def embed(self, text: str) -> list[float] | Awaitable[list[float]]:
        """Return a deterministic vector for local retrieval."""


class DeterministicEmbeddingModel:
    """Dependency-free embedding model for local tests and offline development.

    It is not a replacement for production embeddings, but it gives the memory layer
    a stable vector contract that can later be backed by OpenAI, pgvector, or another
    provider without changing callers.
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


class OpenAIEmbeddingModel:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: int | None = None,
        client: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self._client = client

    async def embed(self, text: str) -> list[float]:
        client = self._client
        if client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:  # pragma: no cover - dependency exists in project deps
                raise RuntimeError("openai package is not installed") from exc
            client = AsyncOpenAI(api_key=self.api_key)

        request: dict[str, Any] = {"model": self.model, "input": text}
        if self.dimensions is not None:
            request["dimensions"] = self.dimensions
        response = await client.embeddings.create(**request)
        return list(response.data[0].embedding)


def build_embedding_model(
    *,
    embedding_backend: str = "local",
    openai_api_key: str | None = None,
    openai_embedding_model: str = "text-embedding-3-small",
    openai_embedding_dimensions: int | None = None,
) -> EmbeddingModel:
    if embedding_backend == "openai":
        if not openai_api_key:
            raise ValueError("XAGENT_OPENAI_API_KEY or OPENAI_API_KEY is required for embeddings.")
        return OpenAIEmbeddingModel(
            api_key=openai_api_key,
            model=openai_embedding_model,
            dimensions=openai_embedding_dimensions,
        )
    return DeterministicEmbeddingModel()
