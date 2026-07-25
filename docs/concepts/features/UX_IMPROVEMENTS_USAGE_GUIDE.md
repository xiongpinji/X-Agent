# X-Agent UX Improvements - Usage Guide

## Quick Start

### 1. Start a Streaming Run

```bash
curl -X POST http://localhost:8000/api/v1/agent/run/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "task": "Deploy application to production",
    "extra_context": {"environment": "production"}
  }'
```

Response:
```json
{
  "run_id": "run-abc123",
  "stream_url": "/api/v1/agent/stream/run-abc123",
  "status": "started"
}
```

### 2. Subscribe to Events

Open a browser or use curl to subscribe to the stream:

```bash
curl -N http://localhost:8000/api/v1/agent/stream/run-abc123 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

You'll receive events in real-time:
```
event: message
data: {"event_type":"message","content":"Starting...","role":"system",...}

event: progress
data: {"event_type":"progress","overall_progress":0.25,...}

event: tool_call
data: {"event_type":"tool_call","tool_name":"read_file",...}
```

### 3. Monitor Tasks

```bash
curl http://localhost:8000/api/v1/tasks?run_id=run-abc123 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. Handle Interactive Questions

```bash
# Get pending questions
curl http://localhost:8000/api/v1/questions/pending?run_id=run-abc123 \
  -H "Authorization: Bearer YOUR_TOKEN"

# Answer a question
curl -X POST http://localhost:8000/api/v1/questions/q-123/answer \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"answer": "production"}'
```

---

## Frontend Integration

### Setup

1. Install dependencies (if not already installed):
```bash
npm install
```

2. Import components:
```typescript
import { StreamingOutput } from '@/components/StreamingOutput';
import { TaskList } from '@/components/TaskList';
import { InteractiveQuestions } from '@/components/InteractiveQuestion';
import { FilePreview } from '@/components/FilePreview';
import { ProgressIndicator } from '@/components/ProgressIndicator';
```

### Complete Example Page

```typescript
import React, { useState } from 'react';
import { StreamingOutput } from '@/components/StreamingOutput';
import { TaskList } from '@/components/TaskList';
import { InteractiveQuestions } from '@/components/InteractiveQuestion';
import { ProgressIndicator } from '@/components/ProgressIndicator';

export function AgentExecutionPage() {
  const [runId, setRunId] = useState<string | null>(null);
  const [task, setTask] = useState('');

  const handleStartRun = async () => {
    try {
      const response = await fetch('/api/v1/agent/run/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task }),
      });
      const data = await response.json();
      setRunId(data.run_id);
    } catch (error) {
      console.error('Failed to start run:', error);
    }
  };

  if (!runId) {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">X-Agent Execution</h1>
        <div className="space-y-4">
          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Enter your task..."
            className="w-full p-4 border rounded-lg"
            rows={4}
          />
          <button
            onClick={handleStartRun}
            disabled={!task}
            className="w-full px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
          >
            Start Execution
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">Execution: {runId}</h1>

      <div className="grid grid-cols-3 gap-6">
        {/* Main streaming output */}
        <div className="col-span-2">
          <StreamingOutput
            runId={runId}
            onComplete={(result) => console.log('Completed:', result)}
            onError={(error) => console.error('Error:', error)}
          />
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Progress */}
          <ProgressIndicator runId={runId} />

          {/* Questions */}
          <InteractiveQuestions runId={runId} />
        </div>
      </div>

      {/* Tasks */}
      <div className="mt-6">
        <TaskList runId={runId} autoRefresh={true} />
      </div>
    </div>
  );
}
```

---

## Backend Integration

### Emitting Events During Execution

