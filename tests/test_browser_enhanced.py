"""
Comprehensive tests for enhanced browser automation.

Tests all components: locator, waiter, interactions, analyzer, recovery, pool, stealth.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from backend.app.services.browser.smart_locator import SmartLocator, LocatorStrategy, LocatorResult
from backend.app.services.browser.waiter import SmartWaiter, WaitStrategy, WaitResult
from backend.app.services.browser.interactions import AdvancedInteractions, InteractionType
from backend.app.services.browser.analyzer import PageAnalyzer, ElementType
from backend.app.services.browser.recovery import ErrorRecovery, ErrorType, RecoveryStrategy
from backend.app.services.browser.pool import BrowserPool, BrowserPoolManager
from backend.app.services.browser.stealth import StealthBrowser


class TestSmartLocator:
    """Tests for SmartLocator."""

    def test_locator_initialization(self):
        """Test locator initialization."""
        locator = SmartLocator("test_session")
        assert locator.session_id == "test_session"
        assert locator.max_retries == 3
        assert len(locator.location_cache) == 0

    def test_find_element_with_cache(self):
        """Test element finding with cache."""
        locator = SmartLocator("test_session")

        # First find
        result1 = locator.find_element(
            css_selector=".button",
            use_cache=True,
        )
        assert result1.found

        # Second find should use cache
        result2 = locator.find_element(
            css_selector=".button",
            use_cache=True,
        )
        assert result2.found
        assert len(locator.location_cache) > 0

    def test_cache_key_building(self):
        """Test cache key building."""
        locator = SmartLocator("test_session")

        key1 = locator._build_cache_key(".button", None, None, None)
        key2 = locator._build_cache_key(".button", None, None, None)
        assert key1 == key2

        key3 = locator._build_cache_key(".link", None, None, None)
        assert key1 != key3

    def test_clear_cache(self):
        """Test cache clearing."""
        locator = SmartLocator("test_session")

        locator.find_element(css_selector=".button")
        assert len(locator.location_cache) > 0

        locator.clear_cache()
        assert len(locator.location_cache) == 0

    def test_get_cache_stats(self):
        """Test cache statistics."""
        locator = SmartLocator("test_session")

        locator.find_element(css_selector=".button")
        locator.find_element(css_selector=".link")

        stats = locator.get_cache_stats()
        assert stats["cache_size"] >= 0
        assert "cached_elements" in stats


class TestSmartWaiter:
    """Tests for SmartWaiter."""

    def test_waiter_initialization(self):
        """Test waiter initialization."""
        waiter = SmartWaiter("test_session")
        assert waiter.session_id == "test_session"
        assert waiter.default_timeout == 30.0
        assert len(waiter.wait_history) == 0

    @pytest.mark.asyncio
    async def test_wait_for_condition(self):
        """Test waiting for condition."""
        waiter = SmartWaiter("test_session")

        # Create mock page
        page = AsyncMock()

        # Test successful condition
        def condition(p):
            return True

        result = await waiter.wait_for_condition(page, condition, timeout=5.0)
        assert result.success
        assert result.strategy_used == WaitStrategy.CUSTOM

    @pytest.mark.asyncio
    async def test_wait_timeout(self):
        """Test wait timeout."""
        waiter = SmartWaiter("test_session")

        page = AsyncMock()

        def condition(p):
            return False

        result = await waiter.wait_for_condition(page, condition, timeout=0.5)
        assert not result.success
        assert result.reason == "Condition timeout"

    def test_wait_stats(self):
        """Test wait statistics."""
        waiter = SmartWaiter("test_session")

        # Record some waits
        result1 = WaitResult(
            success=True,
            strategy_used=WaitStrategy.ADAPTIVE,
            time_taken_ms=100.0,
        )
        result2 = WaitResult(
            success=False,
            strategy_used=WaitStrategy.CUSTOM,
            time_taken_ms=200.0,
        )

        waiter._record_wait(result1)
        waiter._record_wait(result2)

        stats = waiter.get_wait_stats()
        assert stats["total_waits"] == 2
        assert stats["successful"] == 1
        assert stats["failed"] == 1
        assert stats["success_rate"] == 0.5


class TestAdvancedInteractions:
    """Tests for AdvancedInteractions."""

    def test_interactions_initialization(self):
        """Test interactions initialization."""
        interactions = AdvancedInteractions("test_session")
        assert interactions.session_id == "test_session"
        assert len(interactions.interaction_history) == 0

    @pytest.mark.asyncio
    async def test_hover_element(self):
        """Test hover interaction."""
        interactions = AdvancedInteractions("test_session")

        page = AsyncMock()
        element = AsyncMock()
        page.locator.return_value = element
        element.scroll_into_view_if_needed = AsyncMock()
        element.hover = AsyncMock()

        result = await interactions.hover_element(page, ".button")
        assert result.success
        assert result.interaction_type == InteractionType.HOVER

    @pytest.mark.asyncio
    async def test_double_click(self):
        """Test double click interaction."""
        interactions = AdvancedInteractions("test_session")

        page = AsyncMock()
        element = AsyncMock()
        page.locator.return_value = element
        element.scroll_into_view_if_needed = AsyncMock()
        element.dblclick = AsyncMock()

        result = await interactions.double_click(page, ".button")
        assert result.success
        assert result.interaction_type == InteractionType.DOUBLE_CLICK

    def test_interaction_stats(self):
        """Test interaction statistics."""
        interactions = AdvancedInteractions("test_session")

        # Record interactions
        from backend.app.services.browser.interactions import InteractionResult

        result1 = InteractionResult(
            success=True,
            interaction_type=InteractionType.CLICK,
            time_taken_ms=50.0,
        )
        result2 = InteractionResult(
            success=False,
            interaction_type=InteractionType.HOVER,
            time_taken_ms=100.0,
        )

        interactions._record_interaction(result1)
        interactions._record_interaction(result2)

        stats = interactions.get_interaction_stats()
        assert stats["total_interactions"] == 2
        assert stats["successful"] == 1
        assert stats["failed"] == 1


class TestPageAnalyzer:
    """Tests for PageAnalyzer."""

    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        analyzer = PageAnalyzer("test_session")
        assert analyzer.session_id == "test_session"

    @pytest.mark.asyncio
    async def test_extract_buttons(self):
        """Test button extraction."""
        analyzer = PageAnalyzer("test_session")

        page = AsyncMock()
        locators = AsyncMock()
        page.locator.return_value = locators
        locators.count = AsyncMock(return_value=1)
        locators.nth.return_value = AsyncMock()

        buttons = await analyzer._extract_buttons(page)
        assert isinstance(buttons, list)

    @pytest.mark.asyncio
    async def test_extract_links(self):
        """Test link extraction."""
        analyzer = PageAnalyzer("test_session")

        page = AsyncMock()
        locators = AsyncMock()
        page.locator.return_value = locators
        locators.count = AsyncMock(return_value=0)

        links = await analyzer._extract_links(page)
        assert isinstance(links, list)
        assert len(links) == 0


class TestErrorRecovery:
    """Tests for ErrorRecovery."""

    def test_recovery_initialization(self):
        """Test recovery initialization."""
        recovery = ErrorRecovery("test_session")
        assert recovery.session_id == "test_session"
        assert len(recovery.error_history) == 0

    def test_error_classification(self):
        """Test error classification."""
        recovery = ErrorRecovery("test_session")

        # Test timeout error
        timeout_error = TimeoutError("Operation timed out")
        error_type = recovery._classify_error(timeout_error)
        assert error_type == ErrorType.TIMEOUT

        # Test network error
        network_error = Exception("Connection refused")
        error_type = recovery._classify_error(network_error)
        assert error_type == ErrorType.NETWORK_ERROR

    def test_recovery_strategy_selection(self):
        """Test recovery strategy selection."""
        recovery = ErrorRecovery("test_session")

        strategy = recovery._select_recovery_strategy(ErrorType.TIMEOUT)
        assert strategy == RecoveryStrategy.RELOAD

        strategy = recovery._select_recovery_strategy(ErrorType.NETWORK_ERROR)
        assert strategy == RecoveryStrategy.WAIT_AND_RETRY

    @pytest.mark.asyncio
    async def test_detect_captcha(self):
        """Test CAPTCHA detection."""
        recovery = ErrorRecovery("test_session")

        page = AsyncMock()
        locators = AsyncMock()
        page.locator.return_value = locators
        locators.count = AsyncMock(return_value=0)

        has_captcha = await recovery.detect_captcha(page)
        assert isinstance(has_captcha, bool)

    def test_error_stats(self):
        """Test error statistics."""
        recovery = ErrorRecovery("test_session")

        from backend.app.services.browser.recovery import ErrorContext

        error1 = ErrorContext(
            error_type=ErrorType.TIMEOUT,
            error_message="Timeout",
            timestamp=datetime.now().timestamp(),
            recovery_successful=True,
        )
        error2 = ErrorContext(
            error_type=ErrorType.NETWORK_ERROR,
            error_message="Network error",
            timestamp=datetime.now().timestamp(),
            recovery_successful=False,
        )

        recovery.error_history.append(error1)
        recovery.error_history.append(error2)

        stats = recovery.get_error_stats()
        assert stats["total_errors"] == 2
        assert stats["recovered"] == 1
        assert stats["recovery_rate"] == 0.5


class TestBrowserPool:
    """Tests for BrowserPool."""

    def test_pool_initialization(self):
        """Test pool initialization."""
        pool = BrowserPool(max_browsers=5)
        assert pool.max_browsers == 5
        assert len(pool.browsers) == 0

    def test_pool_stats(self):
        """Test pool statistics."""
        pool = BrowserPool(max_browsers=5)

        stats = pool.get_stats()
        assert stats.total_browsers == 0
        assert stats.active_browsers == 0
        assert stats.idle_browsers == 0

    def test_pool_manager(self):
        """Test pool manager."""
        manager = BrowserPoolManager()

        pool = manager.create_pool("test_pool", max_browsers=3)
        assert pool is not None

        retrieved_pool = manager.get_pool("test_pool")
        assert retrieved_pool is pool


class TestStealthBrowser:
    """Tests for StealthBrowser."""

    def test_stealth_initialization(self):
        """Test stealth initialization."""
        stealth = StealthBrowser("test_session")
        assert stealth.session_id == "test_session"

    def test_random_user_agent(self):
        """Test random user agent generation."""
        stealth = StealthBrowser("test_session")

        ua = stealth.get_random_user_agent()
        assert ua.user_agent
        assert ua.browser
        assert ua.os
        assert ua.device

    def test_random_viewport(self):
        """Test random viewport generation."""
        stealth = StealthBrowser("test_session")

        viewport = stealth.get_random_viewport()
        assert "width" in viewport
        assert "height" in viewport
        assert viewport["width"] > 0
        assert viewport["height"] > 0

    def test_random_locale(self):
        """Test random locale generation."""
        stealth = StealthBrowser("test_session")

        locale = stealth.get_random_locale()
        assert locale
        assert "-" in locale

    def test_stealth_context_options(self):
        """Test stealth context options."""
        stealth = StealthBrowser("test_session")

        options = stealth.get_stealth_context_options()
        assert "user_agent" in options
        assert "viewport" in options
        assert "locale" in options
        assert "timezone_id" in options

    def test_stealth_launch_options(self):
        """Test stealth launch options."""
        stealth = StealthBrowser("test_session")

        options = stealth.get_stealth_launch_options()
        assert "headless" in options
        assert "args" in options
        assert isinstance(options["args"], list)


class TestIntegration:
    """Integration tests."""

    @pytest.mark.asyncio
    async def test_locator_with_retry(self):
        """Test locator with retry."""
        locator = SmartLocator("test_session", max_retries=2)

        result = locator.find_element_with_retry(css_selector=".button")
        assert isinstance(result, LocatorResult)

    @pytest.mark.asyncio
    async def test_waiter_with_multiple_strategies(self):
        """Test waiter with multiple strategies."""
        waiter = SmartWaiter("test_session")

        page = AsyncMock()
        page.wait_for_selector = AsyncMock()

        result = await waiter.wait_for_selector(
            page,
            ".button",
            strategy=WaitStrategy.ADAPTIVE,
        )
        assert isinstance(result, WaitResult)

    def test_error_recovery_workflow(self):
        """Test error recovery workflow."""
        recovery = ErrorRecovery("test_session")

        # Register custom handler
        async def custom_handler(session_id, error):
            pass

        recovery.register_error_handler(ErrorType.TIMEOUT, custom_handler)
        assert ErrorType.TIMEOUT in recovery.recovery_handlers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
