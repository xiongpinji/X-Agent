"""
Usage examples for X-Agent streaming and real-time visualization.

This file demonstrates how to integrate streaming functionality
into your X-Agent application.
"""

# ============================================================================
# Backend Examples
# ============================================================================

# Example 1: Basic Agent Execution with Streaming
# ============================================================================

from backend.app.api.streaming_enhanced import event_store
from backend.app.core.agent import AgentLoop
from backend.app.core.contracts import RunContext
import asyncio


async def execute_agent_with_streaming(
    agent: AgentLoop,
    run_id: str,
    context: RunContext,
    task: str,
) -> dict:
    """
    Execute an agent task with real-time streaming updates.

    Args:
        agent: Agent instance
        run_id: Unique run identifier
        context: Execution context
        task: Task to execute

    Returns:
        Execution result
    """
    try:
        # Send initial event
        event_store.add_event(run_id, {
            "event_type": "log",
            "level": "info",
            "message": f"Starting task: {task}",
            "source": "agent",
        })

        # Send progress update
        event_store.add_event(run_id, {
            "event_type": "progress",
            "overall_progress": 0.1,
            "current_step": "Planning",
            "total_steps": 4,
            "completed_steps": 0,
        })

        # Execute agent
        result = await agent.run(context, task, {})

        # Send completion event
        event_store.add_event(run_id, {
            "event_type": "completion",
            "status": "completed",
            "result": result.answer,
            "summary": result.execution_summary,
        })

        return result

    except Exception as e:
        # Send error event
        event_store.add_event(run_id, {
            "event_type": "error",
            "error_code": "EXECUTION_ERROR",
            "error_message": str(e),
            "recoverable": False,
        })
        raise


# Example 2: Task-based Execution with Progress Tracking
# ============================================================================

async def execute_tasks_with_tracking(
    run_id: str,
    tasks: list[dict],
) -> dict:
    """
    Execute multiple tasks with real-time progress tracking.

    Args:
        run_id: Unique run identifier
        tasks: List of tasks to execute

    Returns:
        Execution summary
    """
    total_tasks = len(tasks)
    completed_tasks = 0

    for task_idx, task in enumerate(tasks):
        task_id = task.get("id", f"task-{task_idx}")
        task_title = task.get("title", f"Task {task_idx + 1}")

        # Send task status: running
        event_store.add_event(run_id, {
            "event_type": "task_status",
            "task_id": task_id,
            "status": "running",
            "title": task_title,
            "progress": 0.0,
        })

        try:
            # Simulate task execution
            await asyncio.sleep(1)

            # Send progress updates during execution
            for progress in [0.25, 0.5, 0.75, 1.0]:
                event_store.add_event(run_id, {
                    "event_type": "task_status",
                    "task_id": task_id,
                    "status": "running",
                    "title": task_title,
                    "progress": progress,
                })
                await asyncio.sleep(0.5)

            # Send task completion
            event_store.add_event(run_id, {
                "event_type": "task_status",
                "task_id": task_id,
                "status": "completed",
                "title": task_title,
                "progress": 1.0,
            })

            completed_tasks += 1

        except Exception as e:
            # Send task failure
            event_store.add_event(run_id, {
                "event_type": "task_status",
                "task_id": task_id,
                "status": "failed",
                "title": task_title,
                "progress": 0.0,
            })

            event_store.add_event(run_id, {
                "event_type": "log",
                "level": "error",
                "message": f"Task {task_id} failed: {str(e)}",
                "source": "agent",
            })

        # Send overall progress
        overall_progress = completed_tasks / total_tasks
        event_store.add_event(run_id, {
            "event_type": "progress",
            "overall_progress": overall_progress,
            "current_step": f"Task {task_idx + 1}/{total_tasks}",
            "total_steps": total_tasks,
            "completed_steps": completed_tasks,
        })

    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "success_rate": completed_tasks / total_tasks,
    }


# Example 3: Tool Execution with Streaming
# ============================================================================

