import React, { useEffect, useState, useCallback } from 'react'
import { useAppStore } from '@/store/appStore'
import {
  workflowOps,
  CheckpointSummaryItem,
  CheckpointDetail,
} from '@/services/workflowOps'
import { useI18n } from '@/i18n/context'
import { Play, RefreshCw, Trash2 } from 'lucide-react'
import clsx from 'clsx'

const STATUS_BADGE: Record<string, string> = {
  completed: 'badge-success',
  failed: 'badge-danger',
  paused: 'badge-warning',
}

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

  const statusBadge = (status: string) => STATUS_BADGE[status] ?? 'badge-muted'

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
              <h1 className="page-title">{t('checkpoints.title', 'Checkpoints')}</h1>
              <p className="page-subtitle">{t('checkpoints.subtitle', 'Resume interrupted agent runs from checkpoints')}</p>
            </div>
            <button
              onClick={loadList}
              className={clsx(
                'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100'
              )}
              aria-label={t('checkpoints.refresh', 'Refresh')}
            >
              <RefreshCw size={16} />
              {t('checkpoints.refresh', 'Refresh')}
            </button>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
          {/* Checkpoint 列表 — divider rows, no cards */}
          <section>
            <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
              {t('checkpoints.list', 'Resumable Runs')} ({total})
            </h2>
            {items.length === 0 ? (
              <p className="empty-state">{t('checkpoints.empty', 'No resumable checkpoints')}</p>
            ) : (
              <div>
                {items.map((cp) => (
                  <div
                    key={cp.checkpoint_id}
                    role="button"
                    tabIndex={0}
                    onClick={() => openDetail(cp.trace_id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') openDetail(cp.trace_id)
                    }}
                    className={clsx(
                      'row-line cursor-pointer px-2 -mx-2',
                      selected?.trace_id === cp.trace_id && (theme === 'dark' ? 'bg-slate-800' : 'bg-slate-100')
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <span className={clsx('badge-status', statusBadge(cp.status))}>
                        {cp.status}
                      </span>
                      <span className="text-sm font-medium truncate">
                        {cp.task_preview || cp.trace_id}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-4 flex-wrap cell-data opacity-50">
                      <span>
                        {t('checkpoints.iteration', 'Iteration')}: {cp.iteration}
                      </span>
                      <span>agent: {cp.agent_id}</span>
                      <span>{new Date(cp.created_at).toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* 详情与恢复 */}
          <section>
            <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
              {t('checkpoints.detail', 'Checkpoint Detail')}
            </h2>
            {detailLoading ? (
              <p className="empty-state">
                <RefreshCw size={16} className="inline animate-spin" aria-label={t('common.loading', 'Loading')} />
              </p>
            ) : !selected ? (
              <p className="empty-state">{t('checkpoints.selectHint', 'Select a run to view its checkpoints')}</p>
            ) : (
              <>
                <div className="row-line" style={{ padding: '16px 0' }}>
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span className={clsx('badge-status', statusBadge(selected.status))}>
                      {selected.status}
                    </span>
                    <span className="font-medium cell-data">
                      {selected.trace_id}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 mb-4 cell-data opacity-60">
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
                      className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg transition-colors"
                    >
                      <Play size={14} />
                      {t('checkpoints.resume', 'Resume Execution')}
                    </button>
                    <button
                      onClick={() => handleDelete(selected.trace_id)}
                      disabled={acting}
                      className={clsx(
                        'flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg transition-colors disabled:opacity-50',
                        theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100'
                      )}
                    >
                      <Trash2 size={14} />
                      {t('checkpoints.delete', 'Clean Up')}
                    </button>
                  </div>
                </div>

                {/* 历次 checkpoint 快照 */}
                <div className="mt-6">
                  <h3 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
                    {t('checkpoints.snapshots', 'Snapshots')}
                  </h3>
                  <div className="max-h-96 overflow-y-auto">
                    {selected.checkpoints.map((cp) => (
                      <div key={cp.checkpoint_id} className="row-line text-xs">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={clsx('badge-status', statusBadge(cp.status))}>
                            {cp.status}
                          </span>
                          <span className="font-medium cell-data">#{cp.iteration}</span>
                          {cp.created_at && (
                            <span className="cell-data opacity-50">{new Date(cp.created_at).toLocaleString()}</span>
                          )}
                        </div>
                        <div className="mt-1 flex items-center gap-4 flex-wrap cell-data opacity-50">
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
                          <p className="mt-1 line-clamp-3 opacity-70">
                            {cp.answer_so_far}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}

export default CheckpointsPage