```python
from backend.app.api.streaming import (
    event_store,
    MessageEvent,
    ToolCallEvent,
    ToolResultEvent,
    ProgressEvent,
    ErrorEvent,
    CompletionEvent,
)

async def execute_task(run_id: str, task: str):
    sequence = 0

    # Emit start message
    event_store.add_event(
        run_id,
        MessageEvent(
            run_id=run_id,
            content=f"Starting task: {task}",
            role="system",
            sequence=sequence,
        ),
    )
    sequence += 1

    try:
        # Emit progress
        event_store.add_event(
            run_id,
            ProgressEvent(
                run_id=run_id,
                overall_progress=0.25,
                current_step="Planning",
                total_steps=4,
                completed_steps=1,
                sequence=sequence,
            ),
        )
        sequence += 1

        # Call tool
        event_store.add_event(
            run_id,
            ToolCallEvent(
                run_id=run_id,
                tool_name="read_file",
                arguments={"path": "/path/to/file.py"},
                sequence=sequence,
            ),
        )
        sequence += 1

        # Get result
        result = await read_file("/path/to/file.py")

        # Emit result
        event_store.add_event(
            run_id,
            ToolResultEvent(
                run_id=run_id,
                tool_name="read_file",
                result=result,
                success=True,
                sequence=sequence,
            ),
        )
        sequence += 1

        # Emit completion
        event_store.add_event(
            run_id,
            CompletionEvent(
                run_id=run_id,
                status="completed",
                result={"answer": "Task completed"},
                summary={"duration_seconds": 10},
                sequence=sequence,
            ),
        )

    except Exception as e:
        # Emit error
        event_store.add_event(
            run_id,
            ErrorEvent(
                run_id=run_id,
                error_code="EXECUTION_ERROR",
                error_message=str(e),
                recoverable=False,
                sequence=sequence,
            ),
        )
```

### Managing Tasks

```python
from backend.app.api.tasks_ui import task_store, TaskModel, TaskStatus, TaskPriority

# Create task
task = TaskModel(
    title="Deploy Application",
    description="Deploy new version to production",
    priority=TaskPriority.HIGH,
    run_id=run_id,
    estimated_duration_seconds=600,
)
task = task_store.create(task)

# Update progress
task_store.update(task.task_id, {
    "status": TaskStatus.IN_PROGRESS,
    "progress": 0.5,
    "metadata": {"current_step": "Building"},
})

# Complete task
task_store.update(task.task_id, {
    "status": TaskStatus.COMPLETED,
    "progress": 1.0,
    "result": {"deployment_id": "deploy-123"},
})

# Get statistics
stats = task_store.get_stats(run_id=run_id)
print(f"Total: {stats['total']}, Completed: {stats['completed']}")
```

### Interactive Questions

```python
from backend.app.core.interactive_questions import (
    question_manager,
    InteractiveQuestion,
    QuestionType,
    QuestionOption,
)

# Create question
question = InteractiveQuestion(
    run_id=run_id,
    type=QuestionType.SINGLE_CHOICE,
    title="Select deployment environment",
    options=[
        QuestionOption(value="staging", label="Staging"),
        QuestionOption(value="production", label="Production"),
    ],
    timeout_seconds=300,
    priority="high",
    default_answer="staging",
)
question = question_manager.create_question(question)

# Wait for answer (with timeout)
try:
    answer = await question_manager.wait_for_answer(
        question.question_id,
        timeout_seconds=300,
    )
    print(f"User selected: {answer}")
except asyncio.TimeoutError:
    print("Question timed out, using default answer")
```

---

## Common Patterns

### Pattern 1: Long-Running Task with Progress

```python
async def long_running_task(run_id: str):
    sequence = 0
    total_steps = 10

    for step in range(total_steps):
        # Do work
        await do_work()

        # Emit progress
        event_store.add_event(
            run_id,
            ProgressEvent(
                run_id=run_id,
                overall_progress=(step + 1) / total_steps,
                current_step=f"Step {step + 1}/{total_steps}",
                total_steps=total_steps,
                completed_steps=step + 1,
                sequence=sequence,
            ),
        )
        sequence += 1
```

### Pattern 2: Approval Workflow

```python
async def approval_workflow(run_id: str):
    # Create approval question
    question = InteractiveQuestion(
        run_id=run_id,
        type=QuestionType.CONFIRMATION,
        title="Approve deployment?",
        priority="critical",
        timeout_seconds=600,
    )
    question = question_manager.create_question(question)

    # Wait for approval
    approved = await question_manager.wait_for_answer(question.question_id)

    if approved:
        # Proceed with deployment
        await deploy()
    else:
        # Cancel deployment
        raise Exception("Deployment cancelled by user")
```

