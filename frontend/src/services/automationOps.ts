import axios, { AxiosInstance } from 'axios'

/**
 * Automation operations client — aligned with real backend routers
 * (re-verified via TestClient route enumeration on 2026-07-26):
 *
 * backend/app/api/browser.py          prefix /api/v1/browser           (MOUNTED)
 *   GET    /sessions                          list sessions
 *   POST   /sessions                          create session (503 when no browser backend)
 *   GET    /sessions/{id}                     session detail
 *   GET    /sessions/{id}/correlation         correlation/recovery info
 *   POST   /sessions/{id}/goto                { url }
 *   POST   /sessions/{id}/click               { selector }
 *   POST   /sessions/{id}/fill                { selector, value }
 *   POST   /sessions/{id}/extract-text        { selector }
 *   POST   /sessions/{id}/wait-for            { selector }
 *   POST   /sessions/{id}/screenshot          { path } — saved server-side; data.path returned
 *   POST   /sessions/{id}/close               close session
 *   DELETE /sessions/{id}                     delete session
 *
 * backend/app/api/browser_advanced.py prefix /api/v1/browser/advanced  (MOUNTED)
 *   network:  POST /network/requests|responses|summary|clear
 *   elements: POST /elements/tree|find, POST /elements/{ref}[?session_id=],
 *             POST /elements/{ref}/click[?session_id=], POST /elements/{ref}/fill[?session_id=]
 *   console:  POST /console/messages|errors|summary|clear
 *   snapshot: POST /snapshot, POST /snapshot/compare, POST /snapshot/diff
 *   NOTE: elements/{ref}* take session_id as a QUERY parameter (FastAPI scalar).
 *
 * backend/app/api/desktop.py          prefix /api/v1/desktop           (MOUNTED)
 *   GET  /sessions, POST /sessions, GET /sessions/{id},
 *   POST /sessions/{id}/actions, POST /sessions/{id}/close
 */

export interface BrowserSessionCreateRequest {
  trace_id?: string
  run_id?: string
  tenant_id?: string
  user_id?: string
}

export interface BrowserAction {
  action: string
  ok: boolean
  detail: string
  data: Record<string, unknown>
}

export interface BrowserSession {
  session_id: string
  trace_id?: string | null
  run_id?: string | null
  tenant_id: string
  user_id: string
  current_url?: string | null
  active: boolean
  actions: BrowserAction[]
}

export interface NetworkSummary {
  total_requests: number
  total_responses: number
  failed_responses: number
  total_duration_ms: number
  average_response_time_ms: number
}

export interface ConsoleMessage {
  type: string
  text: string
  timestamp: number
  location?: string | null
}

export interface ConsoleSummary {
  total_messages: number
  error_count: number
  warning_count: number
  log_count: number
  has_errors: boolean
  has_warnings: boolean
}

export interface FoundElement {
  selector: string
  confidence: number
  reason: string
  text?: string | null
  tag_name?: string | null
}

export interface DesktopSession {
  session_id: string
  trace_id?: string | null
  run_id?: string | null
  tenant_id: string
  user_id: string
  provider?: string
  active: boolean
  metadata?: Record<string, unknown>
  provider_session_id?: string
  [key: string]: unknown
}

export interface DesktopActionRequest {
  action: string
  target?: string
  value?: string
  metadata?: Record<string, unknown>
}

/** True when the backend answered 503 — real Playwright backend unavailable. */
export function isBrowserUnavailable(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 503
}

export function errorMessage(error: unknown, fallback = 'Request failed'): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { detail?: unknown; message?: unknown } | undefined
    const detail = data?.detail ?? data?.message
    if (typeof detail === 'string') return detail
    if (detail && typeof detail === 'object' && 'message' in (detail as Record<string, unknown>)) {
      return String((detail as Record<string, unknown>).message)
    }
    if (error.message) return error.message
  }
  return error instanceof Error ? error.message : fallback
}

class AutomationOpsClient {
  private client: AxiosInstance

