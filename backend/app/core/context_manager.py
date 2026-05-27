"""Integration of context management into AgentLoop.

This module provides utilities to integrate ContextCompactor, MemoryPersistence,
and SessionRecovery into the AgentLoop for automatic context management.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.app.core.context_compactor import ContextCompactor
from backend.app.core.memory_persistence import MemoryEntry, MemoryPersistence
from backend.app.core.session_recovery import SessionRecovery, SessionSnapshot

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages context compression, memory persistence, and session recovery."""

    def __init__(
        self,
        memory_dir: str | Path | None = None,
        sessions_dir: str | Path | None = None,
        token_limit: int = 128_000,
        compression_threshold: float = 0.85,
        enable_snapshots: bool = True,
        snapshot_interval: int = 5,
    ) -> None:
        """Initialize context manager.

        Args:
            memory_dir: Directory for persistent memories (optional)
            sessions_dir: Directory for session snapshots (optional)
            token_limit: Maximum token budget
            compression_threshold: Trigger compression at this ratio
            enable_snapshots: Whether to save session snapshots
            snapshot_interval: Save snapshot every N iterations
        """
        self.compactor = ContextCompactor(
            token_limit=token_limit,
            compression_threshold=compression_threshold,
        )
        self.memory_persistence = None
        self.session_recovery = None
        self.enable_snapshots = enable_snapshots
        self.snapshot_interval = snapshot_interval

        if memory_dir:
            self.memory_persistence = MemoryPersistence(memory_dir)
            logger.info(f"Initialized memory persistence at {memory_dir}")

        if sessions_dir:
            self.session_recovery = SessionRecovery(sessions_dir)
            logger.info(f"Initialized session recovery at {sessions_dir}")

    def check_and_compress(
        self,
        messages: list[dict[str, str]],
    ) -> tuple[list[dict[str, str]], bool]:
        """Check if compression is needed and compress if necessary.

        Args:
            messages: Current message list

        Returns:
            Tuple of (compressed_messages, was_compressed)
        """
        if not self.compactor.should_compress(messages):
            return messages, False

        logger.info("Triggering context compression")
        result = self.compactor.compress(messages)

        if result.success:
            logger.info(
                f"Compression successful: {result.metrics.messages_before} -> "
                f"{result.metrics.messages_after} messages, "
                f"ratio: {result.metrics.compression_ratio:.2%}"
            )
            return result.messages, True
        else:
            logger.warning(f"Compression failed: {result.error}")
            return messages, False

    def save_memory_entry(
        self,
        name: str,
        content: str,
        category: str = "reference",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Save a memory entry to persistent storage.

        Args:
            name: Memory name
            content: Memory content
            category: Memory category (user, feedback, project, reference)
            tags: Optional tags
            metadata: Optional metadata

        Returns:
            True if saved successfully
        """
        if not self.memory_persistence:
            logger.warning("Memory persistence not enabled")
            return False

        try:
            entry = MemoryEntry(
                name=name,
                category=category,
                content=content,
                tags=tags or [],
                metadata=metadata or {},
            )
            self.memory_persistence.save_memory(entry)
            logger.info(f"Saved memory entry: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save memory entry {name}: {e}")
            return False

    def load_memory_entry(self, name: str) -> str | None:
        """Load a memory entry from persistent storage.

        Args:
            name: Memory name

        Returns:
            Memory content or None if not found
        """
        if not self.memory_persistence:
            return None

        try:
            entry = self.memory_persistence.load_memory(name)
            if entry:
                return entry.content
            return None
        except Exception as e:
            logger.error(f"Failed to load memory entry {name}: {e}")
            return None

    def search_memories(self, query: str) -> list[tuple[str, str]]:
        """Search memory entries.

        Args:
            query: Search query

        Returns:
            List of (name, content) tuples
        """
        if not self.memory_persistence:
            return []

        try:
            results = self.memory_persistence.search_memories(query)
            return [(entry.name, entry.content) for entry in results]
        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return []

    def create_session(
        self,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Create a new session for recovery.

        Args:
            session_id: Optional session ID
            metadata: Optional metadata

        Returns:
            Session ID or None if recovery not enabled
        """
        if not self.session_recovery:
            return None

        try:
            return self.session_recovery.create_session(session_id, metadata)
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return None

    def save_snapshot(
        self,
        session_id: str,
        iteration: int,
        messages: list[dict[str, str]],
        context: dict[str, Any],
        state: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Save a session snapshot.

        Args:
            session_id: Session ID
            iteration: Iteration number
            messages: Current messages
            context: Current context
            state: Current state
            metadata: Optional metadata

        Returns:
            True if saved successfully
        """
        if not self.session_recovery or not self.enable_snapshots:
            return False

        try:
            snapshot = SessionSnapshot(
                session_id=session_id,
                iteration=iteration,
                messages=messages,
                context=context,
                state=state,
                metadata=metadata or {},
            )
            self.session_recovery.save_snapshot(snapshot)
            logger.debug(f"Saved snapshot for session {session_id} at iteration {iteration}")
            return True
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            return False

    def load_session_snapshot(self, session_id: str) -> SessionSnapshot | None:
        """Load the latest snapshot for a session.

        Args:
            session_id: Session ID

        Returns:
            SessionSnapshot or None if not found
        """
        if not self.session_recovery:
            return None

        try:
            return self.session_recovery.load_latest_snapshot(session_id)
        except Exception as e:
            logger.error(f"Failed to load session snapshot: {e}")
            return None

    def should_save_snapshot(self, iteration: int) -> bool:
        """Check if a snapshot should be saved at this iteration.

        Args:
            iteration: Current iteration number

        Returns:
            True if snapshot should be saved
        """
        return self.enable_snapshots and (iteration % self.snapshot_interval == 0)


class AgentLoopContextIntegration:
    """Helper class for integrating context management into AgentLoop.

    This class provides methods to be called from AgentLoop to manage context
    throughout the agent's execution lifecycle.
    """

    def __init__(self, context_manager: ContextManager) -> None:
        """Initialize integration.

        Args:
            context_manager: ContextManager instance
        """
        self.context_manager = context_manager

    def on_iteration_start(
        self,
        session_id: str | None,
        iteration: int,
        messages: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """Called at the start of each agent iteration.

        Checks for context compression and loads any recovered state.

        Args:
            session_id: Current session ID
            iteration: Current iteration number
            messages: Current messages

        Returns:
            Messages (possibly compressed)
        """
        # Check and compress if needed
        compressed_messages, was_compressed = self.context_manager.check_and_compress(messages)

        if was_compressed:
            logger.info(f"Context compressed at iteration {iteration}")

        return compressed_messages

    def on_iteration_end(
        self,
        session_id: str | None,
        iteration: int,
        messages: list[dict[str, str]],
        context: dict[str, Any],
        state: dict[str, Any],
    ) -> None:
        """Called at the end of each agent iteration.

        Saves snapshots if configured.

        Args:
            session_id: Current session ID
            iteration: Current iteration number
            messages: Current messages
            context: Current context
            state: Current state
        """
        if not session_id:
            return

        # Save snapshot if interval reached
        if self.context_manager.should_save_snapshot(iteration):
            self.context_manager.save_snapshot(
                session_id=session_id,
                iteration=iteration,
                messages=messages,
                context=context,
                state=state,
            )

    def on_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: str,
    ) -> None:
        """Called when a tool is executed.

        Can save important tool calls to memory.

        Args:
            tool_name: Name of tool called
            tool_input: Tool input
            tool_output: Tool output
        """
        # Optionally save important tool calls to memory
        if tool_name in ["write_file", "execute_command", "apply_patch"]:
            summary = f"Tool: {tool_name}\nInput: {str(tool_input)[:200]}\nOutput: {tool_output[:200]}"
            self.context_manager.save_memory_entry(
                name=f"{tool_name}_{len(str(tool_input))}",
                content=summary,
                category="feedback",
                tags=["tool_call", tool_name],
            )

    def on_error(
        self,
        error_message: str,
        context: dict[str, Any],
    ) -> None:
        """Called when an error occurs.

        Saves error information to memory for recovery.

        Args:
            error_message: Error message
            context: Current context
        """
        self.context_manager.save_memory_entry(
            name=f"error_{len(error_message)}",
            content=f"Error: {error_message}\nContext: {str(context)[:500]}",
            category="feedback",
            tags=["error"],
        )

    def on_completion(
        self,
        session_id: str | None,
        final_messages: list[dict[str, str]],
        result: dict[str, Any],
    ) -> None:
        """Called when agent execution completes.

        Saves final state and marks session as completed.

        Args:
            session_id: Session ID
            final_messages: Final messages
            result: Execution result
        """
        if session_id and self.context_manager.session_recovery:
            self.context_manager.session_recovery.update_session_status(session_id, "completed")
            logger.info(f"Session {session_id} marked as completed")

        # Save completion summary to memory
        summary = f"Completed with result: {str(result)[:500]}"
        self.context_manager.save_memory_entry(
            name="completion_summary",
            content=summary,
            category="project",
            tags=["completion"],
        )
