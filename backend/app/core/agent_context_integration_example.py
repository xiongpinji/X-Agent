"""Example integration of context management into AgentLoop.

This file demonstrates how to integrate the context management system
into the existing AgentLoop implementation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.app.core.context_manager import ContextManager, AgentLoopContextIntegration

logger = logging.getLogger(__name__)


class AgentLoopWithContextManagement:
    """Example AgentLoop with integrated context management.

    This shows how to modify the existing AgentLoop to use the context
    management system for automatic compression, memory persistence,
    and session recovery.
    """

    def __init__(
        self,
        # ... existing AgentLoop parameters ...
        memory_dir: str | Path | None = None,
        sessions_dir: str | Path | None = None,
        enable_context_management: bool = True,
    ) -> None:
        """Initialize AgentLoop with context management.

        Args:
            memory_dir: Directory for persistent memories
            sessions_dir: Directory for session snapshots
            enable_context_management: Whether to enable context management
        """
        # ... existing initialization ...

        self.enable_context_management = enable_context_management

        if enable_context_management:
            self.context_manager = ContextManager(
                memory_dir=memory_dir or Path("./memory"),
                sessions_dir=sessions_dir or Path("./sessions"),
                token_limit=128_000,
                compression_threshold=0.85,
                enable_snapshots=True,
                snapshot_interval=5,
            )
            self.context_integration = AgentLoopContextIntegration(self.context_manager)
        else:
            self.context_manager = None
            self.context_integration = None

    async def run(
        self,
        context,
        task: str,
        extra_context: dict | None = None,
        event_callback=None,
    ):
        """Run agent with context management.

        This is a modified version of the existing run method that integrates
        context management at key points.
        """
        # Create session if context management is enabled
        session_id = None
        if self.enable_context_management and self.context_manager:
            session_id = self.context_manager.create_session(
                metadata={
                    "task": task,
                    "trace_id": context.trace_id,
                    "user_id": context.user_id,
                }
            )
            logger.info(f"Created session {session_id} for task: {task}")

        # ... existing initialization code ...
        messages = []
        state = {}
        iteration = 0

        try:
            for iteration in range(self.max_iterations):
                # Check and compress context at iteration start
                if self.enable_context_management and self.context_integration:
                    messages = self.context_integration.on_iteration_start(
                        session_id,
                        iteration,
                        messages,
                    )

                # ... existing iteration logic ...
                # (planning, tool selection, execution, etc.)

                # Example: Tool execution
                try:
                    tool_result = await self._execute_tool(
                        tool_name="example_tool",
                        tool_input={"param": "value"},
                    )

                    # Save tool call to memory if context management enabled
                    if self.enable_context_management and self.context_integration:
                        self.context_integration.on_tool_call(
                            tool_name="example_tool",
                            tool_input={"param": "value"},
                            tool_output=str(tool_result),
                        )

                except Exception as e:
                    # Save error to memory
                    if self.enable_context_management and self.context_integration:
                        self.context_integration.on_error(
                            error_message=str(e),
                            context={"iteration": iteration, "task": task},
                        )
                    raise

                # Save snapshot at iteration end
                if self.enable_context_management and self.context_integration:
                    self.context_integration.on_iteration_end(
                        session_id=session_id,
                        iteration=iteration,
                        messages=messages,
                        context={"task": task, "iteration": iteration},
                        state=state,
                    )

            # Mark completion
            if self.enable_context_management and self.context_integration:
                self.context_integration.on_completion(
                    session_id=session_id,
                    final_messages=messages,
                    result={"status": "completed", "iterations": iteration},
                )

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            if self.enable_context_management and self.context_manager and session_id:
                self.context_manager.session_recovery.update_session_status(
                    session_id,
                    "failed",
                )
            raise

        # ... return result ...


# Integration points in existing AgentLoop

"""
INTEGRATION CHECKLIST:

1. In AgentLoop.__init__:
   - Add context_manager and context_integration initialization
   - Create memory_dir and sessions_dir parameters

2. In AgentLoop.run():
   - Create session at start: session_id = context_manager.create_session()
   - Call on_iteration_start() at beginning of each iteration
   - Call on_tool_call() after each tool execution
   - Call on_error() in exception handlers
   - Call on_iteration_end() at end of each iteration
   - Call on_completion() after loop completes

