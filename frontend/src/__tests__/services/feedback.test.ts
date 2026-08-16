import { beforeEach, describe, expect, it, vi } from 'vitest'

const axiosMock = vi.hoisted(() => {
  const client = {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  }
  return { client, create: vi.fn(() => client) }
})

vi.mock('axios', () => ({
  default: { create: axiosMock.create },
}))

import { feedbackService } from '@/services/feedback'

const backendFeedback = {
  id: 'feedback-1',
  user_id: 'user-1',
  feedback_type: 'bug',
  category: 'UI',
  title: 'Test feedback',
  description: 'Test description',
  sentiment: 'negative',
  severity: 'high',
  status: 'new',
  tags: ['frontend'],
  created_at: '2026-08-16T00:00:00Z',
  updated_at: '2026-08-16T00:00:00Z',
}

describe('FeedbackService backend contract', () => {
  beforeEach(() => {
    axiosMock.client.get.mockReset()
    axiosMock.client.post.mockReset()
    axiosMock.client.patch.mockReset()
    axiosMock.client.put.mockReset()
    axiosMock.client.delete.mockReset()
    localStorage.clear()
  })

  it('creates one authenticated API client', () => {
    expect(axiosMock.create).toHaveBeenCalledWith(expect.objectContaining({
      baseURL: '/api/v1',
      timeout: 30000,
    }))
    expect(axiosMock.client.interceptors.request.use).toHaveBeenCalled()
    expect(axiosMock.client.interceptors.response.use).toHaveBeenCalled()
  })

  it('lists and adapts backend feedback with pagination filters', async () => {
    axiosMock.client.get.mockResolvedValue({
      data: { items: [backendFeedback], total: 21 },
    })

    const result = await feedbackService.listFeedback(2, 20, {
      type: 'bug',
      status: 'open',
      priority: 'high',
    })

    expect(axiosMock.client.get).toHaveBeenCalledWith('/feedback/', {
      params: {
        skip: 20,
        limit: 20,
        feedback_type: 'bug',
        status: 'open',
        severity: 'high',
      },
    })
    expect(result).toMatchObject({
      total: 21,
      page: 2,
      pageSize: 20,
      hasMore: false,
      items: [{
        id: 'feedback-1',
        userId: 'user-1',
        type: 'bug',
        priority: 'high',
        status: 'open',
      }],
    })
  })

  it('gets one feedback through the mounted endpoint', async () => {
    axiosMock.client.get.mockResolvedValue({ data: backendFeedback })
    await expect(feedbackService.getFeedback('feedback-1')).resolves.toMatchObject({
      id: 'feedback-1',
      status: 'open',
    })
    expect(axiosMock.client.get).toHaveBeenCalledWith('/feedback/feedback-1')
  })

  it('creates feedback using the backend request schema', async () => {
    axiosMock.client.post.mockResolvedValue({ data: backendFeedback })
    await feedbackService.createFeedback({
      type: 'bug',
      title: 'Test feedback',
      description: 'Test description',
      priority: 'high',
      tags: ['frontend'],
    })
    expect(axiosMock.client.post).toHaveBeenCalledWith('/feedback/', {
      feedback_type: 'bug',
      title: 'Test feedback',
      description: 'Test description',
      severity: 'high',
      metadata: { tags: ['frontend'] },
    })
  })

  it('updates and resolves feedback through the mounted write endpoints', async () => {
    axiosMock.client.put
      .mockResolvedValueOnce({ data: { ...backendFeedback, status: 'in_progress' } })
    axiosMock.client.post.mockResolvedValueOnce({
      data: { ...backendFeedback, status: 'resolved' },
    })

    await expect(feedbackService.updateFeedback('feedback-1', {
      status: 'in_progress',
    })).resolves.toMatchObject({ status: 'in_progress' })
    await expect(feedbackService.resolveFeedback('feedback-1', 'fixed')).resolves.toMatchObject({
      status: 'resolved',
    })

    expect(axiosMock.client.put).toHaveBeenCalledWith('/feedback/feedback-1', {
      status: 'in_progress',
    })
    expect(axiosMock.client.post).toHaveBeenCalledWith('/feedback/feedback-1/resolve')
  })

  it('adapts backend summary statistics', async () => {
    axiosMock.client.get
      .mockResolvedValueOnce({ data: {
        total: 10,
        by_type: { bug: 4 },
        by_status: { resolved: 3, closed: 2 },
        by_severity: { high: 4 },
      } })
      .mockResolvedValueOnce({ data: { distribution: { negative: 4 } } })
    await expect(feedbackService.getStats()).resolves.toMatchObject({
      total: 10,
      byType: { bug: 4 },
      byPriority: { high: 4 },
      resolutionRate: 0.5,
    })
  })

  it('uses mounted delete, trends, export, and search endpoints', async () => {
    axiosMock.client.delete.mockResolvedValue({ status: 204 })
    axiosMock.client.get
      .mockResolvedValueOnce({
        data: { data_points: [{ date: '2026-08-16', count: 2, resolved: 1 }] },
      })
      .mockResolvedValueOnce({ data: new Blob(['id,title']) })
      .mockResolvedValueOnce({ data: { items: [backendFeedback] } })

    await expect(feedbackService.deleteFeedback('feedback-1')).resolves.toBeUndefined()
    await expect(feedbackService.getTrends()).resolves.toMatchObject([
      { date: '2026-08-16', count: 2 },
    ])
    await expect(feedbackService.exportFeedback('csv')).resolves.toBeInstanceOf(Blob)
    await expect(feedbackService.searchFeedback('login')).resolves.toHaveLength(1)

    expect(axiosMock.client.delete).toHaveBeenCalledWith('/feedback/feedback-1')
    expect(axiosMock.client.get).toHaveBeenNthCalledWith(1, '/feedback/trends', {
      params: { days: 30 },
    })
    expect(axiosMock.client.get).toHaveBeenNthCalledWith(2, '/feedback/export', {
      params: { format: 'csv' },
      responseType: 'blob',
    })
    expect(axiosMock.client.get).toHaveBeenNthCalledWith(3, '/feedback/search', {
      params: { q: 'login' },
    })
  })

  it('keeps notification settings explicitly unavailable', async () => {
    await expect(feedbackService.listNotifications()).rejects.toThrow(
      'Feedback notifications is not supported by the backend',
    )
  })
})
