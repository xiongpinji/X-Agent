import React, { useEffect, useState, useCallback } from 'react'
import { useAppStore } from '@/store/appStore'
import {
  workflowOps,
  WorkflowRunItem,
  WorkflowRunDetail,
  WorkflowRunTimelineEvent,
} from '@/services/workflowOps'
import { useI18n } from '@/i18n/context'
import { RefreshCw } from 'lucide-react'
import clsx from 'clsx'

const STATUS_BADGE: Record<string, string> = {
  completed: 'badge-success',
  running: 'badge-muted',
  failed: 'badge-danger',
  paused: 'badge-warning',
  needs_approval: 'badge-warning',
}

/**
 * 工作流运行回放页 — 端点全部来自 backend/app/api/workflows.py:
 * - GET /api/v1/workflows/runs                       运行历史列表
 * - GET /api/v1/workflows/runs/{run_id}              运行详情(逐节点输出 + 时间线)
 * - POST /api/v1/workflows/runs/{run_id}/resume-approved  审批后恢复(needs_approval)
 */
export const WorkflowRunsPage: React.FC = () => {
  const { theme, setLoading, setError } = useAppStore()
  const { t } = useI18n()
  const [runs, setRuns] = useState<WorkflowRunItem[]>([])
  const [selected, setSelected] = useState<WorkflowRunDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [approvalId, setApprovalId] = useState('')
  const [resuming, setResuming] = useState(false)

  const loadRuns = useCallback(async () => {
    try {
      setLoading(true)
      setRuns(await workflowOps.listRuns(100))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load runs')
    } finally {
      setLoading(false)
    }
  }, [setLoading, setError])

  useEffect(() => {
    loadRuns()
  }, [loadRuns])

  const openDetail = async (runId: string) => {
    try {
      setDetailLoading(true)
      setApprovalId('')
      setSelected(await workflowOps.getRunDetail(runId))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load run detail')
    } finally {
      setDetailLoading(false)
    }
  }

  const handleResumeApproved = async () => {
    if (!selected || !approvalId.trim()) {
      setError(t('runs.needApprovalId', 'approval_id is required'))
      return
    }
    try {
      setResuming(true)
      await workflowOps.resumeApprovedRun(selected.run.run_id, approvalId.trim())
      await openDetail(selected.run.run_id)
      await loadRuns()
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to resume run')
    } finally {
      setResuming(false)
    }
  }

  const statusBadge = (status: string) => STATUS_BADGE[status] ?? 'badge-muted'

  const durationMs = (start?: string, end?: string): string => {
    if (!start || !end) return '—'
    const ms = new Date(end).getTime() - new Date(start).getTime()
    if (Number.isNaN(ms) || ms < 0) return '—'
    return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
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
              <h1 className="page-title">{t('runs.title', 'Workflow Runs')}</h1>
              <p className="page-subtitle">{t('runs.subtitle', 'Run history, node outputs and replay timeline')}</p>
            </div>
            <button
              onClick={loadRuns}
              className={clsx(
                'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100'
              )}
              aria-label={t('runs.refresh', 'Refresh')}
            >
              <RefreshCw size={16} />
              {t('runs.refresh', 'Refresh')}
            </button>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
          {/* 运行历史列表 — divider rows, no cards */}
          <section>
            <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
              {t('runs.history', 'History')} ({runs.length})
            </h2>
            {runs.length === 0 ? (
              <p className="empty-state">{t('runs.empty', 'No workflow runs yet')}</p>
            ) : (
              <div>
                {runs.map((run) => {
                  const total = run.node_results?.length ?? 0
                  const cursor = run.resume_cursor ?? 0
                  return (
                    <div
                      key={run.run_id}
                      role="button"
                      tabIndex={0}
                      onClick={() => openDetail(run.run_id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') openDetail(run.run_id)
                      }}
                      className={clsx(
                        'row-line cursor-pointer px-2 -mx-2',
                        selected?.run?.run_id === run.run_id && (theme === 'dark' ? 'bg-slate-800' : 'bg-slate-100')
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <span className={clsx('badge-status', statusBadge(run.status))}>
                          {run.status}
                        </span>
                        <span className="text-sm font-medium truncate">
                          {run.workflow_name || run.workflow_id}
                        </span>
                        <span className="ml-auto cell-data opacity-50">
                          {run.run_id.slice(0, 8)}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-4 cell-data opacity-50">
                        <span>
                          {t('runs.duration', 'Duration')}: {durationMs(run.started_at, run.completed_at)}
                        </span>
                        <span>
                          {t('runs.progress', 'Nodes')}: {cursor}/{total}
                        </span>
                      </div>
                      {total > 0 && (
                        <div
                          className="mt-2 h-[3px] w-full"
                          style={{ backgroundColor: 'rgba(163,169,177,.25)' }}
                          role="progressbar"
                          aria-valuenow={Math.min(100, Math.round((cursor / total) * 100))}
                          aria-valuemin={0}
                          aria-valuemax={100}
                        >
                          <div
                            className={clsx('h-[3px] transition-all', run.status === 'failed' ? 'bg-[#dc2626]' : theme === 'dark' ? 'bg-slate-300' : 'bg-[#333333]')}
                            style={{ width: `${Math.min(100, (cursor / total) * 100)}%` }}
                          />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </section>

          {/* 运行详情与回放 */}
          <section>
            <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
              {t('runs.detail', 'Run Detail & Replay')}
            </h2>
            {detailLoading ? (
              <p className="empty-state">
                <RefreshCw size={16} className="inline animate-spin" aria-label={t('common.loading', 'Loading')} />
              </p>
            ) : !selected ? (
              <p className="empty-state">{t('runs.selectHint', 'Select a run to inspect node outputs and timeline')}</p>
            ) : (
              <>
                {/* 概要 */}
                <div className="row-line" style={{ padding: '16px 0' }}>
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span className={clsx('badge-status', statusBadge(selected.run.status))}>
                      {selected.run.status}
                    </span>
                    <span className="font-medium text-sm">
                      {selected.run.workflow_name}
                    </span>
                    <span className="cell-data opacity-50">{selected.run.run_id}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 cell-data opacity-60">
                    <span>
                      {t('runs.started', 'Started')}: {new Date(selected.run.started_at).toLocaleString()}
                    </span>
                    <span>
                      {t('runs.duration', 'Duration')}: {durationMs(selected.run.started_at, selected.run.completed_at)}
                    </span>
                  </div>
                  {selected.run.error && (
                    <p className="mt-2 text-xs text-[#dc2626] font-mono break-all">{selected.run.error}</p>
                  )}
                  {/* needs_approval 时提供审批恢复入口 */}
                  {selected.run.status === 'needs_approval' && (
                    <div className="mt-3 flex items-center gap-2">
                      <input
                        value={approvalId}
                        onChange={(e) => setApprovalId(e.target.value)}
                        placeholder="approval_id"
                        className={clsx(
                          'flex-1 px-3 py-1.5 rounded-md border text-sm focus:outline-none focus:ring-2 focus:ring-blue-500',
                          theme === 'dark' ? 'bg-slate-800 border-slate-600 text-white' : 'bg-white border-slate-300 text-slate-900'
                        )}
                      />
                      <button
                        onClick={handleResumeApproved}
                        disabled={resuming}
                        className="px-3 py-1.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg transition-colors"
                      >
                        {t('runs.resumeApproved', 'Resume (approved)')}
                      </button>
                    </div>
                  )}
                </div>

                {/* 逐节点输出 */}
                <div className="mt-6">
                  <h3 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
                    {t('runs.nodes', 'Node Results')} ({selected.run.node_results?.length ?? 0})
                  </h3>
                  <div className="max-h-64 overflow-y-auto">
                    {(selected.run.node_results ?? []).map((node) => (
                      <div key={node.node_id} className="row-line text-xs">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={clsx('badge-status', statusBadge(node.status))}>
                            {node.status}
                          </span>
                          <span className="font-medium">
                            {node.node_id}
                          </span>
                          <span className="cell-data opacity-50">
                            {node.node_type} · {node.attempts} attempt(s)
                            {node.compensated ? ' · compensated' : ''}
                          </span>
                        </div>
                        {node.error && <p className="mt-1 text-[#dc2626] font-mono break-all">{node.error}</p>}
                        {node.output != null && (
                          <pre
                            className={clsx(
                              'mt-1 p-2 rounded overflow-x-auto font-mono',
                              theme === 'dark' ? 'bg-slate-800 text-slate-300' : 'bg-slate-50 text-slate-700'
                            )}
                          >
                            {typeof node.output === 'string' ? node.output : JSON.stringify(node.output, null, 2)}
                          </pre>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* 时间线回放 */}
                <div className="mt-6">
                  <h3 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
                    {t('runs.timeline', 'Replay Timeline')} ({selected.timeline?.length ?? 0})
                  </h3>
                  <ol className="relative ml-2 max-h-64 overflow-y-auto pr-2 border-l" style={{ borderColor: 'var(--divider)' }}>
                    {(selected.timeline ?? []).map((ev: WorkflowRunTimelineEvent, idx: number) => (
                      <li key={`${ev.kind}-${idx}`} className="ml-4 py-1.5">
                        <span
                          className={clsx(
                            'absolute -left-1 mt-1 h-2 w-2 rounded-full',
                            ev.kind.includes('failed')
                              ? 'bg-[#dc2626]'
                              : ev.kind.includes('compensated')
                                ? 'bg-[#d97706]'
                                : ev.kind.includes('completed')
                                  ? 'bg-[#16a34a]'
                                  : theme === 'dark' ? 'bg-slate-400' : 'bg-slate-500'
                          )}
                          aria-hidden="true"
                        />
                        <div className="text-xs font-medium">
                          {ev.kind}
                          {ev.node_id ? ` · ${ev.node_id}` : ''}
                        </div>
                        <div className="cell-data opacity-50">{new Date(ev.timestamp).toLocaleTimeString()}</div>
                        {ev.error && <div className="text-xs text-[#dc2626] font-mono break-all">{ev.error}</div>}
                      </li>
                    ))}
                  </ol>
                </div>
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}

export default WorkflowRunsPage
