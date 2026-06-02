"""Custom Command Plugin - Example custom command plugin"""

import logging
from typing import Any, Dict, Callable, Optional

logger = logging.getLogger(__name__)


class CustomCommandPlugin:
    """Custom command plugin"""

    name = "custom-command"
    version = "0.1.0"
    description = "Custom command plugin"
    author = "X-Agent Team"
    license = "MIT"

    def __init__(self):
        self.enabled = False
        self.commands = {}

    async def initialize(self) -> None:
        """Initialize plugin"""
        logger.info(f"Initializing {self.name}")
        self.enabled = True

    async def register(self) -> None:
        """Register commands"""
        logger.info("Registering commands")
        self.register_command("echo", self.echo_command)
        self.register_command("calculate", self.calculate_command)
        self.register_command("transform", self.transform_command)

    async def cleanup(self) -> None:
        """Cleanup plugin"""
        logger.info(f"Cleaning up {self.name}")
        self.commands.clear()
        self.enabled = False

    def register_command(self, name: str, handler: Callable) -> None:
        """Register command"""
        logger.info(f"Registering command: {name}")
        self.commands[name] = handler

    async def execute_command(self, command: str, **kwargs) -> Dict[str, Any]:
        """Execute command"""
        if command not in self.commands:
            return {
                "status": "error",
                "message": f"Unknown command: {command}"
            }

        try:
            handler = self.commands[command]
            result = await handler(**kwargs)
            return {
                "status": "success",
                "result": result
            }
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def echo_command(self, text: str = "", **kwargs) -> str:
        """Echo command"""
        logger.info(f"Echo: {text}")
        return text

    async def calculate_command(self, expression: str = "", **kwargs) -> float:
        """Calculate command"""
        logger.info(f"Calculate: {expression}")
        try:
            # Simple calculation (in production, use safer evaluation)
            result = eval(expression)
            return result
        except Exception as e:
            raise ValueError(f"Invalid expression: {e}")

    async def transform_command(self, text: str = "", operation: str = "upper", **kwargs) -> str:
        """Transform command"""
        logger.info(f"Transform: {text} ({operation})")

        if operation == "upper":
            return text.upper()
        elif operation == "lower":
            return text.lower()
        elif operation == "reverse":
            return text[::-1]
        elif operation == "capitalize":
            return text.capitalize()
        else:
            raise ValueError(f"Unknown operation: {operation}")


# Export plugin
__all__ = ["CustomCommandPlugin"]
