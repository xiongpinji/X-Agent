import axios, { AxiosInstance } from 'axios'

/**
 * Workflow operations service — 封装三组已核对的真实后端端点
 * (来源: backend/app/api/workflows.py, backend/app/api/checkpoints.py):
 *
 * 1. 工作流调度  GET/POST /api/v1/workflows/schedules*, POST /api/v1/workflows/{id}/schedule
 * 2. 运行回放    GET /api/v1/workflows/runs, GET /api/v1/workflows/runs/{run_id}
 * 3. 断点恢复    GET/POST/DELETE /api/v1/checkpoints*
 *
 * 说明:
 * - 本模块不复用 services/api.ts(该文件由另一代理维护), 自建 axios 实例,
 *   鉴权逻辑(localStorage auth_token -> Bearer)与 api.ts 保持一致。
 * - 后端不存在"启用/禁用调度切换""编辑调度(PUT)"端点, 页面中对应入口标记
 *   为 coming soon, 绝不虚构请求。
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

// ─── 类型(与后端模型字段对齐, snake_case 原样保留) ────────────────────────────

/** GET /workflows/schedules 列表项 (workflows.py:206-210). */
export interface WorkflowScheduleItem {
  id: string
  schedule_id: string
  workflow_id: string
  /** pending | triggered | canceled | failed (WorkflowScheduleStatus) */
  status: string
  run_id: string | null
  locked_by: string | null
  locked_until: string | null
  resource_type: string
  /** store.create 注入: { workflow_id, input_keys, run_at, cron } */
  snapshot: {
    workflow_id?: string
    schedule_id?: string
    status?: string
    input_keys?: string[]
    /** cron 调度的下一次触发时间 (ISO) */
    run_at?: string
    /** 5 段式 cron 表达式, 一次性调度为 null */
    cron?: string | null
    [key: string]: any
  }
}

/** POST /workflows/{workflow_id}/schedule 请求体 (WorkflowScheduleRequest). */
export interface CreateSchedulePayload {
  inputs?: Record<string, any>
  /** 一次性调度: 延迟秒数 (默认 0) */
  delay_seconds?: number
  /** 一次性调度: 指定触发时间 (ISO) */
  run_at?: string | null
  /** 周期调度: 5 段式 cron; 与 run_at/delay_seconds 互斥, cron 优先 */
  cron?: string | null
}

/** POST /workflows/{workflow_id}/schedule 响应 (WorkflowScheduleRecord dump). */
export interface WorkflowScheduleRecord {
  schedule_id: string
  workflow_id: string
  status: string
  run_at: string
  cron: string | null
  run_id: string | null
  error: string | null
  created_at: string
  updated_at: string
  [key: string]: any
}

/** POST /workflows/schedules/run-due 响应项. */
export interface RunDueResult {
  schedule_id: string
  workflow_id: string
  status: string
  run_id: string | null
  [key: string]: any
}

/** GET /workflows/runs 列表项 (WorkflowRunRecord dump + 附加字段). */
export interface WorkflowRunItem {
  run_id: string
  workflow_id: string
  workflow_name: string
  /** draft | running | completed | failed | canceled | paused | needs_approval */
  status: string
  inputs: Record<string, any>
  outputs: Record<string, any>
  node_results: WorkflowNodeResult[]
  started_at: string
  completed_at: string
  error: string | null
  resume_cursor: number
  [key: string]: any
}

export interface WorkflowNodeResult {
  node_id: string
  node_type: string
  status: string
  attempts: number
  output: any
  error: string | null
  started_at: string
  completed_at: string
  agent_trace_id: string | null
  compensated: boolean
  compensation_output?: any
  compensation_error?: string | null
}

export interface WorkflowRunTimelineEvent {
  kind: string
  timestamp: string
  workflow_id?: string
  node_id?: string
  node_type?: string
  status?: string
  attempts?: number
  agent_trace_id?: string
  compensated?: boolean
  error?: string | null
  compensation_error?: string | null
  compensation_output?: any
}

/** GET /workflows/runs/{run_id} 响应(顶层补 run/timeline, 见 workflows.py:593-601). */
export interface WorkflowRunDetail {
  run: WorkflowRunItem
  timeline: WorkflowRunTimelineEvent[]
  snapshot: Record<string, any>
  linked_summaries?: Record<string, any>
  [key: string]: any
}

/** GET /checkpoints 列表项 (CheckpointSummary). */
export interface CheckpointSummaryItem {
  checkpoint_id: string
  trace_id: string
  agent_id: string
  iteration: number
  /** running | paused | failed | completed */
  status: string
  created_at: string
  task_preview: string
}

export interface CheckpointListResponse {
  items: CheckpointSummaryItem[]
  total: number
}

/** GET /checkpoints/{trace_id} 响应 (CheckpointDetailResponse). */
export interface CheckpointDetail {
  trace_id: string
  agent_id: string
  /** CheckpointData dump 列表 */
  checkpoints: Array<{
    checkpoint_id: string
    iteration: number
    status: string
    task?: string
    max_iterations?: number
    remaining_steps?: Array<Record<string, any>>
    completed_steps?: Array<Record<string, any>>
    tool_calls?: Array<Record<string, any>>
    observations?: string[]
    answer_so_far?: string
    trajectory_goal?: string
    trajectory_stage?: string
    created_at?: string
    [key: string]: any
  }>
  latest_iteration: number
  status: string
  resumable: boolean
}

