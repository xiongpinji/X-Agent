import React, { FormEvent, useCallback, useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { feedbackService, Feedback, FeedbackStats, FeedbackTrend } from '@/services/feedback'
import { FeedbackList } from '@/components/feedback/FeedbackList'
import { FeedbackDetail } from '@/components/feedback/FeedbackDetail'
import { FeedbackVisualization } from '@/components/feedback/FeedbackVisualization'
import { BarChart3, Download, MessageSquare, Plus } from 'lucide-react'
import clsx from 'clsx'

type TabType = 'list' | 'analytics'

const emptyDraft = {
  type: 'bug' as Feedback['type'],
  title: '',
  description: '',
  priority: 'medium' as Feedback['priority'],
}

export const FeedbackDashboard: React.FC = () => {
  const { theme, isLoading, setLoading, setError } = useAppStore()
  const [activeTab, setActiveTab] = useState<TabType>('list')
  const [feedbacks, setFeedbacks] = useState<Feedback[]>([])
  const [stats, setStats] = useState<FeedbackStats | null>(null)
  const [trends, setTrends] = useState<FeedbackTrend[] | null>(null)
  const [selectedFeedback, setSelectedFeedback] = useState<Feedback | null>(null)
  const [showDetailModal, setShowDetailModal] = useState(false)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [draft, setDraft] = useState(emptyDraft)

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      const [feedbacksData, statsData, trendsData] = await Promise.all([
        feedbackService.listFeedback(1, 50),
        feedbackService.getStats(),
        feedbackService.getTrends(30, 'day'),
      ])
      setFeedbacks(feedbacksData.items)
      setStats(statsData)
      setTrends(trendsData)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load feedback data')
    } finally {
      setLoading(false)
    }
  }, [setError, setLoading])

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [loadData])

  const handleCreateFeedback = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    try {
      const created = await feedbackService.createFeedback(draft)
      setFeedbacks((current) => [created, ...current])
      setDraft(emptyDraft)
      setShowCreateForm(false)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to create feedback')
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
      setFeedbacks((current) => current.filter((feedback) => feedback.id !== id))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to delete feedback')
    }
  }

  const handleUpdateFeedback = async (id: string, data: Partial<Feedback>) => {
    try {
      const updated = await feedbackService.updateFeedback(id, data)
      setFeedbacks((current) => current.map((feedback) => (
        feedback.id === id ? updated : feedback
      )))
      setSelectedFeedback((current) => current?.id === id ? updated : current)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to update feedback')
    }
  }

  const handleResolveFeedback = async (id: string) => {
    try {
      const updated = await feedbackService.resolveFeedback(id)
      setFeedbacks((current) => current.map((feedback) => (
        feedback.id === id ? updated : feedback
      )))
      setSelectedFeedback((current) => current?.id === id ? updated : current)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to resolve feedback')
    }
  }

  const handleExport = async (format: 'csv' | 'json') => {
    try {
      setLoading(true)
      const blob = await feedbackService.exportFeedback(format)
      const url = window.URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `feedback-export.${format}`
      document.body.appendChild(anchor)
      anchor.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(anchor)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to export feedback')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={clsx('min-h-screen p-8', theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50')}>
      <div className="max-w-7xl mx-auto">
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
                Manage and analyze persisted user feedback
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowCreateForm((visible) => !visible)}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors"
              >
                <Plus size={18} />
                New feedback
              </button>
              {(['csv', 'json'] as const).map((format) => (
                <button
                  key={format}
                  type="button"
                  onClick={() => handleExport(format)}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors uppercase"
                >
                  <Download size={18} />
                  {format}
                </button>
              ))}
            </div>
          </div>

          {showCreateForm && (
            <form
              aria-label="Create feedback"
              onSubmit={handleCreateFeedback}
              className={clsx(
                'mb-5 grid gap-3 rounded-lg border p-4',
                theme === 'dark' ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
              )}
            >
              <label className="grid gap-1 text-sm">
                Title
                <input
                  required
                  value={draft.title}
                  onChange={(event) => setDraft((current) => ({
                    ...current,
                    title: event.target.value,
                  }))}
                  className="rounded border border-slate-300 px-3 py-2 text-slate-900"
                />
              </label>
              <label className="grid gap-1 text-sm">
                Description
                <textarea
                  required
                  value={draft.description}
                  onChange={(event) => setDraft((current) => ({
                    ...current,
                    description: event.target.value,
                  }))}
                  className="rounded border border-slate-300 px-3 py-2 text-slate-900"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="grid gap-1 text-sm">
                  Type
                  <select
                    value={draft.type}
                    onChange={(event) => setDraft((current) => ({
                      ...current,
                      type: event.target.value as Feedback['type'],
                    }))}
                    className="rounded border border-slate-300 px-3 py-2 text-slate-900"
                  >
                    <option value="bug">Bug</option>
                    <option value="feature">Feature</option>
                    <option value="improvement">Improvement</option>
                    <option value="other">Other</option>
                  </select>
                </label>
                <label className="grid gap-1 text-sm">
                  Priority
                  <select
                    value={draft.priority}
                    onChange={(event) => setDraft((current) => ({
                      ...current,
                      priority: event.target.value as Feedback['priority'],
                    }))}
                    className="rounded border border-slate-300 px-3 py-2 text-slate-900"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </label>
              </div>
              <button
                type="submit"
                className="justify-self-start rounded bg-green-600 px-4 py-2 font-medium text-white hover:bg-green-700"
              >
                Create
              </button>
            </form>
          )}

          <div className="flex gap-2 border-b" style={{
            borderColor: theme === 'dark' ? '#475569' : '#e2e8f0'
          }}>
            {(['list', 'analytics'] as const).map((tab) => (
              <button
                key={tab}
                type="button"
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
                {tab === 'list' ? <MessageSquare size={18} /> : <BarChart3 size={18} />}
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>
        </div>

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
