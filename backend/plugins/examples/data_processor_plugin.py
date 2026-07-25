"""
Data Processor Plugin - Example plugin for X-Agent

This plugin demonstrates:
- Basic plugin structure
- Capability implementation
- Permission usage
- Error handling
- Configuration support
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class DataProcessorPlugin:
    """Data processing plugin"""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize plugin"""
        self.config = config or {}
        self.name = "Data Processor"
        self.version = "1.0.0"
        self.logger = logger

    def initialize(self) -> bool:
        """Initialize plugin"""
        try:
            self.logger.info(f"Initializing {self.name} v{self.version}")
            # Validate configuration
            return self._validate_config()
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            return False

    def _validate_config(self) -> bool:
        """Validate configuration"""
        required_keys = []
        for key in required_keys:
            if key not in self.config:
                self.logger.warning(f"Missing config key: {key}")
        return True

    def execute(self, action: str, **kwargs) -> dict[str, Any]:
        """Execute plugin action"""
        try:
            if action == "process_array":
                return self._process_array(**kwargs)
            elif action == "aggregate":
                return self._aggregate(**kwargs)
            elif action == "transform":
                return self._transform(**kwargs)
            elif action == "filter":
                return self._filter(**kwargs)
            elif action == "sort":
                return self._sort(**kwargs)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        except Exception as e:
            self.logger.error(f"Execution failed: {e}")
            return {"success": False, "error": str(e)}

    def _process_array(self, **kwargs) -> dict[str, Any]:
        """Process array data"""
        try:
            data = kwargs.get("data", [])
            operation = kwargs.get("operation", "double")

            if not isinstance(data, list):
                return {"success": False, "error": "Data must be a list"}

            if operation == "double":
                result = [x * 2 for x in data]
            elif operation == "square":
                result = [x ** 2 for x in data]
            elif operation == "sqrt":
                result = [x ** 0.5 for x in data]
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}

            return {
                "success": True,
                "result": result,
                "count": len(result)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _aggregate(self, **kwargs) -> dict[str, Any]:
        """Aggregate data"""
        try:
            data = kwargs.get("data", [])
            method = kwargs.get("method", "sum")

            if not isinstance(data, list):
                return {"success": False, "error": "Data must be a list"}

            if not data:
                return {"success": False, "error": "Data is empty"}

            if method == "sum":
                result = sum(data)
            elif method == "avg":
                result = sum(data) / len(data)
            elif method == "min":
                result = min(data)
            elif method == "max":
                result = max(data)
            else:
                return {"success": False, "error": f"Unknown method: {method}"}

            return {
                "success": True,
                "result": result,
                "method": method
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _transform(self, **kwargs) -> dict[str, Any]:
        """Transform data"""
        try:
            data = kwargs.get("data", {})
            transformation = kwargs.get("transformation", "json")

            if transformation == "json":
                result = json.dumps(data)
            elif transformation == "keys":
                result = list(data.keys()) if isinstance(data, dict) else []
            elif transformation == "values":
                result = list(data.values()) if isinstance(data, dict) else []
            else:
                return {"success": False, "error": f"Unknown transformation: {transformation}"}

            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _filter(self, **kwargs) -> dict[str, Any]:
        """Filter data"""
        try:
            data = kwargs.get("data", [])
            condition = kwargs.get("condition", "gt")
            value = kwargs.get("value", 0)

            if not isinstance(data, list):
                return {"success": False, "error": "Data must be a list"}

            if condition == "gt":
                result = [x for x in data if x > value]
            elif condition == "lt":
                result = [x for x in data if x < value]
            elif condition == "eq":
                result = [x for x in data if x == value]
            elif condition == "gte":
                result = [x for x in data if x >= value]
            elif condition == "lte":
                result = [x for x in data if x <= value]
            else:
                return {"success": False, "error": f"Unknown condition: {condition}"}

            return {
                "success": True,
                "result": result,
                "count": len(result)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _sort(self, **kwargs) -> dict[str, Any]:
        """Sort data"""
        try:
            data = kwargs.get("data", [])
            order = kwargs.get("order", "asc")

            if not isinstance(data, list):
                return {"success": False, "error": "Data must be a list"}

            if order == "asc":
                result = sorted(data)
            elif order == "desc":
                result = sorted(data, reverse=True)
            else:
                return {"success": False, "error": f"Unknown order: {order}"}

            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def shutdown(self) -> bool:
        """Shutdown plugin"""
        try:
            self.logger.info(f"Shutting down {self.name}")
            return True
        except Exception as e:
            self.logger.error(f"Shutdown failed: {e}")
            return False


# Global plugin instance
plugin = DataProcessorPlugin()


def initialize(config: dict[str, Any] | None = None) -> bool:
    """Initialize plugin"""
    global plugin
    plugin = DataProcessorPlugin(config)
    return plugin.initialize()


def execute(action: str, **kwargs) -> dict[str, Any]:
    """Execute plugin action"""
    return plugin.execute(action, **kwargs)


def shutdown() -> bool:
    """Shutdown plugin"""
    return plugin.shutdown()