### Pattern 3: Multi-Step Workflow with Tasks

```python
async def multi_step_workflow(run_id: str):
    # Create main task
    main_task = TaskModel(
        title="Multi-step workflow",
        run_id=run_id,
    )
    main_task = task_store.create(main_task)

    # Create subtasks
    subtasks = []
    for i in range(3):
        subtask = TaskModel(
            title=f"Step {i + 1}",
            parent_task_id=main_task.task_id,
            run_id=run_id,
            depends_on=[st.task_id for st in subtasks],
        )
        subtask = task_store.create(subtask)
        subtasks.append(subtask)

        # Execute step
        task_store.update(subtask.task_id, {
            "status": TaskStatus.IN_PROGRESS,
        })

        await execute_step(i)

        # Complete step
        task_store.update(subtask.task_id, {
            "status": TaskStatus.COMPLETED,
            "progress": 1.0,
        })

    # Complete main task
    task_store.update(main_task.task_id, {
        "status": TaskStatus.COMPLETED,
        "progress": 1.0,
    })
```

---

## Troubleshooting

### Events Not Appearing

1. Check that the run_id is correct
2. Verify authentication token is valid
3. Check browser console for errors
4. Ensure server is emitting events

### Questions Not Showing

1. Verify run_id matches
2. Check question status (should be "pending")
3. Ensure timeout hasn't expired
4. Check browser console for errors

### Tasks Not Updating

1. Verify task_id is correct
2. Check that updates are being sent
3. Ensure refresh interval is appropriate
4. Check for permission errors

### File Preview Not Working

1. Verify file path is correct
2. Check file permissions
3. Ensure file is readable
4. Check file size (very large files may be truncated)

---

## Performance Optimization

### 1. Event Batching

Instead of emitting individual events, batch them:

```python
events = [
    MessageEvent(...),
    ProgressEvent(...),
    ToolCallEvent(...),
]
for event in events:
    event_store.add_event(run_id, event)
```

### 2. Limit Event History

Configure maximum events to keep:

```python
# In streaming.py
MAX_EVENTS_PER_RUN = 10000
```

### 3. Cleanup Expired Questions

Periodically clean up expired questions:

```python
# In background task
question_manager.cleanup_expired()
```

### 4. Pagination for Large Task Lists

```typescript
const [offset, setOffset] = useState(0);
const limit = 50;

const response = await fetch(
  `/api/v1/tasks?run_id=${runId}&limit=${limit}&offset=${offset}`
);
```

---

## Security Considerations

1. **Authentication**: All endpoints require valid authentication
2. **Authorization**: Users can only access their own runs
3. **File Access**: File preview is restricted to readable files
4. **Path Traversal**: Paths are validated to prevent directory traversal
5. **Rate Limiting**: API endpoints are rate-limited
6. **Data Sanitization**: All user input is sanitized

---

## Monitoring and Debugging

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("xagent.streaming")
logger.setLevel(logging.DEBUG)
```

### Monitor Event Flow

```python
# In streaming.py
def add_event(self, run_id: str, event: StreamEvent) -> None:
    logger.debug(f"Event {event.event_type} for run {run_id}")
    # ... rest of implementation
```

### Check Event Store State

```python
# Get all events for a run
events = event_store.get_events(run_id)
print(f"Total events: {len(events)}")

# Get task statistics
stats = task_store.get_stats(run_id)
print(f"Task stats: {stats}")

# Get pending questions
questions = question_manager.get_pending_questions(run_id)
print(f"Pending questions: {len(questions)}")
```

---

## Next Steps

1. **WebSocket Support**: Upgrade from SSE to WebSocket for bidirectional communication
2. **Persistence**: Store events and tasks in database instead of memory
3. **Notifications**: Add email/Slack notifications for important events
4. **Analytics**: Track execution metrics and performance
5. **Replay**: Implement execution replay functionality
6. **Collaboration**: Add multi-user collaboration features

---

## Support

For issues or questions:

1. Check the [API Documentation](../../developer/api/UX_IMPROVEMENTS_API.md)
2. Review [Integration Examples](../backend/app/examples/ux_integration_example.py)
3. Check browser console for errors
4. Enable debug logging
5. Contact the development team
