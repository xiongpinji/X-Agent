"""
DI Container Migration Guide for X-Agent

This document provides a comprehensive guide for migrating from the current
@lru_cache based dependency injection to the new DI container system.

## Overview

The new DI container provides:
- Explicit dependency management
- Circular dependency detection
- Better testability
- Clearer dependency graphs
- Support for async factories
- Thread-safe operations

## Migration Strategy

### Phase 1: Coexistence (Current)
- New DI container is available alongside existing @lru_cache functions
- Existing code continues to work without changes
- New code can use the container

### Phase 2: Gradual Migration
- Replace @lru_cache functions one module at a time
- Update FastAPI dependency injection to use container
- Add integration tests

### Phase 3: Full Migration
- Remove @lru_cache functions
- Use container exclusively
- Optimize performance

## Quick Start

### Basic Usage

```python
from backend.app.core.container import Container, Scope

# Create a container
container = Container()

# Register services
container.singleton(MyService)
container.transient(MyRepository)

# Resolve services
service = container.resolve(MyService)
```

### With Factory Functions

```python
def create_database(container: Container) -> Database:
    config = container.resolve(Config)
    return Database(config.connection_string)

container.singleton(Database, create_database)
db = container.resolve(Database)
```

### With Constructor Injection

```python
class UserService:
    def __init__(self, repository: UserRepository, logger: Logger):
        self.repository = repository
        self.logger = logger

container.singleton(UserRepository)
container.singleton(Logger)
container.singleton(UserService)  # Auto-injects dependencies

service = container.resolve(UserService)
```

### Async Services

```python
async def create_async_service(container: Container) -> AsyncService:
    await asyncio.sleep(0.1)  # Simulate async initialization
    return AsyncService()

container.register_async(AsyncService, create_async_service)
service = await container.resolve_async(AsyncService)
```

## Migration Examples

### Example 1: Simple Service

**Before (using @lru_cache):**
```python
from functools import lru_cache

@lru_cache
def get_user_repository() -> UserRepository:
    return UserRepository()

@lru_cache
def get_user_service() -> UserService:
    return UserService(get_user_repository())
```

**After (using container):**
```python
from backend.app.core.container import Container

container = Container()
container.singleton(UserRepository)
container.singleton(UserService)

# In FastAPI route:
def get_users(service: UserService = Depends(lambda: container.resolve(UserService))):
    return service.get_all()
```

### Example 2: Complex Dependencies

**Before:**
```python
@lru_cache
def get_config() -> Config:
    return Config.from_env()

@lru_cache
def get_database() -> Database:
    config = get_config()
    return Database(config.connection_string)

@lru_cache
def get_user_repository() -> UserRepository:
    db = get_database()
    return UserRepository(db)

@lru_cache
def get_user_service() -> UserService:
    repo = get_user_repository()
    logger = get_logger()
    return UserService(repo, logger)
```

**After:**
```python
container = Container()
container.singleton(Config, lambda c: Config.from_env())
container.singleton(Database)  # Auto-injects Config
container.singleton(UserRepository)  # Auto-injects Database
container.singleton(UserService)  # Auto-injects UserRepository and Logger
container.singleton(Logger)

service = container.resolve(UserService)
```

### Example 3: Circular Dependency Resolution

**Problem:**
```python
class ServiceA:
    def __init__(self, service_b: ServiceB):
        self.service_b = service_b

class ServiceB:
    def __init__(self, service_a: ServiceA):
        self.service_a = service_a
```

**Solution using lazy initialization:**
```python
class ServiceA:
    def __init__(self, container: Container):
        self.container = container
    
    @property
    def service_b(self) -> ServiceB:
        return self.container.resolve(ServiceB)

class ServiceB:
    def __init__(self, container: Container):
        self.container = container
    
    @property
    def service_a(self) -> ServiceA:
        return self.container.resolve(ServiceA)

container = Container()
container.singleton(ServiceA)
container.singleton(ServiceB)
```

## FastAPI Integration

### Current Approach (with @lru_cache)

```python
from fastapi import Depends

@app.get("/users")
def get_users(service: UserService = Depends(get_user_service)):
    return service.get_all()
```

### New Approach (with container)

```python
from fastapi import Depends
from backend.app.dependencies import get_container

def get_user_service_from_container():
    container = get_container()
    return container.resolve(UserService)

@app.get("/users")
def get_users(service: UserService = Depends(get_user_service_from_container)):
    return service.get_all()
```

### Recommended Approach (wrapper functions)

```python
# In dependencies.py
def get_user_service() -> UserService:
    return get_container().resolve(UserService)

# In routes
@app.get("/users")
def get_users(service: UserService = Depends(get_user_service)):
    return service.get_all()
```

## Testing

### Before (with @lru_cache)

```python
def test_user_service():
    # Hard to mock because of @lru_cache
    mock_repo = MagicMock()
    service = UserService(mock_repo)
    assert service.get_user(1) is not None
```

### After (with container)

```python
def test_user_service():
    container = Container()
    mock_repo = MagicMock(spec=UserRepository)
    container.singleton(UserRepository, lambda c: mock_repo)
    container.singleton(UserService)
    
    service = container.resolve(UserService)
    assert service.get_user(1) is not None
```

## Performance Considerations

### Startup Time

The container adds minimal overhead:
- Registration: O(1) per service
- First resolution: O(n) where n = dependency depth
- Subsequent resolutions: O(1) for singletons

### Memory Usage

- Container overhead: ~1KB per service
- Singleton instances: Same as @lru_cache
- Transient instances: Created on demand

### Optimization Tips

1. Use singletons for expensive-to-create services
2. Use transient for stateful services
3. Lazy-load heavy dependencies
4. Use async factories for I/O-bound initialization

## Troubleshooting

### ServiceNotFoundError

**Problem:** Service is not registered
```python
container.resolve(MyService)  # Raises ServiceNotFoundError
```

**Solution:** Register the service first
```python
container.singleton(MyService)
service = container.resolve(MyService)
```

### CircularDependencyError

**Problem:** Services depend on each other
```python
class A:
    def __init__(self, b: B): pass

class B:
    def __init__(self, a: A): pass

container.singleton(A)
container.singleton(B)
container.resolve(A)  # Raises CircularDependencyError
```

**Solution:** Use lazy initialization
```python
class A:
    def __init__(self, container: Container):
        self.container = container
    
    @property
    def b(self) -> B:
        return self.container.resolve(B)
```

### Missing Dependencies

**Problem:** Constructor parameter not registered
```python
class Service:
    def __init__(self, repo: Repository):
        self.repo = repo

container.singleton(Service)
container.resolve(Service)  # Raises ServiceNotFoundError
```

**Solution:** Register all dependencies
```python
container.singleton(Repository)
container.singleton(Service)
service = container.resolve(Service)
```

## Best Practices

1. **Register at startup:** Configure all services during application initialization
2. **Use type hints:** Always use type annotations for constructor parameters
3. **Prefer singletons:** Use singletons for stateless services
4. **Use transient for state:** Use transient for stateful services
5. **Test with container:** Write tests that use the container
6. **Document dependencies:** Add docstrings explaining dependencies
7. **Use factory functions:** For complex initialization logic
8. **Handle errors:** Catch ServiceNotFoundError and CircularDependencyError

## Checklist for Migration

- [ ] Create container.py with Container class
- [ ] Create container_config.py with service registration
- [ ] Create dependencies_refactored.py with backward compatibility
- [ ] Write tests for container functionality
- [ ] Update FastAPI routes to use container
- [ ] Add integration tests
- [ ] Update documentation
- [ ] Performance testing
- [ ] Gradual rollout to production
- [ ] Monitor for issues
- [ ] Remove @lru_cache functions (Phase 3)

## References

- Container implementation: backend/app/core/container.py
- Configuration: backend/app/core/container_config.py
- Tests: tests/test_container.py
- Refactored dependencies: backend/app/dependencies_refactored.py
"""

