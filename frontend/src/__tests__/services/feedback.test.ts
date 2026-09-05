/**
 * FeedbackService tests
 *
 * The service creates its axios instance at module load time, so axios is
 * mocked with a hoisted factory whose per-verb mocks stay controllable from
 * each test. Assertions follow the CURRENT backend contract:
 * - CRUD via GET/POST/PATCH /feedback (no PUT, no DELETE endpoint)
 * - trends / notifications / export / search fail fast with unsupported()
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { feedbackService } from '@/services/feedback'

const http = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  interceptors: {
    request: { use: vi.fn() },
    response: { use: vi.fn() },
  },
}))

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => http),
  },
}))

/** Backend FeedbackResponse payload (snake_case). */
const rawFeedback = {
  id: '1',
  user_id: 'user-1',
  feedback_type: 'bug',
  category: 'UI',
  title: 'Test feedback',
  description: 'Test description',
  sentiment: 'negative',
  severity: 'high',
  status: 'new',
  tags: ['frontend'],
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-01T00:00:00Z',
}

describe('FeedbackService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  describe('listFeedback', () => {
    it('fetches feedbacks with pagination and adapts snake_case fields', async () => {
      http.get.mockResolvedValue({
        data: { items: [rawFeedback], total: 1 },
      })

      const result = await feedbackService.listFeedback(1, 20)

      expect(http.get).toHaveBeenCalledWith('/feedback/', {
        params: { skip: 0, limit: 20, feedback_type: undefined, status: undefined, severity: undefined },
      })
      expect(result.items).toHaveLength(1)
      expect(result.total).toBe(1)
      // adapter: feedback_type -> type, severity -> priority, status new -> open
      expect(result.items[0].type).toBe('bug')
      expect(result.items[0].priority).toBe('high')
      expect(result.items[0].status).toBe('open')
      expect(result.items[0].userId).toBe('user-1')
    })

    it('applies type/status/priority filters as query params', async () => {
      http.get.mockResolvedValue({ data: { items: [], total: 0 } })

      await feedbackService.listFeedback(1, 20, {
        type: 'bug',
        status: 'open',
        priority: 'high',
      })

      expect(http.get).toHaveBeenCalledWith('/feedback/', {
        params: { skip: 0, limit: 20, feedback_type: 'bug', status: 'open', severity: 'high' },
      })
    })

    it('computes hasMore from the page window', async () => {
      http.get.mockResolvedValue({ data: { items: [rawFeedback], total: 30 } })

      const result = await feedbackService.listFeedback(1, 20)
      expect(result.hasMore).toBe(true)
    })
  })

  describe('getFeedback', () => {
    it('fetches a single adapted feedback', async () => {
      http.get.mockResolvedValue({ data: rawFeedback })

      const result = await feedbackService.getFeedback('1')

      expect(http.get).toHaveBeenCalledWith('/feedback/1')
      expect(result.id).toBe('1')
      expect(result.title).toBe('Test feedback')
      expect(result.status).toBe('open')
    })
  })

  describe('createFeedback', () => {
    it('posts the backend payload shape (feedback_type/severity)', async () => {
      http.post.mockResolvedValue({ data: rawFeedback })

      const result = await feedbackService.createFeedback({
        type: 'bug',
        title: 'Test feedback',
      })

      expect(http.post).toHaveBeenCalledWith('/feedback/', {
        feedback_type: 'bug',
        title: 'Test feedback',
        description: '',
        severity: 'medium',
        metadata: undefined,
      })
      expect(result.id).toBe('1')
      expect(result.type).toBe('bug')
    })
  })

  describe('updateFeedback', () => {
    it('status updates go through PATCH with status param (open maps to new)', async () => {
      http.patch.mockResolvedValue({
        data: { ...rawFeedback, status: 'in_progress' },
      })

      const result = await feedbackService.updateFeedback('1', { status: 'in_progress' })

      expect(http.patch).toHaveBeenCalledWith('/feedback/1', null, {
        params: { status: 'in_progress' },
      })
      expect(result.status).toBe('in_progress')
    })
  })

  describe('resolveFeedback', () => {
    it('resolves via PATCH with status=resolved and response', async () => {
      http.patch.mockResolvedValue({
        data: { ...rawFeedback, status: 'resolved', response: 'We fixed this issue' },
      })

      const result = await feedbackService.resolveFeedback('1', 'We fixed this issue')

      expect(http.patch).toHaveBeenCalledWith('/feedback/1', null, {
        params: { status: 'resolved', response: 'We fixed this issue' },
      })
      expect(result.status).toBe('resolved')
      expect(result.response).toBe('We fixed this issue')
    })
  })

  describe('getStats', () => {
    it('adapts backend stats and derives the resolution rate', async () => {
      http.get.mockResolvedValue({
        data: {
          total: 100,
          by_type: { bug: 40, feature: 30 },
          by_status: { new: 30, in_progress: 20, resolved: 40, closed: 10 },
          by_sentiment: { positive: 30, neutral: 40, negative: 30 },
          by_severity: { critical: 10, high: 20 },
        },
      })

      const result = await feedbackService.getStats()

      expect(http.get).toHaveBeenCalledWith('/feedback/stats/summary')
      expect(result.total).toBe(100)
      // resolved (40) + closed (10) over total (100)
      expect(result.resolutionRate).toBe(0.5)
      expect(result.byPriority).toEqual({ critical: 10, high: 20 })
    })
  })

  describe('endpoints without backend support', () => {
    it.each([
      ['deleteFeedback', () => feedbackService.deleteFeedback('1'), 'deletion'],
      ['getTrends', () => feedbackService.getTrends(30), 'trends'],
      ['listNotifications', () => feedbackService.listNotifications(), 'notifications'],
      ['createNotification', () => feedbackService.createNotification({ type: 'slack' }), 'notifications'],
      ['testNotification', () => feedbackService.testNotification('1'), 'notifications'],
      ['exportFeedback', () => feedbackService.exportFeedback('csv'), 'export'],
      ['searchFeedback', () => feedbackService.searchFeedback('login'), 'search'],
    ])('%s fails fast instead of hitting a 404', async (_name, act, feature) => {
      await expect(act()).rejects.toThrow(
        `Feedback ${feature} is not supported by the backend (no such endpoint).`
      )
    })
  })
})
