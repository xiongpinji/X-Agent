"""
Base middleware interface and chain pattern.

Provides:
- Abstract base class for all middleware
- Middleware chain for composing multiple middleware
- Async-first design with minimal overhead
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class BaseMiddleware(BaseHTTPMiddleware, ABC):
    """
    Abstract base class for all middleware.

    Provides:
    - Consistent interface for all middleware
    - Logging and error handling
    - Configuration support
    """

    def __init__(self, app: Any, enabled: bool = True, **config: Any) -> None:
        """
        Initialize middleware.

        Args:
            app: ASGI application
            enabled: Whether middleware is enabled
            **config: Middleware-specific configuration
        """
        super().__init__(app)
        self.enabled = enabled
        self.config = config
        self.logger = logging.getLogger(self.__class__.__module__)

    @abstractmethod
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and response.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        pass

    def is_enabled(self) -> bool:
        """Check if middleware is enabled."""
        return self.enabled

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)


class MiddlewareChain:
    """
    Chain multiple middleware together.

    Provides:
    - Fluent API for adding middleware
    - Ordered execution
    - Error handling and logging
    """

    def __init__(self) -> None:
        """Initialize middleware chain."""
        self._middlewares: list[tuple[BaseMiddleware, bool]] = []
        self.logger = logging.getLogger(__name__)

    def add(
        self,
        middleware: BaseMiddleware,
        enabled: bool = True,
    ) -> MiddlewareChain:
        """
        Add middleware to chain.

        Args:
            middleware: Middleware instance
            enabled: Whether to execute this middleware

        Returns:
            Self for chaining
        """
        self._middlewares.append((middleware, enabled))
        self.logger.debug(
            f"Added middleware: {middleware.__class__.__name__} (enabled={enabled})"
        )
        return self

    async def execute(self, request: Request, call_next: Callable) -> Response:
        """
        Execute middleware chain.

        Args:
            request: HTTP request
            call_next: Final handler

        Returns:
            HTTP response
        """
        if not self._middlewares:
            return await call_next(request)

        async def chain(index: int) -> Response:
            if index >= len(self._middlewares):
                return await call_next(request)

            middleware, enabled = self._middlewares[index]

            if not enabled or not middleware.is_enabled():
                # Skip disabled middleware
                return await chain(index + 1)

            try:
                # Execute middleware
                return await middleware.dispatch(request, lambda: chain(index + 1))
            except Exception as e:
                self.logger.error(
                    f"Error in middleware {middleware.__class__.__name__}: {e}",
                    exc_info=True,
                )
                raise

        return await chain(0)

    def get_stats(self) -> dict[str, Any]:
        """Get chain statistics."""
        return {
            "total_middleware": len(self._middlewares),
            "enabled_middleware": sum(1 for _, enabled in self._middlewares if enabled),
            "middleware_list": [
                {
                    "name": middleware.__class__.__name__,
                    "enabled": enabled and middleware.is_enabled(),
                }
                for middleware, enabled in self._middlewares
            ],
        }
