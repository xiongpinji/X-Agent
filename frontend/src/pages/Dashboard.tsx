import React, { useEffect, useState, useMemo, useCallback } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiClient, DashboardMetrics } from '@/services/api'
import { useI18n } from '@/i18n/context'
import clsx from 'clsx'

interface DashboardStats {
  totalAgents: number
  activeTasks: number
  totalTools: number
  uptime: string
  requestCount: number
  errorRate: string
  avgLatency: string
}

const DIVIDER = 'var(--divider)'

export const Dashboard: React.FC = React.memo(() => {
  const { setLoading, setError } = useAppStore()
  const { t } = useI18n()
  const [stats, setStats] = useState<DashboardStats>({
    totalAgents: 0,
    activeTasks: 0,
    totalTools: 0,
    uptime: '—',
    requestCount: 0,
    errorRate: '—',
    avgLatency: '—',
  })

  useEffect(() => {
    loadDashboardData()
  }, [])

  const loadDashboardData = useCallback(async () => {
    try {
      setLoading(true)
      const [agents, tools, tasks, metricsResp] = await Promise.all([
        apiClient.listAgents(),
        apiClient.listTools(),
        apiClient.listTasks(1, 100),
        apiClient.getMetrics().catch(() => null),
      ])

      const activeTasks = tasks.items.filter(
        (t) => t.status === 'in_progress' || t.status === 'pending'
      ).length

      const metrics: DashboardMetrics = metricsResp || {}

      setStats({
        totalAgents: agents.length,
        activeTasks,
        totalTools: tools.length,
        uptime: String(metrics.uptime || metrics.uptime_percent || '—'),
        requestCount: metrics.total_requests || metrics.request_count || metrics.runs || 0,
        errorRate: metrics.error_rate != null ? `${(metrics.error_rate * 100).toFixed(1)}%` : '—',
        avgLatency: metrics.avg_latency_ms != null ? `${Math.round(metrics.avg_latency_ms)}ms` : '—',
      })
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }, [setLoading, setError])

  // Status row items (numbers in tabular mono, labels 12px uppercase 50%)
  const statusItems = useMemo(() => [
    { label: t('dashboard.totalAgents', 'Total Agents'), value: String(stats.totalAgents) },
    { label: t('dashboard.activeTasks', 'Active Tasks'), value: String(stats.activeTasks) },
    { label: t('dashboard.totalTools', 'Total Tools'), value: String(stats.totalTools) },
    { label: t('dashboard.uptime', 'Uptime'), value: stats.uptime },
  ], [stats, t])

  const quickActions = useMemo(() => [
    { label: t('dashboard.startNewChat', 'Start New Chat'), href: '/chat' },
    { label: t('dashboard.createTask', 'Create Task'), href: '/tasks' },
    { label: t('dashboard.manageWorkflows', 'Workflows'), href: '/workflows' },
    { label: t('dashboard.manageTools', 'Manage Tools'), href: '/tools' },
  ], [t])

  // System metrics rows (mono tabular)
  const metricRows = useMemo(() => [
    { label: t('dashboard.requests', 'Total Requests'), value: String(stats.requestCount) },
    { label: t('dashboard.errorRate', 'Error Rate'), value: stats.errorRate },
    { label: t('dashboard.avgLatency', 'Avg Latency'), value: stats.avgLatency },
  ], [stats, t])

  return (
    <div className="min-h-full px-8 py-10 md:px-12">
      <div className="max-w-4xl">
        {/* Editorial header: short 2px rule + 32px/500 title */}
        <header className="mb-10">
          <div
            className="w-12 border-t-2 mb-5"
            style={{ borderColor: 'var(--fg)' }}
            aria-hidden="true"
          />
          <h1 className="text-[32px] leading-tight font-medium tracking-tight">
            {t('dashboard.title', 'Dashboard')}
          </h1>
          <p className="text-[13px] opacity-50 mt-2">
            {t('dashboard.subtitle', 'Welcome to X-Agent Control Center')}
          </p>
        </header>

        {/* Status row — no cards, 1px vertical dividers */}
        <section aria-label={t('dashboard.title', 'Dashboard')}>
          <dl className="flex flex-wrap gap-y-6">
            {statusItems.map((item, i) => (
              <div
                key={item.label}
                className={clsx(
                  'flex flex-col gap-2 pr-8 mr-8',
                  i < statusItems.length - 1 && 'border-r'
                )}
                style={i < statusItems.length - 1 ? { borderColor: DIVIDER } : undefined}
              >
                <dd className="font-data text-[26px] leading-none order-2">
                  {item.value}
                </dd>
                <dt className="text-[12px] uppercase tracking-[0.06em] opacity-50 order-1">
                  {item.label}
                </dt>
              </div>
            ))}
          </dl>
        </section>

        <hr className="my-10 border-0 border-t" style={{ borderColor: DIVIDER }} />

        {/* Quick actions — text links with → micro-interaction */}
        <section>
          <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
            {t('dashboard.quickActions', 'Quick Actions')}
          </h2>
          <nav className="flex flex-col">
            {quickActions.map((action) => (
              <a
                key={action.href}
                href={action.href}
                className="link-plain group flex items-center justify-between py-3 border-b text-[14px]"
                style={{ borderColor: DIVIDER }}
              >
                <span className="opacity-80 group-hover:opacity-100 transition-opacity duration-200">
                  {action.label}
                </span>
                <span
                  className="opacity-50 transition-transform duration-200 ease-out group-hover:translate-x-[3px]"
                  aria-hidden="true"
                >
                  →
                </span>
              </a>
            ))}
          </nav>
        </section>

        <hr className="my-10 border-0 border-t" style={{ borderColor: DIVIDER }} />

        {/* System metrics — mono tabular rows */}
        <section>
          <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
            {t('dashboard.systemMetrics', 'System Metrics')}
          </h2>
          <div className="font-data text-[13px]">
            {metricRows.map((row) => (
              <div
                key={row.label}
                className="flex items-baseline justify-between py-2.5 border-b"
                style={{ borderColor: DIVIDER }}
              >
                <span className="opacity-50">{row.label}</span>
                <span className="tabular-nums">{row.value}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
})

Dashboard.displayName = 'Dashboard'

export default Dashboard
