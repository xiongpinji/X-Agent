"""Page state snapshot and comparison for browser automation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional
from difflib import unified_diff

try:
    from playwright.async_api import Page
except ImportError:
    Page = object  # type: ignore[assignment]


@dataclass
class DOMSnapshot:
    """Snapshot of the DOM state."""
    html: str
    title: str
    url: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "html_length": len(self.html),
            "title": self.title,
            "url": self.url,
            "timestamp": self.timestamp,
        }


@dataclass
class AccessibilitySnapshot:
    """Snapshot of accessibility tree."""
    tree_json: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tree_size": len(self.tree_json),
            "timestamp": self.timestamp,
        }


@dataclass
class NetworkSnapshot:
    """Snapshot of network state."""
    request_count: int
    response_count: int
    failed_count: int
    total_duration_ms: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_count": self.request_count,
            "response_count": self.response_count,
            "failed_count": self.failed_count,
            "total_duration_ms": self.total_duration_ms,
            "timestamp": self.timestamp,
        }


@dataclass
class ConsoleSnapshot:
    """Snapshot of console state."""
    message_count: int
    error_count: int
    warning_count: int
    messages: list[dict[str, Any]] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_count": self.message_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "timestamp": self.timestamp,
        }


@dataclass
class PageSnapshot:
    """Complete snapshot of page state."""
    dom: DOMSnapshot
    accessibility: Optional[AccessibilitySnapshot] = None
    network: Optional[NetworkSnapshot] = None
    console: Optional[ConsoleSnapshot] = None
    timestamp: float = field(default_factory=time.time)
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dom": self.dom.to_dict(),
            "accessibility": self.accessibility.to_dict() if self.accessibility else None,
            "network": self.network.to_dict() if self.network else None,
            "console": self.console.to_dict() if self.console else None,
            "timestamp": self.timestamp,
            "label": self.label,
        }


@dataclass
class SnapshotDiff:
    """Difference between two snapshots."""
    before_label: str
    after_label: str
    dom_changed: bool
    dom_diff_lines: list[str] = field(default_factory=list)
    title_changed: bool = False
    url_changed: bool = False
    network_changed: bool = False
    console_changed: bool = False
    error_count_increased: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "before_label": self.before_label,
            "after_label": self.after_label,
            "dom_changed": self.dom_changed,
            "dom_diff_lines_count": len(self.dom_diff_lines),
            "title_changed": self.title_changed,
            "url_changed": self.url_changed,
            "network_changed": self.network_changed,
            "console_changed": self.console_changed,
            "error_count_increased": self.error_count_increased,
            "timestamp": self.timestamp,
        }


class PageSnapshotManager:
    """Manages page snapshots and comparisons."""

    def __init__(self, page: Page | None = None):
        self.page = page
        self._snapshots: dict[str, PageSnapshot] = {}

    async def capture_snapshot(
        self,
        page: Page,
        label: str = "",
        include_accessibility: bool = True,
        include_network: bool = False,
        include_console: bool = False,
    ) -> PageSnapshot:
        """Capture a complete snapshot of the page state."""
        self.page = page

        # Capture DOM
        html = await page.content()
        title = await page.title()
        url = page.url

        dom = DOMSnapshot(html=html, title=title, url=url)

        # Capture accessibility tree if requested
        accessibility = None
        if include_accessibility:
            try:
                tree_json = await page.accessibility.snapshot()
                accessibility = AccessibilitySnapshot(tree_json=str(tree_json))
            except Exception:
                pass

        # Placeholder for network snapshot (would need network monitor)
        network = None
        if include_network:
            network = NetworkSnapshot(
                request_count=0,
                response_count=0,
                failed_count=0,
                total_duration_ms=0.0,
            )

        # Placeholder for console snapshot (would need console monitor)
        console = None
        if include_console:
            console = ConsoleSnapshot(
                message_count=0,
                error_count=0,
                warning_count=0,
            )

        snapshot = PageSnapshot(
            dom=dom,
            accessibility=accessibility,
            network=network,
            console=console,
            label=label,
        )

        if label:
            self._snapshots[label] = snapshot

        return snapshot

    def compare_snapshots(
        self,
        before: PageSnapshot,
        after: PageSnapshot,
    ) -> SnapshotDiff:
        """Compare two snapshots and return differences."""
        # Compare DOM
        dom_changed = before.dom.html != after.dom.html
        dom_diff_lines = []

        if dom_changed:
            # Generate unified diff
            before_lines = before.dom.html.split("\n")
            after_lines = after.dom.html.split("\n")
            diff = unified_diff(
                before_lines,
                after_lines,
                lineterm="",
                n=1,  # Context lines
            )
            dom_diff_lines = list(diff)[:50]  # Limit to 50 lines

        # Compare other attributes
        title_changed = before.dom.title != after.dom.title
        url_changed = before.dom.url != after.dom.url

        network_changed = False
        if before.network and after.network:
            network_changed = (
                before.network.request_count != after.network.request_count
                or before.network.response_count != after.network.response_count
            )

        console_changed = False
        error_count_increased = False
        if before.console and after.console:
            console_changed = before.console.message_count != after.console.message_count
            error_count_increased = after.console.error_count > before.console.error_count

        diff = SnapshotDiff(
            before_label=before.label,
            after_label=after.label,
            dom_changed=dom_changed,
            dom_diff_lines=dom_diff_lines,
            title_changed=title_changed,
            url_changed=url_changed,
            network_changed=network_changed,
            console_changed=console_changed,
            error_count_increased=error_count_increased,
        )

        return diff

    def get_snapshot(self, label: str) -> Optional[PageSnapshot]:
        """Get a previously captured snapshot by label."""
        return self._snapshots.get(label)

    def list_snapshots(self) -> list[str]:
        """List all captured snapshot labels."""
        return list(self._snapshots.keys())

    def clear_snapshots(self) -> None:
        """Clear all snapshots."""
        self._snapshots.clear()

    def get_dom_diff(self, before_label: str, after_label: str) -> Optional[list[str]]:
        """Get DOM diff between two labeled snapshots."""
        before = self._snapshots.get(before_label)
        after = self._snapshots.get(after_label)

        if not before or not after:
            return None

        before_lines = before.dom.html.split("\n")
        after_lines = after.dom.html.split("\n")

        diff = unified_diff(
            before_lines,
            after_lines,
            fromfile=before_label,
            tofile=after_label,
            lineterm="",
            n=2,
        )

        return list(diff)
