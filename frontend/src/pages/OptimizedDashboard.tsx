import React, { useEffect, useState } from 'react'
import clsx from 'clsx'
import { useAppStore } from '@/store/appStore'
import { apiClient } from '@/services/api'
import { Button, Card, CardBody, StatCard, Tabs, LoadingState } from '@/components/ui'
import { Activity, Users, Zap, Clock, TrendingUp } from 'lucide-react'

export const OptimizedDashboard: React.FC = () => {
  const { theme, isLoading, setLoading, setError } = useAppStore()
  const [stats, setStats] = useState({
    totalAgents: 0,
    activeTasks: 0,
    totalTools: 0,
    uptime: '99.9%',
    successRate: 98.5,
  })

  useEffect(() => {
    loadDashboardData()
  }, [])

  const loadDashboardData = async () => {
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
        successRate: 98.5,
      })
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }

  const tabs = [
    {
      id: 'overview',
      label: 'Overview',
      content: (
        <div className="space-y-6">
          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <StatCard
              icon={<Users size={24} />}
              label="Total Agents"
              value={stats.totalAgents}
              color="blue"
            />
            <StatCard
              icon={<Activity size={24} />}
              label="Active Tasks"
              value={stats.activeTasks}
              color="green"
            />
            <StatCard
              icon={<Zap size={24} />}
              label="Total Tools"
              value={stats.totalTools}
              color="purple"
            />
            <StatCard
              icon={<Clock size={24} />}
              label="Uptime"
              value={stats.uptime}
              color="orange"
            />
            <StatCard
              icon={<TrendingUp size={24} />}
              label="Success Rate"
              value={`${stats.successRate}%`}
              change={{ value: 2.5, direction: 'up' }}
              color="green"
            />
          </div>

          {/* Quick Actions */}
          <Card>
            <CardBody>
              <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Button variant="primary" className="w-full">
                  Start New Chat
                </Button>
                <Button variant="secondary" className="w-full">
                  Create Task
                </Button>
                <Button variant="secondary" className="w-full">
                  Manage Tools
                </Button>
              </div>
            </CardBody>
          </Card>
        </div>
      ),
    },
    {
      id: 'activity',
      label: 'Recent Activity',
      content: (
        <Card>
          <CardBody>
            <p className="text-slate-600 dark:text-slate-400 text-center py-8">
              No recent activity
            </p>
          </CardBody>
        </Card>
      ),
    },
  ]

  return (
    <div className={clsx('p-8', theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50')}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className={clsx('text-4xl font-bold mb-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
            Dashboard
          </h1>
          <p className={clsx('text-lg', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
            Welcome to X-Agent Control Center
          </p>
        </div>

        {/* Content */}
        {isLoading ? (
          <LoadingState message="Loading dashboard..." />
        ) : (
          <Tabs tabs={tabs} defaultTab="overview" />
        )}
      </div>
    </div>
  )
}

export default OptimizedDashboard
