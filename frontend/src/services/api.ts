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
        if (error.response?.status === 401) {
          localStorage.removeItem('auth_token')
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }
    )
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
  // Backend reality (docs/API_INVENTORY.md, backend/app/api/memory.py):
  //   POST /memory (create) · POST /memory/search · GET /memory/export
  //   GET /memory/{id} — and NO list / PUT / DELETE routes: the memory system
  //   is append-only (revisions + rollback by design). The old client called
  //   GET /memory, GET /memory/search?q=, PUT and DELETE — all 404/405 at runtime.

  private mapMemoryItem(item: Record<string, unknown>): Memory {
    return {
      id: String(item.id ?? ''),
      content: String(item.content ?? ''),
      type: item.layer != null ? `L${item.layer}` : String(item.type ?? 'memory'),
      tags: Array.isArray(item.tags) ? (item.tags as string[]) : [],
      createdAt: String(item.created_at ?? item.createdAt ?? ''),
      updatedAt: String(item.updated_at ?? item.updatedAt ?? ''),
      relevance: typeof item.score === 'number' ? item.score : undefined,
    }
  }

  async listMemories(page: number = 1, pageSize: number = 20): Promise<PaginatedResponse<Memory>> {
    // No GET /memory list endpoint exists — derive the list from the export
    // bundle and paginate client-side.
    const response = await this.client.get<{ bundle?: { memories?: Record<string, unknown>[] } }>('/memory/export')
    const all = (response.data?.bundle?.memories ?? []).map((item) => this.mapMemoryItem(item))
    all.sort((a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''))
    const start = (page - 1) * pageSize
    const items = all.slice(start, start + pageSize)
    return { items, total: all.length, page, pageSize, hasMore: start + items.length < all.length }
  }

  async searchMemories(query: string): Promise<Memory[]> {
    // POST (not GET): backend defines POST /memory/search with {query, top_k}
    const response = await this.client.post<{ items?: Record<string, unknown>[] }>('/memory/search', {
      query,
      top_k: 20,
    })
    return (response.data?.items ?? []).map((item) => this.mapMemoryItem(item))
  }

  async getMemory(id: string): Promise<Memory> {
    const response = await this.client.get<Record<string, unknown>>(`/memory/${id}`)
    return this.mapMemoryItem(response.data ?? {})
  }

  async createMemory(data: Partial<Memory>): Promise<Memory> {
    // POST /memory returns {id} (MemoryStoreResponse), not the full item.
    const response = await this.client.post<{ id: string }>('/memory', {
      content: data.content ?? '',
      summary: data.content ?? '',
      tags: data.tags ?? [],
    })
    return { ...(data as Memory), id: response.data?.id ?? '' }
  }

  async updateMemory(_id: string, _data: Partial<Memory>): Promise<Memory> {
    // Backend memory is append-only: no PUT /memory/{id} exists (revision +
    // rollback is the sanctioned mutation path). Fail loudly instead of 405.
    throw new Error('Memory update is not supported: backend memory is append-only (no PUT /memory/{id})')
  }

  async deleteMemory(_id: string): Promise<void> {
    // No DELETE /memory/{id} on the backend (append-only design, audit trail).
    throw new Error('Memory deletion is not supported by the backend (append-only memory design)')
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
  async sendMessage(message: string, agentId?: string): Promise<ChatMessage> {
    const response = await this.client.post<ChatMessage>('/chat/send', {
      content: message,
      agentId,
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
