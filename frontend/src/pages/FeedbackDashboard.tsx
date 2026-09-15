import React, { useCallback, useEffect, useState } from 'react'
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

  const loadData = useCallback(async () => {
    // Notifications are loaded separately from the core dataset. They now have
    // real backend endpoints (api/notification_configs.py, mounted 2026-09-14),
    // but the split stays: a notifications failure should degrade the tab to its
    // empty state, not take the whole page down (and re-fail on the 30s interval).
    try {
      setLoading(true)
      const [feedbacksData, statsData, trendsData] = await Promise.all([
        feedbackService.listFeedback(1, 50),
        feedbackService.getStats(),
        feedbackService.getTrends(30),
      ])

      setFeedbacks(feedbacksData.items)
      setStats(statsData)
      setTrends(trendsData)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load feedback data')
    } finally {
      setLoading(false)
    }

    try {
      setNotifications(await feedbackService.listNotifications())
    } catch {
      // Transient failure only (network / 403 / 404): the tab renders its empty
      // state rather than taking the whole page down.
      setNotifications([])
    }
  }, [setLoading, setError])

  useEffect(() => {
    loadData()
    // Refresh data every 30 seconds
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [loadData])

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

  // Returns whether the change was persisted so the detail view does not leave
  // its edit mode on failure. This page reports the error itself.
  const handleUpdateFeedback = async (id: string, data: Partial<Feedback>): Promise<boolean> => {
    try {
      const updated = await feedbackService.updateFeedback(id, data)
      setFeedbacks(feedbacks.map((f) => (f.id === id ? updated : f)))
      if (selectedFeedback?.id === id) {
        setSelectedFeedback(updated)
      }
      return true
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to update feedback')
      return false
    }
  }

  // Same contract as handleUpdateFeedback: the boolean drives the editor state.
  const handleResolveFeedback = async (id: string, response: string): Promise<boolean> => {
    try {
      const updated = await feedbackService.resolveFeedback(id, response)
      setFeedbacks(feedbacks.map((f) => (f.id === id ? updated : f)))
      if (selectedFeedback?.id === id) {
        setSelectedFeedback(updated)
      }
      return true
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to resolve feedback')
      return false
    }
  }

  // Returns whether the channel was saved so the form does not close on failure.
  const handleAddNotification = async (data: Partial<NotificationConfig>): Promise<boolean> => {
    try {
      const created = await feedbackService.createNotification(data)
      setNotifications([...notifications, created])
      return true
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to create notification')
      return false
    }
  }

  // Same contract as handleAddNotification: the boolean drives form visibility.
  const handleUpdateNotification = async (
    id: string,
    data: Partial<NotificationConfig>
  ): Promise<boolean> => {
    try {
      const updated = await feedbackService.updateNotification(id, data)
      setNotifications(notifications.map((n) => (n.id === id ? updated : n)))
      return true
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to update notification')
      return false
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

  // Returns the delivery outcome to NotificationSettings. The backend answers
  // 200 with success:false when the channel is configured but nothing could be
  // delivered; discarding that is exactly how the UI used to report a false
  // "sent successfully".
  const handleTestNotification = async (
    id: string
  ): Promise<{ success: boolean; message: string }> => {
    return feedbackService.testNotification(id)
  }

  const handleExport = async (format: 'csv' | 'json') => {
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
                onClick={() => handleExport('json')}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
              >
                <Download size={18} />
                JSON
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
