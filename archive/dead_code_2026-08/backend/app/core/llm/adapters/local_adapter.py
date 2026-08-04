"""Local LLM adapter for running models locally."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from .base import AdapterResponse, LLMAdapter


class LocalAdapter(LLMAdapter):
    """Adapter for local LLM models."""

    def __init__(
        self,
        model: str,
        model_path: str | None = None,
        **kwargs,
    ):
        """Initialize local adapter."""
        super().__init__(model, **kwargs)
        self.model_path = model_path
        self._pipeline = None

    def _get_pipeline(self):
        """Get or create local model pipeline."""
        if self._pipeline is None:
            try:
                from transformers import pipeline
            except ImportError:
                raise ImportError("transformers package is required for local models")

            self._pipeline = pipeline(
                "text-generation",
                model=self.model_path or self.model,
                device=0,  # GPU device
            )

        return self._pipeline

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> AdapterResponse:
        """Send a chat request to local model."""
        start_time = time.time()

        try:
            # Convert messages to prompt
            prompt = self._messages_to_prompt(messages)

            # Get pipeline
            pipeline = self._get_pipeline()

            # Generate response
            outputs = pipeline(
                prompt,
                max_new_tokens=kwargs.get("max_tokens", 512),
                temperature=kwargs.get("temperature", 0.7),
                do_sample=True,
            )

            # Extract response
            response_text = outputs[0]["generated_text"]
            content = response_text.replace(prompt, "").strip()

            # Estimate tokens
            tokens_used = len(content.split())

            latency_ms = (time.time() - start_time) * 1000

            return AdapterResponse(
                content=content,
                tool_calls=[],
                tokens_used=tokens_used,
                model=self.model,
                latency_ms=latency_ms,
            )

        except Exception as e:
            raise RuntimeError(f"Local model error: {e}")

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream a chat response from local model."""
        try:
            prompt = self._messages_to_prompt(messages)
            pipeline = self._get_pipeline()

            # For local models, we'll simulate streaming
            outputs = pipeline(
                prompt,
                max_new_tokens=kwargs.get("max_tokens", 512),
                temperature=kwargs.get("temperature", 0.7),
                do_sample=True,
            )

            response_text = outputs[0]["generated_text"]
            content = response_text.replace(prompt, "").strip()

            # Simulate streaming by yielding words
            for word in content.split():
                yield word + " "

        except Exception as e:
            raise RuntimeError(f"Local model streaming error: {e}")

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for local models."""
        return max(1, len(text.split()))

    def get_model_info(self) -> dict[str, Any]:
        """Get local model information."""
        return {
            "max_tokens": 2048,
            "cost_per_1k_input": 0.0,  # Free for local models
            "cost_per_1k_output": 0.0,
            "local": True,
        }

    def _messages_to_prompt(self, messages: list[dict[str, str]]) -> str:
        """Convert messages to prompt format."""
        prompt_parts = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
            elif role == "tool":
                prompt_parts.append(f"Tool: {content}")

        prompt_parts.append("Assistant:")
        return "\n".join(prompt_parts)
