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
  Ban,
} from 'lucide-react'
import clsx from 'clsx'

type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'error' | string

const ACTIVE_STATUSES = new Set(['queued', 'running'])

const STATUS_BADGE: Record<string, string> = {
  completed: 'badge-success',
  running: 'badge-muted',
  failed: 'badge-danger',
  error: 'badge-danger',
  queued: 'badge-warning',
}

const STATUS_LABEL_KEY: Record<string, [string, string]> = {
  completed: ['sandbox.completed', 'Completed'],
  running: ['sandbox.running', 'Running'],
  failed: ['sandbox.failed', 'Failed'],
  error: ['sandbox.error', 'Error'],
  queued: ['sandbox.queued', 'Queued'],
}

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

  const muted = clsx('text-sm opacity-60')
  const input = clsx(
    'w-full px-3 py-2 border text-sm bg-transparent border-[var(--divider)]'
  )
  const errBox = clsx(
    'mb-6 border px-4 py-3 text-sm',
    'border-[#dc2626]/40 text-[#dc2626]'
  )
  const ghostBtnCls = clsx(
    'flex items-center gap-2 px-3 py-2 border border-[var(--divider)] text-sm font-medium transition-colors hover:bg-[var(--hover)] disabled:opacity-50'
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
    const [key, fallback] = STATUS_LABEL_KEY[status] ?? STATUS_LABEL_KEY.queued
    return (
      <span className={clsx('badge-status', STATUS_BADGE[status] ?? 'badge-muted')}>
        {t(key, fallback)}
      </span>
    )
  }

  return (
    <div className={clsx(
      'min-h-full px-8 py-10',
      theme === 'dark' ? 'bg-slate-950 text-slate-200' : 'bg-[#fafafa] text-[#333333]'
    )}>
      <div className="max-w-6xl">
        {/* Header — Dashboard-style */}
        <header className="mb-8">
          <div
            className={clsx(
              'w-12 border-t-2 mb-5',
              theme === 'dark' ? 'border-slate-200' : 'border-[#333333]'
            )}
            aria-hidden="true"
          />
          <div className="flex items-end justify-between gap-4">
            <div>
              <h1 className="page-title">{t('sandbox.title', 'Sandbox Tasks')}</h1>
              <p className="page-subtitle">
                {t('sandbox.subtitle', 'Submit and monitor isolated sandbox executions')}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={loadTasks}
                disabled={loading}
                className={ghostBtnCls}
                aria-label={t('common.refresh', 'Refresh')}
              >
                <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
              </button>
              <button
                onClick={() => setShowSubmit(true)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors"
              >
                <Plus size={16} />
                {t('sandbox.newTask', 'New Task')}
              </button>
            </div>
          </div>
        </header>

        {loadError && <div role="alert" className={errBox}>{loadError}</div>}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
          {/* Task list — divider rows, no cards */}
          <section>
            <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
              {t('sandbox.taskList', 'Tasks')} ({tasks.length})
            </h2>
            {tasks.length === 0 ? (
              <p className="empty-state">
                {t('sandbox.noTasks', 'No sandbox tasks yet')} · {t('sandbox.submitToStart', 'Submit a task to get started')}
              </p>
            ) : (
              <div className="max-h-[32rem] overflow-y-auto">
                {tasks.map((task) => (
                  <button
                    key={task.task_id}
                    onClick={() => setSelectedId(task.task_id)}
                    className={clsx(
                      'row-line w-full flex items-center justify-between gap-3 px-2 -mx-2 text-left hover:bg-[var(--hover)]',
                      selectedId === task.task_id && 'bg-[var(--hover)]'
                    )}
                  >
                    <span className="cell-data opacity-70 truncate">
                      {task.task_id}
                    </span>
                    {statusBadge(task.status)}
                  </button>
                ))}
              </div>
            )}
          </section>

          {/* Task detail */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50">
                {t('sandbox.detail', 'Detail')}
              </h2>
              {detail && statusBadge(detail.status)}
            </div>
            {!selectedId ? (
              <p className="empty-state">
                {t('sandbox.selectTask', 'Select a task to view its output')}
              </p>
            ) : detailError ? (
              <div role="alert" className={errBox}>{detailError}</div>
            ) : !detail ? (
              <p className="empty-state">{t('common.loading', 'Loading...')}</p>
            ) : (
              <div className="space-y-4 max-h-[32rem] overflow-y-auto">
                <div className="row-line">
                  <p className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-1">{t('sandbox.taskId', 'Task ID')}</p>
                  <p className="cell-data break-all">
                    {detail.task_id}
                  </p>
                </div>
                {detail.backend && (
                  <div className="row-line">
                    <p className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-1">{t('sandbox.backend', 'Backend')}</p>
                    <p className="text-sm">{detail.backend}</p>
                  </div>
                )}
                {detail.error && (
                  <div className="border px-3 py-2 text-sm break-words border-[#dc2626]/40 text-[#dc2626]" role="alert">
                    {detail.error}
                  </div>
                )}
                <div>
                  <p className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2">
                    {t('sandbox.steps', 'Steps')} ({detail.steps.length})
                  </p>
                  {detail.steps.length === 0 ? (
                    <p className={muted}>
                      {ACTIVE_STATUSES.has(detail.status)
                        ? t('sandbox.waitingOutput', 'Waiting for output...')
                        : t('sandbox.noSteps', 'No step output recorded')}
                    </p>
                  ) : (
                    <div>
                      {detail.steps.map((step, i) => (
                        <div key={i} className="row-line">
                          <p className="text-xs font-semibold mb-1">
                            {String(step.name ?? `step ${i + 1}`)}
                          </p>
                          <pre className="cell-data opacity-70 overflow-x-auto whitespace-pre-wrap break-all">
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
                  className={clsx(ghostBtnCls, 'opacity-50 cursor-not-allowed')}
                >
                  <Ban size={16} />
                  {t('sandbox.cancelTask', 'Cancel task')} ({comingSoon})
                </button>
              </div>
            )}
          </section>
        </div>

        {/* Submit modal */}
        {showSubmit && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true">
            <div
              className={clsx(
                'p-6 border w-full max-w-lg max-h-[90vh] overflow-y-auto',
                theme === 'dark' ? 'bg-slate-900' : 'bg-white'
              )}
              style={{ borderColor: 'var(--divider)' }}
            >
              <h3 className="text-lg font-medium mb-4">{t('sandbox.newTask', 'New Task')}</h3>
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
                  <span>
                    {t('sandbox.enableNetwork', 'Enable network access')}
                  </span>
                </label>
              </div>
              <div className="flex gap-2 mt-6">
                <button
                  onClick={() => setShowSubmit(false)}
                  disabled={submitting}
                  className="flex-1 px-4 py-2 border border-[var(--divider)] text-sm font-medium transition-colors hover:bg-[var(--hover)] disabled:opacity-50"
                >
                  {t('common.cancel', 'Cancel')}
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={submitting || !form.name.trim() || !form.command.trim()}
                  className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors disabled:opacity-50"
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