async def execute_tool_with_streaming(
    run_id: str,
    tool_name: str,
    tool_args: dict,
) -> dict:
    """
    Execute a tool with streaming updates.

    Args:
        run_id: Unique run identifier
        tool_name: Name of the tool
        tool_args: Tool arguments

    Returns:
        Tool result
    """
    import time
    import uuid

    tool_id = str(uuid.uuid4())

    # Send tool call event
    event_store.add_event(run_id, {
        "event_type": "tool_call",
        "tool_id": tool_id,
        "tool_name": tool_name,
        "arguments": tool_args,
        "status": "pending",
    })

    event_store.add_event(run_id, {
        "event_type": "log",
        "level": "info",
        "message": f"Calling tool: {tool_name}",
        "source": "agent",
    })

    try:
        start_time = time.time()

        # Execute tool (simulated)
        await asyncio.sleep(2)
        result = {"status": "success", "data": "Tool result"}

        execution_time = (time.time() - start_time) * 1000

        # Send tool result event
        event_store.add_event(run_id, {
            "event_type": "tool_result",
            "tool_id": tool_id,
            "tool_name": tool_name,
            "result": result,
            "success": True,
            "execution_time_ms": execution_time,
        })

        event_store.add_event(run_id, {
            "event_type": "log",
            "level": "info",
            "message": f"Tool {tool_name} completed in {execution_time:.0f}ms",
            "source": "agent",
        })

        return result

    except Exception as e:
        # Send error event
        event_store.add_event(run_id, {
            "event_type": "tool_result",
            "tool_id": tool_id,
            "tool_name": tool_name,
            "result": {"error": str(e)},
            "success": False,
        })

        raise


# ============================================================================
# Frontend Examples
# ============================================================================

# Example 1: Basic Real-time Dashboard
# ============================================================================

"""
// In your React component

import { RealtimeDashboard } from '@/components/streaming/RealtimeVisualization';
import { useParams } from 'react-router-dom';

export function ExecutionPage() {
  const { runId } = useParams();

  return (
    <div className="h-screen bg-gray-100">
      <RealtimeDashboard
        runId={runId}
        layout="split"
      />
    </div>
  );
}
"""


# Example 2: Custom Layout with Individual Components
# ============================================================================

"""
// In your React component

import {
  RealtimeProgressBar,
  RealtimeTaskList,
  RealtimeLogStream,
} from '@/components/streaming/RealtimeVisualization';
import { useParams } from 'react-router-dom';

export function CustomExecutionPage() {
  const { runId } = useParams();

  return (
    <div className="flex h-screen gap-4 p-4 bg-gray-100">
      {/* Left Column */}
      <div className="flex-1 flex flex-col gap-4">
        {/* Progress Bar */}
        <div className="bg-white rounded-lg shadow p-6">
          <RealtimeProgressBar runId={runId} />
        </div>

        {/* Task List */}
        <div className="flex-1 min-h-0">
          <RealtimeTaskList
            runId={runId}
            maxTasks={20}
            onTaskClick={(task) => console.log('Task clicked:', task)}
          />
        </div>
      </div>

      {/* Right Column: Logs */}
      <div className="w-96">
        <RealtimeLogStream
          runId={runId}
          maxLogs={500}
          filterLevel="all"
          autoScroll={true}
        />
      </div>
    </div>
  );
}
"""


# Example 3: Tab-based Layout
# ============================================================================

"""
// In your React component

import { RealtimeDashboard } from '@/components/streaming/RealtimeVisualization';
import { useParams } from 'react-router-dom';

export function TabExecutionPage() {
  const { runId } = useParams();

  return (
    <div className="h-screen">
      <RealtimeDashboard
        runId={runId}
        layout="tabs"
      />
    </div>
  );
}
"""


# Example 4: Monitoring Multiple Runs
# ============================================================================

