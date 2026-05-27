"""
Integration example and usage guide for X-Agent UX improvements.

This module demonstrates how to use the new streaming, task management,
and interactive question APIs.
"""

from typing import Any
import asyncio
from backend.app.api.streaming import event_store, StreamEvent, MessageEvent, ProgressEvent, CompletionEvent
from backend.app.core.interactive_questions import question_manager, InteractiveQuestion, QuestionType, QuestionOption
from backend.app.api.tasks_ui import task_store, TaskModel, TaskStatus, TaskPriority


# ============================================================================
# Example 1: Streaming Events
# ============================================================================

async def example_streaming_events():
    """
    Example: Emit streaming events during agent execution.

    This shows how to emit different types of events that clients can
    subscribe to via the /api/v1/agent/stream/{run_id} endpoint.
    """
    run_id = "example-run-123"
    sequence = 0

    # Emit initial message
    msg_event = MessageEvent(
        run_id=run_id,
        content="Starting task execution...",
        role="system",
        sequence=sequence,
    )
    event_store.add_event(run_id, msg_event)
    sequence += 1

    # Emit progress update
    progress_event = ProgressEvent(
        run_id=run_id,
        overall_progress=0.25,
        current_step="Planning",
        total_steps=4,
        completed_steps=1,
        sequence=sequence,
    )
    event_store.add_event(run_id, progress_event)
    sequence += 1

    # Emit tool call
    from backend.app.api.streaming import ToolCallEvent
    tool_event = ToolCallEvent(
        run_id=run_id,
        tool_name="read_file",
        arguments={"path": "/path/to/file.py"},
        sequence=sequence,
    )
    event_store.add_event(run_id, tool_event)
    sequence += 1

    # Emit tool result
    from backend.app.api.streaming import ToolResultEvent
    result_event = ToolResultEvent(
        run_id=run_id,
        tool_id=tool_event.tool_id,
        tool_name="read_file",
        result={"content": "file content here", "lines": 42},
        success=True,
        sequence=sequence,
    )
    event_store.add_event(run_id, result_event)
    sequence += 1

    # Emit completion
    completion_event = CompletionEvent(
        run_id=run_id,
        status="completed",
        result={"answer": "Task completed successfully"},
        summary={"total_steps": 4, "duration_seconds": 12.5},
        sequence=sequence,
    )
    event_store.add_event(run_id, completion_event)

    print(f"Emitted {sequence} events for run {run_id}")


# ============================================================================
# Example 2: Task Management
# ============================================================================

async def example_task_management():
    """
    Example: Create and manage tasks with dependencies.

    This shows how to create tasks, track progress, and manage dependencies.
    """
    run_id = "example-run-456"

    # Create parent task
    parent_task = TaskModel(
        title="Main Task",
        description="Execute main workflow",
        priority=TaskPriority.HIGH,
        run_id=run_id,
        estimated_duration_seconds=300,
    )
    parent_task = task_store.create(parent_task)
    print(f"Created parent task: {parent_task.task_id}")

    # Create subtasks
    subtask1 = TaskModel(
        title="Subtask 1: Data Collection",
        description="Collect required data",
        priority=TaskPriority.MEDIUM,
        run_id=run_id,
        parent_task_id=parent_task.task_id,
        estimated_duration_seconds=60,
    )
    subtask1 = task_store.create(subtask1)

    subtask2 = TaskModel(
        title="Subtask 2: Processing",
        description="Process collected data",
        priority=TaskPriority.MEDIUM,
        run_id=run_id,
        parent_task_id=parent_task.task_id,
        depends_on=[subtask1.task_id],
        estimated_duration_seconds=120,
    )
    subtask2 = task_store.create(subtask2)

    subtask3 = TaskModel(
        title="Subtask 3: Verification",
        description="Verify results",
        priority=TaskPriority.HIGH,
        run_id=run_id,
        parent_task_id=parent_task.task_id,
        depends_on=[subtask2.task_id],
        estimated_duration_seconds=60,
    )
    subtask3 = task_store.create(subtask3)

    print(f"Created 3 subtasks with dependencies")

    # Update task progress
    task_store.update(subtask1.task_id, {
        "status": TaskStatus.IN_PROGRESS,
        "progress": 0.5,
    })

    # Complete subtask 1
    task_store.update(subtask1.task_id, {
        "status": TaskStatus.COMPLETED,
        "progress": 1.0,
        "result": {"items_collected": 42},
    })

    # Start subtask 2
    task_store.update(subtask2.task_id, {
        "status": TaskStatus.IN_PROGRESS,
        "progress": 0.3,
    })

    print("Updated task statuses and progress")

    # Get task statistics
    stats = task_store.get_stats(run_id=run_id)
    print(f"Task stats: {stats}")


# ============================================================================
# Example 3: Interactive Questions
# ============================================================================

