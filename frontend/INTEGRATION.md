/**
 * Frontend Integration Documentation
 *
 * Complete guide for integrating 7 React components into X-Agent frontend.
 */

# X-Agent Frontend Integration Guide

## Overview

This document describes the integration of 7 React components into the X-Agent frontend application, enabling real-time agent execution monitoring, task management, and user interaction.

## Architecture

### Components

1. **StreamingOutput** - Real-time event display with SSE support
2. **TaskList** - Task management and progress tracking
3. **InteractiveQuestion** - User interaction prompts
4. **FilePreview** - File content viewing with syntax highlighting
5. **ProgressIndicator** - Execution progress visualization
6. **FolderSelector** - Directory mounting and workspace management
7. **AgentWorkspace** - Main layout integrating all components

### Services

1. **SSEClient** (`frontend/src/services/sseClient.ts`)
   - Server-Sent Events connection management
   - Automatic reconnection with exponential backoff
   - Event type handling and parsing

2. **APIClient** (`frontend/src/services/apiClient.ts`)
   - HTTP client for backend API communication
   - Typed request/response handling
   - Error handling and timeouts

3. **AgentStore** (`frontend/src/store/agentStore.ts`)
   - Zustand-based state management
   - Centralized state for runs, tasks, questions, messages
   - Async actions for API calls

## Installation

### Prerequisites

```bash
npm install react react-dom zustand
npm install --save-dev @testing-library/react @testing-library/jest-dom jest
```

### File Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── StreamingOutput.tsx
│   │   ├── TaskList.tsx
│   │   ├── InteractiveQuestion.tsx
│   │   ├── FilePreview.tsx
│   │   ├── ProgressIndicator.tsx
│   │   ├── FolderSelector.tsx
│   │   └── FolderSelector.css
│   ├── pages/
│   │   ├── AgentWorkspace.tsx
│   │   └── AgentWorkspace.css
│   ├── services/
│   │   ├── sseClient.ts
│   │   └── apiClient.ts
│   ├── store/
│   │   └── agentStore.ts
│   └── __tests__/
│       ├── services/
│       │   ├── sseClient.test.ts
│       │   └── apiClient.test.ts
│       └── integration/
│           └── components.test.tsx
```

## Usage

### Basic Setup

```typescript
import React from 'react';
import AgentWorkspace from './pages/AgentWorkspace';

function App() {
  return (
    <AgentWorkspace
      onRunComplete={(result) => console.log('Run completed:', result)}
      onError={(error) => console.error('Error:', error)}
    />
  );
}

export default App;
```

### Using Individual Components

#### StreamingOutput

```typescript
import StreamingOutput from './components/StreamingOutput';

<StreamingOutput
  runId="run-123"
  onComplete={(result) => console.log(result)}
  onError={(error) => console.error(error)}
  maxMessages={1000}
  autoScroll={true}
/>
```

#### TaskList

```typescript
import TaskList from './components/TaskList';

<TaskList
  runId="run-123"
  status="in_progress"
  onTaskClick={(task) => console.log(task)}
  autoRefresh={true}
  refreshInterval={5000}
/>
```

#### InteractiveQuestion

```typescript
import { InteractiveQuestions } from './components/InteractiveQuestion';

<InteractiveQuestions
  runId="run-123"
  onQuestionsUpdate={(questions) => console.log(questions)}
/>
```

#### ProgressIndicator

```typescript
import ProgressIndicator from './components/ProgressIndicator';

<ProgressIndicator
  runId="run-123"
  onProgressUpdate={(progress) => console.log(progress)}
  refreshInterval={2000}
/>
```

#### FilePreview

```typescript
import FilePreview from './components/FilePreview';

<FilePreview
  filePath="/path/to/file.ts"
  maxLines={1000}
  onDownload={(path) => console.log('Download:', path)}
/>
```

#### FolderSelector

```typescript
import FolderSelector from './components/FolderSelector';

<FolderSelector
  onMountChange={(mounts) => console.log(mounts)}
  onError={(error) => console.error(error)}
/>
```

### State Management

```typescript
import { useAgentStore } from './store/agentStore';

