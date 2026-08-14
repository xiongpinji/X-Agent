import React, { useCallback, useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { governanceOps, ApprovalRecord } from '@/services/governanceOps'
import { useI18n } from '@/i18n/context'
import { Check, X, Play, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'
import clsx from 'clsx'

const RISK_BADGE: Record<string, string> = {
  low: 'badge-muted',
  medium: 'badge-warning',
  high: 'badge-danger',
  critical: 'badge-danger',
}

const STATUS_BADGE: Record<string, string> = {
  pending: 'badge-warning',
  approved: 'badge-success',
  rejected: 'badge-danger',
  executed: 'badge-muted',
}

export const ApprovalsPage: React.FC = () => {
  const { theme, setError } = useAppStore()
  const { t } = useI18n()
  const [records, setRecords] = useState<ApprovalRecord[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const loadApprovals = useCallback(async () => {
    try {
      setIsLoading(true)
      setLoadError(null)
      // 列表端点单次只接受一个 status 过滤, 这里拉全量再前端拆分待办/历史
      const data = await governanceOps.listApprovals({ limit: 200 })
      setRecords(data)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load approvals'
      setLoadError(message)
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [setError])

  useEffect(() => {
    loadApprovals()
  }, [loadApprovals])

  const pending = records.filter((r) => r.status === 'pending')
  const history = records
    .filter((r) => r.status !== 'pending')
    .sort((a, b) => String(b.decided_at ?? b.created_at).localeCompare(String(a.decided_at ?? a.created_at)))

  return (
    <div className={clsx('min-h-full px-8 py-10', theme === 'dark' ? 'bg-slate-950 text-slate-200' : 'bg-[#fafafa] text-[#333333]')}>
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
              <h1 className="page-title">{t('approvals.title', 'Approvals')}</h1>
              <p className="page-subtitle">{t('approvals.subtitle', 'Review and decide high-risk tool execution requests')}</p>
            </div>
            <button
              onClick={loadApprovals}
              disabled={isLoading}
              className={clsx(
                'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
                theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100'
              )}
              aria-label={t('common.refresh', 'Refresh')}
            >
              <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
              {t('common.refresh', 'Refresh')}
            </button>
          </div>
        </header>

        {loadError && (
          <div
            role="alert"
            className={clsx(
              'mb-6 rounded-lg border px-4 py-3 text-sm',
              theme === 'dark' ? 'border-red-900 bg-red-950/40 text-red-300' : 'border-red-200 bg-red-50 text-red-700'
            )}
          >
            {loadError}
          </div>
        )}

        {/* Pending list */}
        <section className="mb-10">
          <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
            {t('approvals.pending', 'Pending approvals')} ({pending.length})
          </h2>
          {pending.length === 0 && !isLoading ? (
            <p className="empty-state">{t('approvals.noPending', 'No pending approval requests')}</p>
          ) : (
            <div>
              {pending.map((record) => (
                <PendingCard key={record.id} record={record} onDecided={loadApprovals} />
              ))}
            </div>
          )}
        </section>

        {/* History */}
        <section>
          <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
            {t('approvals.history', 'Approval history')} ({history.length})
          </h2>
          {history.length === 0 && !isLoading ? (
            <p className="empty-state">{t('approvals.noHistory', 'No approval history yet')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="table-dense">
                <thead>
                  <tr>
                    <th>{t('approvals.col.action', 'Action')}</th>
                    <th>{t('approvals.col.risk', 'Risk')}</th>
                    <th>{t('approvals.col.status', 'Status')}</th>
                    <th>{t('approvals.col.decidedBy', 'Decided by')}</th>
                    <th>{t('approvals.col.decidedAt', 'Decided at')}</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((record) => (
                    <tr key={record.id}>
                      <td>
                        <div className="font-medium">{record.action}</div>
                        <div className="cell-data opacity-50">
                          {record.resource_type}/{record.resource_id}
                        </div>
                      </td>
                      <td>
                        <span className={clsx('badge-status', RISK_BADGE[record.risk_level] ?? 'badge-muted')}>
                          {record.risk_level}
                        </span>
                      </td>
                      <td>
                        <span className={clsx('badge-status', STATUS_BADGE[record.status] ?? 'badge-muted')}>
                          {record.status}
                        </span>
                      </td>
                      <td className="cell-data opacity-70">{record.decided_by ?? record.executed_by ?? '—'}</td>
                      <td className="cell-data opacity-70">{formatTime(record.decided_at ?? record.executed_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

const PendingCard: React.FC<{ record: ApprovalRecord; onDecided: () => void }> = ({ record, onDecided }) => {
  const { theme } = useAppStore()
  const { t } = useI18n()
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionResult, setActionResult] = useState<string | null>(null)

  const decide = async (kind: 'approve' | 'reject' | 'execute') => {
    setBusy(true)
    setActionError(null)
    setActionResult(null)
    try {
      if (kind === 'execute') {
        const result = await governanceOps.executeApproved(record.id)
        setActionResult(result.success ? t('approvals.executeOk', 'Executed successfully') : String(result.error ?? 'Execution failed'))
      } else if (kind === 'approve') {
        // decided_by 由服务端绑定 principal, 前端只传 reason
        await governanceOps.approveRequest(record.id, reason)
        onDecided()
        return
      } else {
        await governanceOps.rejectRequest(record.id, reason)
        onDecided()
        return
      }
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Action failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="row-line" style={{ padding: '20px 0' }}>
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={clsx('badge-status', RISK_BADGE[record.risk_level] ?? 'badge-muted')}>
              {record.risk_level}
            </span>
            <span className="text-sm font-semibold">
              {record.action}
            </span>
          </div>
          <p className="text-sm opacity-60">
            {t('approvals.tool', 'Tool')}: {record.resource_id}
            {' · '}
            {t('approvals.requester', 'Requester')}: {record.actor_id}
            {' · '}
            <span className="cell-data">{formatTime(record.created_at)}</span>
          </p>
          {record.reason && (
            <p className="text-sm opacity-60 mt-1">
              {t('approvals.reason', 'Reason')}: {record.reason}
            </p>
          )}
        </div>
        <button
          onClick={() => setExpanded((v) => !v)}
          className={clsx('p-1.5 rounded-md transition-colors', theme === 'dark' ? 'text-slate-400 hover:bg-slate-800' : 'text-slate-500 hover:bg-slate-100')}
          aria-label={t('approvals.toggleDetail', 'Toggle details')}
        >
          {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </button>
      </div>

      {expanded && (
        <pre className={clsx(
          'mb-3 rounded-md p-3 text-xs overflow-auto max-h-48',
          theme === 'dark' ? 'bg-slate-950 text-slate-300 border border-slate-800' : 'bg-slate-50 text-slate-700 border border-slate-200'
        )}>
          {JSON.stringify({ arguments_preview: record.arguments_preview, trace_id: record.trace_id }, null, 2)}
        </pre>
      )}

      {actionError && (
        <div role="alert" className={clsx('mb-3 rounded-md border px-3 py-2 text-xs', theme === 'dark' ? 'border-red-900 bg-red-950/40 text-red-300' : 'border-red-200 bg-red-50 text-red-700')}>
          {actionError}
        </div>
      )}
      {actionResult && (
        <div role="status" className={clsx('mb-3 rounded-md border px-3 py-2 text-xs', theme === 'dark' ? 'border-green-900 bg-green-950/40 text-green-300' : 'border-green-200 bg-green-50 text-green-700')}>
          {actionResult}
        </div>
      )}

      {/* Decision reason + actions */}
      <div className="flex flex-col sm:flex-row gap-2">
        <input
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder={t('approvals.reasonPlaceholder', 'Decision reason (optional)')}
          className={clsx(
            'flex-1 px-3 py-2 rounded-lg text-sm border outline-none',
            theme === 'dark' ? 'bg-slate-950 border-slate-700 text-white placeholder-slate-500' : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400'
          )}
          aria-label={t('approvals.decisionReason', 'Decision reason')}
        />
        <div className="flex gap-2">
          <button
            onClick={() => decide('approve')}
            disabled={busy}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-green-600 text-white hover:bg-green-700 transition-colors disabled:opacity-50"
            aria-label={t('approvals.approve', 'Approve')}
          >
            <Check size={16} />
            {t('approvals.approve', 'Approve')}
          </button>
          <button
            onClick={() => decide('reject')}
            disabled={busy}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors disabled:opacity-50"
            aria-label={t('approvals.reject', 'Reject')}
          >
            <X size={16} />
            {t('approvals.reject', 'Reject')}
          </button>
          {/* 执行端点要求状态为 approved, 待审批状态下置灰提示 */}
          <button
            disabled
            title={`${t('approvals.execute', 'Execute')} (${t('approvals.executeAfterApprove', 'available after approval')})`}
            aria-label={t('approvals.execute', 'Execute')}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium opacity-50 cursor-not-allowed',
              theme === 'dark' ? 'bg-slate-700 text-slate-300' : 'bg-slate-200 text-slate-700'
            )}
          >
            <Play size={16} />
            {t('approvals.execute', 'Execute')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ApprovalsPage
