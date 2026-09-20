"""
Architecture Optimization Integration Guide for X-Agent.

This guide explains how to integrate the new architecture optimization modules
into existing X-Agent code.
"""

# ============================================================================
# 1. EVENT BUS INTEGRATION GUIDE
# ============================================================================

"""
How to use the Event Bus Integration in your code:

Example 1: Publishing Agent Events
"""

from backend.app.core.event_bus_integration import get_event_bus_integration

async def run_agent(agent_id: str, task: str, user_id: str):
    event_bus = get_event_bus_integration()

    try:
        # Publish agent started event
        await event_bus.publish_agent_started(
            agent_id=agent_id,
            task=task,
            user_id=user_id,
            correlation_id="corr_123"
        )

        # Execute agent logic
        result = await execute_agent_logic(agent_id, task)

        # Publish agent completed event
        await event_bus.publish_agent_completed(
            agent_id=agent_id,
            result=result,
            duration_seconds=10.5,
            user_id=user_id
        )

    except Exception as e:
        # Publish agent failed event
        await event_bus.publish_agent_failed(
            agent_id=agent_id,
            error=str(e),
            error_type=type(e).__name__,
            user_id=user_id
        )
        raise


"""
Example 2: Subscribing to Events
"""

from backend.app.core.event_bus import EventType, get_event_bus

async def setup_event_listeners():
    event_bus = get_event_bus()

    # Subscribe to agent completed events
    async def on_agent_completed(event):
        print(f"Agent {event.data['agent_id']} completed")
        # Trigger downstream actions
        await handle_agent_completion(event)

    await event_bus.subscribe(EventType.AGENT_COMPLETED, on_agent_completed)

    # Subscribe to security events
    async def on_auth_failed(event):
        print(f"Authentication failed: {event.data['reason']}")
        # Log security incident
        await log_security_incident(event)

    await event_bus.subscribe(EventType.AUTHENTICATION_FAILED, on_auth_failed)


# ============================================================================
# 2. CACHE INTEGRATION GUIDE
# ============================================================================

"""
How to use the Cache Integration in your code:

Example 1: Caching Database Queries
"""

from backend.app.core.cache_integration import get_cache_integration, cached_query

class UserRepository:
    def __init__(self):
        self._cache_integration = get_cache_integration()

    @cached_query(ttl=3600, prefix="user")
    async def get_user(self, user_id: str):
        """Get user by ID with automatic caching."""
        # This query result will be cached for 1 hour
        return await self._db.query(User).filter(User.id == user_id).first()

    async def update_user(self, user_id: str, data: dict):
        """Update user and invalidate cache."""
        result = await self._db.update(User, user_id, data)

        # Invalidate user cache
        await self._cache_integration.invalidate_user_cache(user_id)

        return result


"""
Example 2: Manual Cache Operations
"""

async def get_workflow_with_cache(workflow_id: str):
    cache_integration = get_cache_integration()

    # Generate cache key
    cache_key = await cache_integration.cache_workflow_query(workflow_id)

    # Try to get from cache
    cached_workflow = await cache_integration.cache_get(cache_key)
    if cached_workflow:
        return cached_workflow

    # Load from database
    workflow = await load_workflow_from_db(workflow_id)

    # Store in cache
    await cache_integration.cache_set(cache_key, workflow, ttl=3600)

    return workflow


"""
Example 3: Cache Warming
"""

async def warm_up_cache():
    cache_integration = get_cache_integration()

    # Warm cache with frequently accessed data
    async def load_tools():
        tools = await get_all_tools()
        return {tool.id: tool for tool in tools}

    await cache_integration.warm_cache(
        data_loader=load_tools,
        prefix="tool",
        ttl=7200
    )


# ============================================================================
# 3. CONCURRENCY OPTIMIZATION GUIDE
# ============================================================================

"""
How to use the Concurrency Optimization in your code:

Example 1: Using Adaptive Concurrency Limiter
"""

from backend.app.core.concurrency_optimization import get_adaptive_limiter

async def process_tasks(tasks: list):
    limiter = get_adaptive_limiter()

    async def process_task(task):
        await limiter.acquire()
        try:
            result = await execute_task(task)
            limiter.release(success=True)
            return result
        except Exception as e:
            limiter.release(success=False)
            raise

    # Process tasks with adaptive concurrency control
    results = await asyncio.gather(*[process_task(t) for t in tasks])

    # Check statistics
    stats = limiter.get_stats()
    print(f"Concurrency stats: {stats}")


