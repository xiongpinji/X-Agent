"""
Dependency Injection Container for X-Agent.

Provides a lightweight, type-safe DI container with support for:
- Singleton and transient scopes
- Lazy initialization
- Constructor injection
- Circular dependency detection
- Async factory functions
- Thread-safe operations
"""

from __future__ import annotations

import asyncio
import inspect
import threading
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, get_type_hints

T = TypeVar("T")
P = TypeVar("P")


class ServiceNotFoundError(Exception):
    """Raised when a service is not registered in the container."""

    def __init__(self, service_type: type, message: str = "") -> None:
        self.service_type = service_type
        type_name = getattr(service_type, "__name__", str(service_type))
        msg = f"Service not found: {type_name}"
        if message:
            msg += f" ({message})"
        super().__init__(msg)


class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected."""

    def __init__(self, chain: list[str]) -> None:
        self.chain = chain
        msg = f"Circular dependency detected: {' -> '.join(chain)} -> {chain[0]}"
        super().__init__(msg)


class ContainerError(Exception):
    """Base exception for container-related errors."""

    pass


class Scope:
    """Enumeration of service scopes."""

    SINGLETON = "singleton"
    TRANSIENT = "transient"


class ServiceFactory(Protocol[T]):
    """Protocol for service factory functions."""

    def __call__(self, container: Container) -> T:
        """Create and return a service instance."""
        ...


class AsyncServiceFactory(Protocol[T]):
    """Protocol for async service factory functions."""

    async def __call__(self, container: Container) -> T:
        """Create and return a service instance asynchronously."""
        ...


@dataclass
class ServiceDescriptor:
    """Describes a registered service."""

    service_type: type
    factory: ServiceFactory | AsyncServiceFactory | type
    scope: str = Scope.SINGLETON
    is_async: bool = False
    instance: Any = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def is_singleton(self) -> bool:
        return self.scope == Scope.SINGLETON

    def is_transient(self) -> bool:
        return self.scope == Scope.TRANSIENT


class Container:
    """
    Lightweight dependency injection container.

    Supports singleton and transient scopes, lazy initialization,
    and circular dependency detection.
    """

    def __init__(self) -> None:
        self._services: dict[type, ServiceDescriptor] = {}
        self._resolution_stack: list[str] = []
        self._lock = threading.RLock()
        self._async_lock = asyncio.Lock()

    def register(
        self,
        service_type: type[T],
        factory: ServiceFactory[T] | type[T] | None = None,
        scope: str = Scope.SINGLETON,
    ) -> Container:
        """
        Register a service in the container.

        Args:
            service_type: The service interface/type
            factory: Factory function or class. If None, service_type is used as factory
            scope: Service scope (singleton or transient)

        Returns:
            Self for method chaining

        Raises:
            ValueError: If scope is invalid
        """
        if scope not in (Scope.SINGLETON, Scope.TRANSIENT):
            raise ValueError(f"Invalid scope: {scope}")

        with self._lock:
            factory = factory or service_type
            descriptor = ServiceDescriptor(
                service_type=service_type,
                factory=factory,
                scope=scope,
                is_async=False,
            )
            self._services[service_type] = descriptor
        return self

    def register_async(
        self,
        service_type: type[T],
        factory: AsyncServiceFactory[T],
        scope: str = Scope.SINGLETON,
    ) -> Container:
        """
        Register an async service factory.

        Args:
            service_type: The service interface/type
            factory: Async factory function
            scope: Service scope (singleton or transient)

        Returns:
            Self for method chaining
        """
        if scope not in (Scope.SINGLETON, Scope.TRANSIENT):
            raise ValueError(f"Invalid scope: {scope}")

        with self._lock:
            descriptor = ServiceDescriptor(
                service_type=service_type,
                factory=factory,
                scope=scope,
                is_async=True,
            )
            self._services[service_type] = descriptor
        return self

    def singleton(
        self,
        service_type: type[T],
        factory: ServiceFactory[T] | type[T] | None = None,
    ) -> Container:
        """Register a singleton service."""
        return self.register(service_type, factory, Scope.SINGLETON)

    def transient(
        self,
        service_type: type[T],
        factory: ServiceFactory[T] | type[T] | None = None,
    ) -> Container:
        """Register a transient service."""
        return self.register(service_type, factory, Scope.TRANSIENT)

    def resolve(self, service_type: type[T]) -> T:
        """
        Resolve a service instance.

        Args:
            service_type: The service type to resolve

        Returns:
            An instance of the service

        Raises:
            ServiceNotFoundError: If service is not registered
            CircularDependencyError: If circular dependency is detected
        """
        with self._lock:
            if service_type not in self._services:
                raise ServiceNotFoundError(service_type)

            descriptor = self._services[service_type]

            # Check for circular dependencies
            service_name = service_type.__name__
            if service_name in self._resolution_stack:
                raise CircularDependencyError([*self._resolution_stack, service_name])

            # Return cached singleton
            if descriptor.is_singleton() and descriptor.instance is not None:
                return descriptor.instance

            # Resolve the service
            self._resolution_stack.append(service_name)
            try:
                instance = self._create_instance(descriptor)
                if descriptor.is_singleton():
                    descriptor.instance = instance
                return instance
            finally:
                self._resolution_stack.pop()

    async def resolve_async(self, service_type: type[T]) -> T:
        """
        Resolve a service instance asynchronously.

        Args:
            service_type: The service type to resolve

        Returns:
            An instance of the service

        Raises:
            ServiceNotFoundError: If service is not registered
            CircularDependencyError: If circular dependency is detected
        """
        async with self._async_lock:
            if service_type not in self._services:
                raise ServiceNotFoundError(service_type)

            descriptor = self._services[service_type]

            # Check for circular dependencies
            service_name = service_type.__name__
            if service_name in self._resolution_stack:
                raise CircularDependencyError([*self._resolution_stack, service_name])

            # Return cached singleton
            if descriptor.is_singleton() and descriptor.instance is not None:
                return descriptor.instance

            # Resolve the service
            self._resolution_stack.append(service_name)
            try:
                if descriptor.is_async:
                    instance = await self._create_instance_async(descriptor)
                else:
                    instance = self._create_instance(descriptor)

                if descriptor.is_singleton():
                    descriptor.instance = instance
                return instance
            finally:
                self._resolution_stack.pop()

    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create an instance of a service."""
        factory = descriptor.factory

        # If factory is a class, try to instantiate with constructor injection
        if inspect.isclass(factory):
            return self._instantiate_class(factory)

        # Otherwise, call the factory function
        return factory(self)

    async def _create_instance_async(self, descriptor: ServiceDescriptor) -> Any:
        """Create an instance of an async service."""
        factory = descriptor.factory

        # If factory is a class, try to instantiate with constructor injection
        if inspect.isclass(factory):
            return self._instantiate_class(factory)

        # Otherwise, call the async factory function
        return await factory(self)

    def _instantiate_class(self, cls: type[T]) -> T:
        """Instantiate a class with constructor injection."""
        sig = inspect.signature(cls.__init__)
        kwargs = {}

        # Resolve string forward-reference annotations (e.g. ``param: "ServiceB"``)
        # to concrete types. ``inspect.signature`` leaves these as strings, which
        # the type-based registry cannot match. ``get_type_hints`` evaluates them
        # against the class's module/global namespace.
        try:
            resolved_hints = get_type_hints(cls.__init__)
        except Exception:
            resolved_hints = {}

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            # Try to resolve by type annotation
            if param.annotation != inspect.Parameter.empty:
                param_type = resolved_hints.get(param_name, param.annotation)
                if param_type in self._services:
                    kwargs[param_name] = self.resolve(param_type)
                elif param.default == inspect.Parameter.empty:
                    raise ServiceNotFoundError(
                        param_type,
                        f"Cannot resolve parameter '{param_name}' of {cls.__name__}",
                    )

        return cls(**kwargs)

    def is_registered(self, service_type: type) -> bool:
        """Check if a service is registered."""
        with self._lock:
            return service_type in self._services

    def clear(self) -> None:
        """Clear all registered services."""
        with self._lock:
            self._services.clear()
            self._resolution_stack.clear()

    @contextmanager
    def scope(self):
        """
        Create a scoped context for transient services.

        Usage:
            with container.scope():
                service = container.resolve(MyService)
        """
        try:
            yield self
        finally:
            pass

    @asynccontextmanager
    async def async_scope(self):
        """
        Create an async scoped context for transient services.

        Usage:
            async with container.async_scope():
                service = await container.resolve_async(MyService)
        """
        try:
            yield self
        finally:
            pass

    def get_service_info(self, service_type: type) -> dict[str, Any]:
        """Get information about a registered service."""
        with self._lock:
            if service_type not in self._services:
                raise ServiceNotFoundError(service_type)

            descriptor = self._services[service_type]
            return {
                "type": service_type.__name__,
                "scope": descriptor.scope,
                "is_async": descriptor.is_async,
                "has_instance": descriptor.instance is not None,
                "factory": descriptor.factory.__name__
                if hasattr(descriptor.factory, "__name__")
                else str(descriptor.factory),
            }

    def get_all_services(self) -> dict[str, dict[str, Any]]:
        """Get information about all registered services."""
        with self._lock:
            return {
                service_type.__name__: self.get_service_info(service_type)
                for service_type in self._services
            }


# Global container instance
_global_container: Container | None = None
_global_container_lock = threading.Lock()


def get_container() -> Container:
    """Get or create the global container instance."""
    global _global_container
    if _global_container is None:
        with _global_container_lock:
            if _global_container is None:
                _global_container = Container()
    return _global_container


def set_container(container: Container) -> None:
    """Set the global container instance."""
    global _global_container
    with _global_container_lock:
        _global_container = container


def reset_container() -> None:
    """Reset the global container instance."""
    global _global_container
    with _global_container_lock:
        if _global_container is not None:
            _global_container.clear()
        _global_container = None
