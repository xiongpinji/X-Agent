import React, { useEffect, useState, useCallback } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiClient } from '@/services/api'
import { workflowOps, WorkflowScheduleItem } from '@/services/workflowOps'
import { useI18n } from '@/i18n/context'
import {
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

const STATUS_BADGE: Record<string, string> = {
  triggered: 'badge-success',
  pending: 'badge-muted',
  failed: 'badge-danger',
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
        wfList.map((wf) => ({ id: String(wf.id ?? wf.workflow_id ?? ''), name: String(wf.name ?? wf.id ?? '') }))
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
    let inputs: Record<string, unknown> = {}
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

  const labelCls = clsx('block text-xs font-medium mb-1 opacity-60')
  const inputCls = clsx(
    'w-full px-3 py-2 border text-sm bg-transparent border-[var(--divider)]'
  )
  const ghostBtnCls = clsx(
    'flex items-center gap-2 px-3 py-2 border border-[var(--divider)] text-sm font-medium transition-colors hover:bg-[var(--hover)] disabled:opacity-50'
  )

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
              <h1 className="page-title">{t('schedules.title', 'Workflow Schedules')}</h1>
              <p className="page-subtitle">{t('schedules.subtitle', 'Cron and one-shot workflow scheduling')}</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleRunDue}
                disabled={triggering}
                className={ghostBtnCls}
              >
                <Zap size={16} />
                {t('schedules.runDue', 'Trigger Due')}
              </button>
              <button
                onClick={() => setShowForm(true)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors"
              >
                <Plus size={16} />
                {t('schedules.create', 'New Schedule')}
              </button>
            </div>
          </div>
        </header>

        {/* 创建调度表单 */}
        {showForm && (
          <section className="mb-8 row-line" style={{ padding: '20px 0' }}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50">
                {t('schedules.formTitle', 'Create Schedule')}
              </h2>
              <button
                onClick={() => setShowForm(false)}
                className="p-1.5 opacity-50 hover:opacity-100 transition-opacity"
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
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium transition-colors"
              >
                <Play size={16} />
                {submitting ? t('schedules.creating', 'Creating...') : t('schedules.submit', 'Create Schedule')}
              </button>
            </div>
          </section>
        )}

        {/* 调度列表 — divider rows, no cards */}
        <section>
          {schedules.length === 0 ? (
            <p className="empty-state">{t('schedules.empty', 'No schedules yet')}</p>
          ) : (
            <div>
              {schedules.map((s) => (
                <div key={s.schedule_id} className="row-line" style={{ padding: '14px 0' }}>
                  <div className="flex items-center justify-between flex-wrap gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium truncate text-sm">
                          {s.workflow_id}
                        </span>
                        <span className={clsx('badge-status', STATUS_BADGE[s.status] ?? 'badge-muted')}>
                          {s.status}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-4 flex-wrap cell-data opacity-50">
                        <span>cron: {s.snapshot?.cron || '—'}</span>
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
                        className={clsx(ghostBtnCls, 'cursor-not-allowed opacity-50')}
                      >
                        <ToggleLeft size={14} />
                        {t('schedules.toggle', 'Toggle')}
                      </button>
                      <button
                        onClick={handleRunDue}
                        disabled={triggering}
                        title={t('schedules.triggerHint', 'Trigger all due schedules (POST /schedules/run-due)')}
                        className={ghostBtnCls}
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
        </section>
      </div>
    </div>
  )
}

export default WorkflowSchedulesPage
