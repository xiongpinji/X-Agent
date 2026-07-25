"""Unit-test level conftest: override expensive root fixtures not needed by unit tests.

The root tests/conftest.py defines an autouse ``_init_global_db`` fixture that
creates a temporary async SQLite database for *every* test.  Unit tests mock all
external dependencies and do NOT need a real database, so we override it here
with a lightweight no-op to reduce per-test overhead from ~10 s to <0.1 s.
"""
from __future__ import annotations

import sys

import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# Override the expensive root-level DB fixture with a no-op for unit tests.
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def _init_global_db():
    """No-op override – unit tests mock all DB access."""
    yield None


# ---------------------------------------------------------------------------
# Recursion limit guard – some tests build deep mock chains.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _prevent_recursion():
    """Increase recursion limit for tests that build deep mock chains."""
    old_limit = sys.getrecursionlimit()
    if old_limit < 3000:
        sys.setrecursionlimit(3000)
    yield
    sys.setrecursionlimit(old_limit)


# ---------------------------------------------------------------------------
# Settings cache reset – prevent lru_cache pollution across tests.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Clear get_settings lru_cache after each test."""
    yield
    try:
        from backend.app.settings import get_settings
        get_settings.cache_clear()
    except (ImportError, AttributeError):
        pass


# ---------------------------------------------------------------------------
# Lifecycle manager reset – prevent shutdown state leaking across tests.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_lifecycle_manager():
    """Reset the lifecycle manager's shutdown state before each test.

    Tests that use ``with TestClient(app)`` trigger the app's shutdown event,
    which sets ``lifecycle._shutdown_event``.  Subsequent tests that create a
    TestClient without the context manager would then get 503 from the
    lifecycle middleware.  Clearing the event here prevents cross-test pollution.
    """
    from backend.app.core.lifecycle import get_lifecycle_manager
    lm = get_lifecycle_manager()
    lm._shutdown_event.clear()
    lm._active_requests = 0
    yield
    # Also reset after the test in case it triggered shutdown
    lm._shutdown_event.clear()
    lm._active_requests = 0


# ---------------------------------------------------------------------------
# Payment / Notification provider reset – prevent singleton leakage.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_providers():
    """Reset payment and notification providers between tests."""
    yield
    # Reset payment provider
    try:
        from backend.app.core.payment_providers import set_payment_provider, MockPaymentProvider
        set_payment_provider(MockPaymentProvider())
    except (ImportError, Exception):
        pass
    # Reset notification provider
    try:
        from backend.app.core.notifications import set_notification_provider, ConsoleNotificationProvider
        set_notification_provider(ConsoleNotificationProvider())
    except (ImportError, Exception):
        pass
