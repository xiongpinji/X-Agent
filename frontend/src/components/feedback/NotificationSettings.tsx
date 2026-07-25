import React, { useState } from 'react'
import { NotificationConfig } from '@/services/feedback'
import { Plus, Trash2, Edit2, Save, Mail, Slack, CheckCircle, AlertCircle } from 'lucide-react'
import clsx from 'clsx'

interface NotificationSettingsProps {
  notifications: NotificationConfig[]
  onAdd: (data: Partial<NotificationConfig>) => void
  onUpdate: (id: string, data: Partial<NotificationConfig>) => void
  onDelete: (id: string) => void
  onTest: (id: string) => void
  theme: 'light' | 'dark'
}

export const NotificationSettings: React.FC<NotificationSettingsProps> = ({
  notifications,
  onAdd,
  onUpdate,
  onDelete,
  onTest,
  theme,
}) => {
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formData, setFormData] = useState<Partial<NotificationConfig>>({
    type: 'email',
    enabled: true,
    triggers: [],
  })
  const [testingId, setTestingId] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<{ id: string; success: boolean; message: string } | null>(null)

  const handleSubmit = async () => {
    if (!formData.target || formData.triggers?.length === 0) {
      alert('Please fill in all required fields')
      return
    }

    if (editingId) {
      await onUpdate(editingId, formData)
      setEditingId(null)
    } else {
      await onAdd(formData)
    }

    setFormData({
      type: 'email',
      enabled: true,
      triggers: [],
    })
    setShowForm(false)
  }

  const handleTest = async (id: string) => {
    setTestingId(id)
    try {
      await onTest(id)
      setTestResult({ id, success: true, message: 'Test notification sent successfully' })
    } catch (error) {
      setTestResult({
        id,
        success: false,
        message: error instanceof Error ? error.message : 'Failed to send test notification',
      })
    } finally {
      setTestingId(null)
      setTimeout(() => setTestResult(null), 3000)
    }
  }

  const triggerOptions = [
    'new_feedback',
    'feedback_resolved',
    'high_priority_feedback',
    'critical_feedback',
    'sentiment_negative',
    'daily_summary',
  ]

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className={clsx(
          'text-lg font-semibold',
          theme === 'dark' ? 'text-white' : 'text-slate-900'
        )}>
          Notification Channels
        </h3>
        <button
          onClick={() => {
            setShowForm(!showForm)
            setEditingId(null)
            setFormData({
              type: 'email',
              enabled: true,
              triggers: [],
            })
          }}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors text-sm"
        >
          <Plus size={16} />
          Add Channel
        </button>
      </div>

      {/* Add/Edit Form */}
      {showForm && (
        <div className={clsx(
          'p-4 rounded-lg border',
          theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-slate-50 border-slate-200'
        )}>
          <div className="space-y-4">
            {/* Type Selection */}
            <div>
              <span className={clsx(
                'block text-sm font-semibold mb-2',
                theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              )}>
                Channel Type
              </span>
              <div className="flex gap-4">
                {(['email', 'slack'] as const).map((type) => (
                  <label key={type} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="type"
                      value={type}
                      checked={formData.type === type}
                      onChange={(e) => setFormData({ ...formData, type: e.target.value as 'email' | 'slack' })}
                      className="w-4 h-4"
                    />
                    <span className={clsx(
                      'text-sm font-medium capitalize',
                      theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
                    )}>
                      {type === 'email' ? <Mail className="inline mr-1" size={16} /> : <Slack className="inline mr-1" size={16} />}
                      {type}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            {/* Target */}
            <div>
              <label className={clsx(
                'block text-sm font-semibold mb-2',
                theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              )}>
                {formData.type === 'email' ? 'Email Address' : 'Webhook URL'}
              </label>
              <input
                type={formData.type === 'email' ? 'email' : 'url'}
                value={formData.target || ''}
                onChange={(e) => setFormData({ ...formData, target: e.target.value })}
                placeholder={formData.type === 'email' ? 'user@example.com' : 'https://hooks.slack.com/...'}
                className={clsx(
                  'w-full px-3 py-2 rounded border outline-none text-sm',
                  theme === 'dark'
                    ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-500'
                    : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400'
                )}
              />
            </div>

            {/* Triggers */}
            <div>
              <span className={clsx(
                'block text-sm font-semibold mb-2',
                theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              )}>
                Triggers
              </span>
              <div className="space-y-2">
                {triggerOptions.map((trigger) => (
                  <label key={trigger} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.triggers?.includes(trigger) || false}
                      onChange={(e) => {
                        const triggers = formData.triggers || []
                        if (e.target.checked) {
                          setFormData({ ...formData, triggers: [...triggers, trigger] })
                        } else {
                          setFormData({
                            ...formData,
                            triggers: triggers.filter((t) => t !== trigger),
                          })
                        }
                      }}
                      className="w-4 h-4"
                    />
                    <span className={clsx(
                      'text-sm',
                      theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
                    )}>
                      {trigger.replace(/_/g, ' ')}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            {/* Enabled Toggle */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.enabled || false}
                onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                className="w-4 h-4"
              />
              <span className={clsx(
                'text-sm font-medium',
                theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              )}>
                Enable this channel
              </span>
            </label>

            {/* Actions */}
            <div className="flex gap-2">
              <button
                onClick={handleSubmit}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors text-sm"
              >
                <Save size={16} />
                {editingId ? 'Update' : 'Add'} Channel
              </button>
              <button
                onClick={() => {
                  setShowForm(false)
                  setEditingId(null)
                  setFormData({
                    type: 'email',
                    enabled: true,
                    triggers: [],
                  })
                }}
                className={clsx(
                  'flex-1 px-4 py-2 rounded-lg font-medium transition-colors text-sm',
                  theme === 'dark'
                    ? 'bg-slate-700 hover:bg-slate-600 text-white'
                    : 'bg-slate-200 hover:bg-slate-300 text-slate-900'
                )}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Test Result */}
      {testResult && (
        <div className={clsx(
          'p-4 rounded-lg flex items-center gap-3',
          testResult.success
            ? theme === 'dark'
              ? 'bg-green-900/30 border border-green-700/50'
              : 'bg-green-50 border border-green-200'
            : theme === 'dark'
              ? 'bg-red-900/30 border border-red-700/50'
              : 'bg-red-50 border border-red-200'
        )}>
          {testResult.success ? (
            <CheckCircle size={20} className={theme === 'dark' ? 'text-green-400' : 'text-green-600'} />
          ) : (
            <AlertCircle size={20} className={theme === 'dark' ? 'text-red-400' : 'text-red-600'} />
          )}
          <p className={clsx(
            'text-sm font-medium',
            testResult.success
              ? theme === 'dark'
                ? 'text-green-300'
                : 'text-green-800'
              : theme === 'dark'
                ? 'text-red-300'
                : 'text-red-800'
          )}>
            {testResult.message}
          </p>
        </div>
      )}

      {/* Notifications List */}
      <div className="space-y-2">
        {notifications.length === 0 ? (
          <div className={clsx(
            'p-6 text-center rounded-lg',
            theme === 'dark' ? 'bg-slate-800' : 'bg-slate-100'
          )}>
            <p className={theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}>
              No notification channels configured
            </p>
          </div>
        ) : (
          notifications.map((notification) => (
            <div
              key={notification.id}
              className={clsx(
                'p-4 rounded-lg border',
                theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200'
              )}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    {notification.type === 'email' ? (
                      <Mail size={18} className={theme === 'dark' ? 'text-blue-400' : 'text-blue-600'} />
                    ) : (
                      <Slack size={18} className={theme === 'dark' ? 'text-purple-400' : 'text-purple-600'} />
                    )}
                    <h4 className={clsx(
                      'font-semibold',
                      theme === 'dark' ? 'text-white' : 'text-slate-900'
                    )}>
                      {notification.type === 'email' ? notification.target : 'Slack Webhook'}
                    </h4>
                    <span className={clsx(
                      'px-2 py-1 rounded text-xs font-medium',
                      notification.enabled
                        ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                        : 'bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-400'
                    )}>
                      {notification.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>

                  <p className={clsx(
                    'text-sm mb-2',
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  )}>
                    Triggers: {notification.triggers.join(', ')}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleTest(notification.id)}
                    disabled={testingId === notification.id}
                    className={clsx(
                      'px-3 py-1 rounded text-sm font-medium transition-colors',
                      testingId === notification.id
                        ? 'bg-slate-400 text-slate-600 cursor-not-allowed'
                        : theme === 'dark'
                          ? 'bg-slate-700 hover:bg-slate-600 text-slate-300'
                          : 'bg-slate-200 hover:bg-slate-300 text-slate-700'
                    )}
                  >
                    {testingId === notification.id ? 'Testing...' : 'Test'}
                  </button>

                  <button
                    onClick={() => {
                      setEditingId(notification.id)
                      setFormData(notification)
                      setShowForm(true)
                    }}
                    className={clsx(
                      'p-2 rounded-lg transition-colors',
                      theme === 'dark'
                        ? 'hover:bg-slate-700 text-slate-400'
                        : 'hover:bg-slate-200 text-slate-600'
                    )}
                  >
                    <Edit2 size={16} />
                  </button>

                  <button
                    onClick={() => {
                      if (confirm('Are you sure you want to delete this notification channel?')) {
                        onDelete(notification.id)
                      }
                    }}
                    className={clsx(
                      'p-2 rounded-lg transition-colors',
                      theme === 'dark'
                        ? 'hover:bg-red-900/20 text-red-400'
                        : 'hover:bg-red-100 text-red-600'
                    )}
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

export default NotificationSettings