  constructor(baseURL: string = '/api/v1') {
    this.client = axios.create({
      baseURL,
      timeout: 60000,
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

  // ---------- browser.py: session control ----------

  async listBrowserSessions(): Promise<BrowserSession[]> {
    const resp = await this.client.get('/browser/sessions')
    return resp.data
  }

  async createBrowserSession(req: BrowserSessionCreateRequest = {}): Promise<BrowserSession> {
    const resp = await this.client.post('/browser/sessions', req)
    return resp.data
  }

  async getBrowserSession(sessionId: string): Promise<BrowserSession> {
    const resp = await this.client.get(`/browser/sessions/${encodeURIComponent(sessionId)}`)
    return resp.data
  }

  async browserGoto(sessionId: string, url: string): Promise<BrowserAction> {
    const resp = await this.client.post(`/browser/sessions/${encodeURIComponent(sessionId)}/goto`, { url })
    return resp.data
  }

  async browserClick(sessionId: string, selector: string): Promise<BrowserAction> {
    const resp = await this.client.post(`/browser/sessions/${encodeURIComponent(sessionId)}/click`, { selector })
    return resp.data
  }

  async browserFill(sessionId: string, selector: string, value: string): Promise<BrowserAction> {
    const resp = await this.client.post(`/browser/sessions/${encodeURIComponent(sessionId)}/fill`, { selector, value })
    return resp.data
  }

  async browserExtractText(sessionId: string, selector: string): Promise<BrowserAction> {
    const resp = await this.client.post(`/browser/sessions/${encodeURIComponent(sessionId)}/extract-text`, { selector })
    return resp.data
  }

  async browserWaitFor(sessionId: string, selector: string): Promise<BrowserAction> {
    const resp = await this.client.post(`/browser/sessions/${encodeURIComponent(sessionId)}/wait-for`, { selector })
    return resp.data
  }

  async browserScreenshot(sessionId: string, path: string): Promise<BrowserAction> {
    const resp = await this.client.post(`/browser/sessions/${encodeURIComponent(sessionId)}/screenshot`, { path })
    return resp.data
  }

  async closeBrowserSession(sessionId: string): Promise<{ closed: boolean }> {
    const resp = await this.client.post(`/browser/sessions/${encodeURIComponent(sessionId)}/close`)
    return resp.data
  }

  // ---------- browser_advanced.py (mounted) ----------

  async networkRequests(sessionId: string, urlPattern?: string): Promise<{ requests: Record<string, unknown>[]; count: number }> {
    const resp = await this.client.post('/browser/advanced/network/requests', { session_id: sessionId, url_pattern: urlPattern ?? null })
    return resp.data
  }

  async networkSummary(sessionId: string): Promise<NetworkSummary> {
    const resp = await this.client.post('/browser/advanced/network/summary', { session_id: sessionId })
    return resp.data
  }

  async clearNetwork(sessionId: string): Promise<{ success: boolean }> {
    const resp = await this.client.post('/browser/advanced/network/clear', { session_id: sessionId })
    return resp.data
  }

  async consoleMessages(sessionId: string, onlyErrors = false): Promise<{ messages: ConsoleMessage[]; count: number }> {
    const resp = await this.client.post('/browser/advanced/console/messages', { session_id: sessionId, only_errors: onlyErrors })
    return resp.data
  }

  async consoleSummary(sessionId: string): Promise<ConsoleSummary> {
    const resp = await this.client.post('/browser/advanced/console/summary', { session_id: sessionId })
    return resp.data
  }

  async findElements(sessionId: string, description: string, limit = 5): Promise<{ elements: FoundElement[]; count: number }> {
    const resp = await this.client.post('/browser/advanced/elements/find', { session_id: sessionId, description, limit })
    return resp.data
  }

  async elementTree(sessionId: string): Promise<Record<string, unknown>> {
    const resp = await this.client.post('/browser/advanced/elements/tree', { session_id: sessionId })
    return resp.data
  }

  /** elements/{ref}/click — session_id is a query parameter per the FastAPI signature. */
  async clickElementByRef(sessionId: string, ref: string): Promise<{ success: boolean; message: string }> {
    const resp = await this.client.post(`/browser/advanced/elements/${encodeURIComponent(ref)}/click`, null, {
      params: { session_id: sessionId },
    })
    return resp.data
  }

  /** elements/{ref}/fill — session_id query param + body value. */
  async fillElementByRef(sessionId: string, ref: string, value: string): Promise<{ success: boolean; message: string }> {
    const resp = await this.client.post(
      `/browser/advanced/elements/${encodeURIComponent(ref)}/fill`,
      { session_id: sessionId, ref, value },
      { params: { session_id: sessionId } },
    )
    return resp.data
  }

  async captureSnapshot(sessionId: string, label: string): Promise<Record<string, unknown>> {
    const resp = await this.client.post('/browser/advanced/snapshot', { session_id: sessionId, label })
    return resp.data
  }

  async compareSnapshots(sessionId: string, beforeLabel: string, afterLabel: string): Promise<Record<string, unknown>> {
    const resp = await this.client.post('/browser/advanced/snapshot/compare', {
      session_id: sessionId,
      before_label: beforeLabel,
      after_label: afterLabel,
    })
    return resp.data
  }

  // ---------- desktop.py (mounted) ----------

  async listDesktopSessions(): Promise<DesktopSession[]> {
    const resp = await this.client.get('/desktop/sessions')
    return resp.data
  }

  async createDesktopSession(provider = 'ui-tars'): Promise<DesktopSession> {
    const resp = await this.client.post('/desktop/sessions', { provider })
    return resp.data
  }

  async sendDesktopAction(sessionId: string, req: DesktopActionRequest): Promise<Record<string, unknown>> {
    const resp = await this.client.post(`/desktop/sessions/${encodeURIComponent(sessionId)}/actions`, req)
    return resp.data
  }

  async closeDesktopSession(sessionId: string): Promise<{ closed: boolean }> {
    const resp = await this.client.post(`/desktop/sessions/${encodeURIComponent(sessionId)}/close`)
    return resp.data
  }
}

export const automationOps = new AutomationOpsClient()
export default automationOps
