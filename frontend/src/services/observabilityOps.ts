import axios, { AxiosInstance } from 'axios'

/**
 * Observability operations service — 封装已核对的真实后端端点
 * (来源: backend/app/api/traces.py, backend/app/api/metrics.py,
 *  backend/app/api/ops.py):
 *
 * 1. Metrics  GET /api/v1/metrics/summary
 * 2. Ops      GET /api/v1/ops/summary
 * 3. Traces   GET /api/v1/traces, GET /api/v1/traces/{id},
 *             GET /api/v1/traces/{id}/replay
 *
 * 说明:
 * - 本模块不复用 services/api.ts(该文件由另一代理维护), 自建 axios 实例,
 *   鉴权逻辑(localStorage auth_token -> Bearer)与 api.ts 保持一致。
 * - components/AnalyticsDashboard.tsx 依赖的 /api/v1/analytics/* router
 *   未在 backend/app/main.py 中挂载, 该孤儿组件不可用, 本页面不复用它。
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

// ─── 类型(与后端模型字段对齐, snake_case 原样保留) ────────────────────────────

/** GET /metrics/summary 响应 (metrics.py _summary_payload). */
export interface MetricsSummary {
  runs: number
  traces: number
  trace_events: number
  memories: number
  workflows: number
  workflow_runs: number
  workflow_schedules: number
  audit_logs: number
  api_keys: number
  active_api_keys: number
  approvals: number
  pending_approvals: number
}

/** GET /ops/summary 响应 (ops.py get_ops_summary). */
export interface OpsSummary {
  healthy: boolean
  failure_traces: Array<{
    trace_id: string
    status: string
    last_event: string | null
    event_count: number
  }>
  approval_backlog: number
  tool_failures: number
  overview: {
    traces: number
    runs: number
    approvals: number
    tools: number
  }
}

/** GET /traces 列表项 (TraceSummary dump). */
export interface TraceSummaryItem {
  trace_id: string
  event_count: number
  started_at: string | null
  ended_at: string | null
  last_event: string | null
  task: string | null
  snapshot: {
    status?: string
    agent_id?: string
    user_id?: string
    request_id?: string
    workflow_id?: string
    tenant_id?: string
    iterations?: number
    tool_call_count?: number
    [key: string]: any
  }
}

/** GET /traces/{id} 事件项 (TraceEvent). */
export interface TraceEventItem {
  trace_id: string
  event: string
  timestamp: string
  data: Record<string, any>
  request_id: string | null
  agent_id: string | null
  tenant_id: string | null
  user_id: string | null
}

/** GET /traces/{id} 响应 (TraceDetail). */
export interface TraceDetailResponse {
  summary: TraceSummaryItem
  events: TraceEventItem[]
}

/**
 * GET /traces/{id}/replay 响应 (build_linked_summary 富载荷)。
 * 顶层含 resource_type/resource_id/snapshot/linked_summaries 等键;
 * 关联资源计数在 snapshot.related_resources / linked_summaries 下。
 */
export interface TraceReplayResponse {
  resource_type: string
  resource_id: string
  snapshot: {
    events?: TraceEventItem[]
    trace_summary?: TraceSummaryItem
    related_resources?: {
      run?: Record<string, any>
      approvals?: Array<Record<string, any>>
      audit_records?: Array<Record<string, any>>
      memory_items?: Array<Record<string, any>>
      tool_executions?: Array<Record<string, any>>
    }
    [key: string]: any
  }
  linked_summaries?: Record<string, any>
  [key: string]: any
}

// ─── 客户端 ─────────────────────────────────────────────────────────────────

class ObservabilityOpsClient {
  private client: AxiosInstance

  constructor(baseURL: string = '/api/v1') {
    this.client = axios.create({
      baseURL,
      timeout: 30000,
      headers: { 'Content-Type': 'application/json' },
    })
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('auth_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    })
  }

  // ── Metrics: /api/v1/metrics (backend: api/metrics.py) ────────────────────

  /** GET /metrics/summary — 资源计数 (runs/traces/memories/workflows...) */
  async getMetricsSummary(): Promise<MetricsSummary> {
    const response = await this.client.get('/metrics/summary')
    return response.data
  }

  // ── Ops: /api/v1/ops (backend: api/ops.py) ────────────────────────────────

  /** GET /ops/summary — 运维健康概览 (失败 trace / 审批积压 / 工具失败) */
  async getOpsSummary(): Promise<OpsSummary> {
    const response = await this.client.get('/ops/summary')
    return response.data
  }

  // ── Traces: /api/v1/traces (backend: api/traces.py) ───────────────────────

  /** GET /traces — trace 列表 (纯列表, 每项含 trace_id) */
  async listTraces(limit: number = 20): Promise<TraceSummaryItem[]> {
    const response = await this.client.get('/traces', { params: { limit } })
    const payload = response.data
    return Array.isArray(payload) ? payload : []
  }

  /** GET /traces/{trace_id} — trace 详情 (summary + 事件时间线) */
  async getTrace(traceId: string): Promise<TraceDetailResponse> {
    const response = await this.client.get(`/traces/${traceId}`)
    return response.data
  }

  /** GET /traces/{trace_id}/replay — 回放 (事件 + 关联资源: run/审批/审计/记忆/工具) */
  async getTraceReplay(traceId: string): Promise<TraceReplayResponse> {
    const response = await this.client.get(`/traces/${traceId}/replay`)
    return response.data
  }
}

export const observabilityOps = new ObservabilityOpsClient()
export default observabilityOps
