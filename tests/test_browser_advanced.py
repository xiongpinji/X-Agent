"""Tests for advanced browser monitoring and automation features."""

from __future__ import annotations

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch

from backend.app.services.browser.network_monitor import NetworkMonitor, NetworkRequest, NetworkResponse
from backend.app.services.browser.element_reference import ElementReferenceSystem, ElementReference, ElementType
from backend.app.services.browser.console_monitor import ConsoleMonitor, ConsoleMessageType
from backend.app.services.browser.natural_locator import NaturalLocator
from backend.app.services.browser.page_snapshot import PageSnapshotManager, PageSnapshot, DOMSnapshot
from backend.app.services.browser.advanced_monitoring import AdvancedBrowserMonitoring


class TestNetworkMonitor:
    """Tests for network monitoring."""

    @pytest.mark.asyncio
    async def test_network_monitor_initialization(self):
        """Test network monitor initialization."""
        monitor = NetworkMonitor()
        assert monitor.page is None
        assert len(monitor.get_requests()) == 0
        assert len(monitor.get_responses()) == 0

    @pytest.mark.asyncio
    async def test_network_request_capture(self):
        """Test capturing network requests."""
        monitor = NetworkMonitor()

        # Simulate request
        req = NetworkRequest(
            url="https://example.com/api",
            method="GET",
            headers={"Content-Type": "application/json"},
        )

        monitor._requests["https://example.com/api"] = req
        requests = monitor.get_requests()

        assert len(requests) == 1
        assert requests[0].url == "https://example.com/api"
        assert requests[0].method == "GET"

    @pytest.mark.asyncio
    async def test_network_response_capture(self):
        """Test capturing network responses."""
        monitor = NetworkMonitor()

        # Simulate response
        resp = NetworkResponse(
            url="https://example.com/api",
            status=200,
            status_text="OK",
            headers={"Content-Type": "application/json"},
        )

        monitor._responses.append(resp)
        responses = monitor.get_responses()

        assert len(responses) == 1
        assert responses[0].status == 200
        assert responses[0].status_text == "OK"

    @pytest.mark.asyncio
    async def test_network_failed_requests(self):
        """Test identifying failed requests."""
        monitor = NetworkMonitor()

        # Add successful response
        monitor._responses.append(
            NetworkResponse(
                url="https://example.com/success",
                status=200,
                status_text="OK",
            )
        )

        # Add failed response
        monitor._responses.append(
            NetworkResponse(
                url="https://example.com/error",
                status=500,
                status_text="Internal Server Error",
            )
        )

        failed = monitor.get_failed_requests()
        assert len(failed) == 1
        assert failed[0].status == 500

    @pytest.mark.asyncio
    async def test_network_summary(self):
        """Test network summary."""
        monitor = NetworkMonitor()

        monitor._requests["url1"] = NetworkRequest(url="url1", method="GET")
        monitor._requests["url2"] = NetworkRequest(url="url2", method="POST")

        monitor._responses.append(
            NetworkResponse(url="url1", status=200, status_text="OK")
        )
        monitor._responses.append(
            NetworkResponse(url="url2", status=404, status_text="Not Found")
        )

        summary = monitor.get_summary()
        assert summary["total_requests"] == 2
        assert summary["total_responses"] == 2
        assert summary["failed_responses"] == 1


class TestElementReference:
    """Tests for element reference system."""

    @pytest.mark.asyncio
    async def test_element_reference_initialization(self):
        """Test element reference initialization."""
        system = ElementReferenceSystem()
        assert system.page is None
        assert len(system._element_map) == 0

    @pytest.mark.asyncio
    async def test_element_reference_creation(self):
        """Test creating element references."""
        elem = ElementReference(
            ref="ref_1",
            tag_name="button",
            element_type=ElementType.BUTTON,
            text="Click me",
        )

        assert elem.ref == "ref_1"
        assert elem.tag_name == "button"
        assert elem.element_type == ElementType.BUTTON
        assert elem.text == "Click me"

    @pytest.mark.asyncio
    async def test_element_type_determination(self):
        """Test element type determination."""
        system = ElementReferenceSystem()

        # Test button
        assert system._determine_element_type("button", None) == ElementType.BUTTON

        # Test link
        assert system._determine_element_type("a", None) == ElementType.LINK

        # Test input
        assert system._determine_element_type("input", None) == ElementType.INPUT

        # Test with ARIA role
        assert system._determine_element_type("div", "button") == ElementType.BUTTON

    @pytest.mark.asyncio
    async def test_element_to_dict(self):
        """Test element serialization."""
        elem = ElementReference(
            ref="ref_1",
            tag_name="button",
            element_type=ElementType.BUTTON,
            text="Click",
            visible=True,
            enabled=True,
        )

        data = elem.to_dict()
        assert data["ref"] == "ref_1"
        assert data["tag_name"] == "button"
        assert data["element_type"] == "button"
        assert data["visible"] is True


