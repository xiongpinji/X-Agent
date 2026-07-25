"""
LLM integration with unified error handling and retry strategies.

Integrates:
- Retry mechanism for LLM calls
- Circuit breaker for service failures
- Graceful degradation with fallback
- Error monitoring
"""

from __future__ import annotations

import logging
import time
from typing import Any

from backend.app.core.circuit_breaker import CircuitBreakerConfig, get_circuit_breaker_registry
from backend.app.core.error_monitor import get_error_monitor
from backend.app.core.exceptions import (
    ErrorCode,
    NetworkError,
    ServiceUnavailableError,
)
from backend.app.core.fallback import get_degradation_policy
from backend.app.core.llm import LLMResponse, LLMRouter
from backend.app.core.retry import retry

logger = logging.getLogger(__name__)


class LLMCallError(NetworkError):
    """LLM call error."""

    def __init__(self, message: str = "LLM call failed", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.SERVICE_UNAVAILABLE,
            **kwargs,
        )


class ResilientLLMRouter:
    """LLM router with resilience features."""

    def __init__(
        self,
        router: LLMRouter,
        enable_retry: bool = True,
        enable_circuit_breaker: bool = True,
        enable_degradation: bool = True,
    ) -> None:
        self.router = router
        self.enable_retry = enable_retry
        self.enable_circuit_breaker = enable_circuit_breaker
        self.enable_degradation = enable_degradation
        self._error_monitor = get_error_monitor()
        self._degradation_policy = get_degradation_policy()
        self._circuit_breaker_registry = get_circuit_breaker_registry()
        self._circuit_breaker = None
        self._last_response_cache: dict[str, LLMResponse] = {}

    async def _get_circuit_breaker(self):
        """Get or create circuit breaker."""
        if self._circuit_breaker is None:
            config = CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=60.0,
                success_threshold=2,
            )
            self._circuit_breaker = await self._circuit_breaker_registry.get_or_create(
                "llm_router", config
            )
        return self._circuit_breaker

    @retry(
        max_attempts=3,
        initial_delay=1.0,
        max_delay=10.0,
        exponential_base=2.0,
        jitter=True,
        timeout=30.0,
        retryable_exceptions=(NetworkError,),
    )
    async def _call_with_retry(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Call LLM with retry."""
        try:
            return await self.router.chat(messages, tools)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise LLMCallError(f"LLM call failed: {e}") from e

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Call LLM with resilience features."""
        start_time = time.time()
        cache_key = self._get_cache_key(messages)

        try:
            # Try circuit breaker
            if self.enable_circuit_breaker:
                circuit_breaker = await self._get_circuit_breaker()
                if self.enable_retry:
                    response = await circuit_breaker.call(
                        self._call_with_retry, messages, tools
                    )
                else:
                    response = await circuit_breaker.call(
                        self.router.chat, messages, tools
                    )
            else:
                if self.enable_retry:
                    response = await self._call_with_retry(messages, tools)
                else:
                    response = await self.router.chat(messages, tools)

            # Cache successful response
            self._last_response_cache[cache_key] = response

            # Record success
            duration = time.time() - start_time
            await self._error_monitor.record_retry(success=True, retry_count=1)

            logger.info(f"LLM call succeeded in {duration:.2f}s")
            return response

        except ServiceUnavailableError as e:
            logger.warning(f"LLM service unavailable: {e}")

            # Try degradation
            if self.enable_degradation:
                return await self._get_degraded_response(messages, cache_key)

            raise

        except Exception as e:
            duration = time.time() - start_time
            await self._error_monitor.record_error(
                LLMCallError(str(e)),
                duration=duration,
            )

            logger.error(f"LLM call failed: {e}")

            # Try degradation
            if self.enable_degradation:
                return await self._get_degraded_response(messages, cache_key)

            raise

    async def _get_degraded_response(
        self,
        messages: list[dict[str, str]],
        cache_key: str,
    ) -> LLMResponse:
        """Get degraded response from cache or default."""
        logger.warning("Using degraded LLM response")

        # Try cache
        if cache_key in self._last_response_cache:
            logger.info("Using cached LLM response")
            return self._last_response_cache[cache_key]

        # Return minimal response
        logger.warning("Returning minimal LLM response")
        return LLMResponse(
            content="Service temporarily unavailable. Please try again.",
            tool_calls=[],
            tokens_used=0,
            model="degraded",
        )

    def _get_cache_key(self, messages: list[dict[str, str]]) -> str:
        """Generate cache key from messages."""
        # Simple hash of last user message
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return f"llm_{hash(msg.get('content', ''))}"
        return "llm_default"

    async def get_metrics(self) -> dict[str, Any]:
        """Get LLM metrics."""
        return {
            "error_stats": await self._error_monitor.get_error_stats(),
            "retry_stats": await self._error_monitor.get_retry_stats(),
            "circuit_breaker": (
                (await self._get_circuit_breaker()).get_metrics().to_dict()
                if self.enable_circuit_breaker
                else None
            ),
        }


def build_resilient_llm_router(
    router: LLMRouter,
    enable_retry: bool = True,
    enable_circuit_breaker: bool = True,
    enable_degradation: bool = True,
) -> ResilientLLMRouter:
    """Build resilient LLM router."""
    return ResilientLLMRouter(
        router,
        enable_retry=enable_retry,
        enable_circuit_breaker=enable_circuit_breaker,
        enable_degradation=enable_degradation,
    )
