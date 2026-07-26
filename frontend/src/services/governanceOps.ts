import axios, { AxiosInstance } from 'axios'

/**
 * Governance operations service — 审批 / 审计 / 备份三组治理端点，
 * 已于 2026-07-26 对照 backend 真实路由表核对:
 *
 * 1. 审批 (backend/app/api/approvals.py, 已挂载):
 *    GET    /api/v1/approvals                      — 列表 (limit/status/tenant_id)
 *    GET    /api/v1/approvals/{id}                 — 详情
 *    POST   /api/v1/approvals/{id}/approve         — 批准 (body: {reason}; decided_by 由服务端绑定 principal, 前端绝不传)
 *    POST   /api/v1/approvals/{id}/reject          — 拒绝 (同上)
 *    POST   /api/v1/approvals/{id}/execute         — 执行已批准的请求
 *    GET    /api/v1/approvals/{id}/correlation     — 关联追踪(页面暂未使用, 保留方法)
 *
 * 2. 审计 (backend/app/api/audit.py, 已挂载, 前缀 /api/v1/audit-logs):
 *    GET /api/v1/audit-logs                        — 列表 (分页 + action/resource_type/outcome/actor_id 等过滤)
 *    GET /api/v1/audit-logs/summary                — 统计 (count/by_action/by_resource_type/by_outcome)
 *    GET /api/v1/audit-logs/verify                 — 哈希链验证
 *    GET /api/v1/audit-logs/export/csv             — CSV 导出 (流)
 *    GET /api/v1/audit-logs/export/json            — JSON 导出
 *    注意: audit_enhanced.py (/api/v1/audit/* 高级搜索/分析/合规报告/XML/PDF)
 *    当前未挂载到 main.py, 页面中对应功能一律置灰 coming soon。
 *
 * 3. 备份 (已挂载):
 *    backup_scheduler.py: POST /api/v1/backup/run, GET /list, GET /status,
 *      POST /restore/{id}, POST /verify/{id}, DELETE /cleanup?keep=N
 *    backup_qdrant.py:    POST /api/v1/backup/qdrant/snapshot, GET /snapshots,
 *      POST /restore, POST /cleanup
 *    注意: backup.py (备份类型/调度 CRUD) 与 backup_monitoring.py (告警/健康)
 *    当前未挂载到 main.py, 页面中对应功能置灰 coming soon。
 *
 * 本模块不复用 services/api.ts(由另一代理维护), 自建 axios 实例,
 * 鉴权逻辑(localStorage auth_token -> Bearer)与 api.ts / workflowOps.ts 一致。
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

// ─── 审批类型 (与 backend/app/core/approvals.py 对齐, snake_case 原样保留) ──────

export interface ApprovalRecord {
  id: string
  tenant_id: string
  actor_id: string
  trace_id: string
  resource_type: string
  resource_id: string
  action: string
  /** low | medium | high | critical */
  risk_level: string
  /** pending | approved | rejected | executed */
  status: string
  reason: string
  arguments_preview: Record<string, any>
  arguments: Record<string, any>
  decided_by: string | null
  decided_at: string | null
  decision_reason: string | null
  executed_by: string | null
  executed_at: string | null
  execution_trace_id: string | null
  linked_policy_trace_id: string | null
  created_at: string
}

/** POST /approvals/{id}/execute 响应 (ToolCallRecord, 仅声明页面用到的字段). */
export interface ApprovalExecuteResult {
  success?: boolean
  error?: string | null
  [key: string]: any
}

// ─── 审计类型 (与 backend/app/core/audit.py 对齐) ──────────────────────────────

export interface AuditLogRecord {
  id: string
  tenant_id: string
  actor_id: string
  action: string
  resource_type: string
  resource_id: string | null
  outcome: string
  trace_id: string | null
  run_id: string | null
  workflow_id: string | null
  details: Record<string, any>
  created_at: string
  prev_hash: string | null
  hash: string | null
  signature: string | null
  snapshot: Record<string, any>
}

