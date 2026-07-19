# Feedback Dashboard Integration Guide

## Overview

This guide explains how to integrate the Feedback Dashboard into the X-Agent application and connect it with the backend feedback system.

## Prerequisites

- Node.js 18+
- npm or yarn
- X-Agent backend API running
- React 18.2+
- TypeScript 5.3+

## Installation

### 1. Install Dependencies

The required dependencies are already in `package.json`:

```bash
cd frontend
npm install
```

Key packages:
- `recharts`: Data visualization
- `@tanstack/react-query`: Data fetching
- `axios`: HTTP client
- `lucide-react`: Icons
- `tailwindcss`: Styling

### 2. Environment Configuration

Create a `.env` file in the frontend directory:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_NAME=X-Agent
VITE_APP_VERSION=1.0.0
```

### 3. Import the Dashboard

In your main routing file (e.g., `src/App.tsx`):

```typescript
import { FeedbackDashboard } from '@/pages/FeedbackDashboard'
import { BrowserRouter, Routes, Route } from 'react-router-dom'

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Other routes */}
        <Route path="/feedback" element={<FeedbackDashboard />} />
      </Routes>
    </BrowserRouter>
  )
}
```

### 4. Add Navigation Link

Add a link to the feedback dashboard in your navigation:

```typescript
import { MessageSquare } from 'lucide-react'

export function Navigation() {
  return (
    <nav>
      {/* Other nav items */}
      <a href="/feedback" className="flex items-center gap-2">
        <MessageSquare size={20} />
        Feedback
      </a>
    </nav>
  )
}
```

## Backend Integration

### API Endpoints Required

The backend must implement these endpoints:

#### Feedback Management
```
GET    /api/v1/feedback
POST   /api/v1/feedback
GET    /api/v1/feedback/:id
PUT    /api/v1/feedback/:id
DELETE /api/v1/feedback/:id
POST   /api/v1/feedback/:id/resolve
```

#### Analytics
```
GET    /api/v1/feedback/stats
GET    /api/v1/feedback/trends
GET    /api/v1/feedback/sentiment-analysis
GET    /api/v1/feedback/category-distribution
```

#### Notifications
```
GET    /api/v1/feedback/notifications
POST   /api/v1/feedback/notifications
PUT    /api/v1/feedback/notifications/:id
DELETE /api/v1/feedback/notifications/:id
POST   /api/v1/feedback/notifications/:id/test
```

#### Export & Search
```
GET    /api/v1/feedback/export
GET    /api/v1/feedback/search
```

### Request/Response Format

**List Feedbacks Request:**
```
GET /api/v1/feedback?page=1&pageSize=20&type=bug&status=open
```

**List Feedbacks Response:**
```json
{
  "items": [
    {
      "id": "fb-001",
      "userId": "user-123",
      "type": "bug",
      "category": "UI",
      "title": "Login button not working",
      "description": "The login button is unresponsive",
      "sentiment": "negative",
      "priority": "high",
      "status": "open",
      "tags": ["urgent"],
      "createdAt": "2026-05-29T10:00:00Z",
      "updatedAt": "2026-05-29T10:00:00Z"
    }
  ],
  "total": 100,
  "page": 1,
  "pageSize": 20,
  "hasMore": true
}
```

**Create Feedback Request:**
```json
{
  "type": "bug",
  "category": "UI",
  "title": "Login button not working",
  "description": "The login button is unresponsive",
  "sentiment": "negative",
  "priority": "high",
  "tags": ["urgent"]
}
```

**Get Stats Response:**
```json
{
  "total": 100,
  "byType": {
    "bug": 40,
    "feature": 30,
    "improvement": 20,
    "other": 10
  },
  "byStatus": {
    "open": 30,
    "in_progress": 20,
    "resolved": 40,
    "closed": 10
  },
  "bySentiment": {
    "positive": 30,
    "neutral": 40,
    "negative": 30
  },
  "byPriority": {
    "critical": 10,
    "high": 20,
    "medium": 40,
    "low": 30
  },
  "avgResolutionTime": 5,
  "resolutionRate": 0.8
}
```

## Customization

### Theming

The dashboard respects the app's theme setting:

```typescript
import { useAppStore } from '@/store/appStore'

