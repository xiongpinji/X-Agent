"""Base LLM adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any


@dataclass
class AdapterResponse:
    """Response from LLM adapter."""

    content: str
    tool_calls: list[dict[str, Any]]
    tokens_used: int
    model: str
    latency_ms: float


class LLMAdapter(ABC):
    """Base class for LLM adapters."""

    def __init__(self, model: str, **kwargs):
        """Initialize adapter."""
        self.model = model
        self.config = kwargs

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> AdapterResponse:
        """Send a chat request."""
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream a chat response."""
        pass

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count."""
        pass

    @abstractmethod
    def get_model_info(self) -> dict[str, Any]:
        """Get model information."""
        pass
