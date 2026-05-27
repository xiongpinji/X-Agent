"""
Tests for the DI container implementation.

Tests cover:
- Service registration and resolution
- Singleton and transient scopes
- Circular dependency detection
- Lazy initialization
- Async factory functions
- Constructor injection
- Thread safety
"""

import asyncio
import pytest
import threading
from typing import Protocol

from backend.app.core.container import (
    Container,
    Scope,
    ServiceNotFoundError,
    CircularDependencyError,
    ContainerError,
)


# ============================================================================
# Test Fixtures and Mock Services
# ============================================================================


class IRepository(Protocol):
    """Mock repository interface."""

    def get(self, id: int) -> str:
        ...


class MockRepository:
    """Mock repository implementation."""

    def __init__(self) -> None:
        self.call_count = 0

    def get(self, id: int) -> str:
        self.call_count += 1
        return f"item_{id}"


class IService(Protocol):
    """Mock service interface."""

    def process(self) -> str:
        ...


class MockService:
    """Mock service with dependency."""

    def __init__(self, repository: MockRepository) -> None:
        self.repository = repository

    def process(self) -> str:
        return self.repository.get(1)


class AsyncService:
    """Mock async service."""

    def __init__(self) -> None:
        self.initialized = True


# ============================================================================
# Basic Registration and Resolution Tests
# ============================================================================


def test_register_and_resolve_singleton():
    """Test registering and resolving a singleton service."""
    container = Container()
    repo = MockRepository()

    container.singleton(MockRepository, lambda c: repo)
    resolved = container.resolve(MockRepository)

    assert resolved is repo
    assert resolved.call_count == 0


def test_register_and_resolve_transient():
    """Test registering and resolving a transient service."""
    container = Container()

    container.transient(MockRepository)
    resolved1 = container.resolve(MockRepository)
    resolved2 = container.resolve(MockRepository)

    assert resolved1 is not resolved2
    assert isinstance(resolved1, MockRepository)
    assert isinstance(resolved2, MockRepository)


def test_singleton_caching():
    """Test that singletons are cached."""
    container = Container()
    call_count = 0

    def factory(c: Container) -> MockRepository:
        nonlocal call_count
        call_count += 1
        return MockRepository()

    container.singleton(MockRepository, factory)
    resolved1 = container.resolve(MockRepository)
    resolved2 = container.resolve(MockRepository)

    assert resolved1 is resolved2
    assert call_count == 1


def test_transient_not_cached():
    """Test that transient services are not cached."""
    container = Container()
    call_count = 0

    def factory(c: Container) -> MockRepository:
        nonlocal call_count
        call_count += 1
        return MockRepository()

    container.transient(MockRepository, factory)
    resolved1 = container.resolve(MockRepository)
    resolved2 = container.resolve(MockRepository)

    assert resolved1 is not resolved2
    assert call_count == 2


# ============================================================================
# Constructor Injection Tests
# ============================================================================


def test_constructor_injection():
    """Test automatic constructor injection."""
    container = Container()
    repo = MockRepository()

    container.singleton(MockRepository, lambda c: repo)
    container.singleton(MockService)

    service = container.resolve(MockService)

    assert service.repository is repo
    assert service.process() == "item_1"


def test_constructor_injection_with_missing_dependency():
    """Test that missing dependencies raise ServiceNotFoundError."""
    container = Container()
    container.singleton(MockService)

    with pytest.raises(ServiceNotFoundError):
        container.resolve(MockService)


# ============================================================================
# Circular Dependency Detection Tests
# ============================================================================


class ServiceA:
    def __init__(self, service_b: "ServiceB") -> None:
        self.service_b = service_b


class ServiceB:
    def __init__(self, service_a: ServiceA) -> None:
        self.service_a = service_a


def test_circular_dependency_detection():
    """Test that circular dependencies are detected."""
    container = Container()
    container.singleton(ServiceA)
    container.singleton(ServiceB)

    with pytest.raises(CircularDependencyError) as exc_info:
        container.resolve(ServiceA)

    assert "ServiceA" in str(exc_info.value)
    assert "ServiceB" in str(exc_info.value)


# ============================================================================
# Async Factory Tests
# ============================================================================


@pytest.mark.asyncio
async def test_async_factory():
    """Test async factory functions."""
    container = Container()

    async def async_factory(c: Container) -> AsyncService:
        await asyncio.sleep(0.01)
        return AsyncService()

    container.register_async(AsyncService, async_factory)
    service = await container.resolve_async(AsyncService)

    assert isinstance(service, AsyncService)
    assert service.initialized


@pytest.mark.asyncio
async def test_async_singleton_caching():
    """Test that async singletons are cached."""
    container = Container()
    call_count = 0

    async def async_factory(c: Container) -> AsyncService:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return AsyncService()

    container.register_async(AsyncService, async_factory, Scope.SINGLETON)
    service1 = await container.resolve_async(AsyncService)
    service2 = await container.resolve_async(AsyncService)

    assert service1 is service2
    assert call_count == 1


# ============================================================================
# Scope Tests
# ============================================================================


