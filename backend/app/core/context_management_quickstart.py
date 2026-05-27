"""Quick start guide for context management system.

This module provides a simple entry point for using the context management system.
"""

from __future__ import annotations

from pathlib import Path

from backend.app.core.context_manager import ContextManager, AgentLoopContextIntegration
from backend.app.core.memory_persistence import MemoryEntry


def setup_context_management(
    base_dir: str | Path = "./x-agent-data",
) -> tuple[ContextManager, AgentLoopContextIntegration]:
    """Quick setup for context management.

    Args:
        base_dir: Base directory for all context management data

    Returns:
        Tuple of (ContextManager, AgentLoopContextIntegration)

    Example:
        >>> context_manager, integration = setup_context_management()
        >>> session_id = context_manager.create_session()
        >>> # Use in AgentLoop...
    """
    base_dir = Path(base_dir)
    memory_dir = base_dir / "memory"
    sessions_dir = base_dir / "sessions"

    context_manager = ContextManager(
        memory_dir=memory_dir,
        sessions_dir=sessions_dir,
        token_limit=128_000,
        compression_threshold=0.85,
        enable_snapshots=True,
        snapshot_interval=5,
    )

    integration = AgentLoopContextIntegration(context_manager)

    return context_manager, integration


# Quick reference examples

def example_basic_usage() -> None:
    """Basic usage example."""
    from backend.app.core.context_compactor import ContextCompactor

    # Create compactor
    compactor = ContextCompactor()

    # Create sample messages
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]

    # Check if compression needed
    if compactor.should_compress(messages):
        result = compactor.compress(messages)
        print(f"Compressed: {result.metrics.compression_ratio:.2%}")


def example_memory_usage() -> None:
    """Memory persistence example."""
    from backend.app.core.memory_persistence import MemoryEntry, MemoryPersistence

    # Initialize
    memory = MemoryPersistence("./memory")

    # Save memory
    entry = MemoryEntry(
        name="my_memory",
        category="project",
        content="Important information",
        tags=["important"],
    )
    memory.save_memory(entry)

    # Load memory
    loaded = memory.load_memory("my_memory")
    print(f"Loaded: {loaded.content}")

    # Search
    results = memory.search_memories("important")
    print(f"Found {len(results)} results")


def example_session_usage() -> None:
    """Session recovery example."""
    from backend.app.core.session_recovery import SessionRecovery, SessionSnapshot

    # Initialize
    recovery = SessionRecovery("./sessions")

    # Create session
    session_id = recovery.create_session()

    # Save snapshot
    snapshot = SessionSnapshot(
        session_id=session_id,
        iteration=0,
        messages=[{"role": "user", "content": "Test"}],
    )
    recovery.save_snapshot(snapshot)

    # Load snapshot
    loaded = recovery.load_latest_snapshot(session_id)
    print(f"Loaded snapshot at iteration {loaded.iteration}")


def example_integration_usage() -> None:
    """Integration example."""
    context_manager, integration = setup_context_management()

    # Create session
    session_id = context_manager.create_session()

    # Simulate iteration
    messages = [{"role": "user", "content": "Task"}]

    # Start iteration
    messages = integration.on_iteration_start(session_id, 0, messages)

    # End iteration
    integration.on_iteration_end(
        session_id,
        0,
        messages,
        context={"task": "example"},
        state={},
    )

    # Complete
    integration.on_completion(session_id, messages, {"status": "done"})


# Configuration presets

