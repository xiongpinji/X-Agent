import axios, { AxiosInstance, AxiosError } from 'axios'

/**
 * API client aligned with the real backend routes (verified against
 * backend FastAPI route table, 332 routes, Wave B).
 *
 * Endpoints that do NOT exist in the backend (e.g. PUT/DELETE /memory/{id},
 * PUT /tools/{id}, POST /tools/{id}/test, GET /chat/history, GET /chat/stream,
 * /ws) were removed on purpose: callers must surface "coming soon" in the UI
 * instead of issuing requests that can only fail.
 */

export interface ApiResponse<T = any> {
  data: T
  status: number
  message?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  hasMore: boolean
}

/** Frontend view model of a task, adapted from backend TaskModel (snake_case). */
export interface Task {
  id: string
  name: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'cancelled'
  /** 0..1 as returned by the backend */
  progress: number
  createdAt: string
  updatedAt: string
  description?: string
  priority?: 'low' | 'medium' | 'high' | 'critical'
  tags?: string[]
  result?: any
  error?: string
}

/** Frontend view model of an agent, adapted from backend agent record. */
export interface Agent {
  id: string
  name: string
  status: 'active' | 'inactive'
  capabilities: string[]
  createdAt: string
  updatedAt: string
}

/** Frontend view model of a memory item, adapted from backend MemoryItem. */
export interface Memory {
  id: string
  content: string
  /** Backend memory layer (1-10) */
  layer: number
  /** 0..1 importance score */
  importance: number
  tags: string[]
  metadata: Record<string, any>
  sessionId?: string
  createdAt: string
  /** Relevance score, present only on search hits */
  relevance?: number
}

/**
 * Frontend view model of a tool, adapted from the backend tool manifest:
 * { name, description, risk_level, required_scope, parameters }.
 * The backend has no enabled/category/stats concept, so those UI affordances
 * are marked "coming soon" in the page.
 */
export interface Tool {
  id: string
  name: string
  description: string
  riskLevel: string
  requiredScope?: string
  parameters?: Record<string, any>
}

export interface AuthTokenResponse {
  access_token: string
  refresh_token?: string
  user?: {
    id: string
    email: string
    display_name?: string
    [key: string]: any
  }
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  metadata?: Record<string, any>
}

export interface ChatRunEvent {
  type: string
  status?: string
  message: string
  created_at?: string
  metadata?: Record<string, any>
}

export interface ChatNextAction {
  id: string
  label: string
  path?: string
}

export interface ChatRunResponse {
  run_id: string
  trace_id?: string
  status: 'accepted' | 'running' | 'completed' | 'failed'
  message: string
  events: ChatRunEvent[]
  approval_required: boolean
  next_actions: ChatNextAction[]
  agent_id: string
  workflow_id?: string
  resource_type: 'workflow_chat'
}

export interface WorkbenchBootstrap {
  console: {
    tenant_id: string
    user_id: string
    agent_id: string
    session_id: string
    created_at: string
  }
  entries: Array<{ id: string; label: string; path: string }>
}

/**
 * Raw agent record as returned by GET /agents/{id} (snake_case preserved).
 * Used by views that display backend fields directly (e.g. the agent
 * workspace), unlike the adapted `Agent` view model.
 */
export interface AgentDetailRecord {
  id: string
  name: string
  status: string
  capabilities: string[]
  created_at?: string
  config?: Record<string, any>
  [key: string]: any
}

/** Payload returned by POST /agent/run (ad-hoc agent task execution). */
export interface AgentRunResult {
  message?: string
  answer?: string
  [key: string]: any
}

/** A single agent's outcome inside a parallel ("ultra mode") run. */
export interface ParallelAgentResult {
  agent_id?: string
  status?: string
  output?: string
  error?: string
  [key: string]: any
}

/** Payload returned by POST /agents/parallel. */
export interface ParallelRunResponse {
  results?: ParallelAgentResult[]
  agent_results?: ParallelAgentResult[]
  [key: string]: any
}

/** Operational metrics returned by GET /metrics (dashboard widgets). */
export interface DashboardMetrics {
  uptime?: string | number
  uptime_percent?: string | number
  total_requests?: number
  request_count?: number
  error_rate?: number | null
  avg_latency_ms?: number | null
  [key: string]: any
}

/** API key record returned by POST /api-keys. */
export interface ApiKeyRecord {
  id?: string
  name?: string
  prefix?: string
  created_at?: string
  [key: string]: any
}

// ---------------------------------------------------------------------------
// snake_case -> camelCase adapters (naming only, no semantic rewriting)
// ---------------------------------------------------------------------------

