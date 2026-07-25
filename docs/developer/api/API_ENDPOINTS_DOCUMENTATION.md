# X-Agent API Endpoints Documentation

Complete documentation for all 66 new API endpoints across 9 core systems.

**Last Updated:** 2026-05-27  
**API Version:** 1.0.0  
**Base URL:** `http://localhost:8000/api/v1`

---

## Table of Contents

1. [Streaming API](#streaming-api) - 4 endpoints
2. [Tasks UI API](#tasks-ui-api) - 8 endpoints
3. [Questions API](#questions-api) - 6 endpoints
4. [File Preview API](#file-preview-api) - 5 endpoints
5. [Parallel Agents API](#parallel-agents-api) - 7 endpoints
6. [Browser Advanced API](#browser-advanced-api) - 8 endpoints
7. [Workspace API](#workspace-api) - 8 endpoints
8. [Tools Batch API](#tools-batch-api) - 6 endpoints
9. [Memory Enhanced API](#memory-enhanced-api) - 10 endpoints

---

## Streaming API

Real-time streaming of agent execution events using Server-Sent Events (SSE).

### 1. Stream Agent Execution
- **Endpoint:** `GET /agent/stream/{run_id}`
- **Description:** Stream real-time agent execution events
- **Parameters:**
  - `run_id` (path, required): Agent run ID
  - `event_types` (query, optional): Comma-separated event types to filter
- **Response:** Server-Sent Events stream
- **Example:**
  ```bash
  curl -N http://localhost:8000/api/v1/agent/stream/run-123
  ```

### 2. Subscribe to Stream
- **Endpoint:** `POST /agent/stream/subscribe`
- **Description:** Subscribe to execution stream with custom filters
- **Request Body:**
  ```json
  {
    "run_id": "run-123",
    "event_types": ["message", "tool_call", "error"],
    "include_metadata": true
  }
  ```
- **Response:** `200 OK` with subscription ID

### 3. Unsubscribe from Stream
- **Endpoint:** `DELETE /agent/stream/{run_id}`
- **Description:** Unsubscribe from execution stream
- **Parameters:**
  - `run_id` (path, required): Agent run ID
- **Response:** `204 No Content`

### 4. Get Stream Status
- **Endpoint:** `GET /agent/stream/status`
- **Description:** Get status of all active streams
- **Response:**
  ```json
  {
    "active_streams": 5,
    "total_events": 1250,
    "uptime_seconds": 3600
  }
  ```

---

## Tasks UI API

Interactive task management for agent workflows.

### 1. List All Tasks
- **Endpoint:** `GET /tasks`
- **Description:** List all tasks with pagination
- **Query Parameters:**
  - `page` (optional): Page number (default: 1)
  - `page_size` (optional): Items per page (default: 20)
  - `status` (optional): Filter by status (pending, in_progress, completed)
- **Response:**
  ```json
  {
    "tasks": [...],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
  ```

### 2. Create New Task
- **Endpoint:** `POST /tasks`
- **Description:** Create a new task
- **Request Body:**
  ```json
  {
    "title": "Task title",
    "description": "Task description",
    "priority": "high",
    "due_date": "2026-06-01T00:00:00Z"
  }
  ```
- **Response:** `201 Created` with task object

### 3. Get Task Details
- **Endpoint:** `GET /tasks/{task_id}`
- **Description:** Get detailed information about a task
- **Parameters:**
  - `task_id` (path, required): Task ID
- **Response:** Task object with full details

### 4. Update Task
- **Endpoint:** `PUT /tasks/{task_id}`
- **Description:** Update task properties
- **Request Body:** Partial task object
- **Response:** Updated task object

### 5. Delete Task
- **Endpoint:** `DELETE /tasks/{task_id}`
- **Description:** Delete a task
- **Parameters:**
  - `task_id` (path, required): Task ID
- **Response:** `204 No Content`

### 6. Mark Task Complete
- **Endpoint:** `POST /tasks/{task_id}/complete`
- **Description:** Mark task as completed
- **Request Body:**
  ```json
  {
    "notes": "Completion notes",
    "result": "success"
  }
  ```
- **Response:** Updated task object

### 7. Filter Tasks
- **Endpoint:** `GET /tasks/filter`
- **Description:** Advanced task filtering
- **Query Parameters:**
  - `query` (required): Filter query
  - `sort_by` (optional): Sort field
  - `order` (optional): asc or desc
- **Response:** Filtered task list

### 8. Batch Task Operations
- **Endpoint:** `POST /tasks/batch`
- **Description:** Perform batch operations on multiple tasks
- **Request Body:**
  ```json
  {
    "operation": "update_status",
    "task_ids": ["task-1", "task-2"],
    "data": {"status": "completed"}
  }
  ```
- **Response:** Batch operation result

---

## Questions API

Interactive question handling for user prompts during execution.

### 1. Ask Interactive Question
- **Endpoint:** `POST /questions/ask`
- **Description:** Ask user an interactive question
- **Request Body:**
  ```json
  {
    "question": "Do you want to proceed?",
    "type": "yes_no",
    "timeout_seconds": 300,
    "context": {}
  }
  ```
- **Response:** Question object with ID

### 2. Get Question Details
- **Endpoint:** `GET /questions/{question_id}`
- **Description:** Get question and current answer status
- **Parameters:**
  - `question_id` (path, required): Question ID
- **Response:** Question object

### 3. Submit Answer
- **Endpoint:** `POST /questions/{question_id}/answer`
- **Description:** Submit answer to a question
- **Request Body:**
  ```json
  {
    "answer": "yes",
    "confidence": 0.95
  }
  ```
- **Response:** `200 OK` with confirmation

### 4. Get Pending Questions
- **Endpoint:** `GET /questions/pending`
- **Description:** Get all pending questions
- **Response:** List of pending questions

### 5. Dismiss Question
- **Endpoint:** `DELETE /questions/{question_id}`
- **Description:** Dismiss a question without answering
- **Parameters:**
  - `question_id` (path, required): Question ID
- **Response:** `204 No Content`

### 6. Batch Question Operations
- **Endpoint:** `POST /questions/batch`
- **Description:** Batch operations on questions
- **Request Body:**
  ```json
  {
    "operation": "dismiss_all",
    "filter": {"status": "pending"}
  }
  ```
- **Response:** Operation result

---

## File Preview API

Generate and manage file previews for various file types.

### 1. Preview File
- **Endpoint:** `GET /files/preview/{file_id}`
- **Description:** Get preview of a file
- **Parameters:**
  - `file_id` (path, required): File ID
  - `format` (query, optional): Preview format (html, text, image)
- **Response:** Preview content

### 2. Generate Preview
- **Endpoint:** `POST /files/preview/generate`
- **Description:** Generate preview for a file
- **Request Body:**
  ```json
  {
    "file_path": "/path/to/file",
    "format": "html",
    "options": {}
  }
  ```
- **Response:** Generated preview

### 3. Get Supported Formats
- **Endpoint:** `GET /files/preview/formats`
- **Description:** Get list of supported preview formats
- **Response:**
  ```json
  {
    "formats": ["html", "text", "image", "pdf"],
    "file_types": {...}
  }
  ```

### 4. Cache Preview
- **Endpoint:** `POST /files/preview/cache`
- **Description:** Cache a preview for faster retrieval
- **Request Body:**
  ```json
  {
    "file_id": "file-123",
    "ttl_hours": 24
  }
  ```
- **Response:** Cache info

### 5. Clear Preview Cache
- **Endpoint:** `DELETE /files/preview/{file_id}`
- **Description:** Clear cached preview
- **Parameters:**
  - `file_id` (path, required): File ID
- **Response:** `204 No Content`

---

## Parallel Agents API

Execute multiple agents in parallel with isolation and communication.

### 1. Spawn Parallel Agents
- **Endpoint:** `POST /agents/parallel/spawn`
- **Description:** Start multiple agents in parallel
- **Request Body:**
  ```json
  {
    "agents": [
      {"id": "agent-1", "task": "..."},
      {"id": "agent-2", "task": "..."}
    ],
    "isolation_mode": "process",
    "timeout_seconds": 3600
  }
  ```
- **Response:** Batch execution object

### 2. Get Batch Status
- **Endpoint:** `GET /agents/parallel/{batch_id}/status`
- **Description:** Get status of parallel batch execution
- **Parameters:**
  - `batch_id` (path, required): Batch ID
- **Response:** Batch status object

### 3. Get Batch Results
- **Endpoint:** `GET /agents/parallel/{batch_id}/results`
- **Description:** Get results from completed batch
- **Parameters:**
  - `batch_id` (path, required): Batch ID
- **Response:** Aggregated results

### 4. Cancel Batch
- **Endpoint:** `POST /agents/parallel/{batch_id}/cancel`
- **Description:** Cancel running batch execution
- **Parameters:**
  - `batch_id` (path, required): Batch ID
- **Response:** Cancellation confirmation

### 5. List All Batches
- **Endpoint:** `GET /agents/parallel/batches`
- **Description:** List all parallel batches
- **Query Parameters:**
  - `status` (optional): Filter by status
  - `limit` (optional): Result limit
- **Response:** List of batches

### 6. Inter-Agent Communication
- **Endpoint:** `POST /agents/parallel/communicate`
- **Description:** Send message between agents
- **Request Body:**
  ```json
  {
    "from_agent": "agent-1",
    "to_agent": "agent-2",
    "message": "...",
    "priority": "high"
  }
  ```
- **Response:** Message delivery confirmation

### 7. Get Batch Logs
- **Endpoint:** `GET /agents/parallel/{batch_id}/logs`
- **Description:** Get execution logs from batch
- **Parameters:**
  - `batch_id` (path, required): Batch ID
  - `agent_id` (query, optional): Filter by agent
- **Response:** Log entries

---

## Browser Advanced API

Advanced browser monitoring and automation capabilities.

### 1. Get Network Requests
- **Endpoint:** `GET /browser/advanced/network`
- **Description:** Get captured network requests
- **Query Parameters:**
  - `session_id` (required): Browser session ID
  - `url_pattern` (optional): Filter by URL pattern
- **Response:** Network requests list

### 2. Get Performance Metrics
- **Endpoint:** `GET /browser/advanced/performance`
- **Description:** Get performance metrics
- **Query Parameters:**
  - `session_id` (required): Browser session ID
- **Response:** Performance data

### 3. Get Console Logs
- **Endpoint:** `GET /browser/advanced/console`
- **Description:** Get browser console logs
- **Query Parameters:**
  - `session_id` (required): Browser session ID
  - `level` (optional): Filter by log level
- **Response:** Console logs

### 4. Start Recording
- **Endpoint:** `POST /browser/advanced/record`
- **Description:** Start recording browser session
- **Request Body:**
  ```json
  {
    "session_id": "session-123",
    "include_network": true,
    "include_console": true
  }
  ```
- **Response:** Recording started confirmation

### 5. Stop Recording
- **Endpoint:** `POST /browser/advanced/stop-record`
- **Description:** Stop recording browser session
- **Request Body:**
  ```json
  {
    "session_id": "session-123"
  }
  ```
- **Response:** Recording stopped confirmation

### 6. Export HAR File
- **Endpoint:** `GET /browser/advanced/har`
- **Description:** Export session as HAR file
- **Query Parameters:**
  - `session_id` (required): Browser session ID
- **Response:** HAR file content

### 7. Take Screenshot
- **Endpoint:** `POST /browser/advanced/screenshot`
- **Description:** Take screenshot of current page
- **Request Body:**
  ```json
  {
    "session_id": "session-123",
    "format": "png"
  }
  ```
- **Response:** Screenshot data

### 8. Get DOM Snapshot
- **Endpoint:** `GET /browser/advanced/dom`
- **Description:** Get DOM snapshot
- **Query Parameters:**
  - `session_id` (required): Browser session ID
- **Response:** DOM structure

---

## Workspace API

Manage workspaces and file system access.

### 1. Create Workspace
- **Endpoint:** `POST /workspace/create`
- **Description:** Create new workspace
- **Request Body:**
  ```json
  {
    "workspace_type": "project",
    "max_size_mb": 1000,
    "ttl_hours": 24
  }
  ```
- **Response:** Workspace object

### 2. Get Workspace Info
- **Endpoint:** `GET /workspace/{workspace_id}`
- **Description:** Get workspace information
- **Parameters:**
  - `workspace_id` (path, required): Workspace ID
- **Response:** Workspace details

### 3. Delete Workspace
- **Endpoint:** `DELETE /workspace/{workspace_id}`
- **Description:** Delete workspace
- **Parameters:**
  - `workspace_id` (path, required): Workspace ID
- **Response:** `204 No Content`

### 4. Mount Directory
- **Endpoint:** `POST /workspace/{workspace_id}/mount`
- **Description:** Mount directory in workspace
- **Request Body:**
  ```json
  {
    "source_path": "/path/to/mount",
    "mount_point": "/mnt/data"
  }
  ```
- **Response:** Mount confirmation

### 5. Unmount Directory
- **Endpoint:** `POST /workspace/{workspace_id}/unmount`
- **Description:** Unmount directory from workspace
- **Request Body:**
  ```json
  {
    "mount_point": "/mnt/data"
  }
  ```
- **Response:** Unmount confirmation

### 6. List Workspace Files
- **Endpoint:** `GET /workspace/{workspace_id}/files`
- **Description:** List files in workspace
- **Parameters:**
  - `workspace_id` (path, required): Workspace ID
  - `path` (query, optional): Directory path
- **Response:** File list

### 7. Upload File
- **Endpoint:** `POST /workspace/{workspace_id}/upload`
- **Description:** Upload file to workspace
- **Parameters:**
  - `workspace_id` (path, required): Workspace ID
- **Request:** Multipart form data with file
- **Response:** Upload confirmation

### 8. List All Workspaces
- **Endpoint:** `GET /workspace/list`
- **Description:** List all workspaces
- **Query Parameters:**
  - `type` (optional): Filter by type
  - `limit` (optional): Result limit
- **Response:** Workspace list

---

## Tools Batch API

Execute multiple tools in parallel with result aggregation.

### 1. Execute Batch Tools
- **Endpoint:** `POST /tools/batch/execute`
- **Description:** Execute multiple tools in parallel
- **Request Body:**
  ```json
  {
    "calls": [
      {"name": "tool_1", "arguments": {...}},
      {"name": "tool_2", "arguments": {...}}
    ],
    "timeout_seconds": 300
  }
  ```
- **Response:** Batch execution object

### 2. Get Batch Status
- **Endpoint:** `GET /tools/batch/{batch_id}/status`
- **Description:** Get batch execution status
- **Parameters:**
  - `batch_id` (path, required): Batch ID
- **Response:** Status object

### 3. Get Batch Results
- **Endpoint:** `GET /tools/batch/{batch_id}/results`
- **Description:** Get batch execution results
- **Parameters:**
  - `batch_id` (path, required): Batch ID
- **Response:** Results object

### 4. Cancel Batch
- **Endpoint:** `POST /tools/batch/{batch_id}/cancel`
- **Description:** Cancel batch execution
- **Parameters:**
  - `batch_id` (path, required): Batch ID
- **Response:** Cancellation confirmation

### 5. Get Batch History
- **Endpoint:** `GET /tools/batch/history`
- **Description:** Get batch execution history
- **Query Parameters:**
  - `limit` (optional): Result limit
  - `offset` (optional): Result offset
- **Response:** History list

### 6. Validate Batch Request
- **Endpoint:** `POST /tools/batch/validate`
- **Description:** Validate batch request before execution
- **Request Body:** Batch request object
- **Response:** Validation result

---

## Memory Enhanced API

Hybrid memory system with auto-tiering and relationship management.

### 1. Store Memory
- **Endpoint:** `POST /memory/store`
- **Description:** Store memory with auto-tiering
- **Request Body:**
  ```json
  {
    "content": "Memory content",
    "type": "fact",
    "importance": 0.8,
    "tags": ["tag1", "tag2"]
  }
  ```
- **Response:** Memory object

### 2. Recall Memory
- **Endpoint:** `GET /memory/recall`
- **Description:** Recall memories based on context
- **Query Parameters:**
  - `context` (required): Context for recall
  - `limit` (optional): Result limit
- **Response:** Recalled memories

### 3. Search Memories
- **Endpoint:** `GET /memory/search`
- **Description:** Search memories
- **Query Parameters:**
  - `query` (required): Search query
  - `type` (optional): Filter by type
  - `limit` (optional): Result limit
- **Response:** Search results

### 4. Create Memory Relationship
- **Endpoint:** `POST /memory/relate`
- **Description:** Create relationship between memories
- **Request Body:**
  ```json
  {
    "memory_id_1": "mem-1",
    "memory_id_2": "mem-2",
    "relationship_type": "related_to",
    "strength": 0.9
  }
  ```
- **Response:** Relationship object

### 5. Get Related Memories
- **Endpoint:** `GET /memory/related/{memory_id}`
- **Description:** Get memories related to given memory
- **Parameters:**
  - `memory_id` (path, required): Memory ID
- **Response:** Related memories

### 6. Merge Memories
- **Endpoint:** `POST /memory/merge`
- **Description:** Merge multiple memories
- **Request Body:**
  ```json
  {
    "memory_ids": ["mem-1", "mem-2"],
    "merge_strategy": "combine"
  }
  ```
- **Response:** Merged memory object

### 7. Get Memory Statistics
- **Endpoint:** `GET /memory/stats`
- **Description:** Get memory system statistics
- **Response:** Statistics object

### 8. Delete Memory
- **Endpoint:** `DELETE /memory/{memory_id}`
- **Description:** Delete memory
- **Parameters:**
  - `memory_id` (path, required): Memory ID
- **Response:** `204 No Content`

### 9. Export Memories
- **Endpoint:** `POST /memory/export`
- **Description:** Export memories to file
- **Request Body:**
  ```json
  {
    "format": "json",
    "filter": {}
  }
  ```
- **Response:** Export file

### 10. Import Memories
- **Endpoint:** `POST /memory/import`
- **Description:** Import memories from file
- **Request:** Multipart form data with file
- **Response:** Import result

---

## Error Handling

All endpoints follow standard HTTP status codes:

- `200 OK` - Successful GET/POST request
- `201 Created` - Resource created successfully
- `204 No Content` - Successful DELETE request
- `400 Bad Request` - Invalid request parameters
- `401 Unauthorized` - Missing or invalid authentication
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Service temporarily unavailable

Error responses include:
```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {}
}
```

---

## Authentication

All endpoints require authentication via:
- Bearer token in `Authorization` header
- API key in `X-API-Key` header

Example:
```bash
curl -H "Authorization: Bearer token" http://localhost:8000/api/v1/tasks
```

---

## Rate Limiting

Rate limits are applied per endpoint:
- Login: 10 requests per minute
- Register: 5 requests per minute
- General API: 100 requests per minute

Rate limit info is included in response headers:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

---

## CORS Configuration

CORS is configured to allow:
- Origins: `http://localhost:3000`, `http://localhost:5173`
- Methods: GET, POST, PUT, PATCH, OPTIONS
- Headers: Authorization, Content-Type, X-Request-Id, X-API-Key

---

## Testing

Run the API endpoint test suite:

```bash
python scripts/test_api_endpoints.py \
  --base-url http://localhost:8000 \
  --output api_test_report.json
```

---

## Changelog

### Version 1.0.0 (2026-05-27)
- Initial release with 66 endpoints
- 9 core systems implemented
- Full documentation and testing suite

---

## Support

For issues or questions:
1. Check the error message and error code
2. Review the endpoint documentation
3. Check the test report for endpoint status
4. Contact the development team

---

**End of Documentation**
