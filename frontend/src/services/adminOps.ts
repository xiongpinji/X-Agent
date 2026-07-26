import axios, { AxiosInstance, AxiosError } from 'axios'

/**
 * Admin operations service (A15/A16), aligned with the real backend routes
 * re-verified on 2026-07-26 against:
 * - backend/app/api/tenants.py       — /api/v1/tenants CRUD + usage + billing
 * - backend/app/api/tenant_quota.py  — /api/v1/tenant/quota, /api/v1/tenant/usage
 * - backend/app/api/billing.py       — /api/v1/billing plans/usage/quota/invoices/subscription
 * - backend/app/api/users.py         — /api/v1/users CRUD + role + activity
 *
 * All admin endpoints enforce the `security:manage` scope server-side; a
 * non-privileged caller receives HTTP 403. Callers should use `isForbidden`
 * to render a graceful permission notice instead of crashing.
 */

// ---------------------------------------------------------------------------
// Types (snake_case preserved, mirroring backend models)
// ---------------------------------------------------------------------------

/** TenantRecord from backend/app/core/admin.py */
export interface TenantRecord {
  id: string
  name: string
  plan: string
  created_at?: string
  updated_at?: string
}

/** UserRecord from backend/app/core/admin.py */
export interface AdminUserRecord {
  id: string
  email: string
  display_name: string
  role: string
  tenant_id: string
  locked_until?: string | null
  failed_login_attempts?: number
  created_at?: string
  updated_at?: string
}

/** GET /tenants/{id}/usage response body */
export interface TenantUsageResponse {
  tenant_id: string
  period: string
  start_date: string
  end_date: string
  usage: {
    runs: number
    agents: number
    memory_gb: number
    api_calls: number
    active_users: number
  }
}

/** GET /tenants/{id}/billing response body */
export interface TenantBillingResponse {
  tenant_id: string
  plan: string
  billing_month: string
  billing: {
    plan_amount: number
    usage_amount: number
    total_amount: number
    currency: string
    status: string
  }
  next_billing_date?: string
}

/** Per-resource breakdown item from the tenant quota manager report */
export interface QuotaBreakdownItem {
  used: number
  limit: number
  remaining: number
  usage_percent: number
}

/** GET /tenant/quota full report (backend/app/core/tenant_quota.py) */
export interface TenantQuotaReport {
  tenant_id: string
  limits: {
    max_agents: number
    max_workflows: number
    max_api_calls_per_day: number
    max_memory_items: number
    max_concurrent_runs: number
    max_storage_mb: number
  }
  usage: {
    agents_count: number
    workflows_count: number
    api_calls_today: number
    memory_items_count: number
    concurrent_runs: number
    storage_used_mb: number
    last_reset_date?: string
  }
  breakdown: Record<string, QuotaBreakdownItem>
}

/** PUT /tenant/quota request body (only provided fields are updated) */
export interface QuotaLimitsUpdate {
  max_agents?: number
  max_workflows?: number
  max_api_calls_per_day?: number
  max_memory_items?: number
  max_concurrent_runs?: number
  max_storage_mb?: number
}

/** PricingTierResponse from backend/app/api/billing.py */
export interface BillingPlan {
  id: string
  tier_name: string
  billing_model: string
  monthly_price?: string | null
  annual_price?: string | null
  api_call_price?: string | null
  token_price?: string | null
  storage_price?: string | null
  monthly_api_calls?: number | null
  monthly_tokens?: number | null
  storage_gb?: number | null
  features?: Record<string, any> | null
  description?: string | null
}

/** UsageResponse from /billing/usage */
export interface BillingUsageDay {
  date: string
  api_calls: number
  tokens_used: number
  storage_used_gb: string
  estimated_cost: string
}

/** InvoiceResponse from /billing/invoices */
export interface BillingInvoice {
  id: string
  invoice_number: string
  period_start: string
  period_end: string
  issue_date: string
  due_date: string
  subtotal: string
  tax: string
  discount: string
  total: string
  status: string
}

/** SubscriptionResponse from /billing/subscription */
export interface BillingSubscription {
  id: string
  status: string
  billing_model: string
  start_date: string
  end_date?: string | null
  renewal_date?: string | null
  auto_renew: boolean
  discount_percent: string
}

/** GET /users/{id}/activity response body */
export interface UserActivityResponse {
  user_id: string
  items: Array<Record<string, any>>
  pagination?: Record<string, any>
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

/** True when the backend rejected the call for missing admin scope. */
export function isForbidden(error: unknown): boolean {
  return (error as AxiosError)?.response?.status === 403
}

/** Extract a human-readable message from a backend error envelope. */
export function errorMessage(error: unknown, fallback: string): string {
  const err = error as AxiosError<any>
  const data = err?.response?.data
  return (
    data?.error?.message ||
    data?.detail ||
    data?.message ||
    err?.message ||
    fallback
  )
}

class AdminOpsClient {
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