/* eslint-disable @typescript-eslint/no-explicit-any */
function adaptTask(raw: any): Task {
  return {
    id: String(raw.task_id ?? raw.id ?? ''),
    name: String(raw.title ?? raw.name ?? ''),
    status: raw.status ?? 'pending',
    progress: typeof raw.progress === 'number' ? raw.progress : 0,
    createdAt: String(raw.created_at ?? raw.createdAt ?? ''),
    updatedAt: String(raw.updated_at ?? raw.completed_at ?? raw.created_at ?? ''),
    description: raw.description ?? '',
    priority: raw.priority,
    tags: Array.isArray(raw.tags) ? raw.tags : [],
    result: raw.result,
    error: raw.error ?? undefined,
  }
}

function adaptAgent(raw: any): Agent {
  return {
    id: String(raw.id ?? ''),
    name: String(raw.name ?? ''),
    status: raw.status === 'inactive' ? 'inactive' : 'active',
    capabilities: Array.isArray(raw.capabilities) ? raw.capabilities : [],
    createdAt: String(raw.created_at ?? raw.createdAt ?? ''),
    updatedAt: String(raw.updated_at ?? raw.updatedAt ?? ''),
  }
}

function adaptMemory(raw: any, relevance?: number): Memory {
  return {
    id: String(raw.id ?? ''),
    content: String(raw.content ?? ''),
    layer: typeof raw.layer === 'number' ? raw.layer : 3,
    importance: typeof raw.importance === 'number' ? raw.importance : 0.5,
    tags: Array.isArray(raw.tags) ? raw.tags : [],
    metadata: raw.metadata ?? {},
    sessionId: raw.session_id ?? undefined,
    createdAt: String(raw.created_at ?? raw.createdAt ?? ''),
    relevance,
  }
}

function adaptTool(raw: any): Tool {
  const name = String(raw.name ?? raw.id ?? '')
  return {
    id: name,
    name,
    description: String(raw.description ?? ''),
    riskLevel: String(raw.risk_level ?? raw.riskLevel ?? 'low'),
    requiredScope: raw.required_scope ?? raw.requiredScope,
    parameters: raw.parameters,
  }
}

