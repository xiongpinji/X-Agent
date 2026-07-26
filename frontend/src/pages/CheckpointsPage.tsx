import React, { useEffect, useState, useCallback } from 'react'
import { useAppStore } from '@/store/appStore'
import {
  workflowOps,
  CheckpointSummaryItem,
  CheckpointDetail,
} from '@/services/workflowOps'
import { useI18n } from '@/i18n/context'
import {
  AlertTriangle,
  Bookmark,
  CheckCircle2,
  PauseCircle,
  Play,
  RefreshCw,
  Trash2,
} from 'lucide-react'
import clsx from 'clsx'

/**
 * 断点恢复页 — 端点全部来自 backend/app/api/checkpoints.py:
 * - GET    /api/v1/checkpoints                  可恢复 run 列表
 * - GET    /api/v1/checkpoints/{trace_id}       checkpoint 详情
 * - POST   /api/v1/checkpoints/{trace_id}/resume  从 checkpoint 恢复执行
 * - DELETE /api/v1/checkpoints/{trace_id}       清理 checkpoint
 */
export const CheckpointsPage: React.FC = () => {
  const { theme, setLoading, setError } = useAppStore()
  const { t } = useI18n()
  const [items, setItems] = useState<CheckpointSummaryItem[]>([])
  const [total, setTotal] = useState(0)
  const [selected, setSelected] = useState<CheckpointDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [acting, setActing] = useState(false)

  const loadList = useCallback(async () => {
    try {
      setLoading(true)
      const resp = await workflowOps.listCheckpoints(50)
      setItems(resp.items)
      setTotal(resp.total)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load checkpoints')
    } finally {
      setLoading(false)
    }
  }, [setLoading, setError])

  useEffect(() => {
    loadList()
  }, [loadList])

  const openDetail = async (traceId: string) => {
    try {
      setDetailLoading(true)
      setSelected(await workflowOps.getCheckpointDetail(traceId))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load checkpoint detail')
    } finally {
      setDetailLoading(false)
    }
  }

  const handleResume = async (traceId: string) => {
    try {
      setActing(true)
      const resp = await workflowOps.resumeCheckpoint(traceId)
      setError(null)
      alert(
        `${t('checkpoints.resumed', 'Resumed')}: ${resp.message}\nnew_trace_id: ${resp.new_trace_id}`
      )
      await loadList()
      if (selected?.trace_id === traceId) {
        await openDetail(traceId).catch(() => setSelected(null))
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to resume from checkpoint')
    } finally {
      setActing(false)
    }
  }

  const handleDelete = async (traceId: string) => {
    try {
      setActing(true)
      await workflowOps.deleteCheckpoints(traceId)
      if (selected?.trace_id === traceId) setSelected(null)
      await loadList()
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to delete checkpoints')
    } finally {
      setActing(false)
    }
  }

  const statusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 size={16} className="text-green-500" />
      case 'failed':
        return <AlertTriangle size={16} className="text-red-500" />
      case 'paused':
        return <PauseCircle size={16} className="text-amber-500" />
      default:
        return <RefreshCw size={16} className="text-blue-500" />
    }
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
              {t('checkpoints.title', 'Checkpoints')}
            </h1>
            <p className={clsx('text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
              {t('checkpoints.subtitle', 'Resume interrupted agent runs from checkpoints')}
            </p>
          </div>
          <button
            onClick={loadList}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            <RefreshCw size={16} />
            {t('checkpoints.refresh', 'Refresh')}
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Checkpoint 列表 */}
          <div className="space-y-3">
            <h2 className={clsx('text-lg font-semibold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('checkpoints.list', 'Resumable Runs')} ({total})
            </h2>
            {items.length === 0 ? (
              <div className={clsx(cardCls, 'p-8 text-center', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>
                <Bookmark size={40} className="mx-auto mb-3 opacity-50" />
                <p>{t('checkpoints.empty', 'No resumable checkpoints')}</p>
              </div>
            ) : (
              items.map((cp) => (
                <div
                  key={cp.checkpoint_id}
                  role="button"
                  tabIndex={0}
                  onClick={() => openDetail(cp.trace_id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') openDetail(cp.trace_id)
                  }}
                  className={clsx(
                    'rounded-lg p-4 cursor-pointer transition-colors border',
                    selected?.trace_id === cp.trace_id
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30'
                      : theme === 'dark'
                        ? 'bg-slate-900 border-slate-700 hover:border-slate-600'
                        : 'bg-white border-slate-200 hover:border-slate-300'
                  )}
                >
                  <div className="flex items-center gap-2">
                    {statusIcon(cp.status)}
                    <span className={clsx('text-sm font-medium truncate', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                      {cp.task_preview || cp.trace_id}
                    </span>
                  </div>
                  <div className={clsx('mt-1 flex items-center gap-4 flex-wrap', mutedCls)}>
                    <span>{cp.status}</span>
                    <span>
                      {t('checkpoints.iteration', 'Iteration')}: {cp.iteration}
                    </span>
                    <span>agent: {cp.agent_id}</span>
                    <span>{new Date(cp.created_at).toLocaleString()}</span>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* 详情与恢复 */}
          <div className="space-y-3">
            <h2 className={clsx('text-lg font-semibold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('checkpoints.detail', 'Checkpoint Detail')}
            </h2>
            {detailLoading ? (
              <div className={clsx(cardCls, 'p-8 text-center', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>
                <RefreshCw size={24} className="mx-auto animate-spin opacity-50" />
              </div>
            ) : !selected ? (
              <div className={clsx(cardCls, 'p-8 text-center text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>
                {t('checkpoints.selectHint', 'Select a run to view its checkpoints')}
              </div>
            ) : (
              <>
                <div className={cardCls}>
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    {statusIcon(selected.status)}
                    <span className={clsx('font-medium font-mono text-sm', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                      {selected.trace_id}
                    </span>
                  </div>
                  <div className={clsx('grid grid-cols-2 gap-2 mb-4', mutedCls)}>
                    <span>agent: {selected.agent_id}</span>
                    <span>
                      {t('checkpoints.latestIteration', 'Latest iteration')}: {selected.latest_iteration}
                    </span>
                    <span>
                      {t('checkpoints.resumable', 'Resumable')}: {selected.resumable ? '✓' : '✗'}
                    </span>
                    <span>
                      {t('checkpoints.count', 'Checkpoints')}: {selected.checkpoints.length}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleResume(selected.trace_id)}
                      disabled={acting || !selected.resumable}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-md transition-colors"
                    >
                      <Play size={14} />
                      {t('checkpoints.resume', 'Resume Execution')}
                    </button>
                    <button
                      onClick={() => handleDelete(selected.trace_id)}
                      disabled={acting}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-md transition-colors"
                    >
                      <Trash2 size={14} />
                      {t('checkpoints.delete', 'Clean Up')}
                    </button>
                  </div>
                </div>

                {/* 历次 checkpoint 快照 */}
                <div className={cardCls}>
                  <h3 className={clsx('text-sm font-semibold mb-3', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                    {t('checkpoints.snapshots', 'Snapshots')}
                  </h3>
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {selected.checkpoints.map((cp) => (
                      <div
                        key={cp.checkpoint_id}
                        className={clsx(
                          'rounded-md p-3 border text-xs',
                          theme === 'dark' ? 'border-slate-700 bg-slate-800/60' : 'border-slate-200 bg-slate-50'
                        )}
                      >
                        <div className="flex items-center gap-2 flex-wrap">
                          {statusIcon(cp.status)}
                          <span className={clsx('font-medium', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                            #{cp.iteration}
                          </span>
                          <span className={mutedCls}>{cp.status}</span>
                          {cp.created_at && <span className={mutedCls}>{new Date(cp.created_at).toLocaleString()}</span>}
                        </div>
                        <div className={clsx('mt-1 flex items-center gap-4 flex-wrap', mutedCls)}>
                          <span>
                            {t('checkpoints.remaining', 'Remaining steps')}: {cp.remaining_steps?.length ?? 0}
                          </span>
                          <span>
                            {t('checkpoints.completedSteps', 'Completed steps')}: {cp.completed_steps?.length ?? 0}
                          </span>
                          <span>
                            {t('checkpoints.toolCalls', 'Tool calls')}: {cp.tool_calls?.length ?? 0}
                          </span>
                        </div>
                        {cp.answer_so_far && (
                          <p className={clsx('mt-1 line-clamp-3', theme === 'dark' ? 'text-slate-300' : 'text-slate-600')}>
                            {cp.answer_so_far}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default CheckpointsPage
