import axios, { AxiosInstance } from 'axios'

/**
 * Security operations service — 封装已核对的真实后端端点
 * (来源: backend/app/api/sso.py, backend/app/api/auth.py):
 *
 * 1. SSO        GET /api/v1/sso/providers, GET /api/v1/sso/status
 * 2. MFA        POST /api/v1/auth/mfa/setup, POST /api/v1/auth/mfa/verify
 * 3. Sessions   GET /api/v1/auth/sessions, DELETE /api/v1/auth/sessions/{id},
 *               POST /api/v1/auth/sessions/revoke-all
 *
 * 说明:
 * - 本模块不复用 services/api.ts(该文件由另一代理维护), 自建 axios 实例,
 *   鉴权逻辑(localStorage auth_token -> Bearer)与 api.ts 保持一致。
 * - 后端不存在 "MFA 禁用" / "MFA 状态查询" 端点, 页面中对应入口置灰
 *   coming soon, 绝不虚构请求。
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

// ─── 类型(与后端模型字段对齐, snake_case 原样保留) ────────────────────────────

/** POST /auth/mfa/setup 请求体 (MFASetupRequest). method: totp | sms | email */
export interface MFASetupPayload {
  method: string
}

/** POST /auth/mfa/setup 响应 (MFASetupResponse). */
export interface MFASetupResponse {
  /** TOTP 密钥 (method=totp) */
  secret: string | null
  /** otpauth:// URI (method=totp) */
  provisioning_uri: string | null
  backup_codes: string[] | null
  /** challenge ID (method=sms/email) */
  challenge_id: string | null
}

/** POST /auth/mfa/verify 响应. */
export interface MFAVerifyResponse {
  verified: boolean
}

/** GET /auth/sessions 单个会话项 (SessionListResponse.sessions[]). */
export interface SessionItem {
  session_id: string
  created_at: string
  last_activity: string
  ip_address: string | null
  device_name: string | null
  mfa_verified: boolean
  trusted_device: boolean
}

/** GET /sso/providers 响应 (脱敏 OIDC 提供方列表 + SAML 状态). */
export interface SSOProvidersResponse {
  oidc_providers: Array<Record<string, any>>
  saml: {
    status: string
    enabled: boolean
    require_signature: boolean
    message?: string
  }
}

/** GET /sso/status 响应 (sso_status). */
export interface SSOStatusResponse {
  oidc: {
    status: string
    features: string[]
    providers_configured: number
  }
  saml: Record<string, any>
  webauthn: Record<string, any>
  ldap: Record<string, any>
  jwt_backend: Record<string, any>
  user_storage_mode: string
  session_issuer_available: boolean
}

// ─── 客户端 ─────────────────────────────────────────────────────────────────

class SecurityOpsClient {
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

  // ── SSO: /api/v1/sso 系列 (backend: api/sso.py) ───────────────────────────

  /** GET /sso/providers — 已配置 OIDC 提供方列表(脱敏) + SAML 状态 */
  async listSSOProviders(): Promise<SSOProvidersResponse> {
    const response = await this.client.get('/sso/providers')
    return response.data
  }

  /** GET /sso/status — SSO 能力状态 (OIDC GA / SAML beta / LDAP / WebAuthn) */
  async getSSOStatus(): Promise<SSOStatusResponse> {
    const response = await this.client.get('/sso/status')
    return response.data
  }

  // ── MFA: /api/v1/auth/mfa 系列 (backend: api/sso.py auth_router) ──────────

  /** POST /auth/mfa/setup — 开始 MFA 设置 (totp 返回 secret+provisioning_uri) */
  async setupMFA(method: string): Promise<MFASetupResponse> {
    const response = await this.client.post('/auth/mfa/setup', { method })
    return response.data
  }

  /** POST /auth/mfa/verify — 校验 MFA 验证码 */
  async verifyMFA(challengeId: string, code: string): Promise<MFAVerifyResponse> {
    const response = await this.client.post('/auth/mfa/verify', {
      challenge_id: challengeId,
      code,
    })
    return response.data
  }

  // ── Sessions: /api/v1/auth/sessions 系列 (backend: api/sso.py auth_router) ─

  /** GET /auth/sessions — 当前用户的活跃会话列表 */
  async listSessions(): Promise<SessionItem[]> {
    const response = await this.client.get('/auth/sessions')
    return response.data?.sessions ?? []
  }

  /** DELETE /auth/sessions/{session_id} — 吊销单个会话 */
  async revokeSession(sessionId: string): Promise<{ revoked: boolean }> {
    const response = await this.client.delete(`/auth/sessions/${sessionId}`)
    return response.data
  }

  /** POST /auth/sessions/revoke-all — 吊销全部会话 (exclude_current 默认为 true) */
  async revokeAllSessions(excludeCurrent: boolean = true): Promise<{ revoked_count: number }> {
    const response = await this.client.post('/auth/sessions/revoke-all', null, {
      params: { exclude_current: excludeCurrent },
    })
    return response.data
  }
}

export const securityOps = new SecurityOpsClient()
export default securityOps