class TestConsoleMonitor:
    """Tests for console monitoring."""

    @pytest.mark.asyncio
    async def test_console_monitor_initialization(self):
        """Test console monitor initialization."""
        monitor = ConsoleMonitor()
        assert monitor.page is None
        assert len(monitor.get_messages()) == 0

    @pytest.mark.asyncio
    async def test_console_message_capture(self):
        """Test capturing console messages."""
        monitor = ConsoleMonitor()

        # Simulate console message
        from backend.app.services.browser.console_monitor import ConsoleMessageRecord

        msg = ConsoleMessageRecord(
            type=ConsoleMessageType.LOG,
            text="Test message",
        )

        monitor._messages.append(msg)
        messages = monitor.get_messages()

        assert len(messages) == 1
        assert messages[0].text == "Test message"
        assert messages[0].type == ConsoleMessageType.LOG

    @pytest.mark.asyncio
    async def test_console_error_filtering(self):
        """Test filtering console errors."""
        monitor = ConsoleMonitor()

        from backend.app.services.browser.console_monitor import ConsoleMessageRecord

        monitor._messages.append(
            ConsoleMessageRecord(type=ConsoleMessageType.LOG, text="Log message")
        )
        monitor._messages.append(
            ConsoleMessageRecord(type=ConsoleMessageType.ERROR, text="Error message")
        )

        errors = monitor.get_errors()
        assert len(errors) == 1
        assert errors[0].type == ConsoleMessageType.ERROR

    @pytest.mark.asyncio
    async def test_console_summary(self):
        """Test console summary."""
        monitor = ConsoleMonitor()

        from backend.app.services.browser.console_monitor import ConsoleMessageRecord

        monitor._messages.append(
            ConsoleMessageRecord(type=ConsoleMessageType.LOG, text="Log")
        )
        monitor._messages.append(
            ConsoleMessageRecord(type=ConsoleMessageType.ERROR, text="Error")
        )
        monitor._messages.append(
            ConsoleMessageRecord(type=ConsoleMessageType.WARNING, text="Warning")
        )

        summary = monitor.get_summary()
        assert summary["total_messages"] == 3
        assert summary["error_count"] == 1
        assert summary["warning_count"] == 1
        assert summary["log_count"] == 1


class TestNaturalLocator:
    """Tests for natural language locator."""

    @pytest.mark.asyncio
    async def test_natural_locator_initialization(self):
        """Test natural locator initialization."""
        locator = NaturalLocator()
        assert locator.page is None

    @pytest.mark.asyncio
    async def test_similarity_calculation(self):
        """Test string similarity calculation."""
        locator = NaturalLocator()

        # Exact match
        assert locator._similarity("search", "search") == 1.0

        # Partial match
        similarity = locator._similarity("search button", "search")
        assert 0.5 < similarity < 1.0

        # No match
        assert locator._similarity("abc", "xyz") < 0.5


class TestPageSnapshot:
    """Tests for page snapshots."""

    @pytest.mark.asyncio
    async def test_snapshot_creation(self):
        """Test creating a snapshot."""
        dom = DOMSnapshot(
            html="<html><body>Test</body></html>",
            title="Test Page",
            url="https://example.com",
        )

        snapshot = PageSnapshot(dom=dom, label="test")

        assert snapshot.dom.html == "<html><body>Test</body></html>"
        assert snapshot.dom.title == "Test Page"
        assert snapshot.label == "test"

    @pytest.mark.asyncio
    async def test_snapshot_manager(self):
        """Test snapshot manager."""
        manager = PageSnapshotManager()

        dom1 = DOMSnapshot(
            html="<html><body>Before</body></html>",
            title="Before",
            url="https://example.com",
        )
        snapshot1 = PageSnapshot(dom=dom1, label="before")

        dom2 = DOMSnapshot(
            html="<html><body>After</body></html>",
            title="After",
            url="https://example.com",
        )
        snapshot2 = PageSnapshot(dom=dom2, label="after")

        manager._snapshots["before"] = snapshot1
        manager._snapshots["after"] = snapshot2

        # Test retrieval
        assert manager.get_snapshot("before") == snapshot1
        assert manager.get_snapshot("after") == snapshot2

        # Test comparison
        diff = manager.compare_snapshots(snapshot1, snapshot2)
        assert diff.dom_changed is True
        assert diff.title_changed is True


class TestAdvancedBrowserMonitoring:
    """Tests for advanced browser monitoring service."""

    @pytest.mark.asyncio
    async def test_session_creation(self):
        """Test creating a monitoring session."""
        monitoring = AdvancedBrowserMonitoring()

        # Mock page
        mock_page = AsyncMock()
        mock_page.on = Mock()
        mock_page.remove_listener = Mock()

        session = await monitoring.create_session("session_1", mock_page)

        assert session.session_id == "session_1"
        assert session.page == mock_page
        assert session.network_monitor is not None
        assert session.element_reference is not None
        assert session.console_monitor is not None

    @pytest.mark.asyncio
    async def test_session_closure(self):
        """Test closing a monitoring session."""
        monitoring = AdvancedBrowserMonitoring()

        mock_page = AsyncMock()
        mock_page.on = Mock()
        mock_page.remove_listener = Mock()

        session = await monitoring.create_session("session_1", mock_page)
        assert monitoring.get_session("session_1") is not None

        success = await monitoring.close_session("session_1")
        assert success is True
        assert monitoring.get_session("session_1") is None

    @pytest.mark.asyncio
    async def test_session_not_found(self):
        """Test error handling for missing session."""
        monitoring = AdvancedBrowserMonitoring()

        with pytest.raises(KeyError):
            monitoring._require_session("nonexistent")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
