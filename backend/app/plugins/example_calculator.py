"""Example Tool Plugin - Simple Calculator"""

from __future__ import annotations

from typing import Any


class CalculatorPlugin:
    """Simple calculator plugin demonstrating plugin interface"""

    PLUGIN_NAME = "calculator"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_AUTHOR = "X-Agent Team"
    PLUGIN_DESCRIPTION = "Basic arithmetic operations plugin"
    PLUGIN_CAPABILITIES = ["add", "subtract", "multiply", "divide"]
    PLUGIN_PERMISSIONS = ["math:execute"]

    @staticmethod
    def add(a: float, b: float) -> dict[str, Any]:
        """Add two numbers"""
        return {"result": a + b, "operation": "add"}

    @staticmethod
    def subtract(a: float, b: float) -> dict[str, Any]:
        """Subtract two numbers"""
        return {"result": a - b, "operation": "subtract"}

    @staticmethod
    def multiply(a: float, b: float) -> dict[str, Any]:
        """Multiply two numbers"""
        return {"result": a * b, "operation": "multiply"}

    @staticmethod
    def divide(a: float, b: float) -> dict[str, Any]:
        """Divide two numbers"""
        if b == 0:
            return {"error": "Division by zero", "operation": "divide"}
        return {"result": a / b, "operation": "divide"}

    @staticmethod
    def execute(action: str, **kwargs) -> dict[str, Any]:
        """Execute plugin action"""
        if action == "add":
            return CalculatorPlugin.add(kwargs.get("a", 0), kwargs.get("b", 0))
        elif action == "subtract":
            return CalculatorPlugin.subtract(kwargs.get("a", 0), kwargs.get("b", 0))
        elif action == "multiply":
            return CalculatorPlugin.multiply(kwargs.get("a", 0), kwargs.get("b", 0))
        elif action == "divide":
            return CalculatorPlugin.divide(kwargs.get("a", 0), kwargs.get("b", 1))
        else:
            return {"error": f"Unknown action: {action}"}


# Plugin entry point
plugin = CalculatorPlugin()
