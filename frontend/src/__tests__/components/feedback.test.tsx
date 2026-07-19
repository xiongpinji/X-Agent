import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FeedbackList } from '@/components/feedback/FeedbackList'
import { FeedbackDetail } from '@/components/feedback/FeedbackDetail'
import { FeedbackVisualization } from '@/components/feedback/FeedbackVisualization'
import { NotificationSettings } from '@/components/feedback/NotificationSettings'
import { Feedback, FeedbackStats, FeedbackTrend, NotificationConfig } from '@/services/feedback'

// Mock data
const mockFeedback: Feedback = {
  id: '1',
  userId: 'user-1',
  type: 'bug',
  category: 'UI',
  title: 'Login button not working',
  description: 'The login button on the homepage is not responding to clicks',
  sentiment: 'negative',
  priority: 'high',
  status: 'open',
  tags: ['urgent', 'frontend'],
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
}

const mockStats: FeedbackStats = {
  total: 100,
  byType: { bug: 40, feature: 30, improvement: 20, other: 10 },
  byStatus: { open: 30, in_progress: 20, resolved: 40, closed: 10 },
  bySentiment: { positive: 30, neutral: 40, negative: 30 },
  byPriority: { critical: 10, high: 20, medium: 40, low: 30 },
  avgResolutionTime: 5,
  resolutionRate: 0.8,
}

const mockTrends: FeedbackTrend[] = [
  {
    date: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    count: 10,
    byType: { bug: 5, feature: 3, improvement: 2, other: 0 },
    bySentiment: { positive: 3, neutral: 4, negative: 3 },
  },
  {
    date: new Date().toISOString(),
    count: 15,
    byType: { bug: 7, feature: 5, improvement: 2, other: 1 },
    bySentiment: { positive: 5, neutral: 6, negative: 4 },
  },
]

const mockNotification: NotificationConfig = {
  id: '1',
  type: 'email',
  enabled: true,
  target: 'admin@example.com',
  triggers: ['new_feedback', 'critical_feedback'],
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
}

describe('FeedbackList Component', () => {
  const mockProps = {
    feedbacks: [mockFeedback],
    isLoading: false,
    onSelectFeedback: vi.fn(),
    onDeleteFeedback: vi.fn(),
    onStatusChange: vi.fn(),
    theme: 'light' as const,
  }

  it('renders feedback list', () => {
    render(<FeedbackList {...mockProps} />)
    expect(screen.getByText('Login button not working')).toBeInTheDocument()
  })

  it('filters feedbacks by search query', async () => {
    render(<FeedbackList {...mockProps} />)
    const searchInput = screen.getByPlaceholderText('Search feedbacks...')

    await userEvent.type(searchInput, 'login')
    expect(screen.getByText('Login button not working')).toBeInTheDocument()
  })

  it('filters feedbacks by type', async () => {
    render(<FeedbackList {...mockProps} />)
    const typeSelect = screen.getByDisplayValue('All Types')

    await userEvent.selectOptions(typeSelect, 'bug')
    expect(screen.getByText('Login button not working')).toBeInTheDocument()
  })

  it('calls onSelectFeedback when clicking on feedback', async () => {
    render(<FeedbackList {...mockProps} />)
    const feedbackItem = screen.getByText('Login button not working').closest('div')

    if (feedbackItem) {
      fireEvent.click(feedbackItem)
    }

    expect(mockProps.onSelectFeedback).toHaveBeenCalledWith(mockFeedback)
  })

  it('calls onDeleteFeedback when clicking delete button', async () => {
    window.confirm = vi.fn(() => true)
    render(<FeedbackList {...mockProps} />)

    const deleteButton = screen.getByTitle('Delete feedback')
    fireEvent.click(deleteButton)

    expect(mockProps.onDeleteFeedback).toHaveBeenCalledWith('1')
  })

  it('shows empty state when no feedbacks', () => {
    render(<FeedbackList {...mockProps} feedbacks={[]} />)
    expect(screen.getByText('No feedbacks found')).toBeInTheDocument()
  })

  it('shows loading state', () => {
    render(<FeedbackList {...mockProps} isLoading={true} />)
    expect(screen.getByText('Loading feedbacks...')).toBeInTheDocument()
  })
})