"""
Example 2: Using Backpressure Handler
"""

from backend.app.core.concurrency_optimization import get_backpressure_handler

async def enqueue_task(task):
    backpressure = get_backpressure_handler()

    # Check if system is under backpressure
    if await backpressure.check_backpressure():
        # Wait for backpressure to be relieved
        if not await backpressure.wait_if_backpressure(timeout=30):
            raise Exception("Backpressure timeout")

    # Enqueue task
    await task_queue.put(task)

    # Update queue size
    await backpressure.update_queue_size(task_queue.qsize())


"""
Example 3: Using Priority Task Scheduler
"""

from backend.app.core.concurrency_optimization import get_priority_scheduler

async def schedule_tasks():
    scheduler = get_priority_scheduler()
    await scheduler.start()

    # Enqueue high-priority task
    await scheduler.enqueue(
        task=lambda: critical_operation(),
        priority=10,
        timeout=30
    )

    # Enqueue normal-priority task
    await scheduler.enqueue(
        task=lambda: normal_operation(),
        priority=0,
        timeout=30
    )

    # Get scheduler statistics
    stats = scheduler.get_stats()
    print(f"Scheduler stats: {stats}")


# ============================================================================
# 4. CONFIGURATION MANAGEMENT GUIDE
# ============================================================================

"""
How to use the Configuration Management in your code:

Example 1: Configuration Encryption
"""

from backend.app.core.config_hot_reload import get_config_encryption

async def store_sensitive_config():
    encryption = get_config_encryption()

    # Encrypt sensitive values
    encrypted_password = encryption.encrypt("my_secret_password")

    # Store encrypted value
    config = {
        "database": {
            "password": encrypted_password
        }
    }

    # Later, decrypt when needed
    decrypted_password = encryption.decrypt(encrypted_password)


"""
Example 2: Configuration Hot-Reload
"""

from backend.app.core.config_hot_reload import get_config_hot_reload
from pathlib import Path

async def setup_config_hot_reload():
    config_file = Path("config/app.yaml")
    hot_reload = get_config_hot_reload(config_file)

    # Register callback for configuration changes
    async def on_config_changed(new_config):
        print(f"Configuration changed: {new_config}")
        # Apply new configuration
        await apply_configuration(new_config)

    hot_reload.register_watcher(on_config_changed)

    # Start monitoring
    await hot_reload.start_monitoring()


"""
Example 3: Configuration Audit
"""

from backend.app.core.config_hot_reload import get_config_audit

async def audit_config_changes():
    audit = get_config_audit()

    # Log configuration change
    await audit.log_change(
        change_type="update",
        key="database.pool_size",
        old_value=10,
        new_value=20,
        user_id="admin",
        reason="Performance optimization"
    )

    # Get audit history
    history = await audit.get_history(limit=50)

    # Get audit report
    report = await audit.get_report()
    print(f"Audit report: {report}")


# ============================================================================
# 5. ERROR HANDLING GUIDE
# ============================================================================

"""
How to use the Enhanced Error Handling in your code:

Example 1: Using Retry Strategy
"""

from backend.app.core.error_handling import ExponentialBackoffRetry

async def call_external_api():
    retry_strategy = ExponentialBackoffRetry(
        max_attempts=3,
        initial_delay=1.0,
        max_delay=60.0
    )

    async def api_call():
        return await external_api.get_data()

    try:
        result = await retry_strategy.execute(api_call)
        return result
    except Exception as e:
        print(f"Failed after retries: {e}")
        raise


"""
Example 2: Using Circuit Breaker
"""

from backend.app.core.error_handling import CircuitBreaker

class ExternalServiceClient:
    def __init__(self):
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0
        )

    async def call_service(self):
        async def service_call():
            return await self._make_request()

        try:
            return await self.circuit_breaker.call(service_call)
        except Exception as e:
            print(f"Service call failed: {e}")
            raise


"""
Example 3: Using Error Tracker
"""

from backend.app.core.error_handling import get_error_tracker, AuthenticationError

async def handle_authentication():
    error_tracker = get_error_tracker()

    try:
        # Authentication logic
        user = await authenticate_user(username, password)
    except AuthenticationError as e:
        # Track error
        await error_tracker.record(e)

        # Get error statistics
        stats = error_tracker.get_stats()
        print(f"Error stats: {stats}")

        raise


# ============================================================================
# 6. INTEGRATION PATTERNS
# ============================================================================

