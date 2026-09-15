/**
 * FeedbackService tests
 *
 * The service creates its axios instance at module load time, so axios is
 * mocked with a hoisted factory whose per-verb mocks stay controllable from
 * each test. Assertions follow the CURRENT backend contract:
 * - CRUD via GET/POST/PATCH/DELETE /feedback
 *   (backend/app/api/feedback.py — all 14 routes mounted as of 2026-09-14)
 * - trends / sentiment-analysis / category-distribution / search / export
 *   are backed by real endpoints and are exercised below
 * - notifications go to /notification-configs
 *   (backend/app/api/notification_configs.py — mounted 2026-09-14); no method
 *   fails fast any more
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { feedbackService } from '@/services/feedback'

const http = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
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
    it('POSTs the note to the dedicated resolve endpoint', async () => {
      /*
       * The regression this guards: this used to PATCH /feedback/1 with
       * `params: { status: 'resolved', response }`. PATCH reads only the `status`
       * query param and silently drops everything else, so the note never reached
       * the backend. The test still passed because the mock fabricated a
       * `response` key the real API cannot produce — a mock that invents the very
       * field under test proves nothing.
       */
      http.post.mockResolvedValue({
        data: { ...rawFeedback, status: 'resolved', resolution_note: 'We fixed this issue' },
      })

      const result = await feedbackService.resolveFeedback('1', 'We fixed this issue')

      expect(http.post).toHaveBeenCalledWith('/feedback/1/resolve', {
        resolution_note: 'We fixed this issue',
      })
      expect(result.status).toBe('resolved')
      expect(result.response).toBe('We fixed this issue')
    })

    it('leaves response undefined when the backend sent no note', async () => {
      http.post.mockResolvedValue({ data: { ...rawFeedback, status: 'resolved' } })

      const result = await feedbackService.resolveFeedback('1', '')

      expect(result.response).toBeUndefined()
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

  describe('deleteFeedback', () => {
    it('issues DELETE and resolves with no payload (backend returns 204)', async () => {
      http.delete.mockResolvedValue({ status: 204, data: '' })

      await expect(feedbackService.deleteFeedback('1')).resolves.toBeUndefined()
      expect(http.delete).toHaveBeenCalledWith('/feedback/1')
    })
  })

  describe('getTrends', () => {
    it('maps data_points {date,count,resolved} and forwards the window', async () => {
      http.get.mockResolvedValue({
        data: {
          period_days: 30,
          data_points: [
            { date: '2026-09-13', count: 3, resolved: 1 },
            { date: '2026-09-14', count: 1, resolved: 0 },
          ],
        },
      })

      const result = await feedbackService.getTrends(30)

      expect(http.get).toHaveBeenCalledWith('/feedback/trends', { params: { days: 30 } })
      expect(result).toEqual([
        { date: '2026-09-13', count: 3, resolved: 1 },
        { date: '2026-09-14', count: 1, resolved: 0 },
      ])
    })

    it('degrades to [] when the backend omits data_points', async () => {
      http.get.mockResolvedValue({ data: {} })

      await expect(feedbackService.getTrends()).resolves.toEqual([])
    })
  })

  describe('sentiment & category distributions', () => {
    it('unwraps the distribution map for sentiment-analysis', async () => {
      http.get.mockResolvedValue({
        data: {
          total: 4,
          distribution: { positive: 1, negative: 3 },
          average_sentiment_score: -0.5,
        },
      })

      await expect(feedbackService.getSentimentAnalysis()).resolves.toEqual({
        positive: 1,
        negative: 3,
      })
      expect(http.get).toHaveBeenCalledWith('/feedback/sentiment-analysis')
    })

    it('unwraps the distribution map for category-distribution', async () => {
      http.get.mockResolvedValue({ data: { total: 2, distribution: { general: 2 } } })

      await expect(feedbackService.getCategoryDistribution()).resolves.toEqual({ general: 2 })
      expect(http.get).toHaveBeenCalledWith('/feedback/category-distribution')
    })
  })

  describe('searchFeedback', () => {
    it('queries ?q= and adapts the returned items', async () => {
      http.get.mockResolvedValue({
        data: { total: 1, skip: 0, limit: 100, items: [rawFeedback] },
      })

      const result = await feedbackService.searchFeedback('login')

      expect(http.get).toHaveBeenCalledWith('/feedback/search', { params: { q: 'login' } })
      expect(result).toHaveLength(1)
      expect(result[0].type).toBe('bug')
      expect(result[0].priority).toBe('high')
    })
  })

  describe('exportFeedback', () => {
    it('requests a blob and returns it untouched', async () => {
      const blob = new Blob(['id,title'], { type: 'text/csv' })
      http.get.mockResolvedValue({ data: blob })

      await expect(feedbackService.exportFeedback('csv')).resolves.toBe(blob)
      expect(http.get).toHaveBeenCalledWith('/feedback/export', {
        params: { format: 'csv' },
        responseType: 'blob',
      })
    })

    it('defaults to csv (there is no pdf renderer on the backend)', async () => {
      http.get.mockResolvedValue({ data: new Blob([]) })

      await feedbackService.exportFeedback()

      expect(http.get).toHaveBeenCalledWith('/feedback/export', {
        params: { format: 'csv' },
        responseType: 'blob',
      })
    })
  })

  describe('notification configs (api/notification_configs.py)', () => {
    const rawConfig = {
      id: 'nc-1',
      type: 'slack',
      enabled: true,
      target: 'https://hooks.slack.com/services/T/B/X',
      triggers: ['new_feedback', 'daily_summary'],
      created_at: '2026-09-14T00:00:00Z',
      updated_at: '2026-09-14T00:00:00Z',
    }

    it('lists configs from /notification-configs/ and adapts snake_case', async () => {
      http.get.mockResolvedValue({ data: [rawConfig] })

      const result = await feedbackService.listNotifications()

      expect(http.get).toHaveBeenCalledWith('/notification-configs/')
      expect(result).toEqual([
        {
          id: 'nc-1',
          type: 'slack',
          enabled: true,
          target: 'https://hooks.slack.com/services/T/B/X',
          triggers: ['new_feedback', 'daily_summary'],
          createdAt: '2026-09-14T00:00:00Z',
          updatedAt: '2026-09-14T00:00:00Z',
        },
      ])
    })

    it('degrades to [] when the backend returns a non-array body', async () => {
      // An object body would blow up on .map without the Array.isArray guard.
      http.get.mockResolvedValue({ data: { detail: 'unexpected shape' } })

      await expect(feedbackService.listNotifications()).resolves.toEqual([])
    })

    it('posts the create payload the backend model accepts', async () => {
      http.post.mockResolvedValue({ data: rawConfig })

      await feedbackService.createNotification({
        type: 'slack',
        target: 'https://hooks.slack.com/services/T/B/X',
        triggers: ['new_feedback'],
        enabled: false,
      })

      expect(http.post).toHaveBeenCalledWith('/notification-configs/', {
        type: 'slack',
        target: 'https://hooks.slack.com/services/T/B/X',
        triggers: ['new_feedback'],
        enabled: false,
      })
    })

    it('fills create defaults so the backend never sees a missing field', async () => {
      http.post.mockResolvedValue({ data: rawConfig })

      await feedbackService.createNotification({ target: 'a@example.com' })

      expect(http.post).toHaveBeenCalledWith('/notification-configs/', {
        type: 'email',
        target: 'a@example.com',
        triggers: [],
        enabled: true,
      })
    })

    it('sends only the provided keys on PATCH (partial update)', async () => {
      http.patch.mockResolvedValue({ data: rawConfig })

      await feedbackService.updateNotification('nc-1', { enabled: false })

      // id / createdAt / updatedAt are server-owned and must not be forwarded.
      expect(http.patch).toHaveBeenCalledWith('/notification-configs/nc-1', {
        enabled: false,
      })
    })

    it('issues DELETE and resolves with no payload (backend returns 204)', async () => {
      http.delete.mockResolvedValue({ status: 204, data: '' })

      await expect(feedbackService.deleteNotification('nc-1')).resolves.toBeUndefined()
      expect(http.delete).toHaveBeenCalledWith('/notification-configs/nc-1')
    })

    it('surfaces a failed delivery instead of claiming success', async () => {
      // The backend answers 200 with success:false when nothing was delivered.
      http.post.mockResolvedValue({
        data: { success: false, message: '未配置真实邮件通道，本次未实际投递。' },
      })

      const result = await feedbackService.testNotification('nc-1')

      expect(http.post).toHaveBeenCalledWith('/notification-configs/nc-1/test')
      expect(result.success).toBe(false)
      expect(result.message).toContain('未实际投递')
    })

    it('treats a missing success flag as a failure, not a success', async () => {
      http.post.mockResolvedValue({ data: { message: 'hmm' } })

      await expect(feedbackService.testNotification('nc-1')).resolves.toEqual({
        success: false,
        message: 'hmm',
      })
    })

    it('reports a real delivery as success', async () => {
      http.post.mockResolvedValue({ data: { success: true, message: '已通过 webhook 投递。' } })

      await expect(feedbackService.testNotification('nc-1')).resolves.toEqual({
        success: true,
        message: '已通过 webhook 投递。',
      })
    })
  })
})
