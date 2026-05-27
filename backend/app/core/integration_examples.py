"""
Integration examples for X-Agent architecture optimization modules.

This file demonstrates how to integrate the new architecture modules
into existing X-Agent services.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import Depends, FastAPI

# Import new architecture modules
from backend.app.core.cache import get_cache_manager, cached
from backend.app.core.concurrency import (
    ConnectionPool,
    ConcurrencyLimiter,
    TaskQueue,
    get_resource_monitor,
)
from backend.app.core.config_management import get_config_manager, get_config
from backend.app.core.error_handling import (
    CircuitBreaker,
    ExponentialBackoffRetry,
    ExternalServiceError,
    get_error_tracker,
)
from backend.app.core.event_bus import Event, EventType, get_event_bus
from backend.app.core.middleware import (
    CachingMiddleware,
    ErrorHandlingMiddleware,
    PerformanceMonitoringMiddleware,
    RequestContextMiddleware,
    StructuredLoggingMiddleware,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 1. Event Bus Integration Examples
# ============================================================================


class EventBusIntegration:
    """Examples of integrating event bus into services."""

    @staticmethod
    async def setup_event_handlers() -> None:
        """Setup event handlers for various events."""
        event_bus = get_event_bus()

        # Handler for agent completion
        async def on_agent_completed(event: Event) -> None:
            logger.info(f"Agent completed: {event.data}")
            # Could trigger notifications, update UI, etc.

        # Handler for errors
        async def on_system_error(event: Event) -> None:
            logger.error(f"System error: {event.data}")
            # Could trigger alerts, escalation, etc.

        # Subscribe handlers
        await event_bus.subscribe(EventType.AGENT_COMPLETED, on_agent_completed)
        await event_bus.subscribe(EventType.SYSTEM_ERROR, on_system_error)

    @staticmethod
    async def publish_agent_event(agent_id: str, status: str) -> None:
        """Publish an agent execution event."""
        event_bus = get_event_bus()

        event = Event(
            event_type=EventType.AGENT_STARTED if status == "started" else EventType.AGENT_COMPLETED,
            source="agent_executor",
            data={"agent_id": agent_id, "status": status},
            user_id="user_123",
            tenant_id="tenant_1",
        )

        await event_bus.publish(event)


# ============================================================================
# 2. Cache Integration Examples
# ============================================================================


class CacheIntegration:
    """Examples of integrating caching into services."""

    def __init__(self) -> None:
        self._cache_manager = get_cache_manager()

    async def get_user_with_cache(self, user_id: str) -> dict[str, Any]:
        """Get user with caching."""
        cache_key = f"user:{user_id}"

        # Try to get from cache
        cached_user = await self._cache_manager.get(cache_key)
        if cached_user is not None:
            logger.debug(f"Cache hit for user {user_id}")
            return cached_user

        # Get from database
        logger.debug(f"Cache miss for user {user_id}, fetching from DB")
        user = await self._fetch_user_from_db(user_id)

        # Store in cache (1 hour TTL)
        await self._cache_manager.set(cache_key, user, ttl=3600)

        return user

    async def invalidate_user_cache(self, user_id: str) -> None:
        """Invalidate user cache."""
        cache_key = f"user:{user_id}"
        await self._cache_manager.delete(cache_key)
        logger.info(f"Invalidated cache for user {user_id}")

    @staticmethod
    async def _fetch_user_from_db(user_id: str) -> dict[str, Any]:
        """Fetch user from database (mock)."""
        await asyncio.sleep(0.1)  # Simulate DB query
        return {"id": user_id, "name": f"User {user_id}"}


# ============================================================================
# 3. Concurrency Control Integration Examples
# ============================================================================


class ConcurrencyIntegration:
    """Examples of integrating concurrency control."""

    def __init__(self) -> None:
        self._agent_limiter = ConcurrencyLimiter(max_concurrent=10)
        self._workflow_limiter = ConcurrencyLimiter(max_concurrent=5)
        self._resource_monitor = get_resource_monitor()

    async def run_agent_with_limit(self, agent_id: str) -> Any:
        """Run agent with concurrency limiting."""
        async def agent_task() -> Any:
            logger.info(f"Running agent {agent_id}")
            await asyncio.sleep(1)  # Simulate agent execution
            return {"agent_id": agent_id, "result": "success"}

        return await self._agent_limiter.run(agent_task())

    async def setup_connection_pool(self) -> ConnectionPool:
        """Setup database connection pool."""

        async def create_connection() -> Any:
            # Mock connection creation
            return {"connection": "mock_db_connection"}

        pool = ConnectionPool(
            factory=create_connection,
            min_size=5,
            max_size=20,
            timeout=30.0,
        )

        await pool.initialize()
        await self._resource_monitor.register_pool("db_pool", pool)

        return pool

    def get_resource_stats(self) -> dict[str, Any]:
        """Get resource usage statistics."""
        return self._resource_monitor.get_report()


# ============================================================================
# 4. Error Handling Integration Examples
# ============================================================================


class ErrorHandlingIntegration:
    """Examples of integrating error handling."""

    def __init__(self) -> None:
        self._retry_strategy = ExponentialBackoffRetry(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=60.0,
        )
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0,
        )
        self._error_tracker = get_error_tracker()

    async def call_external_service_with_retry(self, service_url: str) -> Any:
        """Call external service with retry logic."""

        async def service_call() -> Any:
            logger.info(f"Calling external service: {service_url}")
            # Simulate service call
            return {"status": "success"}

        try:
            return await self._retry_strategy.execute(service_call)
        except Exception as e:
            await self._error_tracker.record(e)
            raise

    async def call_external_service_with_circuit_breaker(self, service_url: str) -> Any:
        """Call external service with circuit breaker."""

        async def service_call() -> Any:
            logger.info(f"Calling external service: {service_url}")
            # Simulate service call
            return {"status": "success"}

        try:
            return await self._circuit_breaker.call(service_call)
        except ExternalServiceError:
            logger.warning("Circuit breaker is open, using fallback")
            return {"status": "fallback"}

    def get_error_stats(self) -> dict[str, Any]:
        """Get error statistics."""
        return self._error_tracker.get_stats()


# ============================================================================
# 5. Configuration Management Integration Examples
# ============================================================================


class ConfigurationIntegration:
    """Examples of integrating configuration management."""

    @staticmethod
    def setup_configuration(app_mode: str = "development") -> None:
        """Setup application configuration."""
        config_manager = get_config_manager()
        config = config_manager.load(app_mode=app_mode)

        logger.info(f"Configuration loaded for mode: {app_mode}")
        logger.info(f"Database backend: {config.database.backend}")
        logger.info(f"Cache backend: {config.cache.backend}")
        logger.info(f"LLM backend: {config.llm.backend}")

    @staticmethod
    def get_database_config() -> dict[str, Any]:
        """Get database configuration."""
        config = get_config()
        return {
            "backend": config.database.backend,
            "url": config.database.url,
            "pool_size": config.database.pool_size,
        }

    @staticmethod
    def get_cache_config() -> dict[str, Any]:
        """Get cache configuration."""
        config = get_config()
        return {
            "backend": config.cache.backend,
            "redis_url": config.cache.redis_url,
            "memory_cache_size": config.cache.memory_cache_size,
        }


# ============================================================================
# 6. Middleware Integration Examples
# ============================================================================


def setup_middleware(app: FastAPI) -> None:
    """Setup middleware for FastAPI application."""
    # Add middleware in reverse order (last added is first executed)
    app.add_middleware(RateLimitingMiddleware, requests_per_minute=60)
    app.add_middleware(CachingMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(PerformanceMonitoringMiddleware)
    app.add_middleware(StructuredLoggingMiddleware)
    app.add_middleware(RequestContextMiddleware)

    logger.info("Middleware stack configured")


# ============================================================================
# 7. Complete Integration Example
# ============================================================================


class XAgentArchitectureIntegration:
    """Complete integration of all architecture modules."""

    def __init__(self) -> None:
        self._event_bus_integration = EventBusIntegration()
        self._cache_integration = CacheIntegration()
        self._concurrency_integration = ConcurrencyIntegration()
        self._error_handling_integration = ErrorHandlingIntegration()
        self._config_integration = ConfigurationIntegration()

    async def initialize(self, app_mode: str = "development") -> None:
        """Initialize all architecture components."""
        logger.info("Initializing X-Agent architecture components...")

        # Setup configuration
        self._config_integration.setup_configuration(app_mode)

        # Setup event handlers
        await self._event_bus_integration.setup_event_handlers()

        # Setup connection pool
        await self._concurrency_integration.setup_connection_pool()

        logger.info("X-Agent architecture components initialized")

    async def run_agent_with_full_integration(self, agent_id: str) -> Any:
        """Run agent with full architecture integration."""
        event_bus = get_event_bus()

        try:
            # Publish agent started event
            await event_bus.publish(
                Event(
                    event_type=EventType.AGENT_STARTED,
                    source="integration_example",
                    data={"agent_id": agent_id},
                )
            )

            # Run agent with concurrency limiting
            result = await self._concurrency_integration.run_agent_with_limit(agent_id)

            # Publish agent completed event
            await event_bus.publish(
                Event(
                    event_type=EventType.AGENT_COMPLETED,
                    source="integration_example",
                    data={"agent_id": agent_id, "result": result},
                )
            )

            return result

        except Exception as e:
            # Record error
            await self._error_handling_integration._error_tracker.record(e)

            # Publish error event
            await event_bus.publish(
                Event(
                    event_type=EventType.AGENT_FAILED,
                    source="integration_example",
                    data={"agent_id": agent_id, "error": str(e)},
                )
            )

            raise

    def get_system_stats(self) -> dict[str, Any]:
        """Get system statistics."""
        return {
            "resources": self._concurrency_integration.get_resource_stats(),
            "errors": self._error_handling_integration.get_error_stats(),
            "database": self._config_integration.get_database_config(),
            "cache": self._config_integration.get_cache_config(),
        }


# ============================================================================
# 8. FastAPI Application Setup Example
# ============================================================================


async def setup_xagent_app(app: FastAPI, app_mode: str = "development") -> None:
    """Setup X-Agent FastAPI application with all architecture components."""

    # Initialize architecture integration
    integration = XAgentArchitectureIntegration()
    await integration.initialize(app_mode)

    # Setup middleware
    setup_middleware(app)

    # Store integration in app state for use in routes
    app.state.integration = integration

    # Add system stats endpoint
    @app.get("/api/v1/system/stats")
    async def get_system_stats() -> dict[str, Any]:
        """Get system statistics."""
        return integration.get_system_stats()

    # Add health check endpoint
    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}

    logger.info("X-Agent FastAPI application setup complete")


# ============================================================================
# Usage Example
# ============================================================================

if __name__ == "__main__":
    # Example usage
    async def main() -> None:
        # Create FastAPI app
        app = FastAPI(title="X-Agent")

        # Setup with architecture components
        await setup_xagent_app(app, app_mode="development")

        # Example: Run agent
        integration = app.state.integration
        result = await integration.run_agent_with_full_integration("agent_123")
        print(f"Agent result: {result}")

        # Example: Get system stats
        stats = integration.get_system_stats()
        print(f"System stats: {stats}")

    asyncio.run(main())
