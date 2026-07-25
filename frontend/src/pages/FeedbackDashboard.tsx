import React, { useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { feedbackService, Feedback, FeedbackStats, FeedbackTrend, NotificationConfig } from '@/services/feedback'
import { FeedbackList } from '@/components/feedback/FeedbackList'
import { FeedbackDetail } from '@/components/feedback/FeedbackDetail'
import { FeedbackVisualization } from '@/components/feedback/FeedbackVisualization'
import { NotificationSettings } from '@/components/feedback/NotificationSettings'
import { Download, Settings, BarChart3, MessageSquare } from 'lucide-react'
import clsx from 'clsx'

type TabType = 'list' | 'analytics' | 'notifications'

export const FeedbackDashboard: React.FC = () => {
  const { theme, isLoading, setLoading, setError } = useAppStore()
  const [activeTab, setActiveTab] = useState<TabType>('list')
  const [feedbacks, setFeedbacks] = useState<Feedback[]>([])
  const [stats, setStats] = useState<FeedbackStats | null>(null)
  const [trends, setTrends] = useState<FeedbackTrend[] | null>(null)
  const [notifications, setNotifications] = useState<NotificationConfig[]>([])
  const [selectedFeedback, setSelectedFeedback] = useState<Feedback | null>(null)
  const [showDetailModal, setShowDetailModal] = useState(false)

  useEffect(() => {
    loadData()
    // Refresh data every 30 seconds
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      const [feedbacksData, statsData, trendsData, notificationsData] = await Promise.all([
        feedbackService.listFeedback(1, 50),
        feedbackService.getStats(),
        feedbackService.getTrends(30, 'day'),
        feedbackService.listNotifications(),
      ])

      setFeedbacks(feedbacksData.items)
      setStats(statsData)
      setTrends(trendsData)
      setNotifications(notificationsData)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load feedback data')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectFeedback = (feedback: Feedback) => {
    setSelectedFeedback(feedback)
    setShowDetailModal(true)
  }

  const handleDeleteFeedback = async (id: string) => {
    if (!confirm('Are you sure you want to delete this feedback?')) return

    try {
      await feedbackService.deleteFeedback(id)
      setFeedbacks(feedbacks.filter((f) => f.id !== id))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to delete feedback')
    }
  }

  const handleUpdateFeedback = async (id: string, data: Partial<Feedback>) => {
    try {
      const updated = await feedbackService.updateFeedback(id, data)
      setFeedbacks(feedbacks.map((f) => (f.id === id ? updated : f)))
      if (selectedFeedback?.id === id) {
        setSelectedFeedback(updated)
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to update feedback')
    }
  }

  const handleResolveFeedback = async (id: string, response: string) => {
    try {
      const updated = await feedbackService.resolveFeedback(id, response)
      setFeedbacks(feedbacks.map((f) => (f.id === id ? updated : f)))
      if (selectedFeedback?.id === id) {
        setSelectedFeedback(updated)
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to resolve feedback')
    }
  }

  const handleAddNotification = async (data: Partial<NotificationConfig>) => {
    try {
      const created = await feedbackService.createNotification(data)
      setNotifications([...notifications, created])
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to create notification')
    }
  }

  const handleUpdateNotification = async (id: string, data: Partial<NotificationConfig>) => {
    try {
      const updated = await feedbackService.updateNotification(id, data)
      setNotifications(notifications.map((n) => (n.id === id ? updated : n)))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to update notification')
    }
  }

  const handleDeleteNotification = async (id: string) => {
    try {
      await feedbackService.deleteNotification(id)
      setNotifications(notifications.filter((n) => n.id !== id))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to delete notification')
    }
  }

  const handleTestNotification = async (id: string) => {
    await feedbackService.testNotification(id)
  }

  const handleExport = async (format: 'csv' | 'pdf') => {
    try {
      setLoading(true)
      const blob = await feedbackService.exportFeedback(format)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `feedback-export.${format}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to export feedback')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={clsx(
      'min-h-screen p-8',
      theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50'
    )}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className={clsx(
                'text-4xl font-bold mb-2',
                theme === 'dark' ? 'text-white' : 'text-slate-900'
              )}>
                Feedback Dashboard
              </h1>
              <p className={clsx(
                'text-sm',
                theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
              )}>
                Manage and analyze user feedback in real-time
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => handleExport('csv')}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
              >
                <Download size={18} />
                CSV
              </button>
              <button
                onClick={() => handleExport('pdf')}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
              >
                <Download size={18} />
                PDF
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-2 border-b" style={{
            borderColor: theme === 'dark' ? '#475569' : '#e2e8f0'
          }}>
            {(['list', 'analytics', 'notifications'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={clsx(
                  'flex items-center gap-2 px-4 py-3 font-medium transition-colors border-b-2',
                  activeTab === tab
                    ? 'border-blue-600 text-blue-600'
                    : theme === 'dark'
                      ? 'border-transparent text-slate-400 hover:text-slate-300'
                      : 'border-transparent text-slate-600 hover:text-slate-900'
                )}
              >
                {tab === 'list' && <MessageSquare size={18} />}
                {tab === 'analytics' && <BarChart3 size={18} />}
                {tab === 'notifications' && <Settings size={18} />}
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div>
          {activeTab === 'list' && (
            <FeedbackList
              feedbacks={feedbacks}
              isLoading={isLoading}
              onSelectFeedback={handleSelectFeedback}
              onDeleteFeedback={handleDeleteFeedback}
              onStatusChange={(id, status) => handleUpdateFeedback(id, { status })}
              theme={theme}
            />
          )}

          {activeTab === 'analytics' && (
            <FeedbackVisualization
              stats={stats}
              trends={trends}
              isLoading={isLoading}
              theme={theme}
            />
          )}

          {activeTab === 'notifications' && (
            <NotificationSettings
              notifications={notifications}
              onAdd={handleAddNotification}
              onUpdate={handleUpdateNotification}
              onDelete={handleDeleteNotification}
              onTest={handleTestNotification}
              theme={theme}
            />
          )}
        </div>

        {/* Detail Modal */}
        {showDetailModal && selectedFeedback && (
          <FeedbackDetail
            feedback={selectedFeedback}
            onClose={() => {
              setShowDetailModal(false)
              setSelectedFeedback(null)
            }}
            onUpdate={handleUpdateFeedback}
            onResolve={handleResolveFeedback}
            theme={theme}
          />
        )}
      </div>
    </div>
  )
}

export default FeedbackDashboard