"""
Pattern 1: Complete Request Lifecycle with All Optimizations
"""

async def handle_request(request_id: str, user_id: str, task: dict):
    event_bus = get_event_bus_integration()
    cache_integration = get_cache_integration()
    limiter = get_adaptive_limiter()
    error_tracker = get_error_tracker()

    try:
        # Publish request started event
        await event_bus.publish_system_warning(
            warning=f"Request {request_id} started",
            component="request_handler",
            user_id=user_id
        )

        # Check concurrency
        await limiter.acquire()

        try:
            # Try to get from cache
            cache_key = f"request:{request_id}"
            cached_result = await cache_integration.cache_get(cache_key)
            if cached_result:
                return cached_result

            # Execute task with retry
            retry_strategy = ExponentialBackoffRetry()
            result = await retry_strategy.execute(
                lambda: execute_task(task)
            )

            # Cache result
            await cache_integration.cache_set(cache_key, result, ttl=3600)

            # Publish success event
            await event_bus.publish_system_warning(
                warning=f"Request {request_id} completed",
                component="request_handler",
                user_id=user_id
            )

            return result

        finally:
            limiter.release(success=True)

    except Exception as e:
        # Track error
        await error_tracker.record(e)

        # Publish error event
        await event_bus.publish_system_error(
            error=str(e),
            error_type=type(e).__name__,
            component="request_handler",
            user_id=user_id
        )

        limiter.release(success=False)
        raise


"""
Pattern 2: Batch Processing with Concurrency Control
"""

async def process_batch(items: list, batch_size: int = 10):
    scheduler = get_priority_scheduler()
    await scheduler.start()

    try:
        for i, item in enumerate(items):
            # Calculate priority based on item importance
            priority = 10 if item.get("urgent") else 0

            # Enqueue task
            await scheduler.enqueue(
                task=lambda item=item: process_item(item),
                priority=priority
            )

        # Wait for completion
        await asyncio.sleep(5)

        # Get statistics
        stats = scheduler.get_stats()
        print(f"Batch processing stats: {stats}")

    finally:
        await scheduler.stop()


# ============================================================================
# 7. MONITORING AND DEBUGGING
# ============================================================================

"""
How to monitor and debug the optimization modules:
"""

async def get_system_health():
    """Get comprehensive system health report."""
    from backend.app.core.concurrency_optimization import (
        get_adaptive_limiter,
        get_backpressure_handler,
        get_priority_scheduler
    )
    from backend.app.core.error_handling import get_error_tracker
    from backend.app.core.cache import get_cache_manager

    health_report = {
        "concurrency": get_adaptive_limiter().get_stats(),
        "backpressure": get_backpressure_handler().get_stats(),
        "scheduler": get_priority_scheduler().get_stats(),
        "errors": get_error_tracker().get_stats(),
        "cache": {
            "l1_size": get_cache_manager()._l1_cache._cache.__len__(),
        }
    }

    return health_report


async def debug_performance():
    """Debug performance issues."""
    health = await get_system_health()

    # Check concurrency
    if health["concurrency"]["active_tasks"] > 40:
        print("WARNING: High concurrency load")

    # Check backpressure
    if health["backpressure"]["backpressure_active"]:
        print("WARNING: Backpressure is active")

    # Check errors
    if health["errors"]["total_errors"] > 100:
        print("WARNING: High error rate")

    return health


# ============================================================================
# 8. BEST PRACTICES
# ============================================================================

"""
Best Practices for Using Architecture Optimization Modules:

1. EVENT BUS
   - Always include correlation_id for tracing
   - Use appropriate event types
   - Subscribe to events early in application startup
   - Handle event processing errors gracefully

2. CACHE
   - Set appropriate TTL values based on data freshness requirements
   - Invalidate cache when data changes
   - Monitor cache hit rates
   - Use cache warming for frequently accessed data

3. CONCURRENCY
   - Monitor adaptive limiter statistics
   - Adjust initial limits based on workload
   - Use priority scheduling for critical tasks
   - Monitor backpressure activation

4. CONFIGURATION
   - Always encrypt sensitive values
   - Enable hot-reload for non-critical configs
   - Audit all configuration changes
   - Test configuration changes in staging first

5. ERROR HANDLING
   - Use appropriate exception types
   - Configure retry strategies based on failure patterns
   - Monitor circuit breaker state
   - Track error trends
"""

# ============================================================================
# END OF INTEGRATION GUIDE
# ============================================================================
