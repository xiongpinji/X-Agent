import React, { useState } from 'react'
import { Feedback } from '@/services/feedback'
import { Search, Eye, Trash2, CheckCircle, Clock, AlertCircle } from 'lucide-react'
import clsx from 'clsx'

interface FeedbackListProps {
  feedbacks: Feedback[]
  isLoading: boolean
  onSelectFeedback: (feedback: Feedback) => void
  onDeleteFeedback: (id: string) => void
  onStatusChange: (id: string, status: Feedback['status']) => void
  theme: 'light' | 'dark'
}

export const FeedbackList: React.FC<FeedbackListProps> = ({
  feedbacks,
  isLoading,
  onSelectFeedback,
  onDeleteFeedback,
  onStatusChange: _onStatusChange,
  theme,
}) => {
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [filterPriority, setFilterPriority] = useState<string>('all')
  const [sortBy, setSortBy] = useState<'date' | 'priority'>('date')

  const filteredFeedbacks = feedbacks.filter((fb) => {
    const matchesSearch =
      fb.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      fb.description.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesType = filterType === 'all' || fb.type === filterType
    const matchesStatus = filterStatus === 'all' || fb.status === filterStatus
    const matchesPriority = filterPriority === 'all' || fb.priority === filterPriority

    return matchesSearch && matchesType && matchesStatus && matchesPriority
  })

  const sortedFeedbacks = [...filteredFeedbacks].sort((a, b) => {
    if (sortBy === 'date') {
      return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    } else {
      const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 }
      return priorityOrder[a.priority] - priorityOrder[b.priority]
    }
  })

  const getStatusIcon = (status: Feedback['status']) => {
    switch (status) {
      case 'resolved':
        return <CheckCircle size={16} className="text-green-500" />
      case 'in_progress':
        return <Clock size={16} className="text-blue-500 animate-spin" />
      case 'closed':
        return <AlertCircle size={16} className="text-slate-500" />
      default:
        return <AlertCircle size={16} className="text-orange-500" />
    }
  }

  const getPriorityColor = (priority: Feedback['priority']) => {
    switch (priority) {
      case 'critical':
        return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
      case 'high':
        return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400'
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
      default:
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400'
    }
  }

  const getSentimentColor = (sentiment: Feedback['sentiment']) => {
    switch (sentiment) {
      case 'positive':
        return 'text-green-600 dark:text-green-400'
      case 'negative':
        return 'text-red-600 dark:text-red-400'
      default:
        return 'text-slate-600 dark:text-slate-400'
    }
  }

  return (
    <div className="space-y-4">
      {/* Search and Filters */}
      <div className="space-y-4">
        <div className={clsx(
          'flex items-center gap-2 px-4 py-2 rounded-lg border',
          theme === 'dark'
            ? 'bg-slate-800 border-slate-700'
            : 'bg-white border-slate-200'
        )}>
          <Search size={18} className={theme === 'dark' ? 'text-slate-400' : 'text-slate-500'} />
          <input
            type="text"
            placeholder="Search feedbacks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={clsx(
              'flex-1 bg-transparent outline-none text-sm',
              theme === 'dark' ? 'text-white placeholder-slate-500' : 'text-slate-900 placeholder-slate-400'
            )}
          />
        </div>

        <div className="flex flex-wrap gap-2">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className={clsx(
              'px-3 py-2 rounded-lg text-sm border outline-none',
              theme === 'dark'
                ? 'bg-slate-800 border-slate-700 text-white'
                : 'bg-white border-slate-200 text-slate-900'
            )}
          >
            <option value="all">All Types</option>
            <option value="bug">Bug</option>
            <option value="feature">Feature</option>
            <option value="improvement">Improvement</option>
            <option value="other">Other</option>
          </select>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className={clsx(
              'px-3 py-2 rounded-lg text-sm border outline-none',
              theme === 'dark'
                ? 'bg-slate-800 border-slate-700 text-white'
                : 'bg-white border-slate-200 text-slate-900'
            )}
          >
            <option value="all">All Status</option>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>

          <select
            value={filterPriority}
            onChange={(e) => setFilterPriority(e.target.value)}
            className={clsx(
              'px-3 py-2 rounded-lg text-sm border outline-none',
              theme === 'dark'
                ? 'bg-slate-800 border-slate-700 text-white'
                : 'bg-white border-slate-200 text-slate-900'
            )}
          >
            <option value="all">All Priorities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>

          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as 'date' | 'priority')}
            className={clsx(
              'px-3 py-2 rounded-lg text-sm border outline-none',
              theme === 'dark'
                ? 'bg-slate-800 border-slate-700 text-white'
                : 'bg-white border-slate-200 text-slate-900'
            )}
          >
            <option value="date">Sort by Date</option>
            <option value="priority">Sort by Priority</option>
          </select>
        </div>
      </div>

      {/* Feedbacks List */}
      <div className="space-y-2">
        {isLoading ? (
          <div className={clsx(
            'p-8 text-center rounded-lg',
            theme === 'dark' ? 'bg-slate-800' : 'bg-slate-100'
          )}>
            <p className={theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}>
              Loading feedbacks...
            </p>
          </div>
        ) : sortedFeedbacks.length === 0 ? (
          <div className={clsx(
            'p-8 text-center rounded-lg',
            theme === 'dark' ? 'bg-slate-800' : 'bg-slate-100'
          )}>
            <p className={clsx(
              'font-medium mb-1',
              theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
            )}>
              No feedbacks found
            </p>
            <p className={theme === 'dark' ? 'text-slate-500' : 'text-slate-600'}>
              Try adjusting your filters or search query
            </p>
          </div>
        ) : (
          sortedFeedbacks.map((feedback) => (
            <div
              key={feedback.id}
              role="button"
              tabIndex={0}
              className={clsx(
                'p-4 rounded-lg border transition-all hover:shadow-md cursor-pointer',
                theme === 'dark'
                  ? 'bg-slate-800 border-slate-700 hover:border-slate-600'
                  : 'bg-white border-slate-200 hover:border-slate-300'
              )}
              onClick={() => onSelectFeedback(feedback)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelectFeedback(feedback); }}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    {getStatusIcon(feedback.status)}
                    <h3 className={clsx(
                      'font-semibold truncate',
                      theme === 'dark' ? 'text-white' : 'text-slate-900'
                    )}>
                      {feedback.title}
                    </h3>
                  </div>

                  <p className={clsx(
                    'text-sm mb-3 line-clamp-2',
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  )}>
                    {feedback.description}
                  </p>

                  <div className="flex flex-wrap items-center gap-2">
                    <span className={clsx(
                      'inline-block px-2 py-1 rounded text-xs font-medium',
                      getPriorityColor(feedback.priority)
                    )}>
                      {feedback.priority}
                    </span>

                    <span className={clsx(
                      'inline-block px-2 py-1 rounded text-xs font-medium',
                      theme === 'dark'
                        ? 'bg-slate-700 text-slate-300'
                        : 'bg-slate-200 text-slate-700'
                    )}>
                      {feedback.type}
                    </span>

                    <span className={clsx(
                      'inline-block px-2 py-1 rounded text-xs font-medium',
                      getSentimentColor(feedback.sentiment)
                    )}>
                      {feedback.sentiment}
                    </span>

                    <span className={clsx(
                      'text-xs',
                      theme === 'dark' ? 'text-slate-500' : 'text-slate-500'
                    )}>
                      {new Date(feedback.createdAt).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onSelectFeedback(feedback)
                    }}
                    className={clsx(
                      'p-2 rounded-lg transition-colors',
                      theme === 'dark'
                        ? 'hover:bg-slate-700 text-slate-400'
                        : 'hover:bg-slate-200 text-slate-600'
                    )}
                    title="View details"
                  >
                    <Eye size={16} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onDeleteFeedback(feedback.id)
                    }}
                    className={clsx(
                      'p-2 rounded-lg transition-colors',
                      theme === 'dark'
                        ? 'hover:bg-red-900/20 text-red-400'
                        : 'hover:bg-red-100 text-red-600'
                    )}
                    title="Delete feedback"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default FeedbackList
