import React, { useEffect, useState, useCallback } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiClient } from '@/services/api'
import { workflowOps, WorkflowScheduleItem } from '@/services/workflowOps'
import { useI18n } from '@/i18n/context'
import {
  CalendarClock,
  Play,
  Plus,
  RefreshCw,
  ToggleLeft,
  X,
  Zap,
} from 'lucide-react'
import clsx from 'clsx'

interface WorkflowOption {
  id: string
  name: string
}

/**
 * 工作流调度运维页 — 端点全部来自 backend/app/api/workflows.py:
 * - GET  /api/v1/workflows/schedules              调度列表
 * - POST /api/v1/workflows/{id}/schedule          创建调度(cron / 一次性)
 * - POST /api/v1/workflows/schedules/run-due      手动触发到期调度
 * 后端暂无"启用/禁用切换"与"编辑调度(PUT)"端点, 对应按钮标记 coming soon。
 */
export const WorkflowSchedulesPage: React.FC = () => {
  const { theme, setLoading, setError } = useAppStore()
  const { t } = useI18n()
  const [schedules, setSchedules] = useState<WorkflowScheduleItem[]>([])
  const [workflows, setWorkflows] = useState<WorkflowOption[]>([])
  const [showForm, setShowForm] = useState(false)
  const [triggering, setTriggering] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // 创建表单状态
  const [formWorkflowId, setFormWorkflowId] = useState('')
  const [formCron, setFormCron] = useState('')
  const [formDelay, setFormDelay] = useState('0')
  const [formRunAt, setFormRunAt] = useState('')
  const [formInputs, setFormInputs] = useState('{}')

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      const [items, wfList] = await Promise.all([
        workflowOps.listSchedules(100),
        apiClient.listWorkflows(),
      ])
      setSchedules(items)
      setWorkflows(
        wfList.map((wf: any) => ({ id: String(wf.id ?? wf.workflow_id ?? ''), name: String(wf.name ?? wf.id ?? '') }))
      )
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load schedules')
    } finally {
      setLoading(false)
    }
  }, [setLoading, setError])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleRunDue = async () => {
    try {
      setTriggering(true)
      const triggered = await workflowOps.runDueSchedules(20)
      if (triggered.length === 0) {
        setError(t('schedules.noneDue', 'No due schedules to trigger right now'))
      }
      await loadData()
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to trigger due schedules')
    } finally {
      setTriggering(false)
    }
  }

  const handleCreate = async () => {
    if (!formWorkflowId) {
      setError(t('schedules.pickWorkflow', 'Please select a workflow'))
      return
    }
    let inputs: Record<string, any> = {}
    try {
      inputs = formInputs.trim() ? JSON.parse(formInputs) : {}
    } catch {
      setError(t('schedules.invalidInputs', 'Inputs must be valid JSON'))
      return
    }
    try {
      setSubmitting(true)
      await workflowOps.createSchedule(formWorkflowId, {
        inputs,
        cron: formCron.trim() || null,
        run_at: formCron.trim() ? null : formRunAt || null,
        delay_seconds: formCron.trim() || formRunAt ? 0 : Number.parseInt(formDelay, 10) || 0,
      })
      setShowForm(false)
      setFormCron('')
      setFormRunAt('')
      setFormDelay('0')
      setFormInputs('{}')
      await loadData()
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to create schedule')
    } finally {
      setSubmitting(false)
    }
  }

  const statusBadge = (status: string) => {
    const color =
      status === 'triggered'
        ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
        : status === 'pending'
          ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
          : status === 'failed'
            ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
            : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
    return <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium', color)}>{status}</span>
  }

  const cardCls = clsx(
    'rounded-lg p-4 border',
    theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
  )
  const labelCls = clsx('block text-xs font-medium mb-1', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')
  const inputCls = clsx(
    'w-full px-3 py-2 rounded-md border text-sm focus:outline-none focus:ring-2 focus:ring-blue-500',
    theme === 'dark' ? 'bg-slate-800 border-slate-600 text-white' : 'bg-white border-slate-300 text-slate-900'
  )

  return (
    <div className={clsx('p-8', theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50')}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className={clsx('text-3xl font-bold mb-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('schedules.title', 'Workflow Schedules')}
            </h1>
            <p className={clsx('text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
              {t('schedules.subtitle', 'Cron and one-shot workflow scheduling')}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRunDue}
              disabled={triggering}
              className="flex items-center gap-2 px-4 py-2 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
            >
              <Zap size={16} />
              {t('schedules.runDue', 'Trigger Due')}
            </button>
            <button
              onClick={() => setShowForm(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
            >
              <Plus size={18} />
              {t('schedules.create', 'New Schedule')}
            </button>
          </div>
        </div>

        {/* 创建调度表单 */}
        {showForm && (
          <div className={clsx(cardCls, 'mb-6')}>
            <div className="flex items-center justify-between mb-4">
              <h2 className={clsx('text-lg font-semibold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                {t('schedules.formTitle', 'Create Schedule')}
              </h2>
              <button
                onClick={() => setShowForm(false)}
                className={clsx('p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>{t('schedules.workflow', 'Workflow')}</label>
                <select value={formWorkflowId} onChange={(e) => setFormWorkflowId(e.target.value)} className={inputCls}>
                  <option value="">{t('schedules.pickWorkflow', 'Select a workflow')}</option>
                  {workflows.map((wf) => (
                    <option key={wf.id} value={wf.id}>
                      {wf.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className={labelCls}>{t('schedules.cron', 'Cron (5-field, optional)')}</label>
                <input
                  value={formCron}
                  onChange={(e) => setFormCron(e.target.value)}
                  placeholder="*/15 * * * *"
                  className={inputCls}
                />
              </div>
              <div>
                <label className={labelCls}>{t('schedules.runAt', 'Run at (ISO, one-shot)')}</label>
                <input
                  type="datetime-local"
                  value={formRunAt}
                  onChange={(e) => setFormRunAt(e.target.value)}
                  disabled={Boolean(formCron.trim())}
                  className={inputCls}
                />
              </div>
              <div>
                <label className={labelCls}>{t('schedules.delay', 'Delay seconds (one-shot)')}</label>
                <input
                  type="number"
                  min={0}
                  value={formDelay}
                  onChange={(e) => setFormDelay(e.target.value)}
                  disabled={Boolean(formCron.trim() || formRunAt)}
                  className={inputCls}
                />
              </div>
              <div className="md:col-span-2">
                <label className={labelCls}>{t('schedules.inputs', 'Inputs (JSON)')}</label>
                <textarea
                  value={formInputs}
                  onChange={(e) => setFormInputs(e.target.value)}
                  rows={3}
                  className={clsx(inputCls, 'font-mono')}
                />
              </div>
            </div>
            <div className="flex justify-end mt-4">
              <button
                onClick={handleCreate}
                disabled={submitting}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
              >
                <Play size={16} />
                {submitting ? t('schedules.creating', 'Creating...') : t('schedules.submit', 'Create Schedule')}
              </button>
            </div>
          </div>
        )}

        {/* 调度列表 */}
        {schedules.length === 0 ? (
          <div className={clsx(cardCls, 'p-8 text-center', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>
            <CalendarClock size={40} className="mx-auto mb-3 opacity-50" />
            <p>{t('schedules.empty', 'No schedules yet')}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {schedules.map((s) => (
              <div key={s.schedule_id} className={cardCls}>
                <div className="flex items-center justify-between flex-wrap gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={clsx('font-medium truncate', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                        {s.workflow_id}
                      </span>
                      {statusBadge(s.status)}
                    </div>
                    <div className={clsx('text-sm mt-1 space-x-4', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
                      <span>
                        cron: <code className="font-mono text-xs">{s.snapshot?.cron || '—'}</code>
                      </span>
                      <span>
                        {t('schedules.nextRun', 'Next run')}:{' '}
                        {s.snapshot?.run_at ? new Date(s.snapshot.run_at).toLocaleString() : '—'}
                      </span>
                      {s.run_id && <span>run: {s.run_id.slice(0, 8)}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* 后端暂无启用/禁用端点 — coming soon */}
                    <button
                      disabled
                      title={t('schedules.toggleSoon', 'Enable/disable toggle: coming soon (no backend endpoint yet)')}
                      className={clsx(
                        'flex items-center gap-1 px-3 py-1.5 text-sm rounded-md border cursor-not-allowed opacity-50',
                        theme === 'dark' ? 'border-slate-600 text-slate-400' : 'border-slate-300 text-slate-500'
                      )}
                    >
                      <ToggleLeft size={14} />
                      {t('schedules.toggle', 'Toggle')}
                    </button>
                    <button
                      onClick={handleRunDue}
                      disabled={triggering}
                      title={t('schedules.triggerHint', 'Trigger all due schedules (POST /schedules/run-due)')}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white rounded-md transition-colors"
                    >
                      <RefreshCw size={14} className={triggering ? 'animate-spin' : ''} />
                      {t('schedules.trigger', 'Trigger')}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default WorkflowSchedulesPage
