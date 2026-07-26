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
      <span className={isDark ? 'text-slate-400' : 'text-slate-500'}>
        {used.toLocaleString()} / {limit.toLocaleString()}{unit ? ` ${unit}` : ''} ({percent}%)
      </span>
    </div>
    <div className={clsx('h-2.5 rounded-full overflow-hidden', isDark ? 'bg-slate-700' : 'bg-slate-200')}>
      <div
        className={clsx(
          'h-full rounded-full transition-all',
          percent >= 90 ? 'bg-red-500' : percent >= 70 ? 'bg-amber-500' : 'bg-blue-600'
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

  const loadBillingData = useCallback(async () => {
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
    loadQuotaReport()
    loadBillingData()
  }, [loadTenants, loadQuotaReport, loadBillingData])

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

  // 403 — graceful permission notice instead of a broken page
  if (forbidden) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className={clsx(
          'p-8 rounded-xl border text-center',
          isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
        )}>
          <div className="text-4xl mb-3">🔒</div>
          <h1 className="text-xl font-bold mb-2">{t('admin.forbidden.title', 'Admin access required')}</h1>
          <p className={clsx('text-sm', isDark ? 'text-slate-400' : 'text-slate-500')}>
            {t('admin.forbidden.desc', 'Your account does not have the security:manage scope. Contact an administrator to manage tenants, quotas and billing.')}
          </p>
        </div>
      </div>
    )
  }

  const tabs: Array<{ id: PageTab; label: string; icon: string }> = [
    { id: 'tenants', label: t('admin.tabs.tenants', 'Tenants'), icon: '🏢' },
    { id: 'detail', label: t('admin.tabs.detail', 'Tenant Detail'), icon: '📊' },
    { id: 'billing', label: t('admin.tabs.billing', 'Billing'), icon: '💳' },
    { id: 'quota', label: t('admin.tabs.quota', 'Quota'), icon: '⚙️' },
  ]

  const selectedTenant = tenants.find(tn => tn.id === selectedTenantId) || null

  const inputCls = clsx(
    'w-full px-3 py-2 rounded-lg border text-sm',
    isDark ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-slate-300'
  )
  const cardCls = clsx(
    'p-4 rounded-xl border',
    isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
  )

  const breakdown = quotaReport?.breakdown ?? {}
  const storageItem = breakdown['storage']
  const apiCallsItem = breakdown['api_calls']
  const memoryItem = breakdown['memory_items']
  const agentsItem = breakdown['agents']
  const workflowsItem = breakdown['workflows']
  const runsItem = breakdown['concurrent_runs']
  const totalTokens = billingUsage.reduce((sum, d) => sum + (d.tokens_used || 0), 0)

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">{t('admin.tenantsBilling.title', 'Tenants & Billing')}</h1>

      {message && (
        <div className={clsx(
          'mb-4 p-3 rounded-lg text-sm',
          message.type === 'success'
            ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
            : 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'
        )} role="alert">
          {message.text}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-slate-200 dark:border-slate-700" role="tablist">
        {tabs.map(tab => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={clsx(
              'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
              activeTab === tab.id
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            )}
          >
            <span className="mr-1.5">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tenants Tab — list + create */}
      {activeTab === 'tenants' && (
        <div className="space-y-6">
          <div className={cardCls}>
            <h2 className="text-sm font-semibold mb-3">{t('admin.tenants.create', 'Create Tenant')}</h2>
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
          </div>

          <div className={cardCls}>
            <h2 className="text-sm font-semibold mb-3">{t('admin.tenants.list', 'Tenants')}</h2>
            {loading ? (
              <p className={clsx('text-sm py-6 text-center', isDark ? 'text-slate-500' : 'text-slate-400')}>
                {t('common.loading', 'Loading...')}
              </p>
            ) : tenants.length === 0 ? (
              <p className={clsx('text-sm py-6 text-center', isDark ? 'text-slate-500' : 'text-slate-400')}>
                {t('admin.tenants.empty', 'No tenants found.')}
              </p>
            ) : (
              <div className="space-y-2">
                {tenants.map(tn => (
                  <div
                    key={tn.id}
                    className={clsx(
                      'flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors',
                      selectedTenantId === tn.id
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                        : isDark ? 'border-slate-700 hover:bg-slate-800' : 'border-slate-200 hover:bg-slate-50'
                    )}
                    onClick={() => { setSelectedTenantId(tn.id); setActiveTab('detail') }}
                  >
                    <div>
                      <p className="text-sm font-medium">{tn.name}</p>
                      <p className={clsx('text-xs', isDark ? 'text-slate-500' : 'text-slate-400')}>
                        {tn.id} • {tn.created_at ? new Date(tn.created_at).toLocaleDateString() : '—'}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={clsx(
                        'px-2 py-0.5 rounded-full text-xs font-medium',
                        tn.plan === 'enterprise'
                          ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300'
                          : tn.plan === 'pro'
                            ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                            : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
                      )}>
                        {tn.plan}
                      </span>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDeleteTenant(tn.id) }}
                        className="text-xs text-red-500 hover:text-red-700 font-medium"
                      >
                        {t('common.delete', 'Delete')}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Detail Tab — quota usage progress bars + tenant usage */}
      {activeTab === 'detail' && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-2">
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
                  'px-3 py-1.5 rounded-lg text-xs font-medium',
                  usagePeriod === p
                    ? 'bg-blue-600 text-white'
                    : isDark ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'
                )}
              >
                {p}
              </button>
            ))}
          </div>

          {/* Quota usage progress bars (GET /tenant/quota breakdown) */}
          <div className={cardCls}>
            <h2 className="text-sm font-semibold mb-4">
              {t('admin.detail.quotaUsage', 'Quota Usage')}
              <span className={clsx('ml-2 text-xs font-normal', isDark ? 'text-slate-500' : 'text-slate-400')}>
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
            <div className="flex justify-between text-sm pt-2 border-t border-slate-200 dark:border-slate-700">
              <span className="font-medium">{t('admin.quota.tokens30d', 'Tokens used (30d)')}</span>
              <span className={isDark ? 'text-slate-400' : 'text-slate-500'}>{totalTokens.toLocaleString()}</span>
            </div>
          </div>

          {/* Per-tenant usage stats (GET /tenants/{id}/usage) */}
          <div className={cardCls}>
            <h2 className="text-sm font-semibold mb-3">
              {t('admin.detail.tenantUsage', 'Tenant Usage')}
              {selectedTenant && <span className="ml-2 font-normal">— {selectedTenant.name}</span>}
            </h2>
            {tenantUsage ? (
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                {([
                  ['runs', tenantUsage.usage.runs],
                  ['agents', tenantUsage.usage.agents],
                  ['memory_gb', tenantUsage.usage.memory_gb],
                  ['api_calls', tenantUsage.usage.api_calls],
                  ['active_users', tenantUsage.usage.active_users],
                ] as const).map(([key, value]) => (
                  <div key={key} className={clsx('p-3 rounded-lg text-center', isDark ? 'bg-slate-800' : 'bg-slate-50')}>
                    <p className="text-lg font-bold">{value}</p>
                    <p className={clsx('text-xs', isDark ? 'text-slate-500' : 'text-slate-400')}>{key}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className={clsx('text-sm', isDark ? 'text-slate-500' : 'text-slate-400')}>
                {selectedTenantId ? t('common.loading', 'Loading...') : t('admin.detail.selectFirst', 'Select a tenant first.')}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Billing Tab */}
      {activeTab === 'billing' && (
        <div className="space-y-6">
          {/* Per-tenant billing (GET /tenants/{id}/billing) */}
          <div className={cardCls}>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <h2 className="text-sm font-semibold">
                {t('admin.billing.tenantBilling', 'Tenant Billing')}
                {selectedTenant && <span className="ml-2 font-normal">— {selectedTenant.name}</span>}
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
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className={clsx('p-3 rounded-lg', isDark ? 'bg-slate-800' : 'bg-slate-50')}>
                  <p className={clsx('text-xs mb-1', isDark ? 'text-slate-500' : 'text-slate-400')}>{t('admin.billing.plan', 'Plan')}</p>
                  <p className="text-sm font-bold">{tenantBilling.plan}</p>
                </div>
                <div className={clsx('p-3 rounded-lg', isDark ? 'bg-slate-800' : 'bg-slate-50')}>
                  <p className={clsx('text-xs mb-1', isDark ? 'text-slate-500' : 'text-slate-400')}>{t('admin.billing.total', 'Total')}</p>
                  <p className="text-sm font-bold">{tenantBilling.billing.total_amount} {tenantBilling.billing.currency}</p>
                </div>
                <div className={clsx('p-3 rounded-lg', isDark ? 'bg-slate-800' : 'bg-slate-50')}>
                  <p className={clsx('text-xs mb-1', isDark ? 'text-slate-500' : 'text-slate-400')}>{t('admin.billing.status', 'Status')}</p>
                  <p className="text-sm font-bold">{tenantBilling.billing.status}</p>
                </div>
                <div className={clsx('p-3 rounded-lg', isDark ? 'bg-slate-800' : 'bg-slate-50')}>
                  <p className={clsx('text-xs mb-1', isDark ? 'text-slate-500' : 'text-slate-400')}>{t('admin.billing.period', 'Period')}</p>
                  <p className="text-sm font-bold">{tenantBilling.billing_month}</p>
                </div>
              </div>
            ) : (
              <p className={clsx('text-sm', isDark ? 'text-slate-500' : 'text-slate-400')}>
                {selectedTenantId ? t('common.loading', 'Loading...') : t('admin.detail.selectFirst', 'Select a tenant first.')}
              </p>
            )}
          </div>

          {/* Subscription + plans */}
          <div className={cardCls}>
            <h2 className="text-sm font-semibold mb-3">{t('admin.billing.subscription', 'Subscription')}</h2>
            {subscription ? (
              <div className="text-sm space-y-1">
                <p>{t('admin.billing.model', 'Model')}: <span className="font-medium">{subscription.billing_model}</span></p>
                <p>{t('admin.billing.renewal', 'Renewal')}: <span className="font-medium">{subscription.renewal_date ? new Date(subscription.renewal_date).toLocaleDateString() : '—'}</span></p>
                <p>{t('admin.billing.autoRenew', 'Auto renew')}: <span className="font-medium">{subscription.auto_renew ? '✓' : '✗'}</span></p>
              </div>
            ) : (
              <p className={clsx('text-sm', isDark ? 'text-slate-500' : 'text-slate-400')}>
                {t('admin.billing.noSubscription', 'No active subscription.')}
              </p>
            )}
            {plans.length > 0 && (
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {plans.map(plan => (
                  <div key={plan.id} className={clsx('p-3 rounded-lg border', isDark ? 'border-slate-700' : 'border-slate-200')}>
                    <p className="text-sm font-semibold">{plan.tier_name}</p>
                    <p className={clsx('text-xs mb-1', isDark ? 'text-slate-500' : 'text-slate-400')}>{plan.billing_model}</p>
                    <p className="text-sm">{plan.monthly_price ? `$${plan.monthly_price}/mo` : '—'}</p>
                    {plan.description && <p className={clsx('text-xs mt-1', isDark ? 'text-slate-500' : 'text-slate-400')}>{plan.description}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Daily usage (GET /billing/usage) */}
          <div className={cardCls}>
            <h2 className="text-sm font-semibold mb-3">{t('admin.billing.usage30d', 'Usage (last 30 days)')}</h2>
            {billingUsage.length === 0 ? (
              <p className={clsx('text-sm', isDark ? 'text-slate-500' : 'text-slate-400')}>
                {t('admin.billing.noUsage', 'No usage records.')}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className={clsx('text-left text-xs', isDark ? 'text-slate-500' : 'text-slate-400')}>
                      <th className="pb-2 pr-4">{t('admin.billing.date', 'Date')}</th>
                      <th className="pb-2 pr-4">{t('admin.billing.apiCalls', 'API Calls')}</th>
                      <th className="pb-2 pr-4">{t('admin.billing.tokens', 'Tokens')}</th>
                      <th className="pb-2 pr-4">{t('admin.billing.storageGb', 'Storage (GB)')}</th>
                      <th className="pb-2">{t('admin.billing.cost', 'Est. Cost')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {billingUsage.map((day, i) => (
                      <tr key={i} className={clsx('border-t', isDark ? 'border-slate-700' : 'border-slate-100')}>
                        <td className="py-2 pr-4">{new Date(day.date).toLocaleDateString()}</td>
                        <td className="py-2 pr-4">{day.api_calls.toLocaleString()}</td>
                        <td className="py-2 pr-4">{day.tokens_used.toLocaleString()}</td>
                        <td className="py-2 pr-4">{day.storage_used_gb}</td>
                        <td className="py-2">{day.estimated_cost}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Invoices (GET /billing/invoices) */}
          <div className={cardCls}>
            <h2 className="text-sm font-semibold mb-3">{t('admin.billing.invoices', 'Invoices')}</h2>
            {invoices.length === 0 ? (
              <p className={clsx('text-sm', isDark ? 'text-slate-500' : 'text-slate-400')}>
                {t('admin.billing.noInvoices', 'No invoices.')}
              </p>
            ) : (
              <div className="space-y-2">
                {invoices.map(inv => (
                  <div key={inv.id} className={clsx('flex items-center justify-between p-3 rounded-lg', isDark ? 'bg-slate-800' : 'bg-slate-50')}>
                    <div>
                      <p className="text-sm font-medium">{inv.invoice_number}</p>
                      <p className={clsx('text-xs', isDark ? 'text-slate-500' : 'text-slate-400')}>
                        {new Date(inv.period_start).toLocaleDateString()} — {new Date(inv.period_end).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-bold">{inv.total}</p>
                      <span className={clsx(
                        'text-xs px-2 py-0.5 rounded-full',
                        inv.status === 'paid'
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                          : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
                      )}>
                        {inv.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Payment / subscribe actions exist in the backend but require a
              payment provider; keep them disabled until integration lands. */}
          <div className={clsx(cardCls, 'opacity-60')}>
            <h2 className="text-sm font-semibold mb-2">{t('admin.billing.payment', 'Payment')}</h2>
            <button disabled className="px-4 py-2 bg-slate-300 dark:bg-slate-700 text-slate-500 dark:text-slate-400 rounded-lg text-sm cursor-not-allowed">
              {t('common.comingSoon', 'Coming soon')}
            </button>
          </div>
        </div>
      )}

      {/* Quota Tab — admin scope (PUT /tenant/quota) */}
      {activeTab === 'quota' && (
        <div className={clsx(cardCls, 'max-w-xl')}>
          <h2 className="text-sm font-semibold mb-1">{t('admin.quota.adjust', 'Adjust Quota Limits')}</h2>
          <p className={clsx('text-xs mb-4', isDark ? 'text-slate-500' : 'text-slate-400')}>
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
        </div>
      )}
    </div>
  )
}

export default TenantsBillingPage