  // --- Tenants (backend/app/api/tenants.py) — security:manage required ---

  async listTenants(): Promise<TenantRecord[]> {
    const response = await this.client.get('/tenants')
    const payload = response.data
    return Array.isArray(payload) ? payload : payload?.data ?? []
  }

  async createTenant(data: { name: string; plan?: string }): Promise<TenantRecord> {
    const response = await this.client.post('/tenants', data)
    return response.data
  }

  async getTenant(id: string): Promise<TenantRecord> {
    const response = await this.client.get(`/tenants/${id}`)
    return response.data
  }

  async updateTenant(id: string, data: { name?: string; plan?: string }): Promise<TenantRecord> {
    const response = await this.client.put(`/tenants/${id}`, data)
    return response.data
  }

  async deleteTenant(id: string): Promise<void> {
    await this.client.delete(`/tenants/${id}`)
  }

  /** GET /tenants/{id}/usage?period=day|week|month|year */
  async getTenantUsage(id: string, period: 'day' | 'week' | 'month' | 'year' = 'month'): Promise<TenantUsageResponse> {
    const response = await this.client.get(`/tenants/${id}/usage`, { params: { period } })
    return response.data
  }

  /** GET /tenants/{id}/billing?month=YYYY-MM */
  async getTenantBilling(id: string, month?: string): Promise<TenantBillingResponse> {
    const response = await this.client.get(`/tenants/${id}/billing`, {
      params: month ? { month } : {},
    })
    return response.data
  }

  // --- Tenant quota (backend/app/api/tenant_quota.py) ---

  /** GET /tenant/quota — full limits + usage + breakdown for current tenant. */
  async getTenantQuota(): Promise<TenantQuotaReport> {
    const response = await this.client.get('/tenant/quota')
    return response.data
  }

  /** PUT /tenant/quota — update quota limits (security:manage scope). */
  async updateTenantQuota(update: QuotaLimitsUpdate): Promise<any> {
    const response = await this.client.put('/tenant/quota', update)
    return response.data
  }

  // --- Billing (backend/app/api/billing.py) — current tenant scope ---

  /** GET /billing/plans */
  async listBillingPlans(): Promise<BillingPlan[]> {
    const response = await this.client.get('/billing/plans')
    const payload = response.data
    return Array.isArray(payload) ? payload : []
  }

  /** GET /billing/usage?days=N */
  async getBillingUsage(days: number = 30): Promise<BillingUsageDay[]> {
    const response = await this.client.get('/billing/usage', { params: { days } })
    const payload = response.data
    return Array.isArray(payload) ? payload : []
  }

  /** GET /billing/invoices */
  async listInvoices(skip: number = 0, limit: number = 10): Promise<BillingInvoice[]> {
    const response = await this.client.get('/billing/invoices', { params: { skip, limit } })
    const payload = response.data
    return Array.isArray(payload) ? payload : []
  }

  /** GET /billing/subscription — 404 when there is no active subscription. */
  async getSubscription(): Promise<BillingSubscription> {
    const response = await this.client.get('/billing/subscription')
    return response.data
  }

  // --- Users (backend/app/api/users.py) — security:manage required ---

  async listUsers(): Promise<AdminUserRecord[]> {
    const response = await this.client.get('/users')
    const payload = response.data
    return Array.isArray(payload) ? payload : payload?.data ?? []
  }

  async createUser(data: {
    email: string
    display_name?: string
    role?: string
    tenant_id?: string
  }): Promise<AdminUserRecord> {
    const response = await this.client.post('/users', data)
    return response.data
  }

  async updateUser(id: string, data: {
    email?: string
    display_name?: string
    role?: string
    tenant_id?: string
  }): Promise<AdminUserRecord> {
    const response = await this.client.put(`/users/${id}`, data)
    return response.data
  }

  /** PUT /users/{id}/role — body { role } */
  async updateUserRole(id: string, role: string): Promise<AdminUserRecord> {
    const response = await this.client.put(`/users/${id}/role`, { role })
    return response.data
  }

  /** GET /users/{id}/activity?limit=&offset= */
  async getUserActivity(id: string, limit: number = 50, offset: number = 0): Promise<UserActivityResponse> {
    const response = await this.client.get(`/users/${id}/activity`, { params: { limit, offset } })
    return response.data
  }

  async deleteUser(id: string): Promise<void> {
    await this.client.delete(`/users/${id}`)
  }
}

export const adminOps = new AdminOpsClient()
export default adminOps
