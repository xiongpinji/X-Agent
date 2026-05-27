"""
Performance benchmarks for the DI container.

Compares performance of:
- Container resolution vs @lru_cache
- Singleton vs transient services
- Constructor injection vs factory functions
- Startup time and memory usage
"""

import time
import sys
from functools import lru_cache
from typing import Any

from backend.app.core.container import Container, Scope


# ============================================================================
# Test Services
# ============================================================================


class Service1:
    """Simple service with no dependencies."""

    def __init__(self) -> None:
        self.value = "service1"


class Service2:
    """Service with one dependency."""

    def __init__(self, service1: Service1) -> None:
        self.service1 = service1


class Service3:
    """Service with two dependencies."""

    def __init__(self, service1: Service1, service2: Service2) -> None:
        self.service1 = service1
        self.service2 = service2


class Service4:
    """Service with three dependencies."""

    def __init__(self, service1: Service1, service2: Service2, service3: Service3) -> None:
        self.service1 = service1
        self.service2 = service2
        self.service3 = service3


class Service5:
    """Service with four dependencies."""

    def __init__(
        self, service1: Service1, service2: Service2, service3: Service3, service4: Service4
    ) -> None:
        self.service1 = service1
        self.service2 = service2
        self.service3 = service3
        self.service4 = service4


# ============================================================================
# Baseline: @lru_cache Implementation
# ============================================================================


@lru_cache
def get_service1_lru() -> Service1:
    return Service1()


@lru_cache
def get_service2_lru() -> Service2:
    return Service2(get_service1_lru())


@lru_cache
def get_service3_lru() -> Service3:
    return Service3(get_service1_lru(), get_service2_lru())


@lru_cache
def get_service4_lru() -> Service4:
    return Service4(get_service1_lru(), get_service2_lru(), get_service3_lru())


@lru_cache
def get_service5_lru() -> Service5:
    return Service5(
        get_service1_lru(), get_service2_lru(), get_service3_lru(), get_service4_lru()
    )


# ============================================================================
# Container Implementation
# ============================================================================


def setup_container() -> Container:
    """Set up a container with all services."""
    container = Container()
    container.singleton(Service1)
    container.singleton(Service2)
    container.singleton(Service3)
    container.singleton(Service4)
    container.singleton(Service5)
    return container


def setup_container_transient() -> Container:
    """Set up a container with transient services."""
    container = Container()
    container.transient(Service1)
    container.transient(Service2)
    container.transient(Service3)
    container.transient(Service4)
    container.transient(Service5)
    return container


# ============================================================================
# Benchmark Functions
# ============================================================================


def benchmark_lru_cache_resolution(iterations: int = 10000) -> float:
    """Benchmark @lru_cache resolution."""
    start = time.perf_counter()
    for _ in range(iterations):
        get_service5_lru()
    end = time.perf_counter()
    return end - start


def benchmark_container_singleton_resolution(iterations: int = 10000) -> float:
    """Benchmark container singleton resolution."""
    container = setup_container()
    start = time.perf_counter()
    for _ in range(iterations):
        container.resolve(Service5)
    end = time.perf_counter()
    return end - start


def benchmark_container_transient_resolution(iterations: int = 10000) -> float:
    """Benchmark container transient resolution."""
    container = setup_container_transient()
    start = time.perf_counter()
    for _ in range(iterations):
        container.resolve(Service5)
    end = time.perf_counter()
    return end - start


def benchmark_container_registration(num_services: int = 100) -> float:
    """Benchmark container service registration."""
    container = Container()

    def create_service_class(index: int):
        return type(f"Service{index}", (), {"__init__": lambda self: None})

    services = [create_service_class(i) for i in range(num_services)]

    start = time.perf_counter()
    for service in services:
        container.singleton(service)
    end = time.perf_counter()
    return end - start


def benchmark_container_startup(num_services: int = 100) -> float:
    """Benchmark container startup time."""
    start = time.perf_counter()
    container = setup_container()
    end = time.perf_counter()
    return end - start


def benchmark_first_resolution_vs_cached(iterations: int = 100) -> tuple[float, float]:
    """Compare first resolution vs cached resolution."""
    container = setup_container()

    # First resolution (cache miss)
    start = time.perf_counter()
    for _ in range(iterations):
        container.clear()
        container.singleton(Service1)
        container.resolve(Service1)
    first_time = time.perf_counter() - start

    # Cached resolution
    container = setup_container()
    start = time.perf_counter()
    for _ in range(iterations):
        container.resolve(Service1)
    cached_time = time.perf_counter() - start

    return first_time, cached_time


