"""Console message monitoring for browser automation."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

try:
    from playwright.async_api import ConsoleMessage, Page
except ImportError:
    Page = ConsoleMessage = object  # type: ignore[assignment]


class ConsoleMessageType(StrEnum):
    """Types of console messages."""
    LOG = "log"
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ConsoleMessageRecord:
    """Represents a console message."""
    type: ConsoleMessageType
    text: str
    timestamp: float = field(default_factory=time.time)
    location: str | None = None
    args: list[str] = field(default_factory=list)
    stack_trace: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "text": self.text,
            "timestamp": self.timestamp,
            "location": self.location,
            "args": self.args,
            "stack_trace": self.stack_trace,
        }


class ConsoleMonitor:
    """Monitors console messages in a browser page."""

    def __init__(self, page: Page | None = None):
        self.page = page
        self._messages: list[ConsoleMessageRecord] = []
        self._listener_attached = False

    async def start_monitoring(self, page: Page) -> None:
        """Start monitoring console messages on the given page."""
        self.page = page
        if self._listener_attached:
            return

        page.on("console", self._on_console_message)
        page.on("pageerror", self._on_page_error)
        self._listener_attached = True

    async def stop_monitoring(self) -> None:
        """Stop monitoring console messages."""
        if self.page and self._listener_attached:
            self.page.remove_listener("console", self._on_console_message)
            self.page.remove_listener("pageerror", self._on_page_error)
            self._listener_attached = False

    def _on_console_message(self, msg: ConsoleMessage) -> None:
        """Handle console message event."""
        try:
            msg_type = self._map_console_type(msg.type)
            text = msg.text
            location = msg.location.get("url", "") if msg.location else None

            # Extract arguments
            args = []
            try:
                for arg in msg.args:
                    try:
                        args.append(str(arg.json_value()))
                    except Exception:
                        args.append(str(arg))
            except Exception:
                pass

            record = ConsoleMessageRecord(
                type=msg_type,
                text=text,
                location=location,
                args=args,
            )
            self._messages.append(record)
        except Exception:
            pass

    def _on_page_error(self, error: Exception) -> None:
        """Handle page error event."""
        try:
            record = ConsoleMessageRecord(
                type=ConsoleMessageType.ERROR,
                text=str(error),
                stack_trace=getattr(error, "__traceback__", None),
            )
            self._messages.append(record)
        except Exception:
            pass

    def _map_console_type(self, console_type: str) -> ConsoleMessageType:
        """Map Playwright console type to our enum."""
        type_map = {
            "log": ConsoleMessageType.LOG,
            "debug": ConsoleMessageType.DEBUG,
            "info": ConsoleMessageType.INFO,
            "warning": ConsoleMessageType.WARNING,
            "error": ConsoleMessageType.ERROR,
        }
        return type_map.get(console_type, ConsoleMessageType.LOG)

    def get_messages(
        self,
        pattern: str | None = None,
        only_errors: bool = False,
        message_type: ConsoleMessageType | None = None,
    ) -> list[ConsoleMessageRecord]:
        """Get console messages with optional filtering."""
        messages = self._messages

        # Filter by type
        if only_errors:
            messages = [m for m in messages if m.type == ConsoleMessageType.ERROR]
        elif message_type:
            messages = [m for m in messages if m.type == message_type]

        # Filter by pattern
        if pattern:
            try:
                regex = re.compile(pattern, re.IGNORECASE)
                messages = [m for m in messages if regex.search(m.text)]
            except re.error:
                pass

        return messages

    def get_errors(self) -> list[ConsoleMessageRecord]:
        """Get all error messages."""
        return self.get_messages(only_errors=True)

    def get_warnings(self) -> list[ConsoleMessageRecord]:
        """Get all warning messages."""
        return self.get_messages(message_type=ConsoleMessageType.WARNING)

    def get_logs(self) -> list[ConsoleMessageRecord]:
        """Get all log messages."""
        return self.get_messages(message_type=ConsoleMessageType.LOG)

    def has_errors(self) -> bool:
        """Check if there are any error messages."""
        return len(self.get_errors()) > 0

    def has_warnings(self) -> bool:
        """Check if there are any warning messages."""
        return len(self.get_warnings()) > 0

    def clear_messages(self) -> None:
        """Clear all captured messages."""
        self._messages.clear()

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of console activity."""
        errors = self.get_errors()
        warnings = self.get_warnings()
        logs = self.get_logs()

        return {
            "total_messages": len(self._messages),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "log_count": len(logs),
            "has_errors": len(errors) > 0,
            "has_warnings": len(warnings) > 0,
            "first_error": errors[0].to_dict() if errors else None,
            "first_warning": warnings[0].to_dict() if warnings else None,
        }

    def get_messages_by_location(self, location: str) -> list[ConsoleMessageRecord]:
        """Get messages from a specific location."""
        return [m for m in self._messages if m.location and location in m.location]
