"""X-Agent Plugin Examples

This package contains example plugins demonstrating various plugin types and patterns.

Available examples:
- HelloWorldPlugin: Basic plugin example
- DatabaseConnectionPlugin: Database integration example
- APIIntegrationPlugin: REST API integration example
- CustomCommandPlugin: Custom command plugin example
- DataProcessingPlugin: Data processing plugin example
- NotificationPlugin: Notification plugin example
"""

from .hello_world_plugin import HelloWorldPlugin
from .database_plugin import DatabaseConnectionPlugin
from .api_plugin import APIIntegrationPlugin
from .custom_command_plugin import CustomCommandPlugin
from .data_processing_plugin import DataProcessingPlugin
from .notification_plugin import NotificationPlugin

__all__ = [
    "HelloWorldPlugin",
    "DatabaseConnectionPlugin",
    "APIIntegrationPlugin",
    "CustomCommandPlugin",
    "DataProcessingPlugin",
    "NotificationPlugin",
]

__version__ = "0.1.0"