async def example_interactive_questions():
    """
    Example: Create and handle interactive questions.

    This shows how to pause execution and ask for user input.
    """
    run_id = "example-run-789"

    # Create a confirmation question
    confirmation_q = InteractiveQuestion(
        run_id=run_id,
        type=QuestionType.CONFIRMATION,
        title="Proceed with deployment?",
        description="Are you sure you want to deploy to production?",
        priority="critical",
        timeout_seconds=300,
        default_answer=False,
    )
    confirmation_q = question_manager.create_question(confirmation_q)
    print(f"Created confirmation question: {confirmation_q.question_id}")

    # Create a choice question
    choice_q = InteractiveQuestion(
        run_id=run_id,
        type=QuestionType.SINGLE_CHOICE,
        title="Select deployment environment",
        description="Which environment should we deploy to?",
        options=[
            QuestionOption(value="staging", label="Staging", description="Test environment"),
            QuestionOption(value="production", label="Production", description="Live environment"),
            QuestionOption(value="canary", label="Canary", description="Limited rollout"),
        ],
        priority="high",
        timeout_seconds=600,
    )
    choice_q = question_manager.create_question(choice_q)
    print(f"Created choice question: {choice_q.question_id}")

    # Create a text input question
    text_q = InteractiveQuestion(
        run_id=run_id,
        type=QuestionType.TEXT_INPUT,
        title="Enter deployment notes",
        description="Provide any notes for this deployment",
        placeholder="e.g., Bug fixes for issue #123",
        min_length=10,
        max_length=500,
        priority="medium",
        timeout_seconds=300,
    )
    text_q = question_manager.create_question(text_q)
    print(f"Created text input question: {text_q.question_id}")

    # Simulate user answering questions
    await asyncio.sleep(1)

    # Answer confirmation
    question_manager.answer_question(confirmation_q.question_id, True)
    print(f"Answered confirmation question")

    # Answer choice
    question_manager.answer_question(choice_q.question_id, "staging")
    print(f"Answered choice question")

    # Answer text
    question_manager.answer_question(text_q.question_id, "Deploying bug fixes for issue #123")
    print(f"Answered text question")

    # Get history
    history = question_manager.get_history(run_id=run_id)
    print(f"Question history: {len(history)} entries")


# ============================================================================
# Example 4: Combined Workflow
# ============================================================================

async def example_combined_workflow():
    """
    Example: Combined workflow using streaming, tasks, and questions.

    This demonstrates a realistic agent execution flow.
    """
    run_id = "example-workflow-001"
    sequence = 0

    # Step 1: Create main task
    main_task = TaskModel(
        title="Deploy Application",
        description="Deploy new version to production",
        priority=TaskPriority.HIGH,
        run_id=run_id,
        estimated_duration_seconds=600,
    )
    main_task = task_store.create(main_task)

    # Step 2: Emit start message
    msg = MessageEvent(
        run_id=run_id,
        content="Starting deployment workflow...",
        role="system",
        sequence=sequence,
    )
    event_store.add_event(run_id, msg)
    sequence += 1

    # Step 3: Update task to in progress
    task_store.update(main_task.task_id, {
        "status": TaskStatus.IN_PROGRESS,
        "progress": 0.1,
    })

    # Step 4: Emit progress
    progress = ProgressEvent(
        run_id=run_id,
        overall_progress=0.1,
        current_step="Validating deployment",
        total_steps=5,
        completed_steps=1,
        sequence=sequence,
    )
    event_store.add_event(run_id, progress)
    sequence += 1

    # Step 5: Ask for confirmation
    confirm_q = InteractiveQuestion(
        run_id=run_id,
        type=QuestionType.CONFIRMATION,
        title="Confirm deployment",
        description="Ready to deploy to production?",
        priority="critical",
        timeout_seconds=300,
    )
    confirm_q = question_manager.create_question(confirm_q)

    # Simulate user confirmation
    await asyncio.sleep(1)
    question_manager.answer_question(confirm_q.question_id, True)

    # Step 6: Continue with deployment
    msg = MessageEvent(
        run_id=run_id,
        content="Deployment confirmed. Proceeding...",
        role="system",
        sequence=sequence,
    )
    event_store.add_event(run_id, msg)
    sequence += 1

    # Step 7: Update progress
    progress = ProgressEvent(
        run_id=run_id,
        overall_progress=0.9,
        current_step="Finalizing deployment",
        total_steps=5,
        completed_steps=5,
        sequence=sequence,
    )
    event_store.add_event(run_id, progress)
    sequence += 1

    # Step 8: Complete task
    task_store.update(main_task.task_id, {
        "status": TaskStatus.COMPLETED,
        "progress": 1.0,
        "result": {"deployment_id": "deploy-123", "duration_seconds": 45},
    })

    # Step 9: Emit completion
    completion = CompletionEvent(
        run_id=run_id,
        status="completed",
        result={"success": True, "deployment_id": "deploy-123"},
        summary={"total_steps": 5, "duration_seconds": 45},
        sequence=sequence,
    )
    event_store.add_event(run_id, completion)

    print(f"Completed workflow for run {run_id}")


# ============================================================================
# Main
# ============================================================================

async def main():
    """Run all examples."""
    print("=" * 70)
    print("X-Agent UX Improvements - Integration Examples")
    print("=" * 70)

    print("\n1. Streaming Events Example")
    print("-" * 70)
    await example_streaming_events()

    print("\n2. Task Management Example")
    print("-" * 70)
    await example_task_management()

    print("\n3. Interactive Questions Example")
    print("-" * 70)
    await example_interactive_questions()

    print("\n4. Combined Workflow Example")
    print("-" * 70)
    await example_combined_workflow()

    print("\n" + "=" * 70)
    print("Examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
