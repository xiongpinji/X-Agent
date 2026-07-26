import axios, { AxiosInstance } from 'axios'

/**
 * Sandbox task operations client — aligned with backend/app/api/sandbox_tasks.py
 * (re-verified on 2026-07-26). Wraps the three real task endpoints:
 *
 *  POST /api/v1/sandbox/tasks            submit (fire-and-forget)
 *  GET  /api/v1/sandbox/tasks            list known task ids + statuses
 *  GET  /api/v1/sandbox/tasks/{task_id}  poll status / steps / error
 *
 * The GitHub webhook endpoint is intentionally NOT exposed here (server-to-server).
 * The backend has no task-cancel/delete endpoint — such actions must be
 * rendered as disabled "coming soon" affordances in pages.
 */

export interface SandboxTaskSubmitRequest {
  name: string
  command: string
  image?: string
  timeout_seconds?: number
  enable_network?: boolean
}

export interface SandboxTaskSubmitResponse {
  task_id: string
  status: string // 'queued'
}

export interface SandboxTaskStep {
  name?: string
  [key: string]: any
}

export interface SandboxTaskStatusResponse {
  task_id: string
  status: string // queued | running | completed | failed | error
  backend?: string | null
  steps: SandboxTaskStep[]
  error?: string | null
}

export interface SandboxTaskListItem {
  task_id: string
  status: string
}

export interface SandboxTaskListResponse {
  tasks: SandboxTaskListItem[]
}

class SandboxOpsClient {
  private client: AxiosInstance

  constructor(baseURL: string = '/api/v1') {
    this.client = axios.create({
      baseURL,
      timeout: 30000,
      headers: { 'Content-Type': 'application/json' },
    })
    // Same auth convention as services/api.ts: Bearer token from localStorage.
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('auth_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    })
  }

  async submitTask(req: SandboxTaskSubmitRequest): Promise<SandboxTaskSubmitResponse> {
    const resp = await this.client.post('/sandbox/tasks', {
      name: req.name,
      command: req.command,
      image: req.image ?? 'python:3.11-slim',
      timeout_seconds: req.timeout_seconds ?? 300,
      enable_network: req.enable_network ?? false,
    })
    return resp.data
  }

  async listTasks(): Promise<SandboxTaskListResponse> {
    const resp = await this.client.get('/sandbox/tasks')
    return resp.data
  }

  async getTask(taskId: string): Promise<SandboxTaskStatusResponse> {
    const resp = await this.client.get(`/sandbox/tasks/${encodeURIComponent(taskId)}`)
    return resp.data
  }
}

export const sandboxOps = new SandboxOpsClient()
export default sandboxOps
