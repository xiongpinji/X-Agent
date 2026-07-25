"""Dependency Injection Container for X-Agent.

Provides a lightweight DI container that manages application dependencies
and allows easy replacement for testing.

Usage:
    from backend.app.container import container, Container
    
    # Get dependencies
    settings = container.settings
    redis = container.redis
    memory = container.memory
    
    # Override for testing
    container.override("memory", mock_memory)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger("xagent.container")

T = TypeVar("T")


class Container:
    """Lightweight dependency injection container.
    
    Manages singleton dependencies and allows runtime overrides for testing.
    Dependencies are lazily initialized on first access.
    """
    
    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], Any]] = {}
        self._singletons: dict[str, Any] = {}
        self._overrides: dict[str, Any] = {}
    
    def register(self, name: str, factory: Callable[[], T]) -> None:
        """Register a dependency factory.
        
        Args:
            name: Dependency name.
            factory: Callable that creates the dependency.
        """
        self._factories[name] = factory
        # Clear any cached singleton
        self._singletons.pop(name, None)
    
    def get(self, name: str) -> Any:
        """Get a dependency by name.
        
        Args:
            name: Dependency name.
            
        Returns:
            The dependency instance.
            
        Raises:
            KeyError: If dependency is not registered.
        """
        # Check overrides first (for testing)
        if name in self._overrides:
            return self._overrides[name]
        
        # Check cached singleton
        if name in self._singletons:
            return self._singletons[name]
        
        # Create from factory
        if name not in self._factories:
            raise KeyError(f"Dependency '{name}' not registered")
        
        instance = self._factories[name]()
        self._singletons[name] = instance
        return instance
    
    def override(self, name: str, instance: Any) -> None:
        """Override a dependency (for testing).
        
        Args:
            name: Dependency name.
            instance: Override instance.
        """
        self._overrides[name] = instance
        logger.debug(f"Dependency '{name}' overridden for testing")
    
    def clear_override(self, name: str) -> None:
        """Clear a dependency override.
        
        Args:
            name: Dependency name.
        """
        self._overrides.pop(name, None)
    
    def clear_all_overrides(self) -> None:
        """Clear all dependency overrides."""
        self._overrides.clear()
    
    def reset(self) -> None:
        """Reset all singletons (for testing)."""
        self._singletons.clear()
        self._overrides.clear()
    
    # Convenience properties for common dependencies
    
    @property
    def settings(self) -> Any:
        """Get application settings."""
        return self.get("settings")
    
    @property
    def redis(self) -> Any:
        """Get Redis client."""
        return self.get("redis")
    
    @property
    def memory(self) -> Any:
        """Get memory system."""
        return self.get("memory")
    
    @property
    def llm_router(self) -> Any:
        """Get LLM router."""
        return self.get("llm_router")
    
    @property
    def tool_registry(self) -> Any:
        """Get tool registry."""
        return self.get("tool_registry")
    
    @property
    def workflow_repository(self) -> Any:
        """Get workflow repository."""
        return self.get("workflow_repository")
    
    @property
    def audit_store(self) -> Any:
        """Get audit store."""
        return self.get("audit_store")
    
    @property
    def trace_store(self) -> Any:
        """Get trace store."""
        return self.get("trace_store")
    
    @property
    def run_store(self) -> Any:
        """Get run store."""
        return self.get("run_store")


# Global container instance
container = Container()


def _register_default_factories() -> None:
    """Register default dependency factories."""
    
    def _create_settings() -> Any:
        from backend.app.settings import get_settings
        return get_settings()
    
    def _create_redis() -> Any:
        from backend.app.core.redis_client import get_redis
        return get_redis()
    
    def _create_memory() -> Any:
        from backend.app.dependencies import get_memory
        return get_memory()
    
    def _create_tool_registry() -> Any:
        from backend.app.core.tool_registry import ToolCatalog
        return ToolCatalog()
    
    def _create_workflow_repository() -> Any:
        from backend.app.dependencies import get_workflow_repository
        return get_workflow_repository()
    
    def _create_audit_store() -> Any:
        from backend.app.dependencies import get_audit_store
        return get_audit_store()
    
    def _create_trace_store() -> Any:
        from backend.app.dependencies import get_trace_store
        return get_trace_store()
    
    def _create_run_store() -> Any:
        from backend.app.dependencies import get_run_store
        return get_run_store()
    
    container.register("settings", _create_settings)
    container.register("redis", _create_redis)
    container.register("memory", _create_memory)
    container.register("tool_registry", _create_tool_registry)
    container.register("workflow_repository", _create_workflow_repository)
    container.register("audit_store", _create_audit_store)
    container.register("trace_store", _create_trace_store)
    container.register("run_store", _create_run_store)


# Register default factories on import
_register_default_factories()


def get_container() -> Container:
    """Get the global container instance."""
    return container


def reset_container() -> None:
    """Reset the container (for testing)."""
    container.reset()
    _register_default_factories()