3. In tool execution methods:
   - Wrap tool calls with try/except
   - Call context_integration.on_tool_call() on success
   - Call context_integration.on_error() on failure

4. In error handling:
   - Call context_integration.on_error() for all exceptions
   - Update session status to "failed" if needed

5. Optional: Add recovery logic:
   - Check for existing session snapshots
   - Load latest snapshot if resuming
   - Restore messages and state from snapshot
"""


# Example: Resuming from a previous session

async def resume_agent_execution(
    agent_loop: AgentLoopWithContextManagement,
    session_id: str,
    context,
    task: str,
) -> Any:
    """Resume agent execution from a previous session.

    Args:
        agent_loop: AgentLoop instance with context management
        session_id: Session ID to resume
        context: Execution context
        task: Task description

    Returns:
        Execution result
    """
    if not agent_loop.context_manager:
        raise ValueError("Context management not enabled")

    # Load latest snapshot
    snapshot = agent_loop.context_manager.load_session_snapshot(session_id)
    if not snapshot:
        logger.warning(f"No snapshot found for session {session_id}, starting fresh")
        return await agent_loop.run(context, task)

    logger.info(f"Resuming session {session_id} from iteration {snapshot.iteration}")

    # Restore state from snapshot
    messages = snapshot.messages
    state = snapshot.state
    context_data = snapshot.context

    # Continue execution from where it left off
    # (This would require modifying AgentLoop.run() to accept initial state)
    # For now, this is a conceptual example

    return {
        "resumed_from": snapshot.iteration,
        "session_id": session_id,
        "status": "resumed",
    }


# Example: Querying saved memories

def query_project_memories(
    agent_loop: AgentLoopWithContextManagement,
    query: str,
) -> list[tuple[str, str]]:
    """Query saved project memories.

    Args:
        agent_loop: AgentLoop instance
        query: Search query

    Returns:
        List of (name, content) tuples
    """
    if not agent_loop.context_manager:
        return []

    return agent_loop.context_manager.search_memories(query)


# Example: Monitoring context compression

def monitor_context_compression(
    agent_loop: AgentLoopWithContextManagement,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """Monitor context compression metrics.

    Args:
        agent_loop: AgentLoop instance
        messages: Current messages

    Returns:
        Compression metrics
    """
    if not agent_loop.context_manager:
        return {}

    compactor = agent_loop.context_manager.compactor

    return {
        "should_compress": compactor.should_compress(messages),
        "current_tokens": compactor.count_messages_tokens(messages),
        "token_limit": compactor.token_limit,
        "usage_ratio": compactor.count_messages_tokens(messages) / compactor.token_limit,
        "compression_threshold": compactor.compression_threshold,
    }


# Example: Session management

def list_active_sessions(
    agent_loop: AgentLoopWithContextManagement,
) -> list[dict[str, Any]]:
    """List all active sessions.

    Args:
        agent_loop: AgentLoop instance

    Returns:
        List of session metadata
    """
    if not agent_loop.context_manager or not agent_loop.context_manager.session_recovery:
        return []

    sessions = agent_loop.context_manager.session_recovery.list_sessions(status="active")
    return [
        {
            "session_id": s.session_id,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
            "snapshot_count": s.snapshot_count,
            "total_iterations": s.total_iterations,
        }
        for s in sessions
    ]


# Example: Cleanup old sessions

def cleanup_old_sessions(
    agent_loop: AgentLoopWithContextManagement,
    max_age_hours: int = 24,
) -> int:
    """Clean up old completed sessions.

    Args:
        agent_loop: AgentLoop instance
        max_age_hours: Maximum age in hours

    Returns:
        Number of sessions deleted
    """
    if not agent_loop.context_manager or not agent_loop.context_manager.session_recovery:
        return 0

    from datetime import UTC, datetime, timedelta

    recovery = agent_loop.context_manager.session_recovery
    cutoff_time = datetime.now(UTC) - timedelta(hours=max_age_hours)
    deleted_count = 0

    for session in recovery.list_sessions(status="completed"):
        if session.updated_at < cutoff_time:
            if recovery.delete_session(session.session_id):
                deleted_count += 1

    logger.info(f"Cleaned up {deleted_count} old sessions")
    return deleted_count
