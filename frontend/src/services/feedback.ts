import axios, { AxiosInstance } from 'axios'

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

/**
 * Mirrors the backend `FeedbackTrendPoint` (api/feedback.py) exactly:
 * `{ date, count, resolved }`. The previous shape declared `byType` /
 * `bySentiment`, which the backend cannot supply — nothing ever read them.
 */
export interface FeedbackTrend {
  date: string
  count: number
  resolved: number
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
    // Backend field is `resolution_note`; the UI model calls it `response`.
    response: raw.resolution_note ?? undefined,
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

/**
 * Backend NotificationConfigResponse (snake_case) -> frontend model.
 * Backend reference: api/notification_configs.py (mounted 2026-09-14).
 * The backend deliberately does not return tenant_id, so the frontend model
 * does not carry it either.
 */
function adaptNotificationConfig(raw: any): NotificationConfig {
  return {
    id: String(raw?.id ?? ''),
    type: (raw?.type ?? 'email') as NotificationConfig['type'],
    enabled: Boolean(raw?.enabled),
    target: String(raw?.target ?? ''),
    triggers: Array.isArray(raw?.triggers) ? raw.triggers.map(String) : [],
    createdAt: String(raw?.created_at ?? raw?.createdAt ?? ''),
    updatedAt: String(raw?.updated_at ?? raw?.updatedAt ?? ''),
  }
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
        const token = localStorage.getItem('auth_token')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
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
  // PUT /{id}, DELETE /{id}, POST /{id}/resolve, GET /{id}/analysis,
  // GET /stats/summary, GET /trends, GET /sentiment-analysis,
  // GET /category-distribution, GET /search, GET /export.
  /**
   * Only declare filters that are really forwarded. `sentiment` and `search` used
   * to be declared here but were never mapped to query params, so a caller that
   * passed them silently got an unfiltered list. They are removed rather than
   * forwarded because `GET /feedback` accepts no such parameters at all — the
   * backend serves server-side search via a separate `GET /feedback/search?q=`.
   * (Everything still declared here does get sent; `tsc` proves no caller
   * depended on the two that were dropped.)
   */
  async listFeedback(
    page: number = 1,
    pageSize: number = 20,
    filters?: {
      type?: string
      status?: string
      priority?: string
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

  // The backend only supports status updates via PATCH /{id}?status=...
  async updateFeedback(id: string, data: Partial<Feedback>): Promise<Feedback> {
    const response = await this.client.patch(`/feedback/${id}`, null, {
      params: { status: data.status === 'open' ? 'new' : data.status },
    })
    return adaptFeedback(response.data)
  }

  // DELETE /feedback/{id} → 204 No Content (cascades to analysis records).
  async deleteFeedback(id: string): Promise<void> {
    await this.client.delete(`/feedback/${id}`)
  }

  // POST /feedback/{id}/resolve, body { resolution_note }. That dedicated action
  // endpoint sets status=resolved + resolved_at, and it is the only path that can
  // carry the note: PATCH /{id} reads just the `status` query param and drops
  // everything else, which is why the old `PATCH ?response=...` silently lost it.
  async resolveFeedback(id: string, response: string): Promise<Feedback> {
    const result = await this.client.post(`/feedback/${id}/resolve`, {
      resolution_note: response,
    })
    return adaptFeedback(result.data)
  }

  // Statistics — GET /api/v1/feedback/stats/summary (B6/C4 adapter above).
  async getStats(_dateRange?: { startDate: string; endDate: string }): Promise<FeedbackStats> {
    const response = await this.client.get('/feedback/stats/summary')
    return adaptStats(response.data)
  }

  // Daily aggregates — GET /feedback/trends?days=N →
  // { period_days, data_points: [{ date, count, resolved }] }.
  // The backend aggregates by day only, so the old `groupBy` argument is gone
  // rather than silently ignored.
  async getTrends(days: number = 30): Promise<FeedbackTrend[]> {
    const response = await this.client.get('/feedback/trends', { params: { days } })
    const points: any[] = response.data?.data_points ?? []
    return points.map((p) => ({
      date: String(p?.date ?? ''),
      count: Number(p?.count ?? 0),
      resolved: Number(p?.resolved ?? 0),
    }))
  }

  // GET /feedback/sentiment-analysis → { total, distribution, average_sentiment_score }.
  // The declared return contract is the distribution map; `total` and
  // `average_sentiment_score` have no consumer in the UI today.
  async getSentimentAnalysis(): Promise<Record<string, number>> {
    const response = await this.client.get('/feedback/sentiment-analysis')
    return response.data?.distribution ?? {}
  }

  // GET /feedback/category-distribution → { total, distribution }.
  async getCategoryDistribution(): Promise<Record<string, number>> {
    const response = await this.client.get('/feedback/category-distribution')
    return response.data?.distribution ?? {}
  }

  // Notification channel configs — backend: api/notification_configs.py,
  // prefix /api/v1/notification-configs. Real endpoints:
  // GET /, POST /, GET /{id}, PATCH /{id}, DELETE /{id}, POST /{id}/test.
  async listNotifications(): Promise<NotificationConfig[]> {
    const response = await this.client.get('/notification-configs/')
    const items: any[] = Array.isArray(response.data) ? response.data : []
    return items.map(adaptNotificationConfig)
  }

  async createNotification(data: Partial<NotificationConfig>): Promise<NotificationConfig> {
    const response = await this.client.post('/notification-configs/', {
      type: data.type ?? 'email',
      target: data.target ?? '',
      triggers: data.triggers ?? [],
      enabled: data.enabled ?? true,
    })
    return adaptNotificationConfig(response.data)
  }

  // PATCH is partial by design: only the keys actually provided are sent, so an
  // untouched field is never overwritten. id / createdAt / updatedAt are
  // server-owned and are not forwarded.
  async updateNotification(
    id: string,
    data: Partial<NotificationConfig>
  ): Promise<NotificationConfig> {
    const payload: Record<string, unknown> = {}
    if (data.type !== undefined) payload.type = data.type
    if (data.target !== undefined) payload.target = data.target
    if (data.triggers !== undefined) payload.triggers = data.triggers
    if (data.enabled !== undefined) payload.enabled = data.enabled

    const response = await this.client.patch(`/notification-configs/${id}`, payload)
    return adaptNotificationConfig(response.data)
  }

  // DELETE /notification-configs/{id} -> 204 No Content.
  async deleteNotification(id: string): Promise<void> {
    await this.client.delete(`/notification-configs/${id}`)
  }

  // POST /notification-configs/{id}/test -> { success, message }.
  // The backend answers 200 even when delivery failed (success:false) — the
  // request succeeded, the delivery did not. Callers must read `success`
  // rather than treating a resolve as a successful delivery.
  async testNotification(id: string): Promise<{ success: boolean; message: string }> {
    const response = await this.client.post(`/notification-configs/${id}/test`)
    const payload = response.data ?? {}
    return {
      success: payload.success === true,
      message: String(payload.message ?? ''),
    }
  }

  // GET /feedback/export?format=csv|json — the backend serves CSV or JSON
  // only; there is no PDF renderer, so 'pdf' was never a reachable format.
  async exportFeedback(format: 'csv' | 'json' = 'csv'): Promise<Blob> {
    const response = await this.client.get('/feedback/export', {
      params: { format },
      responseType: 'blob',
    })
    return response.data as Blob
  }

  // GET /feedback/search?q=... → FeedbackListResponse; the backend scans
  // title/description and narrows to the caller's own items for non-admins.
  async searchFeedback(query: string): Promise<Feedback[]> {
    const response = await this.client.get('/feedback/search', { params: { q: query } })
    const items: any[] = response.data?.items ?? []
    return items.map(adaptFeedback)
  }
}

export const feedbackService = new FeedbackService()
export default feedbackService
