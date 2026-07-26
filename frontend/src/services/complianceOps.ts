import axios, { AxiosInstance } from 'axios'

/**
 * Compliance operations service — GDPR 数据主体权利 + SOC2 合规端点。
 * 已于 2026-07-26 对照 backend 真实路由表核对 (TestClient 枚举 app.routes):
 *
 * 1. GDPR (backend/app/api/gdpr.py, 前缀 /api/v1/gdpr, startup 时已挂载):
 *    POST /gdpr/erase                       — 删除权 Art.17 {user_id, tenant_id?}
 *    POST /gdpr/export                      — 导出权 Art.20 {user_id, tenant_id?}
 *    GET  /gdpr/deletions?user_id=          — 删除请求记录列表
 *    GET  /gdpr/deletions/{request_id}      — 删除证明
 *    POST /gdpr/pii/scan                    — PII 扫描 {text}
 *    POST /gdpr/pii/mask                    — PII 脱敏 {text, strategy: mask|hash|remove|generalize}
 *    GET  /gdpr/residency                   — 数据驻留配置 {enabled, default_region, rules}
 *    PUT  /gdpr/residency/{tenant_id}       — 设置驻留规则 {region, allowed_regions?, block_cross_border?}
 *
 * 2. SOC2 合规 (backend/app/api/compliance.py, 前缀 /api/v1/compliance, startup 时已挂载):
 *    GET  /compliance/evidence/controls     — 已注册 SOC2 控制点
 *    POST /compliance/evidence/collect      — 收集证据 (control_id 为 query 参数, 可选)
 *    GET  /compliance/evidence/report       — 证据收集报告
 *    GET  /compliance/tsc/matrix?category=  — Trust Services Criteria 追溯矩阵
 *    POST /compliance/changes               — 创建变更 {title, description?, change_type?, risk_level?, requester?}
 *    GET  /compliance/changes?status_filter=&risk= — 变更列表
 *    POST /compliance/changes/{id}/approve  — 审批变更 (approver/comment 为 query 参数)
 *    GET  /compliance/changes/{id}/audit-trail — 变更审计轨迹
 *    POST /compliance/incidents             — 报告事件 {title, description?, category?, severity?, reporter?, affected_tenants?}
 *    GET  /compliance/incidents?severity=&phase= — 事件列表
 *    GET  /compliance/incidents/{id}/sla    — 事件 SLA 合规检查
 *    GET  /compliance/soc2/report           — SOC2 就绪度报告 (自动验证)
 *    GET  /compliance/soc2/evidence/{control_id} — 指定控制点证据
 *
 * 枚举值 (与 backend core 对齐):
 *   region: global|eu|cn|us|apac
 *   pii type: email|phone_cn|phone_intl|id_card_cn|ip_address|bank_card|url_with_params
 *   change_type: code|config|infrastructure|database|security|dependency
 *   change risk: low|medium|high|critical
 *   incident category: data_breach|unauthorized_access|malware|denial_of_service|insider_threat|supply_chain|misconfiguration|other
 *   incident severity: critical|high|medium|low
 *
 * 本模块不复用 services/api.ts(由编排者统一维护), 自建 axios 实例,
 * 鉴权逻辑(localStorage auth_token -> Bearer)与 governanceOps.ts 一致。
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

// ─── GDPR 类型 (与 backend/app/api/gdpr.py 响应模型对齐) ──────────────────────

export interface EraseResult {
  request_id: string
  user_id: string
  deleted_counts: Record<string, number>
  total_deleted: number
  errors: string[]
  success: boolean
  completed_at: string
}

export interface ExportResult {
  request_id: string
  user_id: string
  record_counts: Record<string, number>
  total_records: number
  data: Record<string, any>
  exported_at: string
}

export interface DeletionRecord {
  request_id: string
  user_id: string
  total_deleted: number
  success: boolean
  completed_at: string
}

export interface PIIMatch {
  type: string
  value: string
  start: number
  end: number
  confidence: number
}

export interface PIIScanResult {
  has_pii: boolean
  pii_count: number
  matches: PIIMatch[]
}

export interface PIIMaskResult {
  original_length: number
  masked_text: string
  pii_count: number
}

export interface ResidencyRule {
  region: string
  allowed_regions: string[]
  block_cross_border: boolean
}

export interface ResidencyConfig {
  enabled: boolean
  default_region: string
  rules: Record<string, ResidencyRule>
}

// ─── SOC2 合规类型 (与 backend/app/core/compliance/* to_dict 对齐) ─────────────

export interface TSCMapping {
  criteria_id: string
  criteria_name: string
  category: string
  description: string
  implementation: string
  evidence_source: string
  status: string
  notes: string
}

export interface TSCMatrixResponse {
  matrix: TSCMapping[]
  summary: Record<string, number>
  compliance_score: number
}

export interface ChangeRecord {
  change_id: string
  title: string
  description: string
  change_type: string
  risk_level: string
  status: string
  requester: string
  created_at: string
  updated_at: string
  required_approvals: number
  approvals: Array<{ approver: string; role: string; decision: string; comment: string; timestamp: string }>
  [key: string]: any
}

export interface IncidentRecord {
  incident_id: string
  title: string
  description: string
  category: string
  severity: string
  phase: string
  detected_at: string
  contained_at: string | null
  resolved_at: string | null
  closed_at: string | null
  affected_tenants: string[]
  [key: string]: any
}

export type MaskStrategy = 'mask' | 'hash' | 'remove' | 'generalize'

// ─── 客户端 ─────────────────────────────────────────────────────────────────

class ComplianceOpsClient {
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

  // ── GDPR 数据主体权利 ──────────────────────────────────────────────────────

  /** POST /gdpr/erase — 删除权 (Art.17) */
  async eraseUserData(userId: string, tenantId: string = ''): Promise<EraseResult> {
    const response = await this.client.post('/gdpr/erase', { user_id: userId, tenant_id: tenantId })
    return response.data
  }

  /** POST /gdpr/export — 导出权 (Art.20), 返回原始响应供页面下载 */
  async exportUserData(userId: string, tenantId: string = ''): Promise<ExportResult> {
    const response = await this.client.post('/gdpr/export', { user_id: userId, tenant_id: tenantId })
    return response.data
  }

  /** GET /gdpr/deletions — 删除请求记录 */
  async listDeletions(userId?: string): Promise<DeletionRecord[]> {
    const response = await this.client.get('/gdpr/deletions', {
      params: userId ? { user_id: userId } : {},
    })
    const payload = response.data
    return Array.isArray(payload) ? payload : []
  }

  /** GET /gdpr/deletions/{request_id} — 删除证明 */
  async getDeletionProof(requestId: string): Promise<Record<string, any>> {
    const response = await this.client.get(`/gdpr/deletions/${requestId}`)
    return response.data
  }

  // ── PII 扫描 / 脱敏 ───────────────────────────────────────────────────────

  /** POST /gdpr/pii/scan */
  async scanPii(text: string): Promise<PIIScanResult> {
    const response = await this.client.post('/gdpr/pii/scan', { text })
    return response.data
  }

  /** POST /gdpr/pii/mask — strategy: mask | hash | remove | generalize */
  async maskPii(text: string, strategy: MaskStrategy = 'mask'): Promise<PIIMaskResult> {
    const response = await this.client.post('/gdpr/pii/mask', { text, strategy })
    return response.data
  }

  // ── 数据驻留 ──────────────────────────────────────────────────────────────

  /** GET /gdpr/residency */
  async getResidency(): Promise<ResidencyConfig> {
    const response = await this.client.get('/gdpr/residency')
    return response.data
  }

  /** PUT /gdpr/residency/{tenant_id} */
  async setResidencyRule(
    tenantId: string,
    rule: { region: string; allowed_regions: string[]; block_cross_border: boolean },
  ): Promise<ResidencyRule & { tenant_id: string }> {
    const response = await this.client.put(`/gdpr/residency/${encodeURIComponent(tenantId)}`, rule)
    return response.data
  }

  // ── SOC2: TSC 矩阵 ────────────────────────────────────────────────────────

  /** GET /compliance/tsc/matrix */
  async getTscMatrix(category?: string): Promise<TSCMatrixResponse> {
    const response = await this.client.get('/compliance/tsc/matrix', {
      params: category ? { category } : {},
    })
    const payload = response.data
    // category 过滤时响应为 {mappings, category}, 归一化为矩阵结构
    if (payload && Array.isArray(payload.mappings)) {
      return { matrix: payload.mappings, summary: {}, compliance_score: 0 }
    }
    return {
      matrix: Array.isArray(payload?.matrix) ? payload.matrix : [],
      summary: payload?.summary ?? {},
      compliance_score: payload?.compliance_score ?? 0,
    }
  }

  // ── SOC2: 变更管理 ────────────────────────────────────────────────────────

  /** GET /compliance/changes */
  async listChanges(filters: { status_filter?: string; risk?: string } = {}): Promise<ChangeRecord[]> {
    const response = await this.client.get('/compliance/changes', { params: filters })
    return Array.isArray(response.data?.changes) ? response.data.changes : []
  }

  /** POST /compliance/changes */
  async createChange(req: {
    title: string
    description?: string
    change_type?: string
    risk_level?: string
    requester?: string
  }): Promise<ChangeRecord | null> {
    const response = await this.client.post('/compliance/changes', req)
    return response.data?.change ?? null
  }

  /** POST /compliance/changes/{id}/approve — approver/comment 为 query 参数 */
  async approveChange(changeId: string, approver: string = 'admin', comment: string = ''): Promise<ChangeRecord | null> {
    const response = await this.client.post(`/compliance/changes/${encodeURIComponent(changeId)}/approve`, null, {
      params: { approver, comment },
    })
    return response.data?.change ?? null
  }

  // ── SOC2: 事件响应 ────────────────────────────────────────────────────────

  /** GET /compliance/incidents */
  async listIncidents(filters: { severity?: string; phase?: string } = {}): Promise<IncidentRecord[]> {
    const response = await this.client.get('/compliance/incidents', { params: filters })
    return Array.isArray(response.data?.incidents) ? response.data.incidents : []
  }

  /** POST /compliance/incidents */
  async reportIncident(req: {
    title: string
    description?: string
    category?: string
    severity?: string
    reporter?: string
    affected_tenants?: string[]
  }): Promise<IncidentRecord | null> {
    const response = await this.client.post('/compliance/incidents', req)
    return response.data?.incident ?? null
  }

  /** GET /compliance/soc2/report — 就绪度报告 (自动验证, 结构宽松) */
  async getSoc2Report(): Promise<Record<string, any>> {
    const response = await this.client.get('/compliance/soc2/report')
    return response.data
  }

  /** 触发浏览器下载 JSON */
  downloadJson(payload: unknown, filename: string): void {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    URL.revokeObjectURL(url)
  }
}

export const complianceOps = new ComplianceOpsClient()
export default complianceOps
