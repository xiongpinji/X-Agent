"""Analytics system integration example."""

from fastapi import FastAPI
from contextlib import asynccontextmanager

from backend.app.core.analytics import (
    AnalyticsCollector,
    AnalyticsStorage,
    AnalyticsAggregator,
    AnalyticsReporter,
)
from backend.app.core.analytics.middleware import AnalyticsMiddleware
from backend.app.core.analytics.config import AnalyticsConfig
from backend.app.settings import get_settings


class AnalyticsSystem:
    """Integrated analytics system for X-Agent."""

    def __init__(self, config: AnalyticsConfig):
        """Initialize analytics system.

        Args:
            config: Analytics configuration
        """
        self.config = config
        self.collector = AnalyticsCollector(
            buffer_size=config.collector_buffer_size,
            flush_interval_seconds=config.collector_flush_interval_seconds,
        )
        self.storage = AnalyticsStorage(config.database_url)
        self.aggregator = AnalyticsAggregator(self.storage)
        self.reporter = AnalyticsReporter(self.aggregator)

    async def initialize(self) -> None:
        """Initialize analytics system."""
        await self.storage.initialize()
        await self.collector.start()

    async def shutdown(self) -> None:
        """Shutdown analytics system."""
        await self.collector.stop()
        await self.storage.close()

    def get_middleware(self) -> AnalyticsMiddleware:
        """Get analytics middleware.

        Returns:
            Analytics middleware
        """
        return AnalyticsMiddleware(None, self.collector)


# Global analytics system instance
_analytics_system: AnalyticsSystem | None = None


def get_analytics_system() -> AnalyticsSystem:
    """Get global analytics system instance.

    Returns:
        Analytics system instance
    """
    global _analytics_system
    if _analytics_system is None:
        settings = get_settings()
        config = AnalyticsConfig(database_url=settings.database_url)
        _analytics_system = AnalyticsSystem(config)
    return _analytics_system


def setup_analytics(app: FastAPI) -> None:
    """Setup analytics for FastAPI application.

    Args:
        app: FastAPI application
    """
    analytics = get_analytics_system()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        await analytics.initialize()
        yield
        # Shutdown
        await analytics.shutdown()

    app.router.lifespan_context = lifespan

    # Add middleware
    app.add_middleware(AnalyticsMiddleware, collector=analytics.collector)


# Example usage in main application
def create_app() -> FastAPI:
    """Create FastAPI application with analytics.

    Returns:
        FastAPI application
    """
    app = FastAPI(title="X-Agent API")

    # Setup analytics
    setup_analytics(app)

    # Include analytics routes
    from backend.app.api.analytics import router as analytics_router

    app.include_router(analytics_router)

    return app


if __name__ == "__main__":
    import uvicorn

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
