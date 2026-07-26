import React, { useEffect, useState, useMemo, useCallback } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiClient, DashboardMetrics } from '@/services/api'
import { useI18n } from '@/i18n/context'
import { Activity, Users, Zap, Clock } from 'lucide-react'
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

// Memoized StatCard component
const StatCard: React.FC<{
  icon: React.ReactNode
  label: string
  value: string | number
  color: 'blue' | 'green' | 'purple' | 'orange'
}> = React.memo(({ icon, label, value, color }) => {
  const { theme } = useAppStore()
  const colorClasses = {
    blue: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
    green: 'bg-green-500/10 text-green-600 dark:text-green-400',
    purple: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
    orange: 'bg-orange-500/10 text-orange-600 dark:text-orange-400',
  }

  return (
    <div className={clsx(
      'rounded-lg p-6',
      theme === 'dark' ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200'
    )}>
      <div className={clsx('p-3 rounded-lg w-fit mb-4', colorClasses[color])}>
        {icon}
      </div>
      <p className={clsx(
        'text-sm font-medium mb-1',
        theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
      )}>
        {label}
      </p>
      <p className={clsx(
        'text-3xl font-bold',
        theme === 'dark' ? 'text-white' : 'text-slate-900'
      )}>
        {value}
      </p>
    </div>
  )
})

StatCard.displayName = 'StatCard'

// Memoized QuickActionButton component
const QuickActionButton: React.FC<{
  label: string
  href: string
}> = React.memo(({ label, href }) => {
  const { theme } = useAppStore()

  return (
    <a
      href={href}
      className={clsx(
        'px-4 py-3 rounded-lg font-medium transition-colors text-center',
        theme === 'dark'
          ? 'bg-blue-600 hover:bg-blue-700 text-white'
          : 'bg-blue-500 hover:bg-blue-600 text-white'
      )}
    >
      {label}
    </a>
  )
})

QuickActionButton.displayName = 'QuickActionButton'

export const Dashboard: React.FC = React.memo(() => {
  const { theme, setLoading, setError } = useAppStore()
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

  // Memoize stat cards to prevent unnecessary re-renders
  const statCards = useMemo(() => [
    {
      icon: <Users size={24} />,
      label: t('dashboard.totalAgents', 'Total Agents'),
      value: stats.totalAgents,
      color: 'blue' as const,
    },
    {
      icon: <Activity size={24} />,
      label: t('dashboard.activeTasks', 'Active Tasks'),
      value: stats.activeTasks,
      color: 'green' as const,
    },
    {
      icon: <Zap size={24} />,
      label: t('dashboard.totalTools', 'Total Tools'),
      value: stats.totalTools,
      color: 'purple' as const,
    },
    {
      icon: <Clock size={24} />,
      label: t('dashboard.uptime', 'Uptime'),
      value: stats.uptime,
      color: 'orange' as const,
    },
  ], [stats, t])

  const quickActions = useMemo(() => [
    { label: t('dashboard.startNewChat', 'Start New Chat'), href: '/chat' },
    { label: t('dashboard.createTask', 'Create Task'), href: '/tasks' },
    { label: t('dashboard.manageWorkflows', 'Workflows'), href: '/workflows' },
    { label: t('dashboard.manageTools', 'Manage Tools'), href: '/tools' },
  ], [t])

  return (
    <div className={clsx(
      'p-8',
      theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50'
    )}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className={clsx(
            'text-4xl font-bold mb-2',
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          )}>
            {t('dashboard.title', 'Dashboard')}
          </h1>
          <p className={clsx(
            'text-lg',
            theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
          )}>
            {t('dashboard.subtitle', 'Welcome to X-Agent Control Center')}
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {statCards.map((card, index) => (
            <StatCard
              key={index}
              icon={card.icon}
              label={card.label}
              value={card.value}
              color={card.color}
            />
          ))}
        </div>

        {/* Quick Actions */}
        <div className={clsx(
          'rounded-lg p-6 mb-8',
          theme === 'dark' ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200'
        )}>
          <h2 className={clsx(
            'text-xl font-bold mb-4',
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          )}>
            {t('dashboard.quickActions', 'Quick Actions')}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {quickActions.map((action, index) => (
              <QuickActionButton
                key={index}
                label={action.label}
                href={action.href}
              />
            ))}
          </div>
        </div>

        {/* Recent Activity */}
        <div className={clsx(
          'rounded-lg p-6',
          theme === 'dark' ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200'
        )}>
          <h2 className={clsx(
            'text-xl font-bold mb-4',
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          )}>
            {t('dashboard.systemMetrics', 'System Metrics')}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className={clsx('p-4 rounded-lg', theme === 'dark' ? 'bg-slate-800' : 'bg-slate-50')}>
              <p className={clsx('text-xs mb-1', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>{t('dashboard.requests', 'Total Requests')}</p>
              <p className="text-lg font-bold">{stats.requestCount}</p>
            </div>
            <div className={clsx('p-4 rounded-lg', theme === 'dark' ? 'bg-slate-800' : 'bg-slate-50')}>
              <p className={clsx('text-xs mb-1', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>{t('dashboard.errorRate', 'Error Rate')}</p>
              <p className="text-lg font-bold">{stats.errorRate}</p>
            </div>
            <div className={clsx('p-4 rounded-lg', theme === 'dark' ? 'bg-slate-800' : 'bg-slate-50')}>
              <p className={clsx('text-xs mb-1', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>{t('dashboard.avgLatency', 'Avg Latency')}</p>
              <p className="text-lg font-bold">{stats.avgLatency}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
})

Dashboard.displayName = 'Dashboard'

export default Dashboard
