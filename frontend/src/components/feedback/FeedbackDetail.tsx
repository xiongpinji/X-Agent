import React, { useState } from 'react'
import { Feedback } from '@/services/feedback'
import { X, Send, Edit2, Save, AlertCircle, CheckCircle, Clock } from 'lucide-react'
import clsx from 'clsx'

interface FeedbackDetailProps {
  feedback: Feedback
  onClose: () => void
  onUpdate: (id: string, data: Partial<Feedback>) => void
  onResolve: (id: string, response: string) => void
  theme: 'light' | 'dark'
}

export const FeedbackDetail: React.FC<FeedbackDetailProps> = ({
  feedback,
  onClose,
  onUpdate,
  onResolve,
  theme,
}) => {
  const [isEditing, setIsEditing] = useState(false)
  const [editedStatus, setEditedStatus] = useState(feedback.status)
  const [editedPriority, setEditedPriority] = useState(feedback.priority)
  const [responseText, setResponseText] = useState('')
  const [isSubmittingResponse, setIsSubmittingResponse] = useState(false)

  const handleSaveChanges = async () => {
    await onUpdate(feedback.id, {
      status: editedStatus,
      priority: editedPriority,
    })
    setIsEditing(false)
  }

  const handleSubmitResponse = async () => {
    if (!responseText.trim()) return

    setIsSubmittingResponse(true)
    try {
      await onResolve(feedback.id, responseText)
      setResponseText('')
    } finally {
      setIsSubmittingResponse(false)
    }
  }

  const getStatusColor = (status: Feedback['status']) => {
    switch (status) {
      case 'resolved':
        return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
      case 'in_progress':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400'
      case 'closed':
        return 'bg-slate-100 text-slate-800 dark:bg-slate-900/30 dark:text-slate-400'
      default:
        return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400'
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

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className={clsx(
        'rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto',
        theme === 'dark' ? 'bg-slate-900' : 'bg-white'
      )}>
        {/* Header */}
        <div className={clsx(
          'flex items-center justify-between p-6 border-b',
          theme === 'dark' ? 'border-slate-700' : 'border-slate-200'
        )}>
          <h2 className={clsx(
            'text-2xl font-bold',
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          )}>
            {feedback.title}
          </h2>
          <button
            onClick={onClose}
            className={clsx(
              'p-2 rounded-lg transition-colors',
              theme === 'dark'
                ? 'hover:bg-slate-800 text-slate-400'
                : 'hover:bg-slate-100 text-slate-600'
            )}
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Description */}
          <div>
            <h3 className={clsx(
              'text-sm font-semibold mb-2',
              theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
            )}>
              Description
            </h3>
            <p className={clsx(
              'text-sm leading-relaxed',
              theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
            )}>
              {feedback.description}
            </p>
          </div>

          {/* Metadata */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className={clsx(
                'text-xs font-semibold mb-1 uppercase',
                theme === 'dark' ? 'text-slate-500' : 'text-slate-500'
              )}>
                Type
              </p>
              <p className={clsx(
                'text-sm font-medium capitalize',
                theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              )}>
                {feedback.type}
              </p>
            </div>

            <div>
              <p className={clsx(
                'text-xs font-semibold mb-1 uppercase',
                theme === 'dark' ? 'text-slate-500' : 'text-slate-500'
              )}>
                Category
              </p>
              <p className={clsx(
                'text-sm font-medium',
                theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              )}>
                {feedback.category}
              </p>
            </div>

            <div>
              <p className={clsx(
                'text-xs font-semibold mb-1 uppercase',
                theme === 'dark' ? 'text-slate-500' : 'text-slate-500'
              )}>
                Sentiment
              </p>
              <p className={clsx(
                'text-sm font-medium capitalize',
                feedback.sentiment === 'positive' ? 'text-green-600 dark:text-green-400' :
                feedback.sentiment === 'negative' ? 'text-red-600 dark:text-red-400' :
                'text-slate-600 dark:text-slate-400'
              )}>
                {feedback.sentiment}
              </p>
            </div>

            <div>
              <p className={clsx(
                'text-xs font-semibold mb-1 uppercase',
                theme === 'dark' ? 'text-slate-500' : 'text-slate-500'
              )}>
                Created
              </p>
              <p className={clsx(
                'text-sm font-medium',
                theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              )}>
                {new Date(feedback.createdAt).toLocaleDateString()}
              </p>
            </div>
          </div>

          {/* Status and Priority */}
          <div className={clsx(
            'p-4 rounded-lg border',
            theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-slate-50 border-slate-200'
          )}>
            <div className="flex items-center justify-between mb-4">
              <h3 className={clsx(
                'text-sm font-semibold',
                theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              )}>
                Status & Priority
              </h3>
              {!isEditing && (
                <button
                  onClick={() => setIsEditing(true)}
                  className={clsx(
                    'flex items-center gap-1 px-3 py-1 rounded text-sm font-medium transition-colors',
                    theme === 'dark'
                      ? 'hover:bg-slate-700 text-slate-400'
                      : 'hover:bg-slate-200 text-slate-600'
                  )}
                >
                  <Edit2 size={14} />
                  Edit
                </button>
              )}
            </div>

            {isEditing ? (
              <div className="space-y-3">
                <div>
                  <label className={clsx(
                    'block text-xs font-semibold mb-1',
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  )}>
                    Status
                  </label>
                  <select
                    value={editedStatus}
                    onChange={(e) => setEditedStatus(e.target.value as Feedback['status'])}
                    className={clsx(
                      'w-full px-3 py-2 rounded border outline-none text-sm',
                      theme === 'dark'
                        ? 'bg-slate-700 border-slate-600 text-white'
                        : 'bg-white border-slate-300 text-slate-900'
                    )}
                  >
                    <option value="open">Open</option>
                    <option value="in_progress">In Progress</option>
                    <option value="resolved">Resolved</option>
                    <option value="closed">Closed</option>
                  </select>
                </div>

                <div>
                  <label className={clsx(
                    'block text-xs font-semibold mb-1',
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  )}>
                    Priority
                  </label>
                  <select
                    value={editedPriority}
                    onChange={(e) => setEditedPriority(e.target.value as Feedback['priority'])}
                    className={clsx(
                      'w-full px-3 py-2 rounded border outline-none text-sm',
                      theme === 'dark'
                        ? 'bg-slate-700 border-slate-600 text-white'
                        : 'bg-white border-slate-300 text-slate-900'
                    )}
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={handleSaveChanges}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium transition-colors text-sm"
                  >
                    <Save size={14} />
                    Save
                  </button>
                  <button
                    onClick={() => {
                      setIsEditing(false)
                      setEditedStatus(feedback.status)
                      setEditedPriority(feedback.priority)
                    }}
                    className={clsx(
                      'flex-1 px-3 py-2 rounded font-medium transition-colors text-sm',
                      theme === 'dark'
                        ? 'bg-slate-700 hover:bg-slate-600 text-white'
                        : 'bg-slate-200 hover:bg-slate-300 text-slate-900'
                    )}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex gap-4">
                <div>
                  <p className={clsx(
                    'text-xs font-semibold mb-1',
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  )}>
                    Status
                  </p>
                  <span className={clsx(
                    'inline-block px-3 py-1 rounded-full text-sm font-medium',
                    getStatusColor(feedback.status)
                  )}>
                    {feedback.status}
                  </span>
                </div>

                <div>
                  <p className={clsx(
                    'text-xs font-semibold mb-1',
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  )}>
                    Priority
                  </p>
                  <span className={clsx(
                    'inline-block px-3 py-1 rounded-full text-sm font-medium',
                    getPriorityColor(feedback.priority)
                  )}>
                    {feedback.priority}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Response Section */}
          {feedback.status !== 'closed' && (
            <div className={clsx(
              'p-4 rounded-lg border',
              theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-slate-50 border-slate-200'
            )}>
              <h3 className={clsx(
                'text-sm font-semibold mb-3',
                theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              )}>
                Add Response
              </h3>

              <textarea
                value={responseText}
                onChange={(e) => setResponseText(e.target.value)}
                placeholder="Type your response here..."
                className={clsx(
                  'w-full px-3 py-2 rounded border outline-none text-sm resize-none',
                  theme === 'dark'
                    ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-500'
                    : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400'
                )}
                rows={4}
              />

              <button
                onClick={handleSubmitResponse}
                disabled={!responseText.trim() || isSubmittingResponse}
                className={clsx(
                  'mt-3 flex items-center justify-center gap-2 w-full px-4 py-2 rounded font-medium transition-colors text-sm',
                  isSubmittingResponse || !responseText.trim()
                    ? 'bg-slate-400 text-slate-600 cursor-not-allowed'
                    : 'bg-green-600 hover:bg-green-700 text-white'
                )}
              >
                <Send size={16} />
                {isSubmittingResponse ? 'Sending...' : 'Send Response'}
              </button>
            </div>
          )}

          {/* Existing Response */}
          {feedback.response && (
            <div className={clsx(
              'p-4 rounded-lg border',
              theme === 'dark' ? 'bg-green-900/20 border-green-700/50' : 'bg-green-50 border-green-200'
            )}>
              <h3 className={clsx(
                'text-sm font-semibold mb-2',
                theme === 'dark' ? 'text-green-400' : 'text-green-700'
              )}>
                Response
              </h3>
              <p className={clsx(
                'text-sm',
                theme === 'dark' ? 'text-green-300' : 'text-green-800'
              )}>
                {feedback.response}
              </p>
            </div>
          )}

          {/* Tags */}
          {feedback.tags && feedback.tags.length > 0 && (
            <div>
              <p className={clsx(
                'text-xs font-semibold mb-2',
                theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
              )}>
                Tags
              </p>
              <div className="flex flex-wrap gap-2">
                {feedback.tags.map((tag) => (
                  <span
                    key={tag}
                    className={clsx(
                      'px-2 py-1 rounded text-xs font-medium',
                      theme === 'dark'
                        ? 'bg-slate-700 text-slate-300'
                        : 'bg-slate-200 text-slate-700'
                    )}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default FeedbackDetail
