# X-Agent UX Improvements - API Documentation

## Overview

This document describes the new user experience improvement APIs for X-Agent, including real-time streaming, task management, interactive questions, and file preview capabilities.

## Table of Contents

1. [Streaming API](#streaming-api)
2. [Task Management API](#task-management-api)
3. [Interactive Questions API](#interactive-questions-api)
4. [File Preview API](#file-preview-api)
5. [Integration Guide](#integration-guide)
6. [Examples](#examples)

---

## Streaming API

Real-time streaming of agent execution events using Server-Sent Events (SSE).

### Endpoints

#### Subscribe to Stream

```
GET /api/v1/agent/stream/{run_id}
```

Subscribe to real-time events for an agent run.

**Parameters:**
- `run_id` (path): ID of the agent run
- `since_sequence` (query, optional): Get events after this sequence number (default: 0)

**Response:** Server-Sent Events stream

**Event Types:**

1. **message** - Agent message
   ```json
   {
     "event_type": "message",
     "timestamp": "2026-05-27T10:30:00.000Z",
     "run_id": "run-123",
     "content": "Processing task...",
     "role": "assistant",
     "sequence": 1
   }
   ```

2. **tool_call** - Tool invocation
   ```json
   {
     "event_type": "tool_call",
     "timestamp": "2026-05-27T10:30:01.000Z",
     "run_id": "run-123",
     "tool_name": "read_file",
     "tool_id": "tool-456",
     "arguments": {"path": "/path/to/file.py"},
     "sequence": 2
   }
   ```

3. **tool_result** - Tool result
   ```json
   {
     "event_type": "tool_result",
     "timestamp": "2026-05-27T10:30:02.000Z",
     "run_id": "run-123",
     "tool_id": "tool-456",
     "tool_name": "read_file",
     "result": {"content": "...", "lines": 42},
     "success": true,
     "sequence": 3
   }
   ```

4. **progress** - Progress update
   ```json
   {
     "event_type": "progress",
     "timestamp": "2026-05-27T10:30:03.000Z",
     "run_id": "run-123",
     "overall_progress": 0.5,
     "current_step": "Processing",
     "total_steps": 4,
     "completed_steps": 2,
     "sequence": 4
   }
   ```

5. **error** - Error event
   ```json
   {
     "event_type": "error",
     "timestamp": "2026-05-27T10:30:04.000Z",
     "run_id": "run-123",
     "error_code": "TOOL_ERROR",
     "error_message": "Failed to read file",
     "error_details": {"reason": "File not found"},
     "recoverable": true,
     "sequence": 5
   }
   ```

6. **completion** - Execution complete
   ```json
   {
     "event_type": "completion",
     "timestamp": "2026-05-27T10:30:05.000Z",
     "run_id": "run-123",
     "status": "completed",
     "result": {"answer": "Task completed"},
     "summary": {"total_steps": 4, "duration_seconds": 5},
     "sequence": 6
   }
   ```

7. **heartbeat** - Keep-alive signal
   ```json
   {
     "event_type": "heartbeat",
     "timestamp": "2026-05-27T10:30:30.000Z",
     "run_id": "run-123",
     "sequence": 7
   }
   ```

#### Create Streaming Run

```
POST /api/v1/agent/run/stream
```

Create a new agent run with streaming support.

**Request Body:**
```json
{
  "task": "Deploy application to production",
  "extra_context": {
    "environment": "production",
    "version": "1.2.3"
  }
}
```

**Response:**
```json
{
  "run_id": "run-123",
  "stream_url": "/api/v1/agent/stream/run-123",
  "status": "started"
}
```

#### Get Stream Events (Polling)

```
GET /api/v1/agent/stream/{run_id}/events
```

Get buffered events for a run (non-streaming).

**Parameters:**
- `run_id` (path): ID of the agent run
- `since_sequence` (query, optional): Get events after this sequence
- `limit` (query, optional): Maximum events to return (default: 100)

**Response:**
```json
{
  "run_id": "run-123",
  "events": [...],
  "total": 42,
  "limited": false
}
```

---

## Task Management API

CRUD operations and real-time updates for task tracking.

### Endpoints

#### List Tasks

```
GET /api/v1/tasks
```

List tasks with optional filtering.

**Parameters:**
- `run_id` (query, optional): Filter by run ID
- `status` (query, optional): Filter by status (pending, in_progress, completed, failed, cancelled)
- `limit` (query, optional): Maximum tasks to return (default: 100)
- `offset` (query, optional): Number of tasks to skip (default: 0)

**Response:**
```json
{
  "tasks": [...],
  "total": 42,
  "completed": 10,
  "in_progress": 5,
  "failed": 2,
  "pending": 25
}
```

#### Create Task

```
POST /api/v1/tasks
```

Create a new task.

**Request Body:**
```json
{
  "title": "Process data",
  "description": "Process collected data",
  "priority": "high",
  "depends_on": ["task-1"],
  "tags": ["data-processing"],
  "estimated_duration_seconds": 300
}
```

**Response:**
```json
{
  "task_id": "task-123",
  "title": "Process data",
  "status": "pending",
  "progress": 0.0,
  "created_at": "2026-05-27T10:30:00.000Z",
  ...
}
```

#### Get Task

```
GET /api/v1/tasks/{task_id}
```

Get a task by ID.

#### Update Task

```
PUT /api/v1/tasks/{task_id}
```

Update a task.

**Request Body:**
```json
{
  "status": "in_progress",
  "progress": 0.5,
  "metadata": {
    "current_step": "Processing step 2"
  }
}
```

#### Delete Task

```
DELETE /api/v1/tasks/{task_id}
```

Delete a task.

#### Get Task Progress

```
GET /api/v1/tasks/{task_id}/progress
```

Get detailed progress information.

**Response:**
```json
{
  "task_id": "task-123",
  "status": "in_progress",
  "progress": 0.5,
  "estimated_remaining_seconds": 150,
  "current_step_description": "Processing step 2"
}
```

#### Get Task Dependencies

```
GET /api/v1/tasks/{task_id}/dependencies
```

Get task dependency graph.

**Response:**
```json
{
  "task_id": "task-123",
  "dependencies": ["task-1", "task-2"],
  "dependents": ["task-4"],
  "critical_path": ["task-1", "task-2", "task-123"]
}
```

#### Complete Task

```
POST /api/v1/tasks/{task_id}/complete
```

Mark a task as completed.

**Request Body:**
```json
{
  "result": {"items_processed": 42}
}
```

#### Fail Task

```
POST /api/v1/tasks/{task_id}/fail
```

Mark a task as failed.

**Request Body:**
```json
{
  "error": "Failed to process data: connection timeout"
}
```

#### Get Run Task Summary

```
GET /api/v1/tasks/run/{run_id}/summary
```

Get task summary for a run.

---

## Interactive Questions API

Interactive question system for pausing execution and requesting user input.

### Endpoints

#### Create Question

```
POST /api/v1/questions
```

Create an interactive question.

**Request Body:**
```json
{
  "run_id": "run-123",
  "type": "single_choice",
  "title": "Select deployment environment",
  "description": "Which environment should we deploy to?",
  "options": [
    {"value": "staging", "label": "Staging"},
    {"value": "production", "label": "Production"}
  ],
  "timeout_seconds": 300,
  "priority": "high",
  "default_answer": "staging"
}
```

**Response:**
```json
{
  "question_id": "q-123",
  "run_id": "run-123",
  "type": "single_choice",
  "title": "Select deployment environment",
  "status": "pending",
  "created_at": "2026-05-27T10:30:00.000Z",
  "expires_at": "2026-05-27T10:35:00.000Z",
  ...
}
```

#### Get Pending Questions

```
GET /api/v1/questions/pending?run_id={run_id}
```

Get pending questions for a run.

**Response:**
```json
{
  "questions": [...],
  "total": 3,
  "pending": 2
}
```

#### Get Question

```
GET /api/v1/questions/{question_id}
```

Get a question by ID.

#### Answer Question

```
POST /api/v1/questions/{question_id}/answer
```

Submit an answer to a question.

**Request Body:**
```json
{
  "answer": "production"
}
```

#### Timeout Question

```
POST /api/v1/questions/{question_id}/timeout
```

Mark a question as timed out (uses default answer if available).

#### Cancel Question

```
POST /api/v1/questions/{question_id}/cancel
```

Cancel a question.

#### Get Question History

```
GET /api/v1/questions/run/{run_id}/history
```

Get question history for a run.

**Parameters:**
- `limit` (query, optional): Maximum entries to return (default: 100)

---

## File Preview API

File preview and metadata endpoints.

### Endpoints

#### Preview File

```
GET /api/v1/files/preview/{file_path}
```

Get a preview of a file.

**Parameters:**
- `file_path` (path): Path to file
- `max_lines` (query, optional): Maximum lines to preview (default: 1000)

**Response:**
```json
{
  "path": "/path/to/file.py",
  "name": "file.py",
  "mime_type": "text/x-python",
  "size": 1024,
  "preview_type": "code",
  "content": "def hello():\n    print('Hello')\n",
  "language": "python",
  "lines": 2,
  "truncated": false,
  "max_lines": 1000
}
```

#### Get File Metadata

```
GET /api/v1/files/metadata/{file_path}
```

Get file metadata.

**Response:**
```json
{
  "path": "/path/to/file.py",
  "name": "file.py",
  "size": 1024,
  "mime_type": "text/x-python",
  "created_at": "2026-05-27T10:30:00.000Z",
  "modified_at": "2026-05-27T10:30:00.000Z",
  "is_directory": false,
  "is_readable": true,
  "is_writable": false
}
```

#### Download File

```
GET /api/v1/files/download/{file_path}
```

Download a file.

#### List Directory

```
GET /api/v1/files/directory/{dir_path}
```

List files in a directory.

**Parameters:**
- `dir_path` (path): Path to directory
- `recursive` (query, optional): List recursively (default: false)
- `max_depth` (query, optional): Maximum recursion depth (default: 1)

**Response:**
```json
{
  "path": "/path/to/dir",
  "files": [...],
  "directories": [...],
  "total_files": 42,
  "total_size": 1048576
}
```

#### Preview Code

```
GET /api/v1/files/code/{file_path}
```

Get code file preview with syntax highlighting info.

**Parameters:**
- `max_lines` (query, optional): Maximum lines to preview
- `highlight_lines` (query, optional): Comma-separated line numbers to highlight

---

## Integration Guide

### Frontend Integration

#### 1. Streaming Output

```typescript
import { StreamingOutput } from '@/components/StreamingOutput';

export function AgentExecution() {
  return (
    <StreamingOutput
      runId="run-123"
      onComplete={(result) => console.log('Done:', result)}
      onError={(error) => console.error('Error:', error)}
    />
  );
}
```

#### 2. Task List

```typescript
import { TaskList } from '@/components/TaskList';

export function TaskMonitor() {
  return (
    <TaskList
      runId="run-123"
      autoRefresh={true}
      refreshInterval={5000}
    />
  );
}
```

#### 3. Interactive Questions

```typescript
import { InteractiveQuestions } from '@/components/InteractiveQuestion';

export function QuestionHandler() {
  return (
    <InteractiveQuestions
      runId="run-123"
      onQuestionsUpdate={(questions) => console.log('Questions:', questions)}
    />
  );
}
```

#### 4. File Preview

```typescript
import { FilePreview } from '@/components/FilePreview';

export function FileViewer() {
  return (
    <FilePreview
      filePath="/path/to/file.py"
      maxLines={1000}
    />
  );
}
```

#### 5. Progress Indicator

```typescript
import { ProgressIndicator } from '@/components/ProgressIndicator';

export function ProgressMonitor() {
  return (
    <ProgressIndicator
      runId="run-123"
      refreshInterval={2000}
    />
  );
}
```

### Backend Integration

#### 1. Emit Events

```python
from backend.app.api.streaming import event_store, MessageEvent, ProgressEvent

# Emit message
msg = MessageEvent(
    run_id="run-123",
    content="Processing...",
    role="assistant",
    sequence=1,
)
event_store.add_event("run-123", msg)

# Emit progress
progress = ProgressEvent(
    run_id="run-123",
    overall_progress=0.5,
    current_step="Processing",
    total_steps=4,
    completed_steps=2,
    sequence=2,
)
event_store.add_event("run-123", progress)
```

#### 2. Create Tasks

```python
from backend.app.api.tasks_ui import task_store, TaskModel, TaskStatus

task = TaskModel(
    title="Process data",
    description="Process collected data",
    priority="high",
    run_id="run-123",
)
task = task_store.create(task)

# Update progress
task_store.update(task.task_id, {
    "status": TaskStatus.IN_PROGRESS,
    "progress": 0.5,
})
```

#### 3. Ask Questions

```python
from backend.app.core.interactive_questions import (
    question_manager,
    InteractiveQuestion,
    QuestionType,
    QuestionOption,
)

question = InteractiveQuestion(
    run_id="run-123",
    type=QuestionType.SINGLE_CHOICE,
    title="Select option",
    options=[
        QuestionOption(value="a", label="Option A"),
        QuestionOption(value="b", label="Option B"),
    ],
    timeout_seconds=300,
)
question = question_manager.create_question(question)

# Wait for answer
answer = await question_manager.wait_for_answer(question.question_id)
```

---

## Examples

See `backend/app/examples/ux_integration_example.py` for complete working examples.

### Running Examples

```bash
python -m backend.app.examples.ux_integration_example
```

---

## Best Practices

1. **Streaming**: Use SSE for real-time updates, poll for historical data
2. **Tasks**: Create tasks for major workflow steps, use dependencies for ordering
3. **Questions**: Set appropriate timeouts, provide default answers for critical questions
4. **Files**: Limit preview size for large files, use pagination for directories
5. **Performance**: Batch events, limit event history, clean up expired questions

---

## Error Handling

All endpoints return standard HTTP status codes:

- `200 OK`: Success
- `201 Created`: Resource created
- `204 No Content`: Success with no content
- `400 Bad Request`: Invalid request
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Permission denied
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

Error responses include:
```json
{
  "detail": "Error message",
  "error_code": "ERROR_CODE"
}
```

---

## Rate Limiting

- Streaming: No limit (keep-alive connection)
- Tasks: 100 requests/minute
- Questions: 100 requests/minute
- Files: 100 requests/minute

---

## Security

- All endpoints require authentication (Bearer token or API key)
- File preview is restricted to readable files
- Path traversal is prevented
- Large files are truncated for preview
- Sensitive data should not be logged

---

## Changelog

### Version 1.0.0 (2026-05-27)

- Initial release
- Streaming API with SSE support
- Task management with dependencies
- Interactive questions system
- File preview and metadata
- React components for frontend integration