export interface AuditListResponse {
  data: AuditLogRecord[]
  pagination: { limit: number; offset: number; total: number; has_more: boolean }
}

export interface AuditChainVerification {
  valid: boolean
  checked: number
  signed: number
  signature_valid: boolean
  broken_at: string | null
  reason: string | null
}

export interface AuditSummary {
  count: number
  by_action: Record<string, number>
  by_resource_type: Record<string, number>
  by_outcome: Record<string, number>
  [key: string]: any
}

// ─── 备份类型 (与 backup_scheduler.py / backup_qdrant.py 响应模型对齐) ──────────

export interface BackupRunResult {
  backup_id: string
  success: boolean
  started_at: string
  completed_at: string | null
  total_size_bytes: number
  components: Array<{
    component: string
    success: boolean
    files: string[]
    size_bytes: number
    duration_seconds: number
    error: string | null
  }>
}

export interface BackupListItem {
  backup_id: string
  created_at: string
  success: boolean
  total_size_bytes: number
  components: any[]
  path: string
}

export interface BackupSchedulerStatus {
  enabled: boolean
  running: boolean
  schedule_cron: string
  backup_dir: string
  last_run: string | null
  last_success: boolean | null
  last_backup_id: string | null
  retention_days: number
  keep_latest: number
}

export interface QdrantSnapshotListResponse {
  collection: string
  snapshots: Array<Record<string, any>>
  total: number
}

// ─── 客户端 ─────────────────────────────────────────────────────────────────

class GovernanceOpsClient {
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

  // ── 审批: /api/v1/approvals ────────────────────────────────────────────────

  /** GET /approvals — status 可选: pending/approved/rejected/executed; 不传为全部 */
  async listApprovals(params: { limit?: number; status?: string } = {}): Promise<ApprovalRecord[]> {
    const response = await this.client.get('/approvals', {
      params: { limit: params.limit ?? 200, ...(params.status ? { status: params.status } : {}) },
    })
    const payload = response.data
    return Array.isArray(payload) ? payload : []
  }

  /** GET /approvals/{id} — 详情 */
  async getApproval(id: string): Promise<ApprovalRecord> {
    const response = await this.client.get(`/approvals/${id}`)
    return response.data
  }

  /**
   * POST /approvals/{id}/approve — 批准。
   * decided_by 由服务端强制绑定为已认证 principal (P0-07), 前端只传 reason。
   */
  async approveRequest(id: string, reason: string): Promise<ApprovalRecord> {
    const response = await this.client.post(`/approvals/${id}/approve`, { reason })
    return response.data
  }

  /** POST /approvals/{id}/reject — 拒绝 (同样不传 decided_by) */
  async rejectRequest(id: string, reason: string): Promise<ApprovalRecord> {
    const response = await this.client.post(`/approvals/${id}/reject`, { reason })
    return response.data
  }

  /** POST /approvals/{id}/execute — 执行已批准的请求 */
  async executeApproved(id: string): Promise<ApprovalExecuteResult> {
    const response = await this.client.post(`/approvals/${id}/execute`)
    return response.data
  }

  // ── 审计: /api/v1/audit-logs ───────────────────────────────────────────────

  /** GET /audit-logs — 分页 + 过滤列表 */
  async listAuditLogs(params: {
    limit?: number
    offset?: number
    action?: string
    resource_type?: string
    outcome?: string
    actor_id?: string
  } = {}): Promise<AuditListResponse> {
    const response = await this.client.get('/audit-logs', {
      params: { limit: 50, offset: 0, ...params },
    })
    return response.data
  }

  /** GET /audit-logs/summary — 统计 (响应经 build_linked_summary 包装, 取 primary) */
  async getAuditSummary(): Promise<AuditSummary> {
    const response = await this.client.get('/audit-logs/summary')
    const payload = response.data
    const primary = payload?.primary ?? payload?.audit ?? payload ?? {}
    return {
      count: primary.count ?? 0,
      by_action: primary.by_action ?? {},
      by_resource_type: primary.by_resource_type ?? {},
      by_outcome: primary.by_outcome ?? {},
    }
  }

