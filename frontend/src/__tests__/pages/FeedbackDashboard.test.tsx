import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  listFeedback: vi.fn(),
  getStats: vi.fn(),
  getTrends: vi.fn(),
  createFeedback: vi.fn(),
  listNotifications: vi.fn(),
  setLoading: vi.fn(),
  setError: vi.fn(),
}))

vi.mock('@/services/feedback', () => ({
  feedbackService: {
    listFeedback: mocks.listFeedback,
    getStats: mocks.getStats,
    getTrends: mocks.getTrends,
    createFeedback: mocks.createFeedback,
    listNotifications: mocks.listNotifications,
  },
}))

vi.mock('@/store/appStore', () => ({
  useAppStore: () => ({
    theme: 'light',
    isLoading: false,
    setLoading: mocks.setLoading,
    setError: mocks.setError,
  }),
}))

import { FeedbackDashboard } from '@/pages/FeedbackDashboard'

const feedback = {
  id: 'feedback-1',
  userId: 'user-1',
  type: 'bug',
  category: 'product',
  title: 'Broken login',
  description: 'Cannot sign in',
  sentiment: 'negative',
  priority: 'high',
  status: 'open',
  tags: [],
  createdAt: '2026-08-16T00:00:00Z',
  updatedAt: '2026-08-16T00:00:00Z',
}

describe('FeedbackDashboard commercial surface', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listFeedback.mockResolvedValue({
      items: [feedback],
      total: 1,
      page: 1,
      pageSize: 50,
      hasMore: false,
    })
    mocks.getStats.mockResolvedValue({
      total: 1,
      byType: { bug: 1 },
      byStatus: { open: 1 },
      bySentiment: { negative: 1 },
      byPriority: { high: 1 },
      avgResolutionTime: 0,
      resolutionRate: 0,
    })
    mocks.getTrends.mockResolvedValue([])
    mocks.listNotifications.mockRejectedValue(new Error('unsupported'))
    mocks.createFeedback.mockResolvedValue({ ...feedback, id: 'feedback-2', title: 'New issue' })
  })

  it('loads the real feedback surface without calling unsupported notifications', async () => {
    render(<FeedbackDashboard />)

    expect(await screen.findByText('Broken login')).toBeInTheDocument()
    expect(mocks.listNotifications).not.toHaveBeenCalled()
    expect(mocks.setError).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: /notifications/i })).not.toBeInTheDocument()
  })

  it('submits new feedback and projects the persisted response', async () => {
    render(<FeedbackDashboard />)
    await screen.findByText('Broken login')

    await userEvent.click(screen.getByRole('button', { name: 'New feedback' }))
    await userEvent.type(screen.getByLabelText('Title'), 'New issue')
    await userEvent.type(screen.getByLabelText('Description'), 'The workflow is unavailable')
    fireEvent.submit(screen.getByRole('form', { name: 'Create feedback' }))

    await waitFor(() => expect(mocks.createFeedback).toHaveBeenCalledWith({
      type: 'bug',
      title: 'New issue',
      description: 'The workflow is unavailable',
      priority: 'medium',
    }))
    expect(await screen.findByText('New issue')).toBeInTheDocument()
  })
})
