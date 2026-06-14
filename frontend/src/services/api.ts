import axios, { AxiosInstance, AxiosError } from 'axios'

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

export interface Task {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  createdAt: string
  updatedAt: string
  result?: any
  error?: string
}

export interface Agent {
  id: string
  name: string
  status: 'active' | 'inactive'
  capabilities: string[]
  createdAt: string
  updatedAt: string
}

export interface Memory {
  id: string
  content: string
  type: string
  tags: string[]
  createdAt: string
  updatedAt: string
  relevance?: number
}

export interface Tool {
  id: string
  name: string
  description: string
  category: string
  enabled: boolean
  config?: Record<string, any>
  stats?: {
    usageCount: number
    successRate: number
    avgExecutionTime: number
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

export interface WorkbenchActivityItem {
  id: string
  title: string
  subtitle: string
  status: string
  tone: 'success' | 'warning' | 'danger' | 'neutral'
  time: string
}

export interface WorkbenchWorkflowRun {
  id: string
  name: string
  state: string
  progress: number
  owner: string
  tone: 'success' | 'warning' | 'danger' | 'neutral'
}

export interface WorkbenchHome {
  brand: {
    product_name: string
    platform_name: string
    subtitle: string
  }
  summary: string
  metrics: {
    active_agents: number
    running_workflows: number
    pending_approvals: number
    api_calls: number
    storage_used: string
  }
  agent_activity: WorkbenchActivityItem[]
  workflow_runs: WorkbenchWorkflowRun[]
  control_summary?: {
    source?: string
    status?: string
    read_only?: boolean
    execute_enabled?: boolean
    count_scope?: string
    limit?: number
    plan_count?: number
    goal_count?: number
    status_counts?: Record<string, Record<string, number>>
    latest_updated_at?: string | null
    boundary?: string
  }
  runtime_capability_summary?: {
    source?: string
    source_status?: string
    status?: string
    read_only?: boolean
    execute_enabled?: boolean
    ok?: boolean
    summary?: Record<string, number>
    issue_codes?: string[]
    next_actions?: string[]
    boundary?: string
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
      (error: AxiosError) => {
        if (error.response?.status === 401 && localStorage.getItem('auth_token')) {
          localStorage.removeItem('auth_token')
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }
    )
  }

  async getWorkbenchBootstrap(): Promise<WorkbenchBootstrap> {
    const response = await this.client.get<WorkbenchBootstrap>('/workbench')
    return response.data
  }

  async getWorkbenchHome(): Promise<WorkbenchHome> {
    const response = await this.client.get<WorkbenchHome>('/workbench/home')
    return response.data
  }

  // Agents API
  async listAgents(): Promise<Agent[]> {
    const response = await this.client.get<Agent[]>('/agents')
    return response.data
  }

  async getAgent(id: string): Promise<Agent> {
    const response = await this.client.get<Agent>(`/agents/${id}`)
    return response.data
  }

  async createAgent(data: Partial<Agent>): Promise<Agent> {
    const response = await this.client.post<Agent>('/agents', data)
    return response.data
  }

  async updateAgent(id: string, data: Partial<Agent>): Promise<Agent> {
    const response = await this.client.put<Agent>(`/agents/${id}`, data)
    return response.data
  }

  async deleteAgent(id: string): Promise<void> {
    await this.client.delete(`/agents/${id}`)
  }

  // Tasks API
  async listTasks(page: number = 1, pageSize: number = 20): Promise<PaginatedResponse<Task>> {
    const response = await this.client.get<PaginatedResponse<Task>>('/tasks', {
      params: { page, pageSize },
    })
    return response.data
  }

  async getTask(id: string): Promise<Task> {
    const response = await this.client.get<Task>(`/tasks/${id}`)
    return response.data
  }

  async createTask(data: Partial<Task>): Promise<Task> {
    const response = await this.client.post<Task>('/tasks', data)
    return response.data
  }

  async updateTask(id: string, data: Partial<Task>): Promise<Task> {
    const response = await this.client.put<Task>(`/tasks/${id}`, data)
    return response.data
  }

  async deleteTask(id: string): Promise<void> {
    await this.client.delete(`/tasks/${id}`)
  }

  // Memory API
  async listMemories(page: number = 1, pageSize: number = 20): Promise<PaginatedResponse<Memory>> {
    const response = await this.client.get<PaginatedResponse<Memory>>('/memory', {
      params: { page, pageSize },
    })
    return response.data
  }

  async searchMemories(query: string): Promise<Memory[]> {
    const response = await this.client.get<Memory[]>('/memory/search', {
      params: { q: query },
    })
    return response.data
  }

  async getMemory(id: string): Promise<Memory> {
    const response = await this.client.get<Memory>(`/memory/${id}`)
    return response.data
  }

  async createMemory(data: Partial<Memory>): Promise<Memory> {
    const response = await this.client.post<Memory>('/memory', data)
    return response.data
  }

  async updateMemory(id: string, data: Partial<Memory>): Promise<Memory> {
    const response = await this.client.put<Memory>(`/memory/${id}`, data)
    return response.data
  }

  async deleteMemory(id: string): Promise<void> {
    await this.client.delete(`/memory/${id}`)
  }

  // Tools API
  async listTools(): Promise<Tool[]> {
    const response = await this.client.get<Tool[]>('/tools')
    return response.data
  }

  async getTool(id: string): Promise<Tool> {
    const response = await this.client.get<Tool>(`/tools/${id}`)
    return response.data
  }

  async updateTool(id: string, data: Partial<Tool>): Promise<Tool> {
    const response = await this.client.put<Tool>(`/tools/${id}`, data)
    return response.data
  }

  async testTool(id: string, params: Record<string, any>): Promise<any> {
    const response = await this.client.post(`/tools/${id}/test`, params)
    return response.data
  }

  // Chat API
  async sendMessage(message: string, agentId?: string): Promise<ChatRunResponse> {
    const response = await this.client.post<ChatRunResponse>('/workflows/create/chat', {
      request: message,
      agent_id: agentId,
    })
    return response.data
  }

  async getChatHistory(limit: number = 50): Promise<ChatMessage[]> {
    const response = await this.client.get<ChatMessage[]>('/chat/history', {
      params: { limit },
    })
    return response.data
  }

  // Streaming API
  async streamChat(message: string, agentId?: string): Promise<ReadableStream<string>> {
    const response = await this.client.get('/chat/stream', {
      params: { message, agentId },
      responseType: 'stream',
    })
    return response.data
  }

  // Health check
  async healthCheck(): Promise<{ status: string; version: string }> {
    const response = await this.client.get('/health')
    return response.data
  }
}

export const apiClient = new ApiClient()
export default apiClient