  /** GET /audit-logs/verify — 哈希链完整性验证 */
  async verifyAuditChain(): Promise<AuditChainVerification> {
    const response = await this.client.get('/audit-logs/verify')
    return response.data
  }

  /** GET /audit-logs/export/csv — 触发浏览器下载 CSV */
  async exportAuditCsv(filters: { action?: string; resource_type?: string; outcome?: string } = {}): Promise<void> {
    const response = await this.client.get('/audit-logs/export/csv', {
      params: filters,
      responseType: 'blob',
    })
    this.downloadBlob(response.data, 'audit-logs.csv')
  }

  /** GET /audit-logs/export/json — 拉取 JSON 并触发浏览器下载 */
  async exportAuditJson(filters: { action?: string; resource_type?: string; outcome?: string } = {}): Promise<void> {
    const response = await this.client.get('/audit-logs/export/json', { params: filters })
    const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' })
    this.downloadBlob(blob, 'audit-logs.json')
  }

  private downloadBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    URL.revokeObjectURL(url)
  }

  // ── 备份调度: /api/v1/backup (backup_scheduler.py, 已挂载) ─────────────────

  /** POST /backup/run — 手动触发一次全量备份 */
  async runBackup(): Promise<BackupRunResult> {
    const response = await this.client.post('/backup/run')
    return response.data
  }

  /** GET /backup/list — 备份列表 */
  async listBackups(): Promise<{ backups: BackupListItem[]; total: number }> {
    const response = await this.client.get('/backup/list')
    return response.data
  }

  /** GET /backup/status — 调度器状态 */
  async getBackupStatus(): Promise<BackupSchedulerStatus> {
    const response = await this.client.get('/backup/status')
    return response.data
  }

  /** POST /backup/restore/{backup_id} — 从备份恢复 */
  async restoreBackup(backupId: string): Promise<{ backup_id: string; success: boolean; message: string }> {
    const response = await this.client.post(`/backup/restore/${backupId}`)
    return response.data
  }

  /** POST /backup/verify/{backup_id} — 校验备份完整性 */
  async verifyBackup(backupId: string): Promise<{ backup_id: string; valid: boolean; message: string }> {
    const response = await this.client.post(`/backup/verify/${backupId}`)
    return response.data
  }

  /** DELETE /backup/cleanup?keep=N — 清理旧备份 */
  async cleanupBackups(keep: number = 7): Promise<{ removed_count: number; message: string }> {
    const response = await this.client.delete('/backup/cleanup', { params: { keep } })
    return response.data
  }

  // ── Qdrant 快照: /api/v1/backup/qdrant (backup_qdrant.py, 已挂载) ──────────

  /** POST /backup/qdrant/snapshot — collection_name 为空则全量快照 */
  async createQdrantSnapshot(collectionName?: string): Promise<Record<string, any>> {
    const response = await this.client.post('/backup/qdrant/snapshot', {
      collection_name: collectionName || null,
    })
    return response.data
  }

  /** GET /backup/qdrant/snapshots?collection_name= — 列出某集合的快照 */
  async listQdrantSnapshots(collectionName: string): Promise<QdrantSnapshotListResponse> {
    const response = await this.client.get('/backup/qdrant/snapshots', {
      params: { collection_name: collectionName },
    })
    return response.data
  }

  /** POST /backup/qdrant/restore — 从快照恢复集合 */
  async restoreQdrantSnapshot(collectionName: string, snapshotName: string): Promise<Record<string, any>> {
    const response = await this.client.post('/backup/qdrant/restore', {
      collection_name: collectionName,
      snapshot_name: snapshotName,
    })
    return response.data
  }

  /** POST /backup/qdrant/cleanup — 清理旧快照 */
  async cleanupQdrantSnapshots(keepLatest?: number): Promise<{ deleted_count: number; message: string }> {
    const response = await this.client.post('/backup/qdrant/cleanup', {
      keep_latest: keepLatest ?? null,
    })
    return response.data
  }
}

export const governanceOps = new GovernanceOpsClient()
export default governanceOps