describe('FeedbackDetail Component', () => {
  const mockProps = {
    feedback: mockFeedback,
    onClose: vi.fn(),
    onUpdate: vi.fn(),
    onResolve: vi.fn(),
    theme: 'light' as const,
  }

  it('renders feedback details', () => {
    render(<FeedbackDetail {...mockProps} />)
    expect(screen.getByText('Login button not working')).toBeInTheDocument()
    expect(screen.getByText('The login button on the homepage is not responding to clicks')).toBeInTheDocument()
  })

  it('displays status and priority badges', () => {
    render(<FeedbackDetail {...mockProps} />)
    expect(screen.getByText('open')).toBeInTheDocument()
    expect(screen.getByText('high')).toBeInTheDocument()
  })

  it('allows editing status and priority', async () => {
    render(<FeedbackDetail {...mockProps} />)

    const editButton = screen.getByText('Edit')
    fireEvent.click(editButton)

    const statusSelect = screen.getByDisplayValue('open')
    await userEvent.selectOptions(statusSelect, 'in_progress')

    const saveButton = screen.getByText('Save')
    fireEvent.click(saveButton)

    expect(mockProps.onUpdate).toHaveBeenCalled()
  })

  it('allows adding response', async () => {
    render(<FeedbackDetail {...mockProps} />)

    const textarea = screen.getByPlaceholderText('Type your response here...')
    await userEvent.type(textarea, 'We are working on this issue')

    const sendButton = screen.getByText('Send Response')
    fireEvent.click(sendButton)

    expect(mockProps.onResolve).toHaveBeenCalledWith('1', 'We are working on this issue')
  })

  it('closes modal when clicking close button', () => {
    render(<FeedbackDetail {...mockProps} />)

    const closeButton = screen.getByRole('button', { name: '' }).parentElement?.querySelector('button')
    if (closeButton) {
      fireEvent.click(closeButton)
    }

    expect(mockProps.onClose).toHaveBeenCalled()
  })
})

describe('FeedbackVisualization Component', () => {
  const mockProps = {
    stats: mockStats,
    trends: mockTrends,
    isLoading: false,
    theme: 'light' as const,
  }

  it('renders visualization charts', () => {
    render(<FeedbackVisualization {...mockProps} />)
    expect(screen.getByText('Feedback Trends')).toBeInTheDocument()
    expect(screen.getByText('By Type')).toBeInTheDocument()
    expect(screen.getByText('By Status')).toBeInTheDocument()
  })

  it('displays key metrics', () => {
    render(<FeedbackVisualization {...mockProps} />)
    expect(screen.getByText('Total Feedbacks')).toBeInTheDocument()
    expect(screen.getByText('Resolution Rate')).toBeInTheDocument()
    expect(screen.getByText('Avg Resolution Time')).toBeInTheDocument()
  })

  it('shows loading state', () => {
    render(<FeedbackVisualization {...mockProps} isLoading={true} />)
    expect(screen.getByText('Loading visualizations...')).toBeInTheDocument()
  })

  it('shows no data message when stats is null', () => {
    render(<FeedbackVisualization {...mockProps} stats={null} />)
    expect(screen.getByText('No data available')).toBeInTheDocument()
  })
})

describe('NotificationSettings Component', () => {
  const mockProps = {
    notifications: [mockNotification],
    onAdd: vi.fn(),
    onUpdate: vi.fn(),
    onDelete: vi.fn(),
    onTest: vi.fn(),
    theme: 'light' as const,
  }

  it('renders notification channels', () => {
    render(<NotificationSettings {...mockProps} />)
    expect(screen.getByText('admin@example.com')).toBeInTheDocument()
  })

  it('shows add channel form when clicking add button', async () => {
    render(<NotificationSettings {...mockProps} />)

    const addButton = screen.getByText('Add Channel')
    fireEvent.click(addButton)

    expect(screen.getByText('Channel Type')).toBeInTheDocument()
  })

  it('allows adding new notification', async () => {
    render(<NotificationSettings {...mockProps} />)

    const addButton = screen.getByText('Add Channel')
    fireEvent.click(addButton)

    const emailInput = screen.getByPlaceholderText('user@example.com')
    await userEvent.type(emailInput, 'newuser@example.com')

    const checkbox = screen.getByRole('checkbox', { name: /new_feedback/i })
    fireEvent.click(checkbox)

    const submitButton = screen.getByText('Add Channel')
    fireEvent.click(submitButton)

    expect(mockProps.onAdd).toHaveBeenCalled()
  })

  it('allows testing notification', async () => {
    render(<NotificationSettings {...mockProps} />)

    const testButton = screen.getByText('Test')
    fireEvent.click(testButton)

    expect(mockProps.onTest).toHaveBeenCalledWith('1')
  })

  it('allows deleting notification', async () => {
    window.confirm = vi.fn(() => true)
    render(<NotificationSettings {...mockProps} />)

    const deleteButtons = screen.getAllByRole('button')
    const deleteButton = deleteButtons.find(btn => btn.querySelector('svg'))

    if (deleteButton) {
      fireEvent.click(deleteButton)
    }

    expect(mockProps.onDelete).toHaveBeenCalled()
  })

  it('shows empty state when no notifications', () => {
    render(<NotificationSettings {...mockProps} notifications={[]} />)
    expect(screen.getByText('No notification channels configured')).toBeInTheDocument()
  })
})