"""
// In your React component

import { RealtimeTaskList } from '@/components/streaming/RealtimeVisualization';
import { useState } from 'react';

export function MultiRunMonitor() {
  const [runs, setRuns] = useState<string[]>([
    'run-1',
    'run-2',
    'run-3',
  ]);

  return (
    <div className="grid grid-cols-3 gap-4 p-4">
      {runs.map((runId) => (
        <div key={runId} className="h-96">
          <RealtimeTaskList
            runId={runId}
            maxTasks={10}
          />
        </div>
      ))}
    </div>
  );
}
"""


# ============================================================================
# Integration Examples
# ============================================================================

# Example 1: FastAPI Route with Streaming
# ============================================================================

"""
from fastapi import APIRouter, Depends
from backend.app.api.streaming_enhanced import event_store
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal
from uuid import uuid4

router = APIRouter()

@router.post("/execute")
async def execute_task(
    task: str,
    principal: Principal = Depends(get_current_principal),
):
    '''Execute a task with streaming updates.'''
    run_id = str(uuid4())

    # Start background execution
    asyncio.create_task(
        execute_agent_with_streaming(
            agent=get_agent(),
            run_id=run_id,
            context=RunContext(
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
                permission_scope=list(principal.scopes),
            ),
            task=task,
        )
    )

    return {
        "run_id": run_id,
        "stream_url": f"/api/v1/streaming/stream/{run_id}",
    }
"""


# Example 2: React Hook for Custom Streaming
# ============================================================================

"""
// Custom hook for streaming

import { useEffect, useState, useRef } from 'react';

export function useCustomStreaming(runId: string) {
  const [events, setEvents] = useState<any[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const eventSource = new EventSource(
      `/api/v1/streaming/stream/${runId}`
    );

    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        setEvents((prev) => [...prev, data]);
      } catch (e) {
        console.error('Failed to parse event:', e);
      }
    };

    // Listen to all event types
    eventSource.addEventListener('message', handleMessage);
    eventSource.addEventListener('task_status', handleMessage);
    eventSource.addEventListener('progress', handleMessage);
    eventSource.addEventListener('log', handleMessage);
    eventSource.addEventListener('error', handleMessage);

    eventSource.onerror = () => {
      setIsConnected(false);
      eventSource.close();
    };

    eventSourceRef.current = eventSource;
    setIsConnected(true);

    return () => {
      eventSource.close();
    };
  }, [runId]);

  return { events, isConnected };
}

// Usage
export function MyComponent() {
  const { runId } = useParams();
  const { events, isConnected } = useCustomStreaming(runId);

  return (
    <div>
      <p>Status: {isConnected ? 'Connected' : 'Disconnected'}</p>
      <p>Events: {events.length}</p>
    </div>
  );
}
"""


# ============================================================================
# Testing Examples
# ============================================================================

# Example 1: Testing Streaming Functionality
# ============================================================================

"""
import pytest
from backend.app.api.streaming_enhanced import event_store

@pytest.mark.asyncio
async def test_streaming_execution():
    '''Test streaming execution.'''
    run_id = "test-run"

    # Execute with streaming
    result = await execute_agent_with_streaming(
        agent=mock_agent,
        run_id=run_id,
        context=test_context,
        task="Test task",
    )

    # Verify events were emitted
    events = event_store.get_events(run_id)
    assert len(events) > 0

    # Verify event types
    event_types = {e["event_type"] for e in events}
    assert "log" in event_types
    assert "progress" in event_types
    assert "completion" in event_types
"""


# Example 2: Performance Testing
# ============================================================================

"""
import time
from backend.app.api.streaming_enhanced import event_store

def test_streaming_performance():
    '''Test streaming performance.'''
    run_id = "perf-test"
    num_events = 1000

    start = time.time()

    for i in range(num_events):
        event_store.add_event(run_id, {
            "event_type": "log",
            "message": f"Event {i}",
        })

    elapsed = time.time() - start
    throughput = num_events / elapsed

    print(f"Throughput: {throughput:.0f} events/sec")
    assert throughput > 1000  # Should handle 1000+ events/sec
"""


if __name__ == "__main__":
    print("See examples above for usage patterns")
