import React, { useEffect, useState, useCallback } from 'react'
import { useAppStore } from '@/store/appStore'
import {
  workflowOps,
  WorkflowRunItem,
  WorkflowRunDetail,
  WorkflowRunTimelineEvent,
} from '@/services/workflowOps'
import { useI18n } from '@/i18n/context'
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  History,
  PauseCircle,
  RefreshCw,
  ShieldQuestion,
} from 'lucide-react'
import clsx from 'clsx'

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

  const statusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 size={16} className="text-green-500" />
      case 'running':
        return <RefreshCw size={16} className="text-blue-500 animate-spin" />
      case 'failed':
        return <AlertTriangle size={16} className="text-red-500" />
      case 'paused':
        return <PauseCircle size={16} className="text-amber-500" />
      case 'needs_approval':
        return <ShieldQuestion size={16} className="text-purple-500" />
      default:
        return <Clock size={16} className="text-slate-400" />
    }
  }

  const durationMs = (start?: string, end?: string): string => {
    if (!start || !end) return '—'
    const ms = new Date(end).getTime() - new Date(start).getTime()
    if (Number.isNaN(ms) || ms < 0) return '—'
    return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
  }

  const cardCls = clsx(
    'rounded-lg p-4 border',
    theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
  )
  const mutedCls = clsx('text-xs', theme === 'dark' ? 'text-slate-500' : 'text-slate-400')

  return (
    <div className={clsx('p-8', theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50')}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className={clsx('text-3xl font-bold mb-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('runs.title', 'Workflow Runs')}
            </h1>
            <p className={clsx('text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
              {t('runs.subtitle', 'Run history, node outputs and replay timeline')}
            </p>
          </div>
          <button
            onClick={loadRuns}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            <RefreshCw size={16} />
            {t('runs.refresh', 'Refresh')}
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 运行历史列表 */}
          <div className="space-y-3">
            <h2 className={clsx('text-lg font-semibold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('runs.history', 'History')} ({runs.length})
            </h2>
            {runs.length === 0 ? (
              <div className={clsx(cardCls, 'p-8 text-center', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>
                <History size={40} className="mx-auto mb-3 opacity-50" />
                <p>{t('runs.empty', 'No workflow runs yet')}</p>
              </div>
            ) : (
              runs.map((run) => {
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
                      'rounded-lg p-4 cursor-pointer transition-colors border',
                      selected?.run?.run_id === run.run_id
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30'
                        : theme === 'dark'
                          ? 'bg-slate-900 border-slate-700 hover:border-slate-600'
                          : 'bg-white border-slate-200 hover:border-slate-300'
                    )}
                  >
                    <div className="flex items-center gap-2">
                      {statusIcon(run.status)}
                      <span className={clsx('text-sm font-medium truncate', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                        {run.workflow_name || run.workflow_id}
                      </span>
                      <span className={clsx('ml-auto text-xs font-mono', theme === 'dark' ? 'text-slate-500' : 'text-slate-400')}>
                        {run.run_id.slice(0, 8)}
                      </span>
                    </div>
                    <div className={clsx('mt-2 flex items-center gap-4', mutedCls)}>
                      <span>{run.status}</span>
                      <span>
                        {t('runs.duration', 'Duration')}: {durationMs(run.started_at, run.completed_at)}
                      </span>
                      <span>
                        {t('runs.progress', 'Nodes')}: {cursor}/{total}
                      </span>
                    </div>
                    {total > 0 && (
                      <div className="mt-2 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                        <div
                          className={clsx('h-full rounded-full', run.status === 'failed' ? 'bg-red-500' : 'bg-blue-500')}
                          style={{ width: `${Math.min(100, (cursor / total) * 100)}%` }}
                        />
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>

          {/* 运行详情与回放 */}
          <div className="space-y-3">
            <h2 className={clsx('text-lg font-semibold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('runs.detail', 'Run Detail & Replay')}
            </h2>
            {detailLoading ? (
              <div className={clsx(cardCls, 'p-8 text-center', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>
                <RefreshCw size={24} className="mx-auto animate-spin opacity-50" />
              </div>
            ) : !selected ? (
              <div className={clsx(cardCls, 'p-8 text-center text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>
                {t('runs.selectHint', 'Select a run to inspect node outputs and timeline')}
              </div>
            ) : (
              <>
                {/* 概要 */}
                <div className={cardCls}>
                  <div className="flex items-center gap-2 mb-2">
                    {statusIcon(selected.run.status)}
                    <span className={clsx('font-medium', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                      {selected.run.workflow_name}
                    </span>
                    <span className={mutedCls}>{selected.run.run_id}</span>
                  </div>
                  <div className={clsx('grid grid-cols-2 gap-2', mutedCls)}>
                    <span>
                      {t('runs.started', 'Started')}: {new Date(selected.run.started_at).toLocaleString()}
                    </span>
                    <span>
                      {t('runs.duration', 'Duration')}: {durationMs(selected.run.started_at, selected.run.completed_at)}
                    </span>
                  </div>
                  {selected.run.error && (
                    <p className="mt-2 text-xs text-red-500 font-mono break-all">{selected.run.error}</p>
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
                        className="px-3 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-md transition-colors"
                      >
                        {t('runs.resumeApproved', 'Resume (approved)')}
                      </button>
                    </div>
                  )}
                </div>

                {/* 逐节点输出 */}
                <div className={cardCls}>
                  <h3 className={clsx('text-sm font-semibold mb-3', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                    {t('runs.nodes', 'Node Results')} ({selected.run.node_results?.length ?? 0})
                  </h3>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {(selected.run.node_results ?? []).map((node) => (
                      <div
                        key={node.node_id}
                        className={clsx(
                          'rounded-md p-2 border text-xs',
                          theme === 'dark' ? 'border-slate-700 bg-slate-800/60' : 'border-slate-200 bg-slate-50'
                        )}
                      >
                        <div className="flex items-center gap-2">
                          {statusIcon(node.status)}
                          <span className={clsx('font-medium', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                            {node.node_id}
                          </span>
                          <span className={mutedCls}>
                            {node.node_type} · {node.attempts} attempt(s)
                            {node.compensated ? ' · compensated' : ''}
                          </span>
                        </div>
                        {node.error && <p className="mt-1 text-red-500 font-mono break-all">{node.error}</p>}
                        {node.output != null && (
                          <pre
                            className={clsx(
                              'mt-1 p-2 rounded overflow-x-auto font-mono',
                              theme === 'dark' ? 'bg-slate-950 text-slate-300' : 'bg-white text-slate-700'
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
                <div className={cardCls}>
                  <h3 className={clsx('text-sm font-semibold mb-3', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                    {t('runs.timeline', 'Replay Timeline')} ({selected.timeline?.length ?? 0})
                  </h3>
                  <ol className="relative border-l border-slate-300 dark:border-slate-600 ml-2 space-y-3 max-h-64 overflow-y-auto pr-2">
                    {(selected.timeline ?? []).map((ev: WorkflowRunTimelineEvent, idx: number) => (
                      <li key={`${ev.kind}-${idx}`} className="ml-4">
                        <span
                          className={clsx(
                            'absolute -left-1.5 mt-1 h-3 w-3 rounded-full',
                            ev.kind.includes('failed')
                              ? 'bg-red-500'
                              : ev.kind.includes('compensated')
                                ? 'bg-amber-500'
                                : ev.kind.includes('completed')
                                  ? 'bg-green-500'
                                  : 'bg-blue-500'
                          )}
                        />
                        <div className={clsx('text-xs font-medium', theme === 'dark' ? 'text-slate-200' : 'text-slate-800')}>
                          {ev.kind}
                          {ev.node_id ? ` · ${ev.node_id}` : ''}
                        </div>
                        <div className={mutedCls}>{new Date(ev.timestamp).toLocaleTimeString()}</div>
                        {ev.error && <div className="text-xs text-red-500 font-mono break-all">{ev.error}</div>}
                      </li>
                    ))}
                  </ol>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default WorkflowRunsPage
