"""MCP browser control tool with permission control and audit logging."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class BrowserAuditLog:
    """Audit log for browser operations."""

    def __init__(self, max_entries: int = 1000):
        """Initialize audit log.

        Args:
            max_entries: Maximum number of log entries to keep
        """
        self.max_entries = max_entries
        self.entries: list[dict[str, Any]] = []

    def log(
        self,
        operation: str,
        details: dict[str, Any] | None = None,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """Log a browser operation.

        Args:
            operation: Operation type (navigate, click, type, screenshot, etc.)
            details: Additional details
            success: Whether operation succeeded
            error: Error message if failed
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "success": success,
            "details": details or {},
            "error": error,
        }
        self.entries.append(entry)

        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]

        log_level = logging.INFO if success else logging.WARNING
        logger.log(log_level, f"Audit: {operation} - {success}")

    def get_entries(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent audit log entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of audit log entries
        """
        return self.entries[-limit:]

    def clear(self) -> None:
        """Clear all audit logs."""
        self.entries.clear()


class BrowserPermissionChecker:
    """Permission checker for browser operations."""

    def __init__(self, allowed_operations: dict[str, bool] | None = None):
        """Initialize permission checker.

        Args:
            allowed_operations: Dict of operation -> allowed
        """
        self.allowed_operations = allowed_operations or {
            "navigate": True,
            "click": True,
            "type": True,
            "screenshot": True,
            "scroll": True,
            "wait": True,
            "get_page_content": True,
            "execute_script": False,  # Disabled by default for security
        }

    def check_permission(self, operation: str) -> bool:
        """Check if operation is allowed.

        Args:
            operation: Operation type

        Returns:
            True if allowed, False otherwise
        """
        return self.allowed_operations.get(operation, False)

    def set_permission(self, operation: str, allowed: bool) -> None:
        """Set permission for an operation.

        Args:
            operation: Operation type
            allowed: Whether to allow the operation
        """
        self.allowed_operations[operation] = allowed


class BrowserTool:
    """Browser control tool for MCP with permission control and audit logging."""

    def __init__(
        self,
        permission_checker: BrowserPermissionChecker | None = None,
        audit_log: BrowserAuditLog | None = None,
    ):
        """Initialize browser tool.

        Args:
            permission_checker: Permission checker instance
            audit_log: Audit log instance
        """
        self.permission_checker = permission_checker or BrowserPermissionChecker()
        self.audit_log = audit_log or BrowserAuditLog()
        self.browser = None
        self.page = None

    async def navigate(self, url: str) -> dict[str, Any]:
        """Navigate to a URL.

        Args:
            url: URL to navigate to

        Returns:
            Navigation result

        Raises:
            PermissionError: If navigate operation is not allowed
        """
        if not self.permission_checker.check_permission("navigate"):
            error_msg = "Navigate operation not allowed"
            self.audit_log.log("navigate", {"url": url}, False, error=error_msg)
            raise PermissionError(error_msg)

        try:
            # Placeholder - integrate with Playwright or Selenium
            logger.info(f"Navigating to {url}")
            self.audit_log.log("navigate", {"url": url}, True)
            return {
                "success": True,
                "url": url,
                "status": "navigated",
            }
        except Exception as e:
            self.audit_log.log("navigate", {"url": url}, False, error=str(e))
            raise

    async def click(self, selector: str) -> dict[str, Any]:
        """Click an element.

        Args:
            selector: CSS selector of element to click

        Returns:
            Click result

        Raises:
            PermissionError: If click operation is not allowed
        """
        if not self.permission_checker.check_permission("click"):
            error_msg = "Click operation not allowed"
            self.audit_log.log("click", {"selector": selector}, False, error=error_msg)
            raise PermissionError(error_msg)

        try:
            logger.info(f"Clicking element: {selector}")
            self.audit_log.log("click", {"selector": selector}, True)
            return {
                "success": True,
                "selector": selector,
                "status": "clicked",
            }
        except Exception as e:
            self.audit_log.log("click", {"selector": selector}, False, error=str(e))
            raise

    async def type_text(self, selector: str, text: str) -> dict[str, Any]:
        """Type text into an element.

        Args:
            selector: CSS selector of element
            text: Text to type

        Returns:
            Type result

        Raises:
            PermissionError: If type operation is not allowed
        """
        if not self.permission_checker.check_permission("type"):
            error_msg = "Type operation not allowed"
            self.audit_log.log("type", {"selector": selector}, False, error=error_msg)
            raise PermissionError(error_msg)

        try:
            logger.info(f"Typing into element: {selector}")
            self.audit_log.log("type", {"selector": selector, "text_length": len(text)}, True)
            return {
                "success": True,
                "selector": selector,
                "text_length": len(text),
                "status": "typed",
            }
        except Exception as e:
            self.audit_log.log("type", {"selector": selector}, False, error=str(e))
            raise

    async def screenshot(self, filename: str | None = None) -> dict[str, Any]:
        """Take a screenshot.

        Args:
            filename: Optional filename to save screenshot

        Returns:
            Screenshot result

        Raises:
            PermissionError: If screenshot operation is not allowed
        """
        if not self.permission_checker.check_permission("screenshot"):
            error_msg = "Screenshot operation not allowed"
            self.audit_log.log("screenshot", {}, False, error=error_msg)
            raise PermissionError(error_msg)

        try:
            logger.info("Taking screenshot")
            self.audit_log.log("screenshot", {"filename": filename}, True)
            return {
                "success": True,
                "filename": filename or "screenshot.png",
                "status": "captured",
            }
        except Exception as e:
            self.audit_log.log("screenshot", {}, False, error=str(e))
            raise

    async def scroll(self, direction: str = "down", amount: int = 3) -> dict[str, Any]:
        """Scroll the page.

        Args:
            direction: Scroll direction (up, down, left, right)
            amount: Scroll amount

        Returns:
            Scroll result

        Raises:
            PermissionError: If scroll operation is not allowed
        """
        if not self.permission_checker.check_permission("scroll"):
            error_msg = "Scroll operation not allowed"
            self.audit_log.log("scroll", {"direction": direction}, False, error=error_msg)
            raise PermissionError(error_msg)

        try:
            logger.info(f"Scrolling {direction} by {amount}")
            self.audit_log.log("scroll", {"direction": direction, "amount": amount}, True)
            return {
                "success": True,
                "direction": direction,
                "amount": amount,
                "status": "scrolled",
            }
        except Exception as e:
            self.audit_log.log("scroll", {"direction": direction}, False, error=str(e))
            raise

    async def wait(self, duration: float) -> dict[str, Any]:
        """Wait for a duration.

        Args:
            duration: Duration to wait in seconds

        Returns:
            Wait result

        Raises:
            PermissionError: If wait operation is not allowed
        """
        if not self.permission_checker.check_permission("wait"):
            error_msg = "Wait operation not allowed"
            self.audit_log.log("wait", {"duration": duration}, False, error=error_msg)
            raise PermissionError(error_msg)

        try:
            logger.info(f"Waiting for {duration} seconds")
            await asyncio.sleep(duration)
            self.audit_log.log("wait", {"duration": duration}, True)
            return {
                "success": True,
                "duration": duration,
                "status": "waited",
            }
        except Exception as e:
            self.audit_log.log("wait", {"duration": duration}, False, error=str(e))
            raise

    async def get_page_content(self) -> dict[str, Any]:
        """Get page content.

        Returns:
            Page content

        Raises:
            PermissionError: If get_page_content operation is not allowed
        """
        if not self.permission_checker.check_permission("get_page_content"):
            error_msg = "Get page content operation not allowed"
            self.audit_log.log("get_page_content", {}, False, error=error_msg)
            raise PermissionError(error_msg)

        try:
            logger.info("Getting page content")
            self.audit_log.log("get_page_content", {}, True)
            return {
                "success": True,
                "content": "Page content placeholder",
                "status": "retrieved",
            }
        except Exception as e:
            self.audit_log.log("get_page_content", {}, False, error=str(e))
            raise

    async def execute_script(self, script: str) -> dict[str, Any]:
        """Execute JavaScript on the page.

        Args:
            script: JavaScript code to execute

        Returns:
            Execution result

        Raises:
            PermissionError: If execute_script operation is not allowed
        """
        if not self.permission_checker.check_permission("execute_script"):
            error_msg = "Execute script operation not allowed"
            self.audit_log.log("execute_script", {}, False, error=error_msg)
            raise PermissionError(error_msg)

        try:
            logger.info("Executing script")
            self.audit_log.log("execute_script", {"script_length": len(script)}, True)
            return {
                "success": True,
                "result": "Script execution result",
                "status": "executed",
            }
        except Exception as e:
            self.audit_log.log("execute_script", {}, False, error=str(e))
            raise

    def get_audit_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get audit logs.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of audit log entries
        """
        return self.audit_log.get_entries(limit)

    def set_permissions(self, permissions: dict[str, bool]) -> None:
        """Set permissions for operations.

        Args:
            permissions: Dict of operation -> allowed
        """
        for operation, allowed in permissions.items():
            self.permission_checker.set_permission(operation, allowed)

    def get_permissions(self) -> dict[str, bool]:
        """Get current permissions.

        Returns:
            Dict of operation -> allowed
        """
        return self.permission_checker.allowed_operations.copy()

    async def close(self) -> None:
        """Close the browser."""
        if self.browser:
            await self.browser.close()
        logger.info("Browser closed")

    async def __aenter__(self) -> BrowserTool:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