def test_invalid_scope():
    """Test that invalid scopes raise ValueError."""
    container = Container()

    with pytest.raises(ValueError):
        container.register(MockRepository, scope="invalid")


def test_scope_singleton_constant():
    """Test Scope.SINGLETON constant."""
    assert Scope.SINGLETON == "singleton"


def test_scope_transient_constant():
    """Test Scope.TRANSIENT constant."""
    assert Scope.TRANSIENT == "transient"


# ============================================================================
# Service Information Tests
# ============================================================================


def test_get_service_info():
    """Test getting service information."""
    container = Container()
    container.singleton(MockRepository)

    info = container.get_service_info(MockRepository)

    assert info["type"] == "MockRepository"
    assert info["scope"] == Scope.SINGLETON
    assert info["is_async"] is False
    assert info["has_instance"] is False


def test_get_service_info_not_found():
    """Test getting info for unregistered service."""
    container = Container()

    with pytest.raises(ServiceNotFoundError):
        container.get_service_info(MockRepository)


def test_get_all_services():
    """Test getting all registered services."""
    container = Container()
    container.singleton(MockRepository)
    container.transient(MockService)

    services = container.get_all_services()

    assert "MockRepository" in services
    assert "MockService" in services
    assert services["MockRepository"]["scope"] == Scope.SINGLETON
    assert services["MockService"]["scope"] == Scope.TRANSIENT


# ============================================================================
# Thread Safety Tests
# ============================================================================


def test_thread_safe_resolution():
    """Test that resolution is thread-safe."""
    container = Container()
    results = []
    lock = threading.Lock()

    def factory(c: Container) -> MockRepository:
        return MockRepository()

    container.singleton(MockRepository, factory)

    def resolve_service():
        service = container.resolve(MockRepository)
        with lock:
            results.append(service)

    threads = [threading.Thread(target=resolve_service) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # All threads should get the same singleton instance
    assert len(results) == 10
    assert all(service is results[0] for service in results)


def test_thread_safe_registration():
    """Test that registration is thread-safe."""
    container = Container()
    errors = []

    def register_service(index: int):
        try:
            service_type = type(f"Service{index}", (), {})
            container.singleton(service_type)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=register_service, args=(i,)) for i in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(errors) == 0


# ============================================================================
# Method Chaining Tests
# ============================================================================


def test_method_chaining():
    """Test that registration methods support chaining."""
    container = Container()

    result = (
        container.singleton(MockRepository)
        .transient(MockService)
        .singleton(AsyncService)
    )

    assert result is container
    assert container.is_registered(MockRepository)
    assert container.is_registered(MockService)
    assert container.is_registered(AsyncService)


# ============================================================================
# Clear and Reset Tests
# ============================================================================


def test_clear_container():
    """Test clearing all services from container."""
    container = Container()
    container.singleton(MockRepository)
    container.singleton(MockService)

    assert container.is_registered(MockRepository)
    assert container.is_registered(MockService)

    container.clear()

    assert not container.is_registered(MockRepository)
    assert not container.is_registered(MockService)


# ============================================================================
# Error Messages Tests
# ============================================================================


def test_service_not_found_error_message():
    """Test ServiceNotFoundError message."""
    container = Container()

    with pytest.raises(ServiceNotFoundError) as exc_info:
        container.resolve(MockRepository)

    assert "MockRepository" in str(exc_info.value)


def test_circular_dependency_error_message():
    """Test CircularDependencyError message."""
    container = Container()
    container.singleton(ServiceA)
    container.singleton(ServiceB)

    with pytest.raises(CircularDependencyError) as exc_info:
        container.resolve(ServiceA)

    error_msg = str(exc_info.value)
    assert "Circular dependency" in error_msg
    assert "ServiceA" in error_msg
    assert "ServiceB" in error_msg


# ============================================================================
# Integration Tests
# ============================================================================


def test_complex_dependency_graph():
    """Test resolving a complex dependency graph."""
    container = Container()

    class Logger:
        def log(self, msg: str) -> None:
            pass

    class Database:
        def __init__(self, logger: Logger) -> None:
            self.logger = logger

    class UserRepository:
        def __init__(self, db: Database) -> None:
            self.db = db

    class UserService:
        def __init__(self, repo: UserRepository) -> None:
            self.repo = repo

    container.singleton(Logger)
    container.singleton(Database)
    container.singleton(UserRepository)
    container.singleton(UserService)

    service = container.resolve(UserService)

    assert isinstance(service, UserService)
    assert isinstance(service.repo, UserRepository)
    assert isinstance(service.repo.db, Database)
    assert isinstance(service.repo.db.logger, Logger)


def test_mixed_scopes():
    """Test mixing singleton and transient services."""
    container = Container()

    class Config:
        pass

    class Logger:
        def __init__(self, config: Config) -> None:
            self.config = config

    class Service:
        def __init__(self, logger: Logger) -> None:
            self.logger = logger

    container.singleton(Config)
    container.transient(Logger)
    container.transient(Service)

    service1 = container.resolve(Service)
    service2 = container.resolve(Service)

    # Services are different (transient)
    assert service1 is not service2
    # But they share the same config (singleton)
    assert service1.logger.config is service2.logger.config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
