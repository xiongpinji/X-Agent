import React, { useEffect, useState, useMemo, useCallback } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiClient } from '@/services/api'
import { Activity, Users, Zap, Clock } from 'lucide-react'
import clsx from 'clsx'

interface DashboardStats {
  totalAgents: number
  activeTasks: number
  totalTools: number
  uptime: string
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
  const { theme, isLoading, setLoading, setError } = useAppStore()
  const [stats, setStats] = useState<DashboardStats>({
    totalAgents: 0,
    activeTasks: 0,
    totalTools: 0,
    uptime: '99.9%',
  })

  useEffect(() => {
    loadDashboardData()
  }, [])

  const loadDashboardData = useCallback(async () => {
    try {
      setLoading(true)
      const [agents, tools] = await Promise.all([
        apiClient.listAgents(),
        apiClient.listTools(),
      ])

      setStats({
        totalAgents: agents.length,
        activeTasks: 0,
        totalTools: tools.length,
        uptime: '99.9%',
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
      label: 'Total Agents',
      value: stats.totalAgents,
      color: 'blue' as const,
    },
    {
      icon: <Activity size={24} />,
      label: 'Active Tasks',
      value: stats.activeTasks,
      color: 'green' as const,
    },
    {
      icon: <Zap size={24} />,
      label: 'Total Tools',
      value: stats.totalTools,
      color: 'purple' as const,
    },
    {
      icon: <Clock size={24} />,
      label: 'Uptime',
      value: stats.uptime,
      color: 'orange' as const,
    },
  ], [stats])

  const quickActions = useMemo(() => [
    { label: 'Start New Chat', href: '/chat' },
    { label: 'Create Task', href: '/tasks' },
    { label: 'Manage Tools', href: '/tools' },
  ], [])

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
            Dashboard
          </h1>
          <p className={clsx(
            'text-lg',
            theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
          )}>
            Welcome to X-Agent Control Center
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
            Quick Actions
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
            Recent Activity
          </h2>
          <div className={clsx(
            'text-center py-8',
            theme === 'dark' ? 'text-slate-400' : 'text-slate-500'
          )}>
            <p>No recent activity</p>
          </div>
        </div>
      </div>
    </div>
  )
})

Dashboard.displayName = 'Dashboard'

export default Dashboard
