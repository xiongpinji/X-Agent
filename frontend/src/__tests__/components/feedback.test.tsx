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
    resolved: 4,
  },
  {
    date: new Date().toISOString(),
    count: 15,
    resolved: 6,
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
    // onUpdate/onResolve resolve the save outcome, so `true` is the success
    // default. A bare `vi.fn()` resolves `undefined`, which under this contract
    // reports every save as failed and would leave the editor open by accident.
    onUpdate: vi.fn(async () => true),
    onResolve: vi.fn(async () => true),
    theme: 'light' as const,
  }

  beforeEach(() => {
    // Without this, `toHaveBeenCalled()` passes on leakage from an earlier test.
    vi.clearAllMocks()
  })

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

    // Edit mode renders labeled selects (option labels are capitalized)
    const statusSelect = screen.getByLabelText('Status')
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

  it('closes the editor after a successful save', async () => {
    render(<FeedbackDetail {...mockProps} />)

    fireEvent.click(screen.getByText('Edit'))
    fireEvent.click(screen.getByText('Save'))

    // The labelled <select> only exists in edit mode; the read-only view renders
    // a <span> instead. Removing `setIsEditing(false)` makes this fail.
    await waitFor(() => {
      expect(screen.queryByLabelText('Status')).not.toBeInTheDocument()
    })
  })

  it('keeps the editor open with the chosen values when the save fails', async () => {
    /*
     * The regression this guards: the page swallows the API error into its own
     * error banner and never re-throws, so `await onUpdate(...)` could not fail
     * and the editor closed regardless — the discarded change looked saved. Only
     * a `false` outcome can make this assertion fail.
     */
    const failing = { ...mockProps, onUpdate: vi.fn(async () => false) }
    render(<FeedbackDetail {...failing} />)

    fireEvent.click(screen.getByText('Edit'))
    await userEvent.selectOptions(screen.getByLabelText('Status'), 'resolved')
    fireEvent.click(screen.getByText('Save'))

    await waitFor(() => {
      expect(failing.onUpdate).toHaveBeenCalled()
    })
    expect(screen.getByLabelText('Status')).toHaveValue('resolved')
  })

  it('clears the response box only after a successful submit', async () => {
    render(<FeedbackDetail {...mockProps} />)

    const textarea = screen.getByPlaceholderText('Type your response here...')
    await userEvent.type(textarea, 'We are working on this issue')
    fireEvent.click(screen.getByText('Send Response'))

    await waitFor(() => {
      expect(textarea).toHaveValue('')
    })
  })

  it('keeps the response text when the submit fails', async () => {
    /*
     * The regression this guards: on a failed resolve the box was cleared
     * anyway, destroying the resolution note the user had just typed on top of
     * the failure. Only a `false` outcome can make this assertion fail.
     */
    const failing = { ...mockProps, onResolve: vi.fn(async () => false) }
    render(<FeedbackDetail {...failing} />)

    const textarea = screen.getByPlaceholderText('Type your response here...')
    await userEvent.type(textarea, 'keep this note')
    fireEvent.click(screen.getByText('Send Response'))

    await waitFor(() => {
      expect(failing.onResolve).toHaveBeenCalled()
    })
    expect(screen.getByPlaceholderText('Type your response here...')).toHaveValue('keep this note')
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
    // onAdd/onUpdate resolve the save outcome, so `true` is the success default.
    // A bare `vi.fn()` resolves `undefined`, which under this contract reports
    // every save as failed and would leave the form open by accident.
    onAdd: vi.fn(async () => true),
    onUpdate: vi.fn(async () => true),
    onDelete: vi.fn(async () => undefined),
    // The delivery outcome is *returned*, not thrown — the backend answers 200
    // with success:false when the channel is configured but nothing could be
    // delivered. See NotificationSettingsProps.onTest.
    onTest: vi.fn(async () => ({ success: true, message: 'Delivered via smtp.' })),
    theme: 'light' as const,
  }

  beforeEach(() => {
    // Without this, `toHaveBeenCalled()` passes on leakage from an earlier test.
    vi.clearAllMocks()
  })

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

  it('closes the form only after a successful save', async () => {
    render(<NotificationSettings {...mockProps} />)

    const addButton = screen.getByText('Add Channel')
    fireEvent.click(addButton)

    const emailInput = screen.getByPlaceholderText('user@example.com')
    await userEvent.type(emailInput, 'newuser@example.com')

    // Trigger labels render underscores as spaces ("new feedback")
    const checkbox = screen.getByRole('checkbox', { name: /new feedback/i })
    fireEvent.click(checkbox)

    // Two "Add Channel" texts exist while the form is open: header toggle + form submit
    const submitButton = screen.getAllByText('Add Channel')[1]
    fireEvent.click(submitButton)

    expect(mockProps.onAdd).toHaveBeenCalled()
    // Closing the form is the observable half of "saved": asserting only
    // `onAdd` was called would pass even if the save had failed.
    await waitFor(() => {
      expect(screen.queryByText('Channel Type')).not.toBeInTheDocument()
    })
  })

  it('keeps the form open with the input intact when the save fails', async () => {
    /*
     * The regression this guards: the page swallows the API error into its own
     * error banner and never re-throws, so `await onAdd(...)` could not fail.
     * The form then closed regardless, discarding what the user typed on top of
     * the failure. Only a `false` outcome can make this assertion fail.
     */
    const failing = { ...mockProps, onAdd: vi.fn(async () => false) }
    render(<NotificationSettings {...failing} />)

    fireEvent.click(screen.getByText('Add Channel'))

    const emailInput = screen.getByPlaceholderText('user@example.com')
    await userEvent.type(emailInput, 'keepme@example.com')
    fireEvent.click(screen.getByRole('checkbox', { name: /new feedback/i }))
    fireEvent.click(screen.getAllByText('Add Channel')[1])

    await waitFor(() => {
      expect(failing.onAdd).toHaveBeenCalled()
    })
    expect(screen.getByText('Channel Type')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('user@example.com')).toHaveValue('keepme@example.com')
  })

  it('allows testing notification', async () => {
    render(<NotificationSettings {...mockProps} />)

    const testButton = screen.getByText('Test')
    fireEvent.click(testButton)

    expect(mockProps.onTest).toHaveBeenCalledWith('1')
  })

  it('shows the message the backend returned for a successful test', async () => {
    render(<NotificationSettings {...mockProps} />)

    fireEvent.click(screen.getByText('Test'))

    expect(await screen.findByText('Delivered via smtp.')).toBeInTheDocument()
  })

  it('reports a failed delivery instead of a false success', async () => {
    /*
     * The regression this guards: the page used to discard testNotification's
     * return value, so a backend `success: false` still rendered "Test
     * notification sent successfully". Only a success:false response can make
     * this assertion fail — a mock that always resolves true would pass even
     * with the bug in place.
     */
    mockProps.onTest.mockResolvedValueOnce({
      success: false,
      message: '未配置真实邮件通道（当前 provider=ConsoleNotificationProvider），本次未实际投递。',
    })

    render(<NotificationSettings {...mockProps} />)
    fireEvent.click(screen.getByText('Test'))

    expect(await screen.findByText(/未配置真实邮件通道/)).toBeInTheDocument()
    expect(screen.queryByText('Test notification sent successfully')).not.toBeInTheDocument()
  })

  it('still reports transport failures caught from onTest', async () => {
    mockProps.onTest.mockRejectedValueOnce(new Error('Request failed with status code 403'))

    render(<NotificationSettings {...mockProps} />)
    fireEvent.click(screen.getByText('Test'))

    expect(await screen.findByText('Request failed with status code 403')).toBeInTheDocument()
  })

  it('allows deleting notification', async () => {
    window.confirm = vi.fn(() => true)
    render(<NotificationSettings {...mockProps} />)

    // The delete button is the one carrying the lucide-trash2 icon
    const deleteButton = screen
      .getAllByRole('button')
      .find((btn) => btn.querySelector('svg.lucide-trash2'))

    expect(deleteButton).toBeDefined()
    if (deleteButton) {
      fireEvent.click(deleteButton)
    }

    expect(mockProps.onDelete).toHaveBeenCalledWith('1')
  })

  it('shows empty state when no notifications', () => {
    render(<NotificationSettings {...mockProps} notifications={[]} />)
    expect(screen.getByText('No notification channels configured')).toBeInTheDocument()
  })
})