/** POST /checkpoints/{trace_id}/resume 请求体 (ResumeRequest). */
export interface ResumeCheckpointPayload {
  extra_context?: Record<string, any>
  /** null = 从最新 checkpoint 恢复 */
  from_iteration?: number | null
}

/** POST /checkpoints/{trace_id}/resume 响应 (ResumeResponse). */
export interface ResumeCheckpointResponse {
  trace_id: string
  new_trace_id: string
  resumed_from_iteration: number
  status: string
  message: string
}

/** DELETE /checkpoints/{trace_id} 响应 (DeleteResponse). */
export interface DeleteCheckpointResponse {
  trace_id: string
  deleted_count: number
}

// ─── 客户端 ─────────────────────────────────────────────────────────────────

class WorkflowOpsClient {
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

  // ── 调度: /api/v1/workflows/schedules 系列 ────────────────────────────────

  /** GET /workflows/schedules — 调度列表 */
  async listSchedules(limit: number = 50): Promise<WorkflowScheduleItem[]> {
    const response = await this.client.get('/workflows/schedules', { params: { limit } })
    const payload = response.data
    return Array.isArray(payload) ? payload : payload?.items ?? []
  }

  /** GET /workflows/schedules/{schedule_id} — 调度详情(含 inputs/run_at/cron) */
  async getSchedule(scheduleId: string): Promise<WorkflowScheduleRecord> {
    const response = await this.client.get(`/workflows/schedules/${scheduleId}`)
    return response.data
  }

  /** POST /workflows/{workflow_id}/schedule — 创建调度(一次性或 cron) */
  async createSchedule(workflowId: string, payload: CreateSchedulePayload): Promise<WorkflowScheduleRecord> {
    const response = await this.client.post(`/workflows/${workflowId}/schedule`, {
      inputs: payload.inputs ?? {},
      delay_seconds: payload.delay_seconds ?? 0,
      run_at: payload.run_at ?? null,
      cron: payload.cron ?? null,
    })
    return response.data
  }

  /** POST /workflows/schedules/run-due — 手动触发到期调度 */
  async runDueSchedules(limit: number = 20): Promise<RunDueResult[]> {
    const response = await this.client.post('/workflows/schedules/run-due', null, { params: { limit } })
    const payload = response.data
    return Array.isArray(payload) ? payload : []
  }

  // ── 运行回放: /api/v1/workflows/runs 系列 ─────────────────────────────────

  /** GET /workflows/runs — 运行历史列表 */
  async listRuns(limit: number = 50): Promise<WorkflowRunItem[]> {
    const response = await this.client.get('/workflows/runs', { params: { limit } })
    const payload = response.data
    return Array.isArray(payload) ? payload : payload?.items ?? []
  }

  /** GET /workflows/runs/{run_id} — 运行详情(逐节点结果 + 时间线回放) */
  async getRunDetail(runId: string): Promise<WorkflowRunDetail> {
    const response = await this.client.get(`/workflows/runs/${runId}`)
    return response.data
  }

  /** POST /workflows/runs/{run_id}/resume-approved — 审批后恢复运行 */
  async resumeApprovedRun(runId: string, approvalId: string): Promise<WorkflowRunItem> {
    const response = await this.client.post(`/workflows/runs/${runId}/resume-approved`, {
      approval_id: approvalId,
    })
    return response.data
  }

  // ── 断点恢复: /api/v1/checkpoints 系列 ────────────────────────────────────

  /** GET /checkpoints — 可恢复 run 列表 (status=running/paused/failed) */
  async listCheckpoints(limit: number = 20): Promise<CheckpointListResponse> {
    const response = await this.client.get('/checkpoints', { params: { limit } })
    return response.data
  }

  /** GET /checkpoints/{trace_id} — 指定 run 的全部 checkpoint */
  async getCheckpointDetail(traceId: string): Promise<CheckpointDetail> {
    const response = await this.client.get(`/checkpoints/${traceId}`)
    return response.data
  }

  /** POST /checkpoints/{trace_id}/resume — 从 checkpoint 恢复执行 */
  async resumeCheckpoint(traceId: string, payload: ResumeCheckpointPayload = {}): Promise<ResumeCheckpointResponse> {
    const response = await this.client.post(`/checkpoints/${traceId}/resume`, {
      extra_context: payload.extra_context ?? {},
      from_iteration: payload.from_iteration ?? null,
    })
    return response.data
  }

  /** DELETE /checkpoints/{trace_id} — 清理指定 run 的 checkpoint */
  async deleteCheckpoints(traceId: string): Promise<DeleteCheckpointResponse> {
    const response = await this.client.delete(`/checkpoints/${traceId}`)
    return response.data
  }
}

export const workflowOps = new WorkflowOpsClient()
export default workflowOps
