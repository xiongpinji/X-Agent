"""Advanced browser monitoring and automation features integration."""

from __future__ import annotations

from typing import Optional, Any
from dataclasses import dataclass

try:
    from playwright.async_api import Page
except ImportError:
    Page = object  # type: ignore[assignment]

from backend.app.services.browser.network_monitor import NetworkMonitor
from backend.app.services.browser.element_reference import ElementReferenceSystem
from backend.app.services.browser.console_monitor import ConsoleMonitor
from backend.app.services.browser.natural_locator import NaturalLocator
from backend.app.services.browser.page_snapshot import PageSnapshotManager


@dataclass
class AdvancedBrowserSession:
    """Browser session with advanced monitoring capabilities."""
    session_id: str
    page: Page
    network_monitor: NetworkMonitor
    element_reference: ElementReferenceSystem
    console_monitor: ConsoleMonitor
    natural_locator: NaturalLocator
    snapshot_manager: PageSnapshotManager


class AdvancedBrowserMonitoring:
    """Advanced browser monitoring and automation features."""

    def __init__(self):
        self._sessions: dict[str, AdvancedBrowserSession] = {}

    async def create_session(self, session_id: str, page: Page) -> AdvancedBrowserSession:
        """Create a session with advanced monitoring."""
        network_monitor = NetworkMonitor()
        element_reference = ElementReferenceSystem()
        console_monitor = ConsoleMonitor()
        natural_locator = NaturalLocator()
        snapshot_manager = PageSnapshotManager()

        # Start monitoring
        await network_monitor.start_monitoring(page)
        await console_monitor.start_monitoring(page)

        session = AdvancedBrowserSession(
            session_id=session_id,
            page=page,
            network_monitor=network_monitor,
            element_reference=element_reference,
            console_monitor=console_monitor,
            natural_locator=natural_locator,
            snapshot_manager=snapshot_manager,
        )

        self._sessions[session_id] = session
        return session

    async def close_session(self, session_id: str) -> bool:
        """Close a session and stop monitoring."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        try:
            await session.network_monitor.stop_monitoring()
            await session.console_monitor.stop_monitoring()
            del self._sessions[session_id]
            return True
        except Exception:
            return False

    def get_session(self, session_id: str) -> Optional[AdvancedBrowserSession]:
        """Get a session."""
        return self._sessions.get(session_id)

    # Network monitoring
    async def get_network_requests(
        self,
        session_id: str,
        url_pattern: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get network requests."""
        session = self._require_session(session_id)
        requests = session.network_monitor.get_requests(url_pattern)
        return [r.to_dict() for r in requests]

    async def get_network_responses(
        self,
        session_id: str,
        url_pattern: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get network responses."""
        session = self._require_session(session_id)
        responses = session.network_monitor.get_responses(url_pattern)
        return [r.to_dict() for r in responses]

    async def get_network_summary(self, session_id: str) -> dict[str, Any]:
        """Get network summary."""
        session = self._require_session(session_id)
        return session.network_monitor.get_summary()

    async def clear_network_history(self, session_id: str) -> bool:
        """Clear network history."""
        session = self._require_session(session_id)
        session.network_monitor.clear_history()
        return True

    # Element references
    async def build_element_tree(self, session_id: str) -> dict[str, Any]:
        """Build element tree."""
        session = self._require_session(session_id)
        tree = await session.element_reference.build_element_tree(session.page)
        return tree.to_dict()

    async def get_element_by_ref(self, session_id: str, ref: str) -> Optional[dict[str, Any]]:
        """Get element by reference."""
        session = self._require_session(session_id)
        elem = await session.element_reference.get_element_by_ref(ref)
        return elem.to_dict() if elem else None

    async def click_by_ref(self, session_id: str, ref: str) -> bool:
        """Click element by reference."""
        session = self._require_session(session_id)
        return await session.element_reference.click_by_ref(ref)

    async def fill_by_ref(self, session_id: str, ref: str, value: str) -> bool:
        """Fill element by reference."""
        session = self._require_session(session_id)
        return await session.element_reference.fill_by_ref(ref, value)

    # Console monitoring
    async def get_console_messages(
        self,
        session_id: str,
        pattern: Optional[str] = None,
        only_errors: bool = False,
    ) -> list[dict[str, Any]]:
        """Get console messages."""
        session = self._require_session(session_id)
        messages = session.console_monitor.get_messages(pattern, only_errors)
        return [m.to_dict() for m in messages]

    async def get_console_errors(self, session_id: str) -> list[dict[str, Any]]:
        """Get console errors."""
        session = self._require_session(session_id)
        errors = session.console_monitor.get_errors()
        return [e.to_dict() for e in errors]

    async def get_console_summary(self, session_id: str) -> dict[str, Any]:
        """Get console summary."""
        session = self._require_session(session_id)
        return session.console_monitor.get_summary()

    async def clear_console_messages(self, session_id: str) -> bool:
        """Clear console messages."""
        session = self._require_session(session_id)
        session.console_monitor.clear_messages()
        return True

    # Natural language locator
    async def find_element_by_description(
        self,
        session_id: str,
        description: str,
    ) -> Optional[dict[str, Any]]:
        """Find element by description."""
        session = self._require_session(session_id)
        element = await session.natural_locator.find_element(session.page, description)
        if element:
            return {
                "selector": element.selector,
                "confidence": element.confidence,
                "reason": element.reason,
                "text": element.text,
                "tag_name": element.tag_name,
            }
        return None

    async def find_elements_by_description(
        self,
        session_id: str,
        description: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find elements by description."""
        session = self._require_session(session_id)
        elements = await session.natural_locator.find_elements(
            session.page,
            description,
            limit,
        )
        return [
            {
                "selector": e.selector,
                "confidence": e.confidence,
                "reason": e.reason,
                "text": e.text,
                "tag_name": e.tag_name,
            }
            for e in elements
        ]

    # Page snapshots
    async def capture_snapshot(
        self,
        session_id: str,
        label: str = "",
        include_accessibility: bool = True,
        include_network: bool = False,
        include_console: bool = False,
    ) -> dict[str, Any]:
        """Capture page snapshot."""
        session = self._require_session(session_id)
        snapshot = await session.snapshot_manager.capture_snapshot(
            session.page,
            label,
            include_accessibility,
            include_network,
            include_console,
        )
        return snapshot.to_dict()

    async def compare_snapshots(
        self,
        session_id: str,
        before_label: str,
        after_label: str,
    ) -> Optional[dict[str, Any]]:
        """Compare snapshots."""
        session = self._require_session(session_id)
        before = session.snapshot_manager.get_snapshot(before_label)
        after = session.snapshot_manager.get_snapshot(after_label)

        if not before or not after:
            return None

        diff = session.snapshot_manager.compare_snapshots(before, after)
        return diff.to_dict()

    async def get_dom_diff(
        self,
        session_id: str,
        before_label: str,
        after_label: str,
    ) -> Optional[list[str]]:
        """Get DOM diff."""
        session = self._require_session(session_id)
        return session.snapshot_manager.get_dom_diff(before_label, after_label)

    def _require_session(self, session_id: str) -> AdvancedBrowserSession:
        """Get session or raise error."""
        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Advanced browser session not found: {session_id}")
        return session


# Global instance
advanced_browser_monitoring = AdvancedBrowserMonitoring()
