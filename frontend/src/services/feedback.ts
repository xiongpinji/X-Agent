import axios, { AxiosInstance } from 'axios'
import { applyStoredAuth } from './authHeaders'

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

// ---------------------------------------------------------------------------
// Adapters: backend FeedbackResponse (snake_case) -> frontend Feedback model.
// Backend reference: api/feedback.py (FeedbackResponse/FeedbackListResponse/
// FeedbackStatsResponse). Backend statuses: new|acknowledged|in_progress|
// resolved|closed; severity doubles as the frontend priority field (C4).
// ---------------------------------------------------------------------------

/* eslint-disable @typescript-eslint/no-explicit-any */
function adaptFeedback(raw: any): Feedback {
  const statusMap: Record<string, Feedback['status']> = {
    new: 'open',
    acknowledged: 'open',
    in_progress: 'in_progress',
    resolved: 'resolved',
    closed: 'closed',
  }
  return {
    id: String(raw.id ?? ''),
    userId: String(raw.user_id ?? raw.userId ?? ''),
    type: (raw.feedback_type ?? raw.type ?? 'other') as Feedback['type'],
    category: raw.category ?? '',
    title: String(raw.title ?? ''),
    description: String(raw.description ?? ''),
    sentiment: (raw.sentiment ?? 'neutral') as Feedback['sentiment'],
    priority: (raw.severity ?? raw.priority ?? 'medium') as Feedback['priority'],
    status: statusMap[String(raw.status ?? 'new')] ?? 'open',
    tags: Array.isArray(raw.tags) ? raw.tags : [],
    createdAt: String(raw.created_at ?? raw.createdAt ?? ''),
    updatedAt: String(raw.updated_at ?? raw.updatedAt ?? ''),
    resolvedAt: raw.resolved_at ?? raw.resolvedAt ?? undefined,
  }
}

function adaptStats(raw: any): FeedbackStats {
  const byStatus: Record<string, number> = raw.by_status ?? {}
  const resolved = (byStatus.resolved ?? 0) + (byStatus.closed ?? 0)
  const total = typeof raw.total === 'number' ? raw.total : 0
  return {
    total,
    byType: raw.by_type ?? {},
    byStatus,
    bySentiment: raw.by_sentiment ?? {},
    byPriority: raw.by_severity ?? {},
    // The backend stats endpoint does not provide resolution-time metrics.
    avgResolutionTime: 0,
    resolutionRate: total > 0 ? resolved / total : 0,
  }
}

/** Error thrown for endpoints that have no backend counterpart (B7). */
function unsupported(feature: string): Error {
  return new Error(`Feedback ${feature} is not supported by the backend (no such endpoint).`)
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
      applyStoredAuth,
      (error) => Promise.reject(error)
    )

    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('auth_token')
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }
    )
  }

  // Feedback CRUD operations — backend: api/feedback.py, prefix /api/v1/feedback.
  // Real endpoints: POST /, GET /, GET /{id}, PATCH /{id}?status=...,
  // GET /{id}/analysis, GET /stats/summary.
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
    const response = await this.client.get('/feedback/', {
      params: {
        skip: (page - 1) * pageSize,
        limit: pageSize,
        feedback_type: filters?.type || undefined,
        status: filters?.status || undefined,
        severity: filters?.priority || undefined,
      },
    })
    const payload = response.data
    const rawItems: any[] = payload?.items ?? []
    const total: number = typeof payload?.total === 'number' ? payload.total : rawItems.length
    return {
      items: rawItems.map(adaptFeedback),
      total,
      page,
      pageSize,
      hasMore: page * pageSize < total,
    }
  }

  async getFeedback(id: string): Promise<Feedback> {
    const response = await this.client.get(`/feedback/${id}`)
    return adaptFeedback(response.data)
  }

  async createFeedback(data: Partial<Feedback>): Promise<Feedback> {
    const response = await this.client.post('/feedback/', {
      feedback_type: data.type ?? 'other',
      title: data.title ?? '',
      description: data.description ?? '',
      severity: data.priority ?? 'medium',
      metadata: data.tags?.length ? { tags: data.tags } : undefined,
    })
    return adaptFeedback(response.data)
  }

  async updateFeedback(id: string, data: Partial<Feedback>): Promise<Feedback> {
    const payload: Record<string, unknown> = {}
    if (data.type !== undefined) payload.feedback_type = data.type
    if (data.title !== undefined) payload.title = data.title
    if (data.description !== undefined) payload.description = data.description
    if (data.priority !== undefined) payload.severity = data.priority
    if (data.status !== undefined) payload.status = data.status === 'open' ? 'new' : data.status
    if (data.tags !== undefined) payload.metadata = { tags: data.tags }

    const response = await this.client.put(`/feedback/${id}`, payload)
    return adaptFeedback(response.data)
  }

  async deleteFeedback(id: string): Promise<void> {
    await this.client.delete(`/feedback/${id}`)
  }

  async resolveFeedback(id: string, _response?: string): Promise<Feedback> {
    const result = await this.client.post(`/feedback/${id}/resolve`)
    return adaptFeedback(result.data)
  }

  async getStats(_dateRange?: { startDate: string; endDate: string }): Promise<FeedbackStats> {
    const [statsResponse, sentimentResponse] = await Promise.all([
      this.client.get('/feedback/stats/summary'),
      this.client.get('/feedback/sentiment-analysis'),
    ])
    return {
      ...adaptStats(statsResponse.data),
      bySentiment: sentimentResponse.data?.distribution ?? {},
    }
  }

  async getTrends(
    days: number = 30,
    _groupBy: 'day' | 'week' | 'month' = 'day'
  ): Promise<FeedbackTrend[]> {
    const response = await this.client.get('/feedback/trends', { params: { days } })
    const points: any[] = response.data?.data_points ?? []
    return points.map((point) => ({
      date: String(point.date ?? ''),
      count: Number(point.count ?? 0),
      byType: {},
      bySentiment: {},
    }))
  }

  async getSentimentAnalysis(
    _dateRange?: { startDate: string; endDate: string }
  ): Promise<Record<string, number>> {
    const response = await this.client.get('/feedback/sentiment-analysis')
    return response.data?.distribution ?? {}
  }

  async getCategoryDistribution(): Promise<Record<string, number>> {
    const response = await this.client.get('/feedback/category-distribution')
    return response.data?.distribution ?? {}
  }

  // Notifications — no backend endpoints exist.
  async listNotifications(): Promise<NotificationConfig[]> {
    throw unsupported('notifications')
  }

  async createNotification(_data: Partial<NotificationConfig>): Promise<NotificationConfig> {
    throw unsupported('notifications')
  }

  async updateNotification(
    _id: string,
    _data: Partial<NotificationConfig>
  ): Promise<NotificationConfig> {
    throw unsupported('notifications')
  }

  async deleteNotification(_id: string): Promise<void> {
    throw unsupported('notifications')
  }

  async testNotification(_id: string): Promise<{ success: boolean; message: string }> {
    throw unsupported('notifications')
  }

  async exportFeedback(
    format: 'csv' | 'json',
    _filters?: Record<string, any>
  ): Promise<Blob> {
    const response = await this.client.get('/feedback/export', {
      params: { format },
      responseType: 'blob',
    })
    return response.data
  }

  async searchFeedback(query: string): Promise<Feedback[]> {
    const response = await this.client.get('/feedback/search', { params: { q: query } })
    const items: any[] = response.data?.items ?? []
    return items.map(adaptFeedback)
  }
}

export const feedbackService = new FeedbackService()
export default feedbackService
