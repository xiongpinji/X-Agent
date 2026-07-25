"""Application lifecycle manager — startup/shutdown orchestration.

Provides production-grade graceful shutdown with:
- Drain period for load-balancer detection (health → 503)
- Active-request tracking with configurable timeout
- Ordered teardown of all service connections (reverse dependency order)
- Signal handling for SIGTERM/SIGINT (Unix) and Ctrl+C (Windows)
"""

from __future__ import annotations

import asyncio
import logging
import signal
import time
from contextlib import suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger("xagent.lifecycle")


class LifecycleManager:
    """Orchestrates application startup and graceful shutdown.

    Shutdown sequence (reverse dependency order):
        1. Signal: stop accepting new work (health → 503 "draining")
        2. Wait for active in-flight requests (up to timeout)
        3. Flush audit buffers
        4. Close MCP connections
        5. Close Qdrant client
        6. Close Redis pool
        7. Close DB pool / engine
        8. Flush OTel spans/metrics
    """

    def __init__(self) -> None:
        self._shutdown_event = asyncio.Event()
        self._active_requests: int = 0
        self._lock = asyncio.Lock()
        self._started_at: float = 0.0
        self._shutdown_at: float = 0.0
        self._app: FastAPI | None = None

    # ─── Public API ────────────────────────────────────────────────────────────

    @property
    def is_shutting_down(self) -> bool:
        """Whether the application is in the process of shutting down."""
        return self._shutdown_event.is_set()

    @property
    def active_requests(self) -> int:
        """Number of currently in-flight requests."""
        return self._active_requests

    @property
    def uptime_seconds(self) -> float:
        """Seconds since application startup."""
        if self._started_at == 0.0:
            return 0.0
        return time.monotonic() - self._started_at

    def track_request_start(self) -> None:
        """Increment active request counter (called by middleware)."""
        self._active_requests += 1

    def track_request_end(self) -> None:
        """Decrement active request counter (called by middleware)."""
        self._active_requests = max(0, self._active_requests - 1)

    async def on_startup(self, app: FastAPI) -> None:
        """Initialize lifecycle tracking and install signal handlers.

        Called during the FastAPI startup event. Sets up signal handlers
        for graceful shutdown on SIGTERM/SIGINT.
        """
        self._app = app
        self._started_at = time.monotonic()
        self._shutdown_event.clear()
        self._install_signal_handlers()
        logger.info("LifecycleManager started — graceful shutdown armed")

    async def on_shutdown(self, timeout: float = 30.0, drain_seconds: float = 5.0) -> None:
        """Graceful shutdown in reverse dependency order.

        Args:
            timeout: Maximum seconds to wait for in-flight requests to complete.
            drain_seconds: Seconds to wait after marking as draining, allowing
                          load balancers to detect the 503 health status and
                          stop routing new traffic.
        """
        if self._shutdown_event.is_set():
            logger.warning("Shutdown already in progress — skipping duplicate call")
            return

        self._shutdown_at = time.monotonic()
        self._shutdown_event.set()
        logger.info(
            "Graceful shutdown initiated (timeout=%.1fs, drain=%.1fs, active_requests=%d)",
            timeout, drain_seconds, self._active_requests,
        )

        # Phase 1: Drain period — health returns 503, LBs stop routing
        if drain_seconds > 0:
            logger.info("Drain phase: waiting %.1fs for load balancer detection", drain_seconds)
            await asyncio.sleep(drain_seconds)

        # Phase 2: Wait for in-flight requests to complete
        await self._wait_for_requests(timeout)

        # Phase 3: Teardown services in reverse dependency order
        await self._teardown_services()

        elapsed = time.monotonic() - self._shutdown_at
        logger.info("Graceful shutdown complete (%.2fs elapsed)", elapsed)

    # ─── Internal ──────────────────────────────────────────────────────────────

    async def _wait_for_requests(self, timeout: float) -> None:
        """Wait for active requests to drain, up to timeout seconds."""
        if self._active_requests == 0:
            logger.info("No in-flight requests — proceeding with teardown")
            return

        logger.info("Waiting for %d in-flight request(s) to complete (timeout=%.1fs)",
                    self._active_requests, timeout)
        deadline = time.monotonic() + timeout
        poll_interval = 0.25

        while self._active_requests > 0:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.warning(
                    "Shutdown timeout reached with %d request(s) still active — forcing shutdown",
                    self._active_requests,
                )
                break
            await asyncio.sleep(min(poll_interval, remaining))

        if self._active_requests == 0:
            logger.info("All in-flight requests completed")

    async def _teardown_services(self) -> None:
        """Tear down all services in reverse dependency order."""
        app = self._app
        if app is None:
            return

        # 1. Flush audit buffers
        await self._shutdown_audit_shipper(app)

        # 2. Close MCP connections
        await self._shutdown_mcp()

        # 3. Stop sandbox worker
        await self._shutdown_sandbox_worker()

        # 4. Close Qdrant (if applicable)
        await self._shutdown_qdrant()

        # 5. Close Redis
        await self._shutdown_redis()

        # 6. Close DB pool
        await self._shutdown_database()

        # 7. Flush OTel
        await self._shutdown_otel(app)

    async def _shutdown_audit_shipper(self, app: FastAPI) -> None:
        """Flush and stop the audit shipper."""
        try:
            from backend.app.dependencies import set_audit_shipper

            shipper = getattr(app.state, "audit_shipper", None)
            if shipper:
                await shipper.stop()
                set_audit_shipper(None)
                logger.info("Audit shipper flushed and stopped")
        except Exception as e:
            logger.error("Error during audit shipper shutdown: %s", e, exc_info=True)

    async def _shutdown_mcp(self) -> None:
        """Close all MCP server connections."""
        try:
            from backend.app.core.mcp.manager import shutdown_mcp_manager

            await shutdown_mcp_manager()
            logger.info("MCP manager shutdown complete")
        except Exception as e:
            logger.error("Error during MCP manager shutdown: %s", e, exc_info=True)

    async def _shutdown_sandbox_worker(self) -> None:
        """Stop the sandbox background worker."""
        try:
            from backend.app.api.sandbox_tasks import stop_sandbox_worker

            await stop_sandbox_worker()
            logger.info("Sandbox worker stopped")
        except Exception as e:
            logger.error("Error during sandbox worker shutdown: %s", e, exc_info=True)

    async def _shutdown_qdrant(self) -> None:
        """Close Qdrant client if connected."""
        try:
            from backend.app.services.memory.qdrant_client import vector_client

            if hasattr(vector_client, "close") and vector_client.has_real_client:
                await vector_client.close()
                logger.info("Qdrant client closed")
        except Exception as e:
            logger.debug("Qdrant shutdown skipped: %s", e)

    async def _shutdown_redis(self) -> None:
        """Close Redis connection pool."""
        try:
            from backend.app.core.redis_client import close_redis

            await close_redis()
            logger.info("Redis connection pool closed")
        except Exception as e:
            logger.debug("Redis shutdown: %s", e)

    async def _shutdown_database(self) -> None:
        """Dispose database engine/pool."""
        try:
            from backend.app.core.database import _db_manager

            if _db_manager is not None:
                await _db_manager.close()
                logger.info("Database pool disposed")
        except Exception as e:
            logger.debug("Database shutdown: %s", e)

    async def _shutdown_otel(self, app: FastAPI) -> None:
        """Flush OpenTelemetry spans and metrics."""
        try:
            otel = getattr(app.state, "otel_exporter", None)
            if otel and otel.is_active:
                from opentelemetry import metrics as _otel_metrics
                from opentelemetry import trace as _otel_trace

                provider = _otel_trace.get_tracer_provider()
                if hasattr(provider, "force_flush"):
                    provider.force_flush(timeout_millis=5000)
                meter_provider = _otel_metrics.get_meter_provider()
                if hasattr(meter_provider, "force_flush"):
                    meter_provider.force_flush(timeout_millis=5000)
                logger.info("OTel providers flushed")
        except Exception as e:
            logger.debug("OTel shutdown flush skipped: %s", e)

    def _install_signal_handlers(self) -> None:
        """Install SIGTERM/SIGINT handlers for graceful shutdown.

        On Windows, only SIGINT (Ctrl+C) is available via signal.signal.
        SIGTERM is handled by the ASGI server (uvicorn) which triggers
        the shutdown event.
        """
        loop = asyncio.get_running_loop()

        def _signal_handler(sig: int) -> None:
            logger.info("Received signal %s — initiating graceful shutdown", signal.Signals(sig).name)
            self._shutdown_event.set()

        # SIGTERM — standard container/orchestrator stop signal
        with suppress(NotImplementedError, OSError):
            loop.add_signal_handler(signal.SIGTERM, _signal_handler, signal.SIGTERM)

        # SIGINT — Ctrl+C
        with suppress(NotImplementedError, OSError):
            loop.add_signal_handler(signal.SIGINT, _signal_handler, signal.SIGINT)


# ─── Module-level singleton ────────────────────────────────────────────────────

_lifecycle_manager: LifecycleManager | None = None


def get_lifecycle_manager() -> LifecycleManager:
    """Get the global LifecycleManager singleton."""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        _lifecycle_manager = LifecycleManager()
    return _lifecycle_manager
