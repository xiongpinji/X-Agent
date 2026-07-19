# Feedback Dashboard Developer Guide

## Architecture Overview

The Feedback Dashboard is built with a modular, component-based architecture using React and TypeScript:

```
frontend/
├── src/
│   ├── services/
│   │   └── feedback.ts          # API service layer
│   ├── components/
│   │   └── feedback/
│   │       ├── FeedbackList.tsx         # Feedback list component
│   │       ├── FeedbackDetail.tsx       # Detail modal component
│   │       ├── FeedbackVisualization.tsx # Charts and analytics
│   │       └── NotificationSettings.tsx  # Notification config
│   ├── pages/
│   │   └── FeedbackDashboard.tsx        # Main dashboard page
│   └── __tests__/
│       ├── components/
│       │   └── feedback.test.tsx        # Component tests
│       └── services/
│           └── feedback.test.ts         # Service tests
└── docs/
    └── FEEDBACK_DASHBOARD_USER_GUIDE.md
```

## Technology Stack

- **React 18.2**: UI framework
- **TypeScript 5.3**: Type safety
- **Recharts 2.10**: Data visualization
- **React Query 5.28**: Data fetching and caching
- **Axios 1.6**: HTTP client
- **TailwindCSS 3.3**: Styling
- **Lucide React 0.294**: Icons
- **Vitest**: Unit testing
- **React Testing Library**: Component testing

## Service Layer

### FeedbackService

Located in `src/services/feedback.ts`, this service handles all API communication:

```typescript
// Feedback CRUD
feedbackService.listFeedback(page, pageSize, filters)
feedbackService.getFeedback(id)
feedbackService.createFeedback(data)
feedbackService.updateFeedback(id, data)
feedbackService.deleteFeedback(id)
feedbackService.resolveFeedback(id, response)

// Analytics
feedbackService.getStats(dateRange)
feedbackService.getTrends(days, groupBy)
feedbackService.getSentimentAnalysis(dateRange)
feedbackService.getCategoryDistribution()

// Notifications
feedbackService.listNotifications()
feedbackService.createNotification(data)
feedbackService.updateNotification(id, data)
feedbackService.deleteNotification(id)
feedbackService.testNotification(id)

// Export
feedbackService.exportFeedback(format, filters)

// Search
feedbackService.searchFeedback(query)
```

### API Endpoints

The service communicates with these backend endpoints:

```
GET    /api/v1/feedback                    # List feedbacks
GET    /api/v1/feedback/:id                # Get feedback
POST   /api/v1/feedback                    # Create feedback
PUT    /api/v1/feedback/:id                # Update feedback
DELETE /api/v1/feedback/:id                # Delete feedback
POST   /api/v1/feedback/:id/resolve        # Resolve feedback

GET    /api/v1/feedback/stats              # Get statistics
GET    /api/v1/feedback/trends             # Get trends
GET    /api/v1/feedback/sentiment-analysis # Sentiment analysis
GET    /api/v1/feedback/category-distribution # Category distribution

GET    /api/v1/feedback/notifications      # List notifications
POST   /api/v1/feedback/notifications      # Create notification
PUT    /api/v1/feedback/notifications/:id  # Update notification
DELETE /api/v1/feedback/notifications/:id  # Delete notification
POST   /api/v1/feedback/notifications/:id/test # Test notification

GET    /api/v1/feedback/export             # Export feedbacks
GET    /api/v1/feedback/search             # Search feedbacks
```

## Component Structure

### FeedbackList Component

Displays a filterable, sortable list of feedbacks:

**Props:**
```typescript
interface FeedbackListProps {
  feedbacks: Feedback[]
  isLoading: boolean
  onSelectFeedback: (feedback: Feedback) => void
  onDeleteFeedback: (id: string) => void
  onStatusChange: (id: string, status: Feedback['status']) => void
  theme: 'light' | 'dark'
}
```

**Features:**
- Search by title/description
- Filter by type, status, priority
- Sort by date or priority
- Real-time status updates
- Delete functionality

### FeedbackDetail Component

Modal for viewing and editing feedback details:

**Props:**
```typescript
interface FeedbackDetailProps {
  feedback: Feedback
  onClose: () => void
  onUpdate: (id: string, data: Partial<Feedback>) => void
  onResolve: (id: string, response: string) => void
  theme: 'light' | 'dark'
}
```

**Features:**
- View complete feedback information
- Edit status and priority
- Add responses
- Display existing responses
- Show tags and metadata

### FeedbackVisualization Component

Charts and analytics dashboard:

**Props:**
```typescript
interface FeedbackVisualizationProps {
  stats: FeedbackStats | null
  trends: FeedbackTrend[] | null
  isLoading: boolean
  theme: 'light' | 'dark'
}
```

**Charts:**
- Feedback trends (line chart)
- Type distribution (pie chart)
- Status distribution (bar chart)
- Sentiment distribution (pie chart)
- Priority distribution (bar chart)

### NotificationSettings Component

Configure notification channels:

**Props:**
```typescript
interface NotificationSettingsProps {
  notifications: NotificationConfig[]
  onAdd: (data: Partial<NotificationConfig>) => void
  onUpdate: (id: string, data: Partial<NotificationConfig>) => void
  onDelete: (id: string) => void
  onTest: (id: string) => void
  theme: 'light' | 'dark'
}
```

**Features:**
- Add email/Slack channels
- Configure triggers
- Test notifications
- Edit/delete channels

## Data Types

