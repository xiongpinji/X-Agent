"""Hello World Plugin - Basic example plugin"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class HelloWorldPlugin:
    """Simple Hello World plugin"""

    name = "hello-world"
    version = "0.1.0"
    description = "A simple Hello World plugin"
    author = "X-Agent Team"
    license = "MIT"

    def __init__(self):
        self.enabled = False
        self.tools = {}

    async def initialize(self) -> None:
        """Initialize plugin"""
        logger.info(f"Initializing {self.name}")
        self.enabled = True

    async def register(self) -> None:
        """Register tools"""
        logger.info("Registering tools")
        self.tools["hello"] = self.hello_tool
        self.tools["greet"] = self.greet_tool

    async def cleanup(self) -> None:
        """Cleanup plugin"""
        logger.info(f"Cleaning up {self.name}")
        self.enabled = False

    async def hello_tool(self, **kwargs) -> Dict[str, Any]:
        """Simple hello tool"""
        return {
            "status": "success",
            "message": "Hello, World!"
        }

    async def greet_tool(self, name: str = "World", **kwargs) -> Dict[str, Any]:
        """Greet tool"""
        if not name:
            raise ValueError("Name cannot be empty")

        return {
            "status": "success",
            "message": f"Hello, {name}!"
        }


# Export plugin
__all__ = ["HelloWorldPlugin"]