export function MyComponent() {
  const { theme } = useAppStore()
  
  return (
    <div className={theme === 'dark' ? 'bg-slate-900' : 'bg-white'}>
      {/* Content */}
    </div>
  )
}
```

### Custom Colors

Modify the color scheme in `FeedbackVisualization.tsx`:

```typescript
const COLORS = {
  bug: '#ef4444',
  feature: '#3b82f6',
  improvement: '#10b981',
  other: '#8b5cf6',
  // ... more colors
}
```

### Custom Triggers

Add new notification triggers in `NotificationSettings.tsx`:

```typescript
const triggerOptions = [
  'new_feedback',
  'feedback_resolved',
  'high_priority_feedback',
  'critical_feedback',
  'sentiment_negative',
  'daily_summary',
  // Add new triggers here
  'weekly_summary',
  'monthly_report',
]
```

## Data Flow

```
User Action
    ↓
Component Event Handler
    ↓
FeedbackService API Call
    ↓
Backend API
    ↓
Database
    ↓
Response
    ↓
Update Component State
    ↓
Re-render UI
```

## Real-time Updates

The dashboard auto-refreshes every 30 seconds:

```typescript
useEffect(() => {
  loadData()
  const interval = setInterval(loadData, 30000) // 30 seconds
  return () => clearInterval(interval)
}, [])
```

To implement real-time updates with WebSocket:

```typescript
import { useEffect } from 'react'

useEffect(() => {
  const ws = new WebSocket('ws://localhost:8000/feedback/updates')
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    // Update state with new data
    setFeedbacks(prev => [...prev, data])
  }
  
  return () => ws.close()
}, [])
```

## Error Handling

The dashboard includes comprehensive error handling:

```typescript
try {
  const data = await feedbackService.listFeedback()
  setFeedbacks(data.items)
} catch (error) {
  if (error.response?.status === 401) {
    // Handle unauthorized
    redirectToLogin()
  } else if (error.response?.status === 500) {
    // Handle server error
    showErrorMessage('Server error occurred')
  } else {
    // Handle other errors
    showErrorMessage(error.message)
  }
}
```

## Authentication

The service automatically includes auth tokens:

```typescript
// In FeedbackService
private setupInterceptors() {
  this.client.interceptors.request.use((config) => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })
}
```

Ensure your backend validates these tokens.

## Performance Optimization

### Pagination
The dashboard uses pagination to handle large datasets:

```typescript
const [page, setPage] = useState(1)
const { data } = await feedbackService.listFeedback(page, 20)
```

### Caching
React Query automatically caches API responses:

```typescript
const { data, isLoading } = useQuery({
  queryKey: ['feedbacks', page],
  queryFn: () => feedbackService.listFeedback(page),
})
```

### Lazy Loading
Analytics data is loaded on-demand when the tab is selected.

## Testing Integration

### Unit Tests
```bash
npm test
```

### Integration Tests
```bash
npm test -- --integration
```

### E2E Tests
```bash
npm run test:e2e
```

## Deployment

### Development
```bash
npm run dev
```

### Production Build
```bash
npm run build
npm run preview
```

### Docker Deployment
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "preview"]
```

## Monitoring

### Error Tracking
Integrate with error tracking service:

```typescript
import * as Sentry from "@sentry/react"

Sentry.init({
  dsn: process.env.VITE_SENTRY_DSN,
  environment: process.env.NODE_ENV,
})
```

### Analytics
Track user interactions:

```typescript
import { analytics } from '@/services/analytics'

const handleSelectFeedback = (feedback) => {
  analytics.track('feedback_viewed', {
    feedbackId: feedback.id,
    type: feedback.type,
  })
  // ...
}
```

## Troubleshooting

### API Connection Issues
1. Verify backend is running
2. Check `VITE_API_BASE_URL` environment variable
3. Check CORS configuration on backend
4. Verify authentication token is valid

### Data Not Loading
1. Check browser console for errors
2. Verify API endpoints are implemented
3. Check network tab in DevTools
4. Verify response format matches expected types

### Performance Issues
1. Check network tab for slow requests
2. Profile React components with DevTools
3. Reduce refresh interval if needed
4. Implement pagination for large datasets

## Support

For issues or questions:
1. Check the [User Guide](./FEEDBACK_DASHBOARD_USER_GUIDE.md)
2. Check the [Developer Guide](./FEEDBACK_DASHBOARD_DEVELOPER_GUIDE.md)
3. Review test files for usage examples
4. Check backend API documentation

## Next Steps

1. Implement backend API endpoints
2. Configure environment variables
3. Add dashboard route to application
4. Test with sample data
5. Deploy to production
6. Monitor performance and errors
7. Gather user feedback
8. Iterate and improve