### Feedback
```typescript
interface Feedback {
  id: string
  userId: string
  type: 'bug' | 'feature' | 'improvement' | 'other'
  category: string
  title: string
  description: string
  sentiment: 'positive' | 'neutral' | 'negative'
  priority: 'low' | 'medium' | 'high' | 'critical'
  status: 'open' | 'in_progress' | 'resolved' | 'closed'
  tags: string[]
  attachments?: string[]
  createdAt: string
  updatedAt: string
  resolvedAt?: string
  response?: string
}
```

### FeedbackStats
```typescript
interface FeedbackStats {
  total: number
  byType: Record<string, number>
  byStatus: Record<string, number>
  bySentiment: Record<string, number>
  byPriority: Record<string, number>
  avgResolutionTime: number
  resolutionRate: number
}
```

### NotificationConfig
```typescript
interface NotificationConfig {
  id: string
  type: 'email' | 'slack'
  enabled: boolean
  target: string
  triggers: string[]
  createdAt: string
  updatedAt: string
}
```

## Testing

### Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm test -- --watch

# Run specific test file
npm test -- feedback.test.tsx

# Generate coverage report
npm test -- --coverage
```

### Test Structure

Tests are organized by type:

**Component Tests** (`__tests__/components/feedback.test.tsx`):
- Rendering tests
- User interaction tests
- Props validation
- Event handler tests

**Service Tests** (`__tests__/services/feedback.test.ts`):
- API call tests
- Error handling
- Data transformation
- Mocking axios

### Writing Tests

Example component test:
```typescript
describe('FeedbackList Component', () => {
  it('renders feedback list', () => {
    render(<FeedbackList {...mockProps} />)
    expect(screen.getByText('Test feedback')).toBeInTheDocument()
  })

  it('filters feedbacks by search', async () => {
    render(<FeedbackList {...mockProps} />)
    const input = screen.getByPlaceholderText('Search feedbacks...')
    await userEvent.type(input, 'test')
    expect(screen.getByText('Test feedback')).toBeInTheDocument()
  })
})
```

## State Management

The dashboard uses Zustand for global state management via `useAppStore`:

```typescript
const { theme, isLoading, setLoading, setError } = useAppStore()
```

Local component state is managed with React hooks:
```typescript
const [feedbacks, setFeedbacks] = useState<Feedback[]>([])
const [selectedFeedback, setSelectedFeedback] = useState<Feedback | null>(null)
```

## Styling

All components use TailwindCSS with theme support:

```typescript
className={clsx(
  'p-4 rounded-lg border',
  theme === 'dark' 
    ? 'bg-slate-800 border-slate-700' 
    : 'bg-white border-slate-200'
)}
```

Color scheme:
- **Light**: White backgrounds, slate text
- **Dark**: Slate-900 backgrounds, white text

## Performance Optimization

### Data Fetching
- Auto-refresh every 30 seconds
- Pagination with 50 items per page
- Lazy loading of analytics data

### Rendering
- Memoization of expensive components
- Virtual scrolling for large lists (future enhancement)
- Debounced search input

### Caching
- React Query for automatic caching
- LocalStorage for user preferences
- Browser cache for static assets

## Error Handling

All API calls include error handling:

```typescript
try {
  const data = await feedbackService.listFeedback()
  setFeedbacks(data.items)
} catch (error) {
  setError(error instanceof Error ? error.message : 'Failed to load')
}
```

Error messages are displayed to users via the app store.

## Accessibility

Components follow WCAG guidelines:
- Semantic HTML elements
- ARIA labels for interactive elements
- Keyboard navigation support
- Color contrast compliance
- Focus management in modals

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Mobile)

## Development Workflow

### Setup
```bash
cd frontend
npm install
npm run dev
```

### Building
```bash
npm run build
npm run preview
```

### Linting
```bash
npm run lint
npm run format
```

### Type Checking
```bash
npm run type-check
```

## Common Tasks

### Adding a New Filter
1. Add filter state in component
2. Update filter logic in `filteredFeedbacks`
3. Add filter UI element
4. Update API call with filter params

### Adding a New Chart
1. Create chart component using Recharts
2. Add data transformation logic
3. Import in FeedbackVisualization
4. Add to layout grid

### Adding a New Notification Trigger
1. Add trigger option to `triggerOptions` array
2. Update backend to handle trigger
3. Add trigger checkbox in form
4. Test notification sending

## Deployment

### Production Build
```bash
npm run build
```

### Environment Variables
```
VITE_API_BASE_URL=https://api.example.com/api/v1
VITE_APP_NAME=X-Agent Feedback
```

### Docker
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

## Troubleshooting

### Build Errors
- Clear `node_modules` and reinstall: `rm -rf node_modules && npm install`
- Clear Vite cache: `rm -rf .vite`

### Type Errors
- Run `npm run type-check` to identify issues
- Ensure all imports are correct
- Check TypeScript version compatibility

### Test Failures
- Update snapshots: `npm test -- -u`
- Clear test cache: `npm test -- --clearCache`
- Check mock data matches current types

## Contributing

1. Create a feature branch
2. Make changes with tests
3. Run linting and type checking
4. Submit pull request
5. Ensure CI/CD passes

## Resources

- [React Documentation](https://react.dev)
- [TypeScript Handbook](https://www.typescriptlang.org/docs)
- [Recharts Documentation](https://recharts.org)
- [TailwindCSS Documentation](https://tailwindcss.com/docs)
- [Vitest Documentation](https://vitest.dev)
