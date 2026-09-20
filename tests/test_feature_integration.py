"""Integration tests for Phase 3 feature enhancements."""

import asyncio
import pytest
import time
from unittest.mock import Mock, AsyncMock, patch

from backend.app.services.browser.enhanced_automation import (
    EnhancedBrowserAutomation,
    ElementInfo,
    ElementDetectionMethod,
    WaitStrategy,
)
from backend.app.core.advanced_repair_loop import (
    AdvancedRepairLoop,
    FailureRecord,
    FailureCategory,
    RepairStrategy,
    RepairSuggestion,
)


class TestEnhancedBrowserAutomation:
    """Tests for enhanced browser automation."""

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test creating a browser session."""
        automation = EnhancedBrowserAutomation()

        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        session = await automation.create_session(
            "session_1",
            mock_browser,
            mock_context,
            mock_page,
        )

        assert session.session_id == "session_1"
        assert session.browser == mock_browser
        assert session.page == mock_page

    @pytest.mark.asyncio
    async def test_close_session(self):
        """Test closing a browser session."""
        automation = EnhancedBrowserAutomation()

        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        await automation.create_session(
            "session_1",
            mock_browser,
            mock_context,
            mock_page,
        )

        success = await automation.close_session("session_1")

        assert success is True
        mock_page.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_element_by_selector(self):
        """Test finding element by CSS selector."""
        automation = EnhancedBrowserAutomation()

        mock_page = AsyncMock()
        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_page.locator = Mock(return_value=mock_locator)

        await automation.create_session(
            "session_1",
            AsyncMock(),
            AsyncMock(),
            mock_page,
        )

        element = await automation.find_element(
            "session_1",
            ".button",
            ElementDetectionMethod.CSS_SELECTOR,
        )

        assert element is not None
        assert element.selector == ".button"

    @pytest.mark.asyncio
    async def test_click_element(self):
        """Test clicking an element."""
        automation = EnhancedBrowserAutomation()

        mock_page = AsyncMock()
        mock_locator = AsyncMock()
        mock_locator.scroll_into_view_if_needed = AsyncMock()
        mock_locator.wait_for = AsyncMock()
        mock_locator.click = AsyncMock()
        mock_page.locator = Mock(return_value=mock_locator)

        await automation.create_session(
            "session_1",
            AsyncMock(),
            AsyncMock(),
            mock_page,
        )

        element = ElementInfo(selector=".button", method=ElementDetectionMethod.CSS_SELECTOR)
        success = await automation.click_element("session_1", element)

        assert success is True
        mock_locator.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_fill_input(self):
        """Test filling an input element."""
        automation = EnhancedBrowserAutomation()

        mock_page = AsyncMock()
        mock_locator = AsyncMock()
        mock_locator.scroll_into_view_if_needed = AsyncMock()
        mock_locator.wait_for = AsyncMock()
        mock_locator.clear = AsyncMock()
        mock_locator.fill = AsyncMock()
        mock_page.locator = Mock(return_value=mock_locator)

        await automation.create_session(
            "session_1",
            AsyncMock(),
            AsyncMock(),
            mock_page,
        )

        element = ElementInfo(selector="input", method=ElementDetectionMethod.CSS_SELECTOR)
        success = await automation.fill_input("session_1", element, "test value")

        assert success is True
        mock_locator.fill.assert_called_once_with("test value")


class TestAdvancedRepairLoop:
    """Tests for advanced repair loop."""

    @pytest.mark.asyncio
    async def test_analyze_failure(self):
        """Test failure analysis."""
        repair = AdvancedRepairLoop()

        error = TimeoutError("Operation timed out")
        failure = await repair.analyze_failure(error, {"operation": "test"})

        assert failure.error_type == "TimeoutError"
        assert failure.category == FailureCategory.TIMEOUT
        assert failure.context["operation"] == "test"

    @pytest.mark.asyncio
    async def test_suggest_repair_transient(self):
        """Test repair suggestion for transient failure."""
        repair = AdvancedRepairLoop()

        failure = FailureRecord(
            id="failure_1",
            error_message="Connection refused",
            error_type="ConnectionError",
            category=FailureCategory.TRANSIENT,
        )

        suggestion = await repair.suggest_repair(failure)

        assert suggestion.strategy == RepairStrategy.RETRY
        assert suggestion.confidence > 0.5

    @pytest.mark.asyncio
    async def test_suggest_repair_resource(self):
        """Test repair suggestion for resource failure."""
        repair = AdvancedRepairLoop()

        failure = FailureRecord(
            id="failure_1",
            error_message="Out of memory",
            error_type="MemoryError",
            category=FailureCategory.RESOURCE,
        )

        suggestion = await repair.suggest_repair(failure)

        assert suggestion.strategy == RepairStrategy.COMPENSATE
        assert len(suggestion.compensation_actions) > 0

    @pytest.mark.asyncio
    async def test_execute_retry(self):
        """Test retry execution."""
        repair = AdvancedRepairLoop(max_retries=3)

        call_count = 0

        def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "success"

        failure = FailureRecord(
            id="failure_1",
            error_message="Connection failed",
            error_type="ConnectionError",
            category=FailureCategory.TRANSIENT,
        )

        suggestion = RepairSuggestion(strategy=RepairStrategy.RETRY)

        success, result = await repair.execute_repair(
            failure,
            suggestion,
            failing_operation,
        )

        assert success is True
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_learning_update(self):
        """Test learning record update."""
        repair = AdvancedRepairLoop(learning_enabled=True)

        failure = FailureRecord(
            id="failure_1",
            error_message="Connection failed",
            error_type="ConnectionError",
            category=FailureCategory.TRANSIENT,
        )

        await repair._update_learning(failure, RepairStrategy.RETRY, True)
        await repair._update_learning(failure, RepairStrategy.RETRY, True)
        await repair._update_learning(failure, RepairStrategy.RETRY, False)

        stats = repair.get_learning_stats()

        assert stats["total_patterns"] > 0
        assert stats["avg_success_rate"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
