"""
Performance Optimization Configuration and Integration Examples.

Shows how to integrate all performance optimizations into the FastAPI application.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

class PerformanceConfig:
    """Performance optimization configuration."""

    # Database Configuration
    DB_MIN_POOL_SIZE = 10
    DB_MAX_POOL_SIZE = 20
    DB_MAX_QUERIES = 50000
    DB_QUERY_TIMEOUT = 60

    # Cache Configuration
    CACHE_L1_MAX_SIZE = 1000  # In-memory cache max items
    CACHE_L2_TTL = 3600  # Redis cache TTL in seconds
    CACHE_WARM_INTERVAL = 1800  # Cache warming interval in seconds

    # API Response Configuration
    RESPONSE_COMPRESSION_MIN_SIZE = 1024  # Minimum size for compression
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    # Rate Limiting Configuration
    RATE_LIMIT_REQUESTS_PER_SECOND = 100
    RATE_LIMIT_BURST_SIZE = 200

    # Performance Monitoring Configuration
    METRICS_WINDOW_SIZE = 1000  # Number of metrics to keep
    ALERT_RESPONSE_TIME_THRESHOLD = 1.0  # seconds
    ALERT_ERROR_RATE_THRESHOLD = 5.0  # percentage
    ALERT_CACHE_HIT_THRESHOLD = 50.0  # percentage


# ============================================================================
# INTEGRATION EXAMPLE
# ============================================================================

async def setup_performance_optimizations(app: FastAPI) -> None:
    """Set up all performance optimizations for the application."""

    # 1. Setup Database Connection Pool
    logger.info("Setting up database connection pool...")
    from backend.app.core.db_optimization import DatabaseConnectionPool, QueryOptimizer

    db_pool = DatabaseConnectionPool(
        database_url="postgresql://user:password@localhost/xagent",
        min_size=PerformanceConfig.DB_MIN_POOL_SIZE,
        max_size=PerformanceConfig.DB_MAX_POOL_SIZE,
        max_queries=PerformanceConfig.DB_MAX_QUERIES,
    )
    await db_pool.initialize()

    # Add indexes
    indexes = QueryOptimizer.add_indexes(db_pool)
    for index in indexes:
        try:
            await db_pool.execute(index)
        except Exception as e:
            logger.warning(f"Index creation failed (may already exist): {e}")

    # Store in app state
    app.state.db_pool = db_pool

    # 2. Setup Multi-Level Cache
    logger.info("Setting up multi-level cache...")
    from backend.app.core.cache_optimization import (
        MultiLevelCache,
        CacheWarmer,
        CachePreloader,
    )

    # Assuming Redis client is available
    redis_client = None  # Initialize your Redis client here
    cache = MultiLevelCache(l1_cache={}, l2_cache=redis_client)
    app.state.cache = cache

    # Setup cache warming
    warmer = CacheWarmer(cache)
    app.state.cache_warmer = warmer

    # Setup cache preloader
    preloader = CachePreloader(cache)

    # Preload critical data
    async def load_workflows() -> list[dict[str, Any]]:
        # Load workflows from database
        return []

    async def load_agents() -> list[dict[str, Any]]:
        # Load agents from database
        return []

    async def load_tools() -> list[dict[str, Any]]:
        # Load tools from database
        return []

    await preloader.preload_workflows(load_workflows)
    await preloader.preload_agents(load_agents)
    await preloader.preload_tools(load_tools)

    # 3. Setup Performance Monitoring
    logger.info("Setting up performance monitoring...")
    from backend.app.core.performance_monitor import PerformanceMonitor, PerformanceAlert

    monitor = PerformanceMonitor(window_size=PerformanceConfig.METRICS_WINDOW_SIZE)
    app.state.monitor = monitor

    alert = PerformanceAlert(
        response_time_threshold=PerformanceConfig.ALERT_RESPONSE_TIME_THRESHOLD,
        error_rate_threshold=PerformanceConfig.ALERT_ERROR_RATE_THRESHOLD,
        cache_hit_threshold=PerformanceConfig.ALERT_CACHE_HIT_THRESHOLD,
    )
    app.state.alert = alert

    # 4. Add Middleware
    logger.info("Adding performance middleware...")
    from backend.app.core.performance_middleware import (
        PerformanceMonitoringMiddleware,
        ResponseCompressionMiddleware,
        CacheHeaderMiddleware,
        RequestDeduplicationMiddleware,
        RateLimitingMiddleware,
    )

    # Add middleware in reverse order (they execute in reverse order)
    app.add_middleware(
        RateLimitingMiddleware,
        requests_per_second=PerformanceConfig.RATE_LIMIT_REQUESTS_PER_SECOND,
        burst_size=PerformanceConfig.RATE_LIMIT_BURST_SIZE,
    )
    app.add_middleware(RequestDeduplicationMiddleware)
    app.add_middleware(CacheHeaderMiddleware)
    app.add_middleware(ResponseCompressionMiddleware)
    app.add_middleware(PerformanceMonitoringMiddleware)

    logger.info("Performance optimizations setup complete")


async def shutdown_performance_optimizations(app: FastAPI) -> None:
    """Clean up performance optimization resources."""
    logger.info("Shutting down performance optimizations...")

    # Close database pool
    if hasattr(app.state, "db_pool"):
        await app.state.db_pool.close()

    # Stop cache warming
    if hasattr(app.state, "cache_warmer"):
        await app.state.cache_warmer.stop_all_warming()

    logger.info("Performance optimizations shutdown complete")


# ============================================================================
# API ENDPOINT EXAMPLES WITH OPTIMIZATION
# ============================================================================

from fastapi import APIRouter, Depends, Query, Request
from backend.app.core.api_optimization import ResponseOptimizer, PaginationHelper

router = APIRouter(prefix="/api/v1", tags=["optimized"])


@router.get("/workflows")
async def list_workflows_optimized(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    fields: str | None = Query(None),
) -> dict[str, Any]:
    """List workflows with optimization."""
    # Get cache
    cache = request.app.state.cache

    # Try to get from cache
    cache_key = f"workflows:list:{page}:{page_size}"
    cached_result = await cache.get(cache_key)
    if cached_result:
        cache.stats.record_hit()
        return cached_result

    cache.stats.record_miss()

    # Fetch from database (simulated)
    workflows = [
        {"id": "1", "name": "Workflow 1", "status": "active"},
        {"id": "2", "name": "Workflow 2", "status": "inactive"},
    ]

    # Parse fields
    include_fields = fields.split(",") if fields else None

    # Build optimized response
    response = ResponseOptimizer.build_list_response(
        items=workflows,
        total=len(workflows),
        page=page,
        page_size=page_size,
        include_fields=include_fields,
    )

    # Cache response
    await cache.set(cache_key, response, ttl=300)

    return response


@router.get("/workflows/{workflow_id}")
async def get_workflow_optimized(
    request: Request,
    workflow_id: str,
    fields: str | None = Query(None),
) -> dict[str, Any]:
    """Get workflow with optimization."""
    # Get cache
    cache = request.app.state.cache

    # Try to get from cache
    cache_key = f"workflow:{workflow_id}"
    cached_result = await cache.get(cache_key)
    if cached_result:
        cache.stats.record_hit()
        return cached_result

    cache.stats.record_miss()

    # Fetch from database (simulated)
    workflow = {
        "id": workflow_id,
        "name": f"Workflow {workflow_id}",
        "status": "active",
        "nodes": [],
        "edges": [],
    }

    # Parse fields
    include_fields = fields.split(",") if fields else None

    # Build optimized response
    from backend.app.core.api_optimization import EfficientSerializer

    response = EfficientSerializer.select_fields(workflow, include_fields)

    # Cache response
    await cache.set(cache_key, response, ttl=3600)

    return response


@router.get("/memory/search")
async def search_memory_optimized(
    request: Request,
    query: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=50),
    page: int = Query(1, ge=1),
) -> dict[str, Any]:
    """Search memory with optimization."""
    # Get cache
    cache = request.app.state.cache

    # Try to get from cache
    cache_key = f"memory:search:{query}:{top_k}:{page}"
    cached_result = await cache.get(cache_key)
    if cached_result:
        cache.stats.record_hit()
        return cached_result

    cache.stats.record_miss()

    # Search memory (simulated)
    results = [
        {"id": "1", "content": f"Memory result for {query}"},
        {"id": "2", "content": f"Another result for {query}"},
    ]

    # Paginate results
    paginated = PaginationHelper.paginate(results, page, top_k)

    # Cache response
    await cache.set(cache_key, paginated, ttl=300)

    return paginated


@router.get("/performance/report")
async def get_performance_report(request: Request) -> dict[str, Any]:
    """Get performance report."""
    monitor = request.app.state.monitor

    # Get all reports
    reports = monitor.get_all_reports()

    # Convert to dict
    report_dicts = {key: report.to_dict() for key, report in reports.items()}

    return {
        "reports": report_dicts,
        "cache_stats": request.app.state.cache.get_stats(),
    }


@router.get("/performance/html-report")
async def get_performance_html_report(request: Request) -> str:
    """Get performance report as HTML."""
    from fastapi.responses import HTMLResponse

    monitor = request.app.state.monitor
    html_report = monitor.generate_html_report()

    return HTMLResponse(content=html_report)


# ============================================================================
# USAGE IN MAIN APPLICATION
# ============================================================================

"""
Example of how to use in main FastAPI application:

from fastapi import FastAPI
from backend.app.core.performance_config import setup_performance_optimizations, shutdown_performance_optimizations

app = FastAPI()

@app.on_event("startup")
async def startup():
    await setup_performance_optimizations(app)

@app.on_event("shutdown")
async def shutdown():
    await shutdown_performance_optimizations(app)

# Include optimized routes
app.include_router(router)
"""
