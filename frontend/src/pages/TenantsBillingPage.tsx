import React, { useCallback, useEffect, useState } from 'react'
import { useI18n } from '@/i18n/context'
import { useAppStore } from '@/store/appStore'
import {
  adminOps,
  isForbidden,
  errorMessage,
  TenantRecord,
  TenantUsageResponse,
  TenantBillingResponse,
  TenantQuotaReport,
  BillingPlan,
  BillingUsageDay,
  BillingInvoice,
  BillingSubscription,
} from '@/services/adminOps'
import clsx from 'clsx'

type PageTab = 'tenants' | 'detail' | 'billing' | 'quota'

const DIVIDER = 'var(--divider)'

const PLAN_BADGE: Record<string, string> = {
  enterprise: 'badge-warning',
  pro: 'badge-muted',
  free: 'badge-muted',
}

/** Progress bar for one quota resource (real data from /tenant/quota breakdown). */
const UsageBar: React.FC<{
  label: string
  used: number
  limit: number
  percent: number
  isDark: boolean
  unit?: string
}> = ({ label, used, limit, percent, isDark, unit }) => (
  <div className="mb-4">
    <div className="flex justify-between text-sm mb-1">
      <span className="font-medium">{label}</span>
      <span className="cell-data opacity-60">
        {used.toLocaleString()} / {limit.toLocaleString()}{unit ? ` ${unit}` : ''} ({percent}%)
      </span>
    </div>
    <div
      className="h-[3px] w-full"
      style={{ backgroundColor: 'rgba(163,169,177,.25)' }}
      role="progressbar"
      aria-valuenow={Math.min(100, percent)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <div
        className={clsx(
          'h-[3px] transition-all',
          percent >= 90 ? 'bg-[#dc2626]' : percent >= 70 ? 'bg-[#d97706]' : isDark ? 'bg-slate-300' : 'bg-[#333333]'
        )}
        style={{ width: `${Math.min(100, percent)}%` }}
      />
    </div>
  </div>
)

const TenantsBillingPage: React.FC = () => {
  const { t } = useI18n()
  const { theme } = useAppStore()
  const isDark = theme === 'dark'

  const [activeTab, setActiveTab] = useState<PageTab>('tenants')
  const [forbidden, setForbidden] = useState(false)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Tenants tab
  const [tenants, setTenants] = useState<TenantRecord[]>([])
  const [newTenantName, setNewTenantName] = useState('')
  const [newTenantPlan, setNewTenantPlan] = useState('free')
  const [selectedTenantId, setSelectedTenantId] = useState<string | null>(null)

  // Detail tab
  const [tenantUsage, setTenantUsage] = useState<TenantUsageResponse | null>(null)
  const [usagePeriod, setUsagePeriod] = useState<'day' | 'week' | 'month' | 'year'>('month')
  const [quotaReport, setQuotaReport] = useState<TenantQuotaReport | null>(null)

  // Billing tab
  const [tenantBilling, setTenantBilling] = useState<TenantBillingResponse | null>(null)
  const [billingMonth, setBillingMonth] = useState('')
  const [plans, setPlans] = useState<BillingPlan[]>([])
  const [billingUsage, setBillingUsage] = useState<BillingUsageDay[]>([])
  const [invoices, setInvoices] = useState<BillingInvoice[]>([])
  const [subscription, setSubscription] = useState<BillingSubscription | null>(null)

  // Quota tab (admin scope)
  const [quotaForm, setQuotaForm] = useState({
    max_agents: '',
    max_workflows: '',
    max_api_calls_per_day: '',
    max_memory_items: '',
    max_concurrent_runs: '',
    max_storage_mb: '',
  })
  const [savingQuota, setSavingQuota] = useState(false)

  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 4000)
  }

  const handleError = (error: unknown, fallback: string) => {
    if (isForbidden(error)) {
      setForbidden(true)
      return
    }
    showMessage('error', errorMessage(error, fallback))
  }

  const loadTenants = useCallback(async () => {
    setLoading(true)
    try {
      const list = await adminOps.listTenants()
      setTenants(list)
      if (!selectedTenantId && list.length > 0) {
        setSelectedTenantId(list[0].id)
      }
    } catch (error) {
      handleError(error, t('admin.tenants.loadFailed', 'Failed to load tenants'))
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTenantId])

  const loadQuotaReport = useCallback(async () => {
    try {
      const report = await adminOps.getTenantQuota()
      setQuotaReport(report)
    } catch (error) {
      handleError(error, t('admin.quota.loadFailed', 'Failed to load quota'))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const _loadBillingData = useCallback(async () => {
    try {
      const [planList, usage, invoiceList] = await Promise.all([
        adminOps.listBillingPlans(),
        adminOps.getBillingUsage(30),
        adminOps.listInvoices(0, 10),
      ])
      setPlans(planList)
      setBillingUsage(usage)
      setInvoices(invoiceList)
    } catch (error) {
      handleError(error, t('admin.billing.loadFailed', 'Failed to load billing data'))
    }
    // Subscription 404 means "no active subscription" — not an error state.
    try {
      setSubscription(await adminOps.getSubscription())
    } catch {
      setSubscription(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    loadTenants()
  }, [loadTenants])

  const loadTenantUsage = useCallback(async () => {
    if (!selectedTenantId) return
    try {
      setTenantUsage(await adminOps.getTenantUsage(selectedTenantId, usagePeriod))
    } catch (error) {
      handleError(error, t('admin.usage.loadFailed', 'Failed to load tenant usage'))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTenantId, usagePeriod])

  const loadTenantBilling = useCallback(async () => {
    if (!selectedTenantId) return
    try {
      setTenantBilling(await adminOps.getTenantBilling(selectedTenantId, billingMonth || undefined))
    } catch (error) {
      handleError(error, t('admin.billing.loadFailed', 'Failed to load billing data'))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTenantId, billingMonth])

  useEffect(() => {
    if (activeTab === 'detail') loadTenantUsage()
  }, [activeTab, loadTenantUsage])

  useEffect(() => {
    if (activeTab === 'billing') loadTenantBilling()
  }, [activeTab, loadTenantBilling])

  const handleCreateTenant = async () => {
    if (!newTenantName.trim()) return
    try {
      const created = await adminOps.createTenant({ name: newTenantName.trim(), plan: newTenantPlan })
      setTenants(prev => [...prev, created])
      setSelectedTenantId(created.id)
      setNewTenantName('')
      showMessage('success', t('admin.tenants.created', 'Tenant created'))
    } catch (error) {
      handleError(error, t('admin.tenants.createFailed', 'Failed to create tenant'))
    }
  }

  const handleDeleteTenant = async (id: string) => {
    if (!window.confirm(t('admin.tenants.deleteConfirm', 'Delete this tenant? This action cannot be undone.'))) {
      return
    }
    try {
      await adminOps.deleteTenant(id)
      setTenants(prev => prev.filter(tn => tn.id !== id))
      if (selectedTenantId === id) setSelectedTenantId(null)
      showMessage('success', t('admin.tenants.deleted', 'Tenant deleted'))
    } catch (error) {
      handleError(error, t('admin.tenants.deleteFailed', 'Failed to delete tenant'))
    }
  }

  const handleSaveQuota = async () => {
    setSavingQuota(true)
    try {
      const update: Record<string, number> = {}
      ;(Object.keys(quotaForm) as Array<keyof typeof quotaForm>).forEach(key => {
        const raw = quotaForm[key].trim()
        if (raw !== '') {
          const value = Number(raw)
          if (Number.isFinite(value) && value >= 0) update[key] = Math.floor(value)
        }
      })
      await adminOps.updateTenantQuota(update)
      showMessage('success', t('admin.quota.saved', 'Quota limits updated'))
      await loadQuotaReport()
    } catch (error) {
      handleError(error, t('admin.quota.saveFailed', 'Failed to update quota'))
    } finally {
      setSavingQuota(false)
    }
  }

  const inputCls = clsx(
    'w-full px-3 py-2 rounded-lg border text-sm',
    isDark ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-slate-300'
  )

  // 403 — graceful permission notice instead of a broken page
  if (forbidden) {
    return (
      <div className={clsx(
        'min-h-full px-8 py-10',
        isDark ? 'bg-slate-950 text-slate-200' : 'bg-[#fafafa] text-[#333333]'
      )}>
        <div className="max-w-3xl">
          <header className="mb-8">
            <div
              className={clsx('w-12 border-t-2 mb-5', isDark ? 'border-slate-200' : 'border-[#333333]')}
              aria-hidden="true"
            />
            <h1 className="page-title">{t('admin.forbidden.title', 'Admin access required')}</h1>
            <p className="page-subtitle">
              {t('admin.forbidden.desc', 'Your account does not have the security:manage scope. Contact an administrator to manage tenants, quotas and billing.')}
            </p>
          </header>
        </div>
      </div>
    )
  }

  const tabs: Array<{ id: PageTab; label: string; disabled?: boolean }> = [
    { id: 'tenants', label: t('admin.tabs.tenants', 'Tenants') },
    { id: 'detail', label: t('admin.tabs.detail', 'Tenant Detail'), disabled: true },
    { id: 'billing', label: t('admin.tabs.billing', 'Billing'), disabled: true },
    { id: 'quota', label: t('admin.tabs.quota', 'Quota'), disabled: true },
  ]

  const selectedTenant = tenants.find(tn => tn.id === selectedTenantId) || null

  const breakdown = quotaReport?.breakdown ?? {}
  const storageItem = breakdown['storage']
  const apiCallsItem = breakdown['api_calls']
  const memoryItem = breakdown['memory_items']
  const agentsItem = breakdown['agents']
  const workflowsItem = breakdown['workflows']
  const runsItem = breakdown['concurrent_runs']
  const totalTokens = billingUsage.reduce((sum, d) => sum + (d.tokens_used || 0), 0)

  return (
    <div className={clsx(
      'min-h-full px-8 py-10',
      isDark ? 'bg-slate-950 text-slate-200' : 'bg-[#fafafa] text-[#333333]'
    )}>
      <div className="max-w-5xl">
        {/* Header — Dashboard-style */}
        <header className="mb-8">
          <div
            className={clsx('w-12 border-t-2 mb-5', isDark ? 'border-slate-200' : 'border-[#333333]')}
            aria-hidden="true"
          />
          <h1 className="page-title">{t('admin.tenantsBilling.title', 'Tenants & Billing')}</h1>
          <p className="page-subtitle">{t('admin.tenantsBilling.subtitle', 'Manage tenants, quota usage and billing')}</p>
        </header>

        {message && (
          <div className={clsx(
            'mb-4 px-3 py-2 rounded-lg text-sm border',
            message.type === 'success'
              ? 'border-[#16a34a]/30 text-[#16a34a]'
              : 'border-[#dc2626]/30 text-[#dc2626]'
          )} role="alert">
            {message.text}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 mb-8 border-b" style={{ borderColor: DIVIDER }} role="tablist">
          {tabs.map(tab => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-disabled={tab.disabled || undefined}
              disabled={tab.disabled}
              title={tab.disabled ? t('admin.tabs.unavailable', 'Unavailable until real usage and billing data sources are connected') : undefined}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                  : 'border-transparent opacity-50 enabled:hover:opacity-100',
                tab.disabled && 'cursor-not-allowed'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tenants Tab — list + create */}
        {activeTab === 'tenants' && (
          <div>
            <section className="mb-10">
              <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-3">
                {t('admin.tenants.create', 'Create Tenant')}
              </h2>
              <div className="flex flex-wrap gap-2">
                <input
                  type="text"
                  value={newTenantName}
                  onChange={e => setNewTenantName(e.target.value)}
                  placeholder={t('admin.tenants.namePlaceholder', 'Tenant name')}
                  className={clsx(inputCls, 'flex-1 min-w-[200px]')}
                />
                <select
                  value={newTenantPlan}
                  onChange={e => setNewTenantPlan(e.target.value)}
                  className={clsx(inputCls, 'w-36')}
                  aria-label={t('admin.tenants.plan', 'Plan')}
                >
                  <option value="free">free</option>
                  <option value="pro">pro</option>
                  <option value="enterprise">enterprise</option>
                </select>
                <button
                  onClick={handleCreateTenant}
                  disabled={!newTenantName.trim()}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  {t('common.create', 'Create')}
                </button>
              </div>
            </section>

            <section>
              <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
                {t('admin.tenants.list', 'Tenants')}
              </h2>
              {loading ? (
                <p className="empty-state">{t('common.loading', 'Loading...')}</p>
              ) : tenants.length === 0 ? (
                <p className="empty-state">{t('admin.tenants.empty', 'No tenants found.')}</p>
              ) : (
                <div>
                  {tenants.map(tn => (
                    <div
                      key={tn.id}
                      className={clsx(
                        'row-line flex items-center justify-between gap-3 px-2 -mx-2',
                        selectedTenantId === tn.id && (isDark ? 'bg-slate-800' : 'bg-slate-100')
                      )}
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{tn.name}</p>
                        <p className="cell-data opacity-50 truncate">
                          {tn.id} • {tn.created_at ? new Date(tn.created_at).toLocaleDateString() : '—'}
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className={clsx('badge-status', PLAN_BADGE[tn.plan] ?? 'badge-muted')}>
                          {tn.plan}
                        </span>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDeleteTenant(tn.id) }}
                          className="text-xs text-[#dc2626] opacity-60 hover:opacity-100 transition-opacity font-medium"
                        >
                          {t('common.delete', 'Delete')}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}

        {/* Detail Tab — quota usage progress bars + tenant usage */}
        {activeTab === 'detail' && (
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-8">
              <select
                value={selectedTenantId ?? ''}
                onChange={e => setSelectedTenantId(e.target.value)}
                className={clsx(inputCls, 'max-w-xs')}
                aria-label={t('admin.detail.selectTenant', 'Select tenant')}
              >
                {tenants.length === 0 && <option value="">{t('admin.tenants.empty', 'No tenants found.')}</option>}
                {tenants.map(tn => <option key={tn.id} value={tn.id}>{tn.name}</option>)}
              </select>
              {(['day', 'week', 'month', 'year'] as const).map(p => (
                <button
                  key={p}
                  onClick={() => setUsagePeriod(p)}
                  className={clsx(
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                    usagePeriod === p
                      ? 'bg-blue-600 text-white'
                      : isDark ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100'
                  )}
                >
                  {p}
                </button>
              ))}
            </div>

            {/* Quota usage progress bars (GET /tenant/quota breakdown) */}
            <section className="mb-10">
              <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-4">
                {t('admin.detail.quotaUsage', 'Quota Usage')}
                <span className="ml-2 normal-case tracking-normal">
                  {t('admin.detail.currentTenant', '(current tenant)')}
                </span>
              </h2>
              {apiCallsItem && (
                <UsageBar label={t('admin.quota.apiCalls', 'API Requests')} used={apiCallsItem.used} limit={apiCallsItem.limit} percent={apiCallsItem.usage_percent} isDark={isDark} />
              )}
              {storageItem && (
                <UsageBar label={t('admin.quota.storage', 'Storage')} used={Math.round(storageItem.used)} limit={storageItem.limit} percent={storageItem.usage_percent} isDark={isDark} unit="MB" />
              )}
              {memoryItem && (
                <UsageBar label={t('admin.quota.memoryItems', 'Memory Items')} used={memoryItem.used} limit={memoryItem.limit} percent={memoryItem.usage_percent} isDark={isDark} />
              )}
              {agentsItem && (
                <UsageBar label={t('admin.quota.agents', 'Agents')} used={agentsItem.used} limit={agentsItem.limit} percent={agentsItem.usage_percent} isDark={isDark} />
              )}
              {workflowsItem && (
                <UsageBar label={t('admin.quota.workflows', 'Workflows')} used={workflowsItem.used} limit={workflowsItem.limit} percent={workflowsItem.usage_percent} isDark={isDark} />
              )}
              {runsItem && (
                <UsageBar label={t('admin.quota.concurrentRuns', 'Concurrent Runs')} used={runsItem.used} limit={runsItem.limit} percent={runsItem.usage_percent} isDark={isDark} />
              )}
              {/* Token quota is not part of the backend quota manager; show the
                  real 30-day token total from /billing/usage instead. */}
              <div className="flex justify-between text-sm pt-3 border-t" style={{ borderColor: DIVIDER }}>
                <span className="font-medium">{t('admin.quota.tokens30d', 'Tokens used (30d)')}</span>
                <span className="cell-data opacity-60">{totalTokens.toLocaleString()}</span>
              </div>
            </section>

            {/* Per-tenant usage stats (GET /tenants/{id}/usage) — status row */}
            <section>
              <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-3">
                {t('admin.detail.tenantUsage', 'Tenant Usage')}
                {selectedTenant && <span className="ml-2 normal-case tracking-normal">— {selectedTenant.name}</span>}
              </h2>
              {tenantUsage ? (
                <dl className="flex flex-wrap gap-y-6">
                  {([
                    ['runs', tenantUsage.usage.runs],
                    ['agents', tenantUsage.usage.agents],
                    ['memory_gb', tenantUsage.usage.memory_gb],
                    ['api_calls', tenantUsage.usage.api_calls],
                    ['active_users', tenantUsage.usage.active_users],
                  ] as const).map(([key, value], i) => (
                    <div
                      key={key}
                      className={clsx('flex flex-col gap-2 pr-8 mr-8', i < 4 && 'border-r')}
                      style={i < 4 ? { borderColor: DIVIDER } : undefined}
                    >
                      <dd className="font-data text-[22px] leading-none order-2">{value}</dd>
                      <dt className="text-[12px] uppercase tracking-[0.06em] opacity-50 order-1">{key}</dt>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="empty-state">
                  {selectedTenantId ? t('common.loading', 'Loading...') : t('admin.detail.selectFirst', 'Select a tenant first.')}
                </p>
              )}
            </section>
          </div>
        )}

        {/* Billing Tab */}
        {activeTab === 'billing' && (
          <div>
            {/* Per-tenant billing (GET /tenants/{id}/billing) */}
            <section className="mb-10">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50">
                  {t('admin.billing.tenantBilling', 'Tenant Billing')}
                  {selectedTenant && <span className="ml-2 normal-case tracking-normal">— {selectedTenant.name}</span>}
                </h2>
                <input
                  type="month"
                  value={billingMonth}
                  onChange={e => setBillingMonth(e.target.value)}
                  className={clsx(inputCls, 'w-40')}
                  aria-label={t('admin.billing.month', 'Billing month')}
                />
              </div>
              {tenantBilling ? (
                <dl className="flex flex-wrap gap-y-6">
                  {([
                    [t('admin.billing.plan', 'Plan'), tenantBilling.plan],
                    [t('admin.billing.total', 'Total'), `${tenantBilling.billing.total_amount} ${tenantBilling.billing.currency}`],
                    [t('admin.billing.status', 'Status'), tenantBilling.billing.status],
                    [t('admin.billing.period', 'Period'), tenantBilling.billing_month],
                  ] as Array<[string, string]>).map(([label, value], i) => (
                    <div
                      key={label}
                      className={clsx('flex flex-col gap-2 pr-8 mr-8', i < 3 && 'border-r')}
                      style={i < 3 ? { borderColor: DIVIDER } : undefined}
                    >
                      <dd className="font-data text-[18px] leading-none order-2">{value}</dd>
                      <dt className="text-[12px] uppercase tracking-[0.06em] opacity-50 order-1">{label}</dt>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="empty-state">
                  {selectedTenantId ? t('common.loading', 'Loading...') : t('admin.detail.selectFirst', 'Select a tenant first.')}
                </p>
              )}
            </section>

            {/* Subscription + plans */}
            <section className="mb-10">
              <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
                {t('admin.billing.subscription', 'Subscription')}
              </h2>
              {subscription ? (
                <div className="font-data text-[13px] mb-4">
                  <div className="flex items-baseline justify-between py-2 border-b" style={{ borderColor: DIVIDER }}>
                    <span className="opacity-50">{t('admin.billing.model', 'Model')}</span>
                    <span>{subscription.billing_model}</span>
                  </div>
                  <div className="flex items-baseline justify-between py-2 border-b" style={{ borderColor: DIVIDER }}>
                    <span className="opacity-50">{t('admin.billing.renewal', 'Renewal')}</span>
                    <span>{subscription.renewal_date ? new Date(subscription.renewal_date).toLocaleDateString() : '—'}</span>
                  </div>
                  <div className="flex items-baseline justify-between py-2 border-b" style={{ borderColor: DIVIDER }}>
                    <span className="opacity-50">{t('admin.billing.autoRenew', 'Auto renew')}</span>
                    <span>{subscription.auto_renew ? '✓' : '✗'}</span>
                  </div>
                </div>
              ) : (
                <p className="empty-state">{t('admin.billing.noSubscription', 'No active subscription.')}</p>
              )}
              {plans.length > 0 && (
                <div>
                  {plans.map(plan => (
                    <div key={plan.id} className="row-line flex items-baseline justify-between gap-4">
                      <div className="min-w-0">
                        <p className="text-sm font-medium">{plan.tier_name}</p>
                        {plan.description && <p className="text-xs opacity-50 truncate">{plan.description}</p>}
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="cell-data opacity-50">{plan.billing_model}</span>
                        <span className="cell-data">{plan.monthly_price ? `$${plan.monthly_price}/mo` : '—'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Daily usage (GET /billing/usage) */}
            <section className="mb-10">
              <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
                {t('admin.billing.usage30d', 'Usage (last 30 days)')}
              </h2>
              {billingUsage.length === 0 ? (
                <p className="empty-state">{t('admin.billing.noUsage', 'No usage records.')}</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="table-dense">
                    <thead>
                      <tr>
                        <th>{t('admin.billing.date', 'Date')}</th>
                        <th>{t('admin.billing.apiCalls', 'API Calls')}</th>
                        <th>{t('admin.billing.tokens', 'Tokens')}</th>
                        <th>{t('admin.billing.storageGb', 'Storage (GB)')}</th>
                        <th>{t('admin.billing.cost', 'Est. Cost')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {billingUsage.map((day, i) => (
                        <tr key={i}>
                          <td className="cell-data opacity-70">{new Date(day.date).toLocaleDateString()}</td>
                          <td className="cell-data opacity-70">{day.api_calls.toLocaleString()}</td>
                          <td className="cell-data opacity-70">{day.tokens_used.toLocaleString()}</td>
                          <td className="cell-data opacity-70">{day.storage_used_gb}</td>
                          <td className="cell-data opacity-70">{day.estimated_cost}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* Invoices (GET /billing/invoices) */}
            <section className="mb-10">
              <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
                {t('admin.billing.invoices', 'Invoices')}
              </h2>
              {invoices.length === 0 ? (
                <p className="empty-state">{t('admin.billing.noInvoices', 'No invoices.')}</p>
              ) : (
                <div>
                  {invoices.map(inv => (
                    <div key={inv.id} className="row-line flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <p className="text-sm font-medium cell-data">{inv.invoice_number}</p>
                        <p className="cell-data opacity-50">
                          {new Date(inv.period_start).toLocaleDateString()} — {new Date(inv.period_end).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="cell-data">{inv.total}</span>
                        <span className={clsx('badge-status', inv.status === 'paid' ? 'badge-success' : 'badge-warning')}>
                          {inv.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Payment / subscribe actions exist in the backend but require a
                payment provider; keep them disabled until integration lands. */}
            <section>
              <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
                {t('admin.billing.payment', 'Payment')}
              </h2>
              <button
                disabled
                className={clsx(
                  'px-4 py-2 rounded-lg text-sm font-medium cursor-not-allowed opacity-50',
                  isDark ? 'bg-slate-800 text-slate-400' : 'bg-white border border-slate-200 text-slate-500'
                )}
              >
                {t('common.comingSoon', 'Coming soon')}
              </button>
            </section>
          </div>
        )}

        {/* Quota Tab — admin scope (PUT /tenant/quota) */}
        {activeTab === 'quota' && (
          <section className="max-w-xl">
            <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-1">
              {t('admin.quota.adjust', 'Adjust Quota Limits')}
            </h2>
            <p className="text-[13px] opacity-60 mb-4">
              {t('admin.quota.adjustDesc', 'Only filled fields are updated. Requires admin scope.')}
            </p>
            <div className="space-y-3">
              {([
                ['max_agents', t('admin.quota.agents', 'Agents')],
                ['max_workflows', t('admin.quota.workflows', 'Workflows')],
                ['max_api_calls_per_day', t('admin.quota.apiCallsPerDay', 'API calls / day')],
                ['max_memory_items', t('admin.quota.memoryItems', 'Memory Items')],
                ['max_concurrent_runs', t('admin.quota.concurrentRuns', 'Concurrent Runs')],
                ['max_storage_mb', t('admin.quota.storageMb', 'Storage (MB)')],
              ] as const).map(([key, label]) => (
                <div key={key} className="flex items-center gap-3">
                  <label className="w-40 text-sm">{label}</label>
                  <input
                    type="number"
                    min={0}
                    value={quotaForm[key]}
                    onChange={e => setQuotaForm(prev => ({ ...prev, [key]: e.target.value }))}
                    placeholder={quotaReport ? String(quotaReport.limits[key]) : ''}
                    className={clsx(inputCls, 'flex-1')}
                  />
                </div>
              ))}
            </div>
            <button
              onClick={handleSaveQuota}
              disabled={savingQuota}
              className="mt-5 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {savingQuota ? t('common.saving', 'Saving...') : t('common.save', 'Save Changes')}
            </button>
          </section>
        )}
      </div>
    </div>
  )
}

export default TenantsBillingPage
