import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import {
  sandboxOps,
  SandboxTaskListItem,
  SandboxTaskStatusResponse,
} from '@/services/sandboxOps'
import { useI18n } from '@/i18n/context'
import {
  Plus,
  RefreshCw,
  CheckCircle,
  Clock,
  AlertCircle,
  Loader2,
  TerminalSquare,
  XCircle,
  Ban,
} from 'lucide-react'
import clsx from 'clsx'

type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'error' | string

const ACTIVE_STATUSES = new Set(['queued', 'running'])

export const SandboxTasksPage: React.FC = () => {
  const { theme, setError } = useAppStore()
  const { t } = useI18n()
  const [tasks, setTasks] = useState<SandboxTaskListItem[]>([])
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [showSubmit, setShowSubmit] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<SandboxTaskStatusResponse | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const comingSoon = t('common.comingSoon', 'Coming soon')

  // Submit form state (matches TaskSubmitRequest in the backend)
  const [form, setForm] = useState({
    name: '',
    command: '',
    image: 'python:3.11-slim',
    timeout_seconds: '300',
    enable_network: false,
  })

  const card = clsx(
    'rounded-lg p-6',
    theme === 'dark' ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200'
  )
  const muted = clsx('text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')
  const heading = clsx('text-lg font-bold', theme === 'dark' ? 'text-white' : 'text-slate-900')
  const input = clsx(
    'w-full px-3 py-2 rounded-lg border text-sm outline-none transition-colors',
    theme === 'dark'
      ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-blue-500'
      : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-blue-500'
  )
  const errBox = clsx(
    'mb-6 rounded-lg border px-4 py-3 text-sm',
    theme === 'dark'
      ? 'border-red-900 bg-red-950/40 text-red-300'
      : 'border-red-200 bg-red-50 text-red-700'
  )

  const loadTasks = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const resp = await sandboxOps.listTasks()
      // Newest first (backend dict preserves insertion order)
      setTasks([...(resp.tasks ?? [])].reverse())
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to load sandbox tasks'
      setLoadError(msg)
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [setError])

  useEffect(() => {
    loadTasks()
  }, [loadTasks])

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const fetchDetail = useCallback(async (taskId: string) => {
    try {
      const resp = await sandboxOps.getTask(taskId)
      setDetail(resp)
      setDetailError(null)
      if (!ACTIVE_STATUSES.has(resp.status)) {
        stopPolling()
      }
    } catch (error) {
      setDetailError(error instanceof Error ? error.message : 'Failed to load task detail')
      stopPolling()
    }
  }, [stopPolling])

  // Poll the selected task while it is queued/running
  useEffect(() => {
    stopPolling()
    if (!selectedId) {
      setDetail(null)
      return
    }
    fetchDetail(selectedId)
    pollRef.current = setInterval(() => fetchDetail(selectedId), 2000)
    return stopPolling
  }, [selectedId, fetchDetail, stopPolling])

  const handleSubmit = async () => {
    setSubmitting(true)
    setLoadError(null)
    try {
      const timeout = Math.min(3600, Math.max(1, Number(form.timeout_seconds) || 300))
      const resp = await sandboxOps.submitTask({
        name: form.name.trim(),
        command: form.command,
        image: form.image.trim() || 'python:3.11-slim',
        timeout_seconds: timeout,
        enable_network: form.enable_network,
      })
      setShowSubmit(false)
      setForm({ name: '', command: '', image: 'python:3.11-slim', timeout_seconds: '300', enable_network: false })
      setSelectedId(resp.task_id)
      await loadTasks()
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to submit task'
      setLoadError(msg)
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const statusBadge = (status: TaskStatus) => {
    switch (status) {
      case 'completed':
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-500/10 text-green-600">
            <CheckCircle size={12} /> {t('sandbox.completed', 'Completed')}
          </span>
        )
      case 'running':
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-600">
            <Loader2 size={12} className="animate-spin" /> {t('sandbox.running', 'Running')}
          </span>
        )
      case 'failed':
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-600">
            <AlertCircle size={12} /> {t('sandbox.failed', 'Failed')}
          </span>
        )
      case 'error':
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-600">
            <XCircle size={12} /> {t('sandbox.error', 'Error')}
          </span>
        )
      default:
        return (
          <span className={clsx(
            'flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
            theme === 'dark' ? 'bg-slate-700 text-slate-300' : 'bg-slate-100 text-slate-600'
          )}>
            <Clock size={12} /> {t('sandbox.queued', 'Queued')}
          </span>
        )
    }
  }

  return (
    <div className={clsx('p-8', theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50')}>
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className={clsx('text-3xl font-bold mb-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('sandbox.title', 'Sandbox Tasks')}
            </h1>
            <p className={muted}>
              {t('sandbox.subtitle', 'Submit and monitor isolated sandbox executions')}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={loadTasks}
              disabled={loading}
              className={clsx(
                'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
                theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
              )}
              aria-label={t('common.refresh', 'Refresh')}
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            </button>
            <button
              onClick={() => setShowSubmit(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
            >
              <Plus size={20} />
              {t('sandbox.newTask', 'New Task')}
            </button>
          </div>
        </div>

        {loadError && <div role="alert" className={errBox}>{loadError}</div>}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Task list */}
          <div className={clsx(card, 'p-0 overflow-hidden')}>
            <div className={clsx(
              'px-6 py-4 border-b flex items-center gap-2',
              theme === 'dark' ? 'border-slate-700' : 'border-slate-200'
            )}>
              <TerminalSquare size={18} className="text-blue-500" />
              <h2 className={heading}>{t('sandbox.taskList', 'Tasks')}</h2>
              <span className={muted}>({tasks.length})</span>
            </div>
            {tasks.length === 0 ? (
              <div className={clsx('p-8 text-center', muted)}>
                <p className="text-lg font-medium mb-2">{t('sandbox.noTasks', 'No sandbox tasks yet')}</p>
                <p className="text-sm">{t('sandbox.submitToStart', 'Submit a task to get started')}</p>
              </div>
            ) : (
              <div className="max-h-[32rem] overflow-y-auto">
                {tasks.map((task) => (
                  <button
                    key={task.task_id}
                    onClick={() => setSelectedId(task.task_id)}
                    className={clsx(
                      'w-full flex items-center justify-between gap-3 px-6 py-3 text-left transition-colors border-b last:border-b-0',
                      theme === 'dark' ? 'border-slate-800 hover:bg-slate-800/60' : 'border-slate-100 hover:bg-slate-50',
                      selectedId === task.task_id && (theme === 'dark' ? 'bg-slate-800' : 'bg-blue-50')
                    )}
                  >
                    <span className={clsx(
                      'text-sm font-mono truncate',
                      theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
                    )}>
                      {task.task_id}
                    </span>
                    {statusBadge(task.status)}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Task detail */}
          <div className={clsx(card, 'p-0 overflow-hidden')}>
            <div className={clsx(
              'px-6 py-4 border-b flex items-center justify-between',
              theme === 'dark' ? 'border-slate-700' : 'border-slate-200'
            )}>
              <h2 className={heading}>{t('sandbox.detail', 'Detail')}</h2>
              {detail && statusBadge(detail.status)}
            </div>
            {!selectedId ? (
              <div className={clsx('p-8 text-center', muted)}>
                {t('sandbox.selectTask', 'Select a task to view its output')}
              </div>
            ) : detailError ? (
              <div className={clsx('p-6', errBox, 'm-6 mb-6')}>{detailError}</div>
            ) : !detail ? (
              <div className={clsx('p-8 text-center', muted)}>{t('common.loading', 'Loading...')}</div>
            ) : (
              <div className="p-6 space-y-4 max-h-[32rem] overflow-y-auto">
                <div>
                  <p className={clsx('text-xs mb-1', muted)}>{t('sandbox.taskId', 'Task ID')}</p>
                  <p className={clsx('text-sm font-mono break-all', theme === 'dark' ? 'text-slate-300' : 'text-slate-700')}>
                    {detail.task_id}
                  </p>
                </div>
                {detail.backend && (
                  <div>
                    <p className={clsx('text-xs mb-1', muted)}>{t('sandbox.backend', 'Backend')}</p>
                    <p className={clsx('text-sm', theme === 'dark' ? 'text-slate-300' : 'text-slate-700')}>{detail.backend}</p>
                  </div>
                )}
                {detail.error && (
                  <div className={clsx(
                    'rounded-md border px-3 py-2 text-sm break-words',
                    theme === 'dark' ? 'border-red-900 bg-red-950/40 text-red-300' : 'border-red-200 bg-red-50 text-red-700'
                  )} role="alert">
                    {detail.error}
                  </div>
                )}
                <div>
                  <p className={clsx('text-xs mb-2', muted)}>
                    {t('sandbox.steps', 'Steps')} ({detail.steps.length})
                  </p>
                  {detail.steps.length === 0 ? (
                    <p className={muted}>
                      {ACTIVE_STATUSES.has(detail.status)
                        ? t('sandbox.waitingOutput', 'Waiting for output...')
                        : t('sandbox.noSteps', 'No step output recorded')}
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {detail.steps.map((step, i) => (
                        <div key={i} className={clsx(
                          'rounded-md border',
                          theme === 'dark' ? 'border-slate-700' : 'border-slate-200'
                        )}>
                          <div className={clsx(
                            'px-3 py-1.5 text-xs font-semibold border-b',
                            theme === 'dark' ? 'border-slate-700 text-slate-300 bg-slate-800' : 'border-slate-200 text-slate-700 bg-slate-50'
                          )}>
                            {String(step.name ?? `step ${i + 1}`)}
                          </div>
                          <pre className={clsx(
                            'px-3 py-2 text-xs overflow-x-auto whitespace-pre-wrap break-all',
                            theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                          )}>
                            {JSON.stringify(step, null, 2)}
                          </pre>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                {/* Backend exposes no cancel/delete for sandbox tasks */}
                <button
                  disabled
                  title={`${t('sandbox.cancelTask', 'Cancel task')} (${comingSoon})`}
                  aria-label={`${t('sandbox.cancelTask', 'Cancel task')} (${comingSoon})`}
                  className={clsx(
                    'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium opacity-50 cursor-not-allowed',
                    theme === 'dark' ? 'bg-slate-700 text-slate-300' : 'bg-slate-200 text-slate-700'
                  )}
                >
                  <Ban size={16} />
                  {t('sandbox.cancelTask', 'Cancel task')} ({comingSoon})
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Submit modal */}
        {showSubmit && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true">
            <div className={clsx(card, 'w-full max-w-lg max-h-[90vh] overflow-y-auto')}>
              <h3 className={clsx(heading, 'mb-4')}>{t('sandbox.newTask', 'New Task')}</h3>
              <div className="space-y-3">
                <div>
                  <label className={clsx(muted, 'block mb-1')}>{t('sandbox.taskName', 'Name')}</label>
                  <input
                    className={input}
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="my-sandbox-task"
                  />
                </div>
                <div>
                  <label className={clsx(muted, 'block mb-1')}>{t('sandbox.command', 'Command')}</label>
                  <textarea
                    className={clsx(input, 'font-mono min-h-[5rem]')}
                    value={form.command}
                    onChange={(e) => setForm({ ...form, command: e.target.value })}
                    placeholder={'python -c "print(\'hello\')"'}
                  />
                </div>
                <div>
                  <label className={clsx(muted, 'block mb-1')}>{t('sandbox.image', 'Container image')}</label>
                  <input
                    className={input}
                    value={form.image}
                    onChange={(e) => setForm({ ...form, image: e.target.value })}
                    placeholder="python:3.11-slim"
                  />
                </div>
                <div>
                  <label className={clsx(muted, 'block mb-1')}>
                    {t('sandbox.timeout', 'Timeout (seconds, 1-3600)')}
                  </label>
                  <input
                    className={input}
                    type="number"
                    min={1}
                    max={3600}
                    value={form.timeout_seconds}
                    onChange={(e) => setForm({ ...form, timeout_seconds: e.target.value })}
                  />
                </div>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.enable_network}
                    onChange={(e) => setForm({ ...form, enable_network: e.target.checked })}
                    className="w-4 h-4 accent-blue-600"
                  />
                  <span className={theme === 'dark' ? 'text-slate-300' : 'text-slate-700'}>
                    {t('sandbox.enableNetwork', 'Enable network access')}
                  </span>
                </label>
              </div>
              <div className="flex gap-2 mt-6">
                <button
                  onClick={() => setShowSubmit(false)}
                  disabled={submitting}
                  className={clsx(
                    'flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
                    theme === 'dark' ? 'bg-slate-700 text-slate-300 hover:bg-slate-600' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
                  )}
                >
                  {t('common.cancel', 'Cancel')}
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={submitting || !form.name.trim() || !form.command.trim()}
                  className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {submitting ? t('common.loading', 'Loading...') : t('sandbox.submit', 'Submit')}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default SandboxTasksPage