class ContextManagementPresets:
    """Pre-configured context management setups."""

    @staticmethod
    def minimal() -> ContextManager:
        """Minimal setup (compression only, no persistence)."""
        return ContextManager(
            memory_dir=None,
            sessions_dir=None,
            token_limit=128_000,
            compression_threshold=0.85,
        )

    @staticmethod
    def standard() -> ContextManager:
        """Standard setup (compression + memory + sessions)."""
        return ContextManager(
            memory_dir="./memory",
            sessions_dir="./sessions",
            token_limit=128_000,
            compression_threshold=0.85,
            enable_snapshots=True,
            snapshot_interval=5,
        )

    @staticmethod
    def aggressive() -> ContextManager:
        """Aggressive compression (lower threshold, more frequent snapshots)."""
        return ContextManager(
            memory_dir="./memory",
            sessions_dir="./sessions",
            token_limit=64_000,
            compression_threshold=0.7,
            enable_snapshots=True,
            snapshot_interval=2,
        )

    @staticmethod
    def conservative() -> ContextManager:
        """Conservative compression (higher threshold, less frequent snapshots)."""
        return ContextManager(
            memory_dir="./memory",
            sessions_dir="./sessions",
            token_limit=256_000,
            compression_threshold=0.95,
            enable_snapshots=True,
            snapshot_interval=10,
        )


# Utility functions

def save_important_memory(
    context_manager: ContextManager,
    name: str,
    content: str,
    tags: list[str] | None = None,
) -> bool:
    """Save an important memory entry.

    Args:
        context_manager: ContextManager instance
        name: Memory name
        content: Memory content
        tags: Optional tags

    Returns:
        True if saved successfully
    """
    return context_manager.save_memory_entry(
        name=name,
        content=content,
        category="project",
        tags=tags or ["important"],
    )


def get_session_info(
    context_manager: ContextManager,
    session_id: str,
) -> dict | None:
    """Get information about a session.

    Args:
        context_manager: ContextManager instance
        session_id: Session ID

    Returns:
        Session info dict or None
    """
    if not context_manager.session_recovery:
        return None

    metadata = context_manager.session_recovery.get_session_metadata(session_id)
    if not metadata:
        return None

    return {
        "session_id": metadata.session_id,
        "created_at": metadata.created_at.isoformat(),
        "updated_at": metadata.updated_at.isoformat(),
        "status": metadata.status,
        "snapshot_count": metadata.snapshot_count,
        "total_iterations": metadata.total_iterations,
    }


def check_compression_status(
    context_manager: ContextManager,
    messages: list[dict[str, str]],
) -> dict:
    """Check current compression status.

    Args:
        context_manager: ContextManager instance
        messages: Current messages

    Returns:
        Status dict
    """
    compactor = context_manager.compactor
    tokens = compactor.count_messages_tokens(messages)
    usage_ratio = tokens / compactor.token_limit

    return {
        "current_tokens": tokens,
        "token_limit": compactor.token_limit,
        "usage_ratio": usage_ratio,
        "usage_percent": usage_ratio * 100,
        "should_compress": compactor.should_compress(messages),
        "compression_threshold": compactor.compression_threshold,
        "messages_count": len(messages),
    }


# CLI-like interface for testing

def cli_demo() -> None:
    """Interactive demo of context management system."""
    print("X-Agent Context Management System - Demo")
    print("=" * 50)

    # Setup
    context_manager, integration = setup_context_management()
    print("✓ Context management initialized")

    # Create session
    session_id = context_manager.create_session(
        metadata={"demo": True}
    )
    print(f"✓ Session created: {session_id}")

    # Save memory
    context_manager.save_memory_entry(
        name="demo_memory",
        content="This is a demo memory entry",
        category="reference",
        tags=["demo"],
    )
    print("✓ Memory saved")

    # Load memory
    content = context_manager.load_memory_entry("demo_memory")
    print(f"✓ Memory loaded: {content[:50]}...")

    # Check compression
    messages = [
        {"role": "user", "content": f"Message {i}"}
        for i in range(10)
    ]
    status = check_compression_status(context_manager, messages)
    print(f"✓ Compression status: {status['usage_percent']:.1f}% usage")

    # Save snapshot
    context_manager.save_snapshot(
        session_id=session_id,
        iteration=0,
        messages=messages,
        context={"demo": True},
        state={},
    )
    print("✓ Snapshot saved")

    # Get session info
    info = get_session_info(context_manager, session_id)
    print(f"✓ Session info: {info['snapshot_count']} snapshots")

    print("=" * 50)
    print("Demo completed successfully!")


if __name__ == "__main__":
    # Run demo
    cli_demo()