class ApiClient {
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
      async (error: AxiosError) => {
        const originalRequest = error.config as any
        // Token refresh logic: on 401, try to refresh once
        if (error.response?.status === 401 && !originalRequest._retry) {
          const refreshToken = localStorage.getItem('refresh_token')
          if (refreshToken) {
            originalRequest._retry = true
            try {
              const resp = await this.client.post('/auth/refresh', { refresh_token: refreshToken })
              const { access_token, refresh_token: newRefresh } = resp.data
              localStorage.setItem('auth_token', access_token)
              if (newRefresh) localStorage.setItem('refresh_token', newRefresh)
              originalRequest.headers.Authorization = `Bearer ${access_token}`
              return this.client(originalRequest)
            } catch {
              // Refresh failed, force logout
              localStorage.removeItem('auth_token')
              localStorage.removeItem('refresh_token')
              window.location.href = '/login'
            }
          } else {
            localStorage.removeItem('auth_token')
            window.location.href = '/login'
          }
        }
        return Promise.reject(error)
      }
    )
  }

  async getWorkbenchBootstrap(): Promise<WorkbenchBootstrap> {
    const response = await this.client.get<WorkbenchBootstrap>('/workbench')
    return response.data
  }

  // Agents API — GET /api/v1/agents returns { data: [...] }
  async listAgents(): Promise<Agent[]> {
    const response = await this.client.get('/agents')
    const payload = response.data
    const items = Array.isArray(payload) ? payload : payload?.data ?? []
    return items.map(adaptAgent)
  }

  async getAgent(id: string): Promise<Agent> {
    const response = await this.client.get(`/agents/${id}`)
    return adaptAgent(response.data)
  }

  async createAgent(data: Partial<Agent>): Promise<Agent> {
    const response = await this.client.post('/agents', data)
    return adaptAgent(response.data)
  }

  async updateAgent(id: string, data: Partial<Agent>): Promise<Agent> {
    const response = await this.client.put(`/agents/${id}`, data)
    return adaptAgent(response.data)
  }

  async deleteAgent(id: string): Promise<void> {
    await this.client.delete(`/agents/${id}`)
  }

  // Tasks API — GET /api/v1/tasks returns TaskListResponse { tasks, total, ... }
  async listTasks(page: number = 1, pageSize: number = 100): Promise<PaginatedResponse<Task>> {
    const limit = pageSize
    const offset = (page - 1) * pageSize
    const response = await this.client.get('/tasks', {
      params: { limit, offset },
    })
    const payload = response.data
    const rawItems: any[] = Array.isArray(payload) ? payload : payload?.tasks ?? []
    const total: number = typeof payload?.total === 'number' ? payload.total : rawItems.length
    return {
      items: rawItems.map(adaptTask),
      total,
      page,
      pageSize,
      hasMore: offset + rawItems.length < total,
    }
  }

  async getTask(id: string): Promise<Task> {
    const response = await this.client.get(`/tasks/${id}`)
    return adaptTask(response.data)
  }

  async createTask(data: { title: string; description?: string; priority?: string; tags?: string[] }): Promise<Task> {
    const response = await this.client.post('/tasks', data)
    return adaptTask(response.data)
  }

  async updateTask(id: string, data: Record<string, any>): Promise<Task> {
    const response = await this.client.put(`/tasks/${id}`, data)
    return adaptTask(response.data)
  }

  async deleteTask(id: string): Promise<void> {
    await this.client.delete(`/tasks/${id}`)
  }

  // Memory API — the backend exposes POST /memory/search (no GET list endpoint);
  // an empty query returns the most relevant items and acts as the list view.
  async listMemories(topK: number = 50): Promise<PaginatedResponse<Memory>> {
    const response = await this.client.post('/memory/search', {
      query: '',
      top_k: topK,
    })
    const rawItems: any[] = response.data?.items ?? []
    return {
      items: rawItems.map((item) => adaptMemory(item)),
      total: rawItems.length,
      page: 1,
      pageSize: topK,
      hasMore: false,
    }
  }

  async searchMemories(query: string, topK: number = 50): Promise<Memory[]> {
    const response = await this.client.post('/memory/search', {
      query,
      top_k: topK,
      include_scores: true,
    })
    const rawItems: any[] = response.data?.items ?? []
    const hits: any[] = response.data?.hits ?? []
    const scoreById = new Map<string, number>(
      hits
        .filter((hit) => hit && hit.item && typeof hit.score === 'number')
        .map((hit) => [String(hit.item.id), hit.score as number])
    )
    return rawItems.map((item) => adaptMemory(item, scoreById.get(String(item?.id ?? ''))))
  }

  async getMemory(id: string): Promise<Memory> {
    const response = await this.client.get(`/memory/${id}`)
    return adaptMemory(response.data)
  }

  // POST /api/v1/memory — returns { id }
  async createMemory(data: { content: string; layer?: number; importance?: number; tags?: string[]; metadata?: Record<string, any> }): Promise<{ id: string }> {
    const response = await this.client.post('/memory', {
      content: data.content,
      layer: data.layer ?? 3,
      importance: data.importance ?? 0.5,
      tags: data.tags ?? [],
      metadata: data.metadata ?? {},
    })
    return response.data
  }

  // NOTE: the backend has no PUT/DELETE /memory/{id} endpoints. Editing and
  // deleting memories is marked "coming soon" in the UI until it lands.

  // PUT /api/v1/memory/{id} — update a memory item
  async updateMemory(id: string, data: { content?: string; layer?: number; importance?: number; tags?: string[]; metadata?: Record<string, any> }): Promise<Memory> {
    const response = await this.client.put(`/memory/${id}`, data)
    return adaptMemory(response.data)
  }

  // DELETE /api/v1/memory/{id} — delete a memory item
  async deleteMemory(id: string): Promise<void> {
    await this.client.delete(`/memory/${id}`)
  }

  // Tools API — GET /api/v1/tools returns the tool manifest list.
  async listTools(): Promise<Tool[]> {
    const response = await this.client.get('/tools')
    const payload = response.data
    const items = Array.isArray(payload) ? payload : payload?.data ?? []
    return items.map(adaptTool)
  }

  // NOTE: the backend has no PUT /tools/{id} or POST /tools/{id}/test endpoints.
  // Toggling and ad-hoc testing of tools is marked "coming soon" in the UI.

  // PUT /api/v1/tools/{name} — update tool config
  async updateTool(name: string, data: { enabled?: boolean; config?: Record<string, any> }): Promise<any> {
    const response = await this.client.put(`/tools/${name}`, data)
    return response.data
  }

  // POST /api/v1/tools/{name}/test — test a tool
  async testTool(name: string, parameters: Record<string, any> = {}): Promise<any> {
    const response = await this.client.post(`/tools/${name}/test`, { parameters })
    return response.data
  }

  // Workflows API — GET /api/v1/workflows, POST /api/v1/workflows/{id}/run
  async listWorkflows(): Promise<any[]> {
    const response = await this.client.get('/workflows')
    const payload = response.data
    return Array.isArray(payload) ? payload : payload?.items ?? []
  }

  async getWorkflow(id: string): Promise<any> {
    const response = await this.client.get(`/workflows/${id}`)
    return response.data
  }

  async runWorkflow(id: string, input?: Record<string, any>): Promise<any> {
    const response = await this.client.post(`/workflows/${id}/run`, { input: input ?? {} })
    return response.data
  }

  async listWorkflowRuns(limit: number = 20): Promise<any[]> {
    const response = await this.client.get('/workflows/runs', { params: { limit } })
    const payload = response.data
    return Array.isArray(payload) ? payload : payload?.items ?? []
  }

  // Chat API — POST /api/v1/workflows/create/chat
  async sendMessage(message: string, agentId?: string): Promise<ChatRunResponse> {
    const response = await this.client.post<ChatRunResponse>('/workflows/create/chat', {
      request: message,
      agent_id: agentId,
    })
    return response.data
  }

  // NOTE: the backend has no GET /chat/history or GET /chat/stream endpoints.
  // History persistence is marked "coming soon" in the UI.

  // Auth API — POST /api/v1/auth/login, POST /api/v1/auth/register
  async login(email: string, password: string): Promise<AuthTokenResponse> {
    const response = await this.client.post<AuthTokenResponse>('/auth/login', {
      email,
      password,
    })
    return response.data
  }

  async register(email: string, password: string): Promise<AuthTokenResponse> {
    const response = await this.client.post<AuthTokenResponse>('/auth/register', {
      email,
      password,
    })
    return response.data
  }

  async refreshToken(refreshToken: string): Promise<AuthTokenResponse> {
    const response = await this.client.post<AuthTokenResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    })
    return response.data
  }

  async logout(): Promise<void> {
    await this.client.post('/auth/logout')
  }

  // Code Review API — POST /api/v1/code-review/file
  async postCodeReview(content: string, language: string): Promise<any> {
    const response = await this.client.post('/code-review/file', { content, language })
    return response.data
  }

  // Evolution API — GET /api/v1/evolution/stats, GET /api/v1/evolution/skills
  async getEvolutionStats(): Promise<{ total_tasks: number; patterns_extracted: number; skills_promoted: number; [key: string]: any }> {
    const response = await this.client.get('/evolution/stats')
    return response.data
  }

  async getEvolutionSkills(): Promise<any[]> {
    const response = await this.client.get('/evolution/skills')
    const payload = response.data
    return Array.isArray(payload) ? payload : payload?.skills ?? payload?.items ?? []
  }

  // Goals API — GET /api/v1/goals, POST /api/v1/goals
  async getGoals(): Promise<any[]> {
    const response = await this.client.get('/goals')
    const payload = response.data
    return Array.isArray(payload) ? payload : payload?.goals ?? payload?.items ?? []
  }

  async createGoal(objective: string): Promise<any> {
    const response = await this.client.post('/goals', { objective })
    return response.data
  }

  // Health check — GET /api/v1/health/live returns { status: "alive", timestamp }
  async healthCheck(): Promise<{ status: string; version?: string }> {
    const response = await this.client.get('/health/live')
    return response.data
  }

  // Agent detail (raw record) — GET /api/v1/agents/{id}. Keeps backend
  // field names, unlike getAgent() which adapts to the Agent view model.
  async getAgentDetail(id?: string): Promise<AgentDetailRecord> {
    const response = await this.client.get<AgentDetailRecord>(`/agents/${id}`)
    return response.data
  }

  // POST /api/v1/agent/run — run an ad-hoc task on a specific agent
  async runAgentTask(task: string, agentId?: string): Promise<AgentRunResult> {
    const response = await this.client.post<AgentRunResult>('/agent/run', {
      task,
      extra_context: { agent_id: agentId },
    })
    return response.data
  }

  // POST /api/v1/agents/parallel — "ultra mode" parallel agent execution
  async runParallelAgents(
    tasks: Array<{ goal: string; description: string }>,
    maxParallel: number = 4
  ): Promise<ParallelRunResponse> {
    const response = await this.client.post<ParallelRunResponse>('/agents/parallel', {
      tasks,
      max_parallel: maxParallel,
    })
    return response.data
  }

  // GET /api/v1/metrics — operational metrics for the dashboard
  async getMetrics(): Promise<DashboardMetrics> {
    const response = await this.client.get<DashboardMetrics>('/metrics')
    return response.data
  }

  // PUT /api/v1/users/me — update the current user's profile
  async updateProfile(data: { display_name?: string; email?: string }): Promise<void> {
    await this.client.put('/users/me', data)
  }

  // POST /api/v1/api-keys — create a new API key
  async createApiKey(name: string): Promise<ApiKeyRecord> {
    const response = await this.client.post<ApiKeyRecord>('/api-keys', { name })
    return response.data
  }

  // DELETE /api/v1/api-keys/{id} — revoke an API key
  async deleteApiKey(id: string): Promise<void> {
    await this.client.delete(`/api-keys/${id}`)
  }
}

export const apiClient = new ApiClient()
export default apiClient