function MyComponent() {
  const {
    currentRun,
    tasks,
    messages,
    pendingQuestions,
    isRunning,
    startRun,
    stopRun,
    answerQuestion,
  } = useAgentStore();

  const handleStart = async () => {
    try {
      await startRun('My task description');
    } catch (error) {
      console.error('Failed to start run:', error);
    }
  };

  return (
    <div>
      <button onClick={handleStart} disabled={isRunning}>
        Start
      </button>
      <div>Tasks: {tasks.length}</div>
      <div>Messages: {messages.length}</div>
    </div>
  );
}
```

## API Integration

### Backend Endpoints

The frontend expects the following backend API endpoints:

#### Agent Runs
- `POST /api/v1/agent/run/stream` - Start new agent run
- `GET /api/v1/agent/runs/{runId}` - Get run details
- `GET /api/v1/agent/runs` - List runs
- `POST /api/v1/agent/runs/{runId}/cancel` - Cancel run
- `GET /api/v1/agent/stream/{runId}` - SSE stream endpoint

#### Tasks
- `GET /api/v1/tasks` - List tasks
- `GET /api/v1/tasks/{taskId}` - Get task details
- `PATCH /api/v1/tasks/{taskId}` - Update task

#### Questions
- `GET /api/v1/questions/pending` - Get pending questions
- `GET /api/v1/questions/{questionId}` - Get question details
- `POST /api/v1/questions/{questionId}/answer` - Submit answer
- `POST /api/v1/questions/{questionId}/cancel` - Cancel question

#### Files
- `GET /api/v1/files/metadata/{path}` - Get file metadata
- `GET /api/v1/files/preview/{path}` - Get file preview
- `GET /api/v1/files/directory/{path}` - List directory
- `GET /api/v1/files/download/{path}` - Download file

#### Workspace
- `GET /api/v1/workspace/mounts` - List mounts
- `POST /api/v1/workspace/mount` - Mount directory
- `DELETE /api/v1/workspace/mount/{mountId}` - Unmount directory

## Responsive Design

The workspace supports three layouts:

### Desktop (>1024px)
- Three-column layout
- Left panel: Input and workspace
- Center panel: Streaming output
- Right panel: Progress and questions
- Bottom panel: Tasks

### Tablet (768px-1024px)
- Tab-based navigation
- Single column content
- Collapsible sections

### Mobile (<768px)
- Single column layout
- Stacked components
- Touch-friendly buttons

## Testing

### Run Tests

```bash
npm test
```

### Test Coverage

```bash
npm test -- --coverage
```

### Test Files

- `frontend/src/__tests__/services/sseClient.test.ts` - SSE client tests
- `frontend/src/__tests__/services/apiClient.test.ts` - API client tests
- `frontend/src/__tests__/integration/components.test.tsx` - Component integration tests

## Performance Optimization

### Virtual Scrolling

For large message lists, implement virtual scrolling:

```typescript
import { FixedSizeList } from 'react-window';

<FixedSizeList
  height={600}
  itemCount={messages.length}
  itemSize={80}
>
  {({ index, style }) => (
    <div style={style}>
      {renderMessage(messages[index])}
    </div>
  )}
</FixedSizeList>
```

### Lazy Loading

Components support lazy loading:

```typescript
const StreamingOutput = React.lazy(() => import('./components/StreamingOutput'));

<Suspense fallback={<div>Loading...</div>}>
  <StreamingOutput runId={runId} />
</Suspense>
```

### Message Limiting

StreamingOutput automatically limits messages to 1000 (configurable):

```typescript
<StreamingOutput
  runId={runId}
  maxMessages={500}  // Limit to 500 messages
/>
```

## Error Handling

### API Errors

```typescript
try {
  await startRun('task');
} catch (error) {
  if (error instanceof Error) {
    console.error('API Error:', error.message);
  }
}
```

### SSE Connection Errors

```typescript
<StreamingOutput
  runId={runId}
  onError={(error) => {
    console.error('Connection error:', error.message);
    // Implement retry logic
  }}
/>
```

## Accessibility

- ARIA labels on all interactive elements
- Keyboard navigation support
- High contrast mode support
- Screen reader friendly
- Reduced motion support

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari 14+, Chrome Android)

## Troubleshooting

### SSE Connection Issues

1. Check CORS headers on backend
2. Verify `/api/v1/agent/stream/{runId}` endpoint
3. Check browser console for connection errors
4. Verify EventSource support in browser

### API Request Failures

1. Check API base URL configuration
2. Verify authentication headers if needed
3. Check network tab in browser DevTools
4. Verify backend API is running

### Component Not Rendering

1. Check console for React errors
2. Verify component props are correct
3. Check CSS is loaded
4. Verify Zustand store is initialized

## Deployment

### Build

```bash
npm run build
```

### Environment Variables

```env
REACT_APP_API_BASE_URL=https://api.example.com/api/v1
REACT_APP_SSE_TIMEOUT=60000
```

### Docker

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

## Future Enhancements

1. WebSocket support for real-time updates
2. Offline mode with service workers
3. Advanced filtering and search
4. Custom themes and styling
5. Plugin system for extensions
6. Analytics and monitoring
7. Collaborative features
8. Mobile app (React Native)

## Support

For issues or questions:
1. Check documentation
2. Review test files for examples
3. Check browser console for errors
4. Review backend API logs
5. Open GitHub issue with reproduction steps
