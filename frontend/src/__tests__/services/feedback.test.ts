import { describe, it, expect, beforeEach, vi } from 'vitest'
import axios from 'axios'
import { feedbackService, Feedback, FeedbackStats } from '@/services/feedback'

vi.mock('axios')

describe('FeedbackService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  describe('listFeedback', () => {
    it('should fetch feedbacks with pagination', async () => {
      const mockData = {
        items: [
          {
            id: '1',
            userId: 'user-1',
            type: 'bug',
            category: 'UI',
            title: 'Test feedback',
            description: 'Test description',
            sentiment: 'negative',
            priority: 'high',
            status: 'open',
            tags: [],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
          },
        ],
        total: 1,
        page: 1,
        pageSize: 20,
        hasMore: false,
      }

      vi.mocked(axios.create).mockReturnValue({
        get: vi.fn().mockResolvedValue({ data: mockData }),
      } as any)

      const result = await feedbackService.listFeedback(1, 20)
      expect(result.items).toHaveLength(1)
      expect(result.total).toBe(1)
    })

    it('should apply filters', async () => {
      const mockData = {
        items: [],
        total: 0,
        page: 1,
        pageSize: 20,
        hasMore: false,
      }

      vi.mocked(axios.create).mockReturnValue({
        get: vi.fn().mockResolvedValue({ data: mockData }),
      } as any)

      await feedbackService.listFeedback(1, 20, {
        type: 'bug',
        status: 'open',
        priority: 'high',
      })

      expect(axios.create).toHaveBeenCalled()
    })
  })

  describe('getFeedback', () => {
    it('should fetch single feedback', async () => {
      const mockFeedback: Feedback = {
        id: '1',
        userId: 'user-1',
        type: 'bug',
        category: 'UI',
        title: 'Test feedback',
        description: 'Test description',
        sentiment: 'negative',
        priority: 'high',
        status: 'open',
        tags: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      }

      vi.mocked(axios.create).mockReturnValue({
        get: vi.fn().mockResolvedValue({ data: mockFeedback }),
      } as any)

      const result = await feedbackService.getFeedback('1')
      expect(result.id).toBe('1')
      expect(result.title).toBe('Test feedback')
    })
  })

  describe('createFeedback', () => {
    it('should create new feedback', async () => {
      const newFeedback: Feedback = {
        id: '2',
        userId: 'user-1',
        type: 'feature',
        category: 'API',
        title: 'New feature request',
        description: 'Add export functionality',
        sentiment: 'positive',
        priority: 'medium',
        status: 'open',
        tags: ['enhancement'],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      }

      vi.mocked(axios.create).mockReturnValue({
        post: vi.fn().mockResolvedValue({ data: newFeedback }),
      } as any)

      const result = await feedbackService.createFeedback({
        type: 'feature',
        title: 'New feature request',
      })

      expect(result.id).toBe('2')
      expect(result.type).toBe('feature')
    })
  })

  describe('updateFeedback', () => {
    it('should update feedback', async () => {
      const updatedFeedback: Feedback = {
        id: '1',
        userId: 'user-1',
        type: 'bug',
        category: 'UI',
        title: 'Test feedback',
        description: 'Test description',
        sentiment: 'negative',
        priority: 'high',
        status: 'in_progress',
        tags: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      }

      vi.mocked(axios.create).mockReturnValue({
        put: vi.fn().mockResolvedValue({ data: updatedFeedback }),
      } as any)

      const result = await feedbackService.updateFeedback('1', {
        status: 'in_progress',
      })

      expect(result.status).toBe('in_progress')
    })
  })

  describe('deleteFeedback', () => {
    it('should delete feedback', async () => {
      vi.mocked(axios.create).mockReturnValue({
        delete: vi.fn().mockResolvedValue({}),
      } as any)

      await expect(feedbackService.deleteFeedback('1')).resolves.toBeUndefined()
    })
  })

  describe('resolveFeedback', () => {
    it('should resolve feedback with response', async () => {
      const resolvedFeedback: Feedback = {
        id: '1',
        userId: 'user-1',
        type: 'bug',
        category: 'UI',
        title: 'Test feedback',
        description: 'Test description',
        sentiment: 'negative',
        priority: 'high',
        status: 'resolved',
        tags: [],
        response: 'We fixed this issue',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        resolvedAt: new Date().toISOString(),
      }

      vi.mocked(axios.create).mockReturnValue({
        post: vi.fn().mockResolvedValue({ data: resolvedFeedback }),
      } as any)

      const result = await feedbackService.resolveFeedback('1', 'We fixed this issue')
      expect(result.status).toBe('resolved')
      expect(result.response).toBe('We fixed this issue')
    })
  })

  describe('getStats', () => {
    it('should fetch feedback statistics', async () => {
      const mockStats: FeedbackStats = {
        total: 100,
        byType: { bug: 40, feature: 30, improvement: 20, other: 10 },
        byStatus: { open: 30, in_progress: 20, resolved: 40, closed: 10 },
        bySentiment: { positive: 30, neutral: 40, negative: 30 },
        byPriority: { critical: 10, high: 20, medium: 40, low: 30 },
        avgResolutionTime: 5,
        resolutionRate: 0.8,
      }

      vi.mocked(axios.create).mockReturnValue({
        get: vi.fn().mockResolvedValue({ data: mockStats }),
      } as any)

      const result = await feedbackService.getStats()
      expect(result.total).toBe(100)
      expect(result.resolutionRate).toBe(0.8)
    })
  })

  describe('getTrends', () => {
    it('should fetch feedback trends', async () => {
      const mockTrends = [
        {
          date: new Date().toISOString(),
          count: 10,
          byType: { bug: 5, feature: 3, improvement: 2, other: 0 },
          bySentiment: { positive: 3, neutral: 4, negative: 3 },
        },
      ]

      vi.mocked(axios.create).mockReturnValue({
        get: vi.fn().mockResolvedValue({ data: mockTrends }),
      } as any)

      const result = await feedbackService.getTrends(30, 'day')
      expect(result).toHaveLength(1)
      expect(result[0].count).toBe(10)
    })
  })

  describe('Notifications', () => {
    it('should list notifications', async () => {
      const mockNotifications = [
        {
          id: '1',
          type: 'email',
          enabled: true,
          target: 'admin@example.com',
          triggers: ['new_feedback'],
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      ]

      vi.mocked(axios.create).mockReturnValue({
        get: vi.fn().mockResolvedValue({ data: mockNotifications }),
      } as any)

      const result = await feedbackService.listNotifications()
      expect(result).toHaveLength(1)
      expect(result[0].type).toBe('email')
    })

    it('should create notification', async () => {
      const newNotification = {
        id: '2',
        type: 'slack',
        enabled: true,
        target: 'https://hooks.slack.com/...',
        triggers: ['critical_feedback'],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      }

      vi.mocked(axios.create).mockReturnValue({
        post: vi.fn().mockResolvedValue({ data: newNotification }),
      } as any)

      const result = await feedbackService.createNotification({
        type: 'slack',
        target: 'https://hooks.slack.com/...',
      })

      expect(result.type).toBe('slack')
    })

    it('should test notification', async () => {
      const mockResult = { success: true, message: 'Test sent successfully' }

      vi.mocked(axios.create).mockReturnValue({
        post: vi.fn().mockResolvedValue({ data: mockResult }),
      } as any)

      const result = await feedbackService.testNotification('1')
      expect(result.success).toBe(true)
    })
  })

  describe('Export', () => {
    it('should export feedback as CSV', async () => {
      const mockBlob = new Blob(['csv data'], { type: 'text/csv' })

      vi.mocked(axios.create).mockReturnValue({
        get: vi.fn().mockResolvedValue({ data: mockBlob }),
      } as any)

      const result = await feedbackService.exportFeedback('csv')
      expect(result).toBeInstanceOf(Blob)
    })

    it('should export feedback as PDF', async () => {
      const mockBlob = new Blob(['pdf data'], { type: 'application/pdf' })

      vi.mocked(axios.create).mockReturnValue({
        get: vi.fn().mockResolvedValue({ data: mockBlob }),
      } as any)

      const result = await feedbackService.exportFeedback('pdf')
      expect(result).toBeInstanceOf(Blob)
    })
  })

  describe('Search', () => {
    it('should search feedbacks', async () => {
      const mockResults = [
        {
          id: '1',
          userId: 'user-1',
          type: 'bug',
          category: 'UI',
          title: 'Login issue',
          description: 'Cannot login',
          sentiment: 'negative',
          priority: 'high',
          status: 'open',
          tags: [],
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      ]

      vi.mocked(axios.create).mockReturnValue({
        get: vi.fn().mockResolvedValue({ data: mockResults }),
      } as any)

      const result = await feedbackService.searchFeedback('login')
      expect(result).toHaveLength(1)
      expect(result[0].title).toContain('Login')
    })
  })
})