# Example usage code
if __name__ == "__main__":
    from backend.app.core.container import Container

    # Example 1: Basic usage
    print("Example 1: Basic Usage")
    print("-" * 50)

    class Logger:
        def log(self, msg: str) -> None:
            print(f"[LOG] {msg}")

    class Database:
        def __init__(self, logger: Logger) -> None:
            self.logger = logger

        def query(self, sql: str) -> str:
            self.logger.log(f"Executing: {sql}")
            return "result"

    class UserRepository:
        def __init__(self, db: Database) -> None:
            self.db = db

        def get_user(self, user_id: int) -> dict:
            result = self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
            return {"id": user_id, "name": "John"}

    class UserService:
        def __init__(self, repo: UserRepository) -> None:
            self.repo = repo

        def get_user(self, user_id: int) -> dict:
            return self.repo.get_user(user_id)

    container = Container()
    container.singleton(Logger)
    container.singleton(Database)
    container.singleton(UserRepository)
    container.singleton(UserService)

    service = container.resolve(UserService)
    user = service.get_user(1)
    print(f"User: {user}")
    print()

    # Example 2: Transient services
    print("Example 2: Transient Services")
    print("-" * 50)

    class RequestContext:
        def __init__(self) -> None:
            self.request_id = id(self)

    container2 = Container()
    container2.transient(RequestContext)

    ctx1 = container2.resolve(RequestContext)
    ctx2 = container2.resolve(RequestContext)
    print(f"Context 1 ID: {ctx1.request_id}")
    print(f"Context 2 ID: {ctx2.request_id}")
    print(f"Are they different? {ctx1 is not ctx2}")
    print()

    # Example 3: Factory functions
    print("Example 3: Factory Functions")
    print("-" * 50)

    class Config:
        def __init__(self, env: str = "dev") -> None:
            self.env = env
            self.debug = env == "dev"

    def create_config(container: Container) -> Config:
        import os

        env = os.getenv("ENV", "dev")
        return Config(env)

    container3 = Container()
    container3.singleton(Config, create_config)

    config = container3.resolve(Config)
    print(f"Environment: {config.env}")
    print(f"Debug mode: {config.debug}")
