import axios, { AxiosInstance } from 'axios'
import { clearStoredAuthSession, getAuthHeaders, redirectToLogin } from './authHeaders'

export interface Feedback {
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

export interface FeedbackStats {
  total: number
  byType: Record<string, number>
  byStatus: Record<string, number>
  bySentiment: Record<string, number>
  byPriority: Record<string, number>
  avgResolutionTime: number
  resolutionRate: number
}

export interface FeedbackTrend {
  date: string
  count: number
  byType: Record<string, number>
  bySentiment: Record<string, number>
}

export interface NotificationConfig {
  id: string
  type: 'email' | 'slack'
  enabled: boolean
  target: string
  triggers: string[]
  createdAt: string
  updatedAt: string
}

export interface PaginatedFeedback {
  items: Feedback[]
  total: number
  page: number
  pageSize: number
  hasMore: boolean
}

class FeedbackService {
  private client: AxiosInstance
  private baseURL: string

  constructor(baseURL: string = '/api/v1') {
    this.baseURL = baseURL
    this.client = axios.create({
      baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    this.setupInterceptors()
  }

  private setupInterceptors() {
    this.client.interceptors.request.use(
      (config) => {
        const authHeaders = getAuthHeaders()
        if (authHeaders.Authorization) {
          config.headers.Authorization = authHeaders.Authorization
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          clearStoredAuthSession()
          redirectToLogin()
        }
        return Promise.reject(error)
      }
    )
  }

  // Feedback CRUD operations
  async listFeedback(
    page: number = 1,
    pageSize: number = 20,
    filters?: {
      type?: string
      status?: string
      sentiment?: string
      priority?: string
      search?: string
    }
  ): Promise<PaginatedFeedback> {
    const response = await this.client.get<PaginatedFeedback>('/feedback', {
      params: { page, pageSize, ...filters },
    })
    return response.data
  }

  async getFeedback(id: string): Promise<Feedback> {
    const response = await this.client.get<Feedback>(`/feedback/${id}`)
    return response.data
  }

  async createFeedback(data: Partial<Feedback>): Promise<Feedback> {
    const response = await this.client.post<Feedback>('/feedback', data)
    return response.data
  }

  async updateFeedback(id: string, data: Partial<Feedback>): Promise<Feedback> {
    const response = await this.client.put<Feedback>(`/feedback/${id}`, data)
    return response.data
  }

  async deleteFeedback(id: string): Promise<void> {
    await this.client.delete(`/feedback/${id}`)
  }

  async resolveFeedback(id: string, response: string): Promise<Feedback> {
    const result = await this.client.post<Feedback>(`/feedback/${id}/resolve`, {
      response,
    })
    return result.data
  }

  // Statistics and analytics
  async getStats(dateRange?: { startDate: string; endDate: string }): Promise<FeedbackStats> {
    const response = await this.client.get<FeedbackStats>('/feedback/stats', {
      params: dateRange,
    })
    return response.data
  }

  async getTrends(
    days: number = 30,
    groupBy: 'day' | 'week' | 'month' = 'day'
  ): Promise<FeedbackTrend[]> {
    const response = await this.client.get<FeedbackTrend[]>('/feedback/trends', {
      params: { days, groupBy },
    })
    return response.data
  }

  async getSentimentAnalysis(
    dateRange?: { startDate: string; endDate: string }
  ): Promise<Record<string, number>> {
    const response = await this.client.get<Record<string, number>>(
      '/feedback/sentiment-analysis',
      { params: dateRange }
    )
    return response.data
  }

  async getCategoryDistribution(): Promise<Record<string, number>> {
    const response = await this.client.get<Record<string, number>>(
      '/feedback/category-distribution'
    )
    return response.data
  }

  // Notifications
  async listNotifications(): Promise<NotificationConfig[]> {
    const response = await this.client.get<NotificationConfig[]>('/feedback/notifications')
    return response.data
  }

  async createNotification(data: Partial<NotificationConfig>): Promise<NotificationConfig> {
    const response = await this.client.post<NotificationConfig>(
      '/feedback/notifications',
      data
    )
    return response.data
  }

  async updateNotification(
    id: string,
    data: Partial<NotificationConfig>
  ): Promise<NotificationConfig> {
    const response = await this.client.put<NotificationConfig>(
      `/feedback/notifications/${id}`,
      data
    )
    return response.data
  }

  async deleteNotification(id: string): Promise<void> {
    await this.client.delete(`/feedback/notifications/${id}`)
  }

  async testNotification(id: string): Promise<{ success: boolean; message: string }> {
    const response = await this.client.post<{ success: boolean; message: string }>(
      `/feedback/notifications/${id}/test`
    )
    return response.data
  }

  // Export
  async exportFeedback(
    format: 'csv' | 'pdf',
    filters?: Record<string, any>
  ): Promise<Blob> {
    const response = await this.client.get(`/feedback/export`, {
      params: { format, ...filters },
      responseType: 'blob',
    })
    return response.data
  }

  // Search
  async searchFeedback(query: string): Promise<Feedback[]> {
    const response = await this.client.get<Feedback[]>('/feedback/search', {
      params: { q: query },
    })
    return response.data
  }
}

export const feedbackService = new FeedbackService()
export default feedbackService