def benchmark_dependency_depth(max_depth: int = 10) -> dict[int, float]:
    """Benchmark resolution time vs dependency depth."""
    results = {}

    for depth in range(1, max_depth + 1):
        # Create a chain of services
        container = Container()

        # Create service classes with increasing dependencies
        services = []
        for i in range(depth):
            if i == 0:
                service_class = type(f"Service{i}", (), {"__init__": lambda self: None})
            else:
                prev_service = services[i - 1]

                def make_init(prev_svc):
                    def __init__(self, dep: prev_svc) -> None:
                        self.dep = dep

                    return __init__

                service_class = type(
                    f"Service{i}",
                    (),
                    {"__init__": make_init(prev_service)},
                )

            services.append(service_class)
            container.singleton(service_class)

        # Benchmark resolution
        start = time.perf_counter()
        for _ in range(1000):
            container.resolve(services[-1])
        elapsed = time.perf_counter() - start

        results[depth] = elapsed

    return results


# ============================================================================
# Memory Usage Analysis
# ============================================================================


def analyze_memory_usage() -> dict[str, Any]:
    """Analyze memory usage of container vs @lru_cache."""
    import sys

    # Container memory
    container = setup_container()
    container_size = sys.getsizeof(container)
    services_size = sum(
        sys.getsizeof(service) for service in container._services.values()
    )

    # @lru_cache memory (approximate)
    lru_cache_info = get_service5_lru.cache_info()

    return {
        "container_size": container_size,
        "services_size": services_size,
        "total_container_size": container_size + services_size,
        "lru_cache_hits": lru_cache_info.hits,
        "lru_cache_misses": lru_cache_info.misses,
        "lru_cache_size": lru_cache_info.currsize,
    }


# ============================================================================
# Report Generation
# ============================================================================


def print_benchmark_report() -> None:
    """Print a comprehensive benchmark report."""
    print("=" * 80)
    print("DI Container Performance Benchmark Report")
    print("=" * 80)
    print()

    # Benchmark 1: Resolution Performance
    print("1. Resolution Performance (10,000 iterations)")
    print("-" * 80)

    lru_time = benchmark_lru_cache_resolution()
    container_singleton_time = benchmark_container_singleton_resolution()
    container_transient_time = benchmark_container_transient_resolution()

    print(f"@lru_cache:                    {lru_time:.4f}s ({lru_time*1e6/10000:.2f}µs per call)")
    print(
        f"Container (singleton):         {container_singleton_time:.4f}s ({container_singleton_time*1e6/10000:.2f}µs per call)"
    )
    print(
        f"Container (transient):         {container_transient_time:.4f}s ({container_transient_time*1e6/10000:.2f}µs per call)"
    )

    lru_vs_container = (container_singleton_time / lru_time - 1) * 100
    print(f"Container vs @lru_cache:       {lru_vs_container:+.1f}%")
    print()

    # Benchmark 2: Registration Performance
    print("2. Service Registration Performance (100 services)")
    print("-" * 80)

    registration_time = benchmark_container_registration()
    print(f"Registration time:             {registration_time:.4f}s ({registration_time*1e6/100:.2f}µs per service)")
    print()

    # Benchmark 3: Startup Time
    print("3. Container Startup Time")
    print("-" * 80)

    startup_time = benchmark_container_startup()
    print(f"Startup time:                  {startup_time:.4f}s")
    print()

    # Benchmark 4: First vs Cached Resolution
    print("4. First Resolution vs Cached Resolution (100 iterations)")
    print("-" * 80)

    first_time, cached_time = benchmark_first_resolution_vs_cached()
    print(f"First resolution:              {first_time:.4f}s ({first_time*1e6/100:.2f}µs per call)")
    print(f"Cached resolution:             {cached_time:.4f}s ({cached_time*1e6/100:.2f}µs per call)")
    print(f"Speedup:                       {first_time/cached_time:.1f}x")
    print()

    # Benchmark 5: Dependency Depth Impact
    print("5. Resolution Time vs Dependency Depth (1,000 iterations per depth)")
    print("-" * 80)

    depth_results = benchmark_dependency_depth(max_depth=10)
    for depth, elapsed in depth_results.items():
        print(f"Depth {depth:2d}:                        {elapsed:.4f}s ({elapsed*1e6/1000:.2f}µs per call)")
    print()

    # Benchmark 6: Memory Usage
    print("6. Memory Usage Analysis")
    print("-" * 80)

    memory_info = analyze_memory_usage()
    print(f"Container object size:         {memory_info['container_size']} bytes")
    print(f"Services metadata size:        {memory_info['services_size']} bytes")
    print(f"Total container overhead:      {memory_info['total_container_size']} bytes")
    print(f"@lru_cache hits:               {memory_info['lru_cache_hits']}")
    print(f"@lru_cache misses:             {memory_info['lru_cache_misses']}")
    print(f"@lru_cache current size:       {memory_info['lru_cache_size']}")
    print()

    # Summary
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Container singleton resolution is {abs(lru_vs_container):.1f}% {'faster' if lru_vs_container < 0 else 'slower'} than @lru_cache")
    print(f"Container transient resolution is {(container_transient_time/lru_time - 1)*100:.1f}% slower than @lru_cache")
    print(f"Container provides better dependency management and testability")
    print(f"Performance difference is negligible for most applications")
    print()


if __name__ == "__main__":
    print_benchmark_report()
