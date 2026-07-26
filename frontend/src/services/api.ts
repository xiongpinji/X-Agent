import axios, { AxiosInstance, AxiosError } from 'axios'

/**
 * API client aligned with the real backend routes (re-verified against the
 * backend FastAPI route table on 2026-07-26).
 *
 * Notes:
 * - PUT/DELETE /memory/{id}, PUT /tools/{name}, POST /tools/{name}/test and
 *   the /chat/history endpoint group all exist in the backend and are wired.
 * - GET /chat/stream and /ws still do not exist; callers must not use them.
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

/** Session summary returned by GET /api/v1/chat/history (snake_case, seconds). */
export interface ChatSessionSummary {
  id: string
  title: string
  agent_id: string
  created_at: number
  updated_at: number
  message_count: number
}

/** Message record returned by the /chat/history endpoints (timestamp in seconds). */
export interface ChatHistoryMessage {
  id: string
  role: string
  content: string
  timestamp: number
  metadata?: Record<string, any>
}

/** Full session payload returned by GET /api/v1/chat/history/{session_id}. */
export interface ChatSessionDetail {
  id: string
  title: string
  agent_id: string
  messages: ChatHistoryMessage[]
  created_at: number
  updated_at: number
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
  task_id?: string
  agent_id?: string
  status?: string
  output?: string
  tokens_used?: number
  duration_seconds?: number
  error?: string
  [key: string]: any
}

/**
 * Payload returned by POST /agents/parallel/ultra (UltraResult.to_dict()):
 * { execution_id, task, subtasks, results, merged_answer, merge_strategy,
 *   total_tokens, total_duration_seconds, agents_used, status }.
 */
export interface ParallelRunResponse {
  execution_id?: string
  results?: ParallelAgentResult[]
  agent_results?: ParallelAgentResult[]
  merged_answer?: string
  agents_used?: number
  status?: string
  [key: string]: any
}

/**
 * Operational metrics returned by GET /metrics/summary (dashboard widgets).
 * The backend summary exposes count fields (runs, traces, memories,
 * workflows, workflow_runs, audit_logs, api_keys, approvals, ...); uptime /
 * latency / error-rate fields are not provided and render as "—" in the UI.
 */
export interface DashboardMetrics {
  runs?: number
  traces?: number
  memories?: number
  workflows?: number
  pending_approvals?: number
  uptime?: string | number
  uptime_percent?: string | number
  total_requests?: number
  request_count?: number
  error_rate?: number | null
  avg_latency_ms?: number | null
  [key: string]: any
}

/** API key record as returned by the /security/api-keys endpoints. */
export interface ApiKeyRecord {
  id: string
  name: string
  key_prefix: string
  revoked?: boolean
  created_at?: string
  expires_at?: string | null
  last_used_at?: string | null
  [key: string]: any
}

/** Response of POST /security/api-keys: the raw key plus its record. */
export interface ApiKeyCreateResponse {
  key: string
  record: ApiKeyRecord
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

  // PUT /api/v1/memory/{id} — update a memory item (backend: api/memory.py)
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

  // PUT /api/v1/tools/{name} — update tool config (backend: api/tools.py)
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

  // Chat history API — backend: api/chat_history.py, prefix /api/v1/chat.
  // All five endpoints exist and are wired to ChatPage persistence.

  /** GET /api/v1/chat/history — list sessions for the current user. */
  async listChatSessions(limit: number = 50): Promise<ChatSessionSummary[]> {
    const response = await this.client.get('/chat/history', { params: { limit } })
    return response.data?.sessions ?? []
  }

  /** GET /api/v1/chat/history/{session_id} — full message history of a session. */
  async getChatSession(sessionId: string): Promise<ChatSessionDetail> {
    const response = await this.client.get(`/chat/history/${sessionId}`)
    return response.data
  }

  /** POST /api/v1/chat/history — create a new session. */
  async createChatSession(data: { title?: string; agent_id?: string } = {}): Promise<{ id: string; title: string; created_at: number }> {
    const response = await this.client.post('/chat/history', data)
    return response.data
  }

  /** POST /api/v1/chat/history/{session_id}/messages — append a message. */
  async addChatMessage(
    sessionId: string,
    message: { role: string; content: string; metadata?: Record<string, any> }
  ): Promise<{ id: string; session_id: string; message_count: number }> {
    const response = await this.client.post(`/chat/history/${sessionId}/messages`, message)
    return response.data
  }

  /** DELETE /api/v1/chat/history/{session_id} — delete one session. */
  async deleteChatSession(sessionId: string): Promise<void> {
    await this.client.delete(`/chat/history/${sessionId}`)
  }

  /** DELETE /api/v1/chat/history — clear all history for the current user. */
  async clearChatHistory(): Promise<void> {
    await this.client.delete('/chat/history')
  }

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

  // POST /api/v1/agents/run — run an ad-hoc task on a specific agent
  // (backend: api/agents.py; body {task, extra_context} is accepted as-is).
  async runAgentTask(task: string, agentId?: string): Promise<AgentRunResult> {
    const response = await this.client.post<AgentRunResult>('/agents/run', {
      task,
      extra_context: { agent_id: agentId },
    })
    return response.data
  }

  // POST /api/v1/agents/parallel/ultra — "ultra mode" parallel agent execution.
  // Backend UltraRequest: {task, max_agents, budget_tokens_per_agent,
  // timeout_seconds, merge_strategy}. The frontend task list is joined into a
  // single coordinator task; maxParallel maps to max_agents (C5).
  async runParallelAgents(
    tasks: Array<{ goal: string; description: string }>,
    maxParallel: number = 4
  ): Promise<ParallelRunResponse> {
    const task = tasks
      .map((t, i) => `Subtask ${i + 1}: ${t.goal}${t.description && t.description !== t.goal ? `\n${t.description}` : ''}`)
      .join('\n\n')
    const response = await this.client.post<ParallelRunResponse>('/agents/parallel/ultra', {
      task,
      max_agents: maxParallel,
    })
    return response.data
  }

  // GET /api/v1/metrics/summary — operational metrics for the dashboard
  // (backend: api/metrics.py; returns count fields such as runs, traces,
  // memories, workflows, api_keys, approvals...).
  async getMetrics(): Promise<DashboardMetrics> {
    const response = await this.client.get<DashboardMetrics>('/metrics/summary')
    return response.data
  }

  // PUT /api/v1/auth/me — update the current user's profile.
  // NOTE (C6): backend update_me (api/auth.py:570) currently accepts no body
  // fields and returns the principal; the call succeeds but display_name/email
  // are not yet persisted server-side.
  async updateProfile(data: { display_name?: string; email?: string }): Promise<void> {
    await this.client.put('/auth/me', data)
  }

  // Security API — backend: api/security.py, prefix /api/v1/security.
  // GET /api/v1/security/api-keys — list API keys
  async listApiKeys(): Promise<ApiKeyRecord[]> {
    const response = await this.client.get<ApiKeyRecord[]>('/security/api-keys')
    return response.data
  }

  // POST /api/v1/security/api-keys — create a new API key.
  // Backend returns APIKeyCreateResponse {key, record}.
  async createApiKey(name: string): Promise<ApiKeyCreateResponse> {
    const response = await this.client.post<ApiKeyCreateResponse>('/security/api-keys', { name })
    return response.data
  }

  // DELETE /api/v1/security/api-keys/{id} — revoke an API key
  async deleteApiKey(id: string): Promise<void> {
    await this.client.delete(`/security/api-keys/${id}`)
  }
}

export const apiClient = new ApiClient()
export default apiClient
