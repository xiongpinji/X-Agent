import React, { useCallback, useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { governanceOps, ApprovalRecord } from '@/services/governanceOps'
import { useI18n } from '@/i18n/context'
import { ShieldCheck, Check, X, Play, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'
import clsx from 'clsx'

const RISK_STYLES: Record<string, string> = {
  low: 'bg-slate-500/10 text-slate-600 dark:text-slate-300',
  medium: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  high: 'bg-orange-500/10 text-orange-600 dark:text-orange-400',
  critical: 'bg-red-500/10 text-red-600 dark:text-red-400',
}

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  approved: 'bg-green-500/10 text-green-600 dark:text-green-400',
  rejected: 'bg-red-500/10 text-red-600 dark:text-red-400',
  executed: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
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
    <div className={clsx('p-8', theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50')}>
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8 flex items-start justify-between">
          <div>
            <h1 className={clsx('text-3xl font-bold mb-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('approvals.title', 'Approvals')}
            </h1>
            <p className={clsx('text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
              {t('approvals.subtitle', 'Review and decide high-risk tool execution requests')}
            </p>
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
          <h2 className={clsx('text-lg font-semibold mb-4 flex items-center gap-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
            <ShieldCheck size={18} />
            {t('approvals.pending', 'Pending approvals')} ({pending.length})
          </h2>
          {pending.length === 0 && !isLoading ? (
            <div className={clsx('text-center py-10 rounded-lg border', theme === 'dark' ? 'border-slate-800 text-slate-400' : 'border-slate-200 text-slate-500 bg-white')}>
              {t('approvals.noPending', 'No pending approval requests')}
            </div>
          ) : (
            <div className="space-y-4">
              {pending.map((record) => (
                <PendingCard key={record.id} record={record} onDecided={loadApprovals} />
              ))}
            </div>
          )}
        </section>

        {/* History */}
        <section>
          <h2 className={clsx('text-lg font-semibold mb-4', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
            {t('approvals.history', 'Approval history')} ({history.length})
          </h2>
          {history.length === 0 && !isLoading ? (
            <div className={clsx('text-center py-10 rounded-lg border', theme === 'dark' ? 'border-slate-800 text-slate-400' : 'border-slate-200 text-slate-500 bg-white')}>
              {t('approvals.noHistory', 'No approval history yet')}
            </div>
          ) : (
            <div className={clsx('rounded-lg border overflow-hidden', theme === 'dark' ? 'border-slate-800' : 'border-slate-200 bg-white')}>
              <table className="w-full text-sm">
                <thead className={theme === 'dark' ? 'bg-slate-900 text-slate-400' : 'bg-slate-50 text-slate-600'}>
                  <tr>
                    <th className="text-left px-4 py-3 font-medium">{t('approvals.col.action', 'Action')}</th>
                    <th className="text-left px-4 py-3 font-medium">{t('approvals.col.risk', 'Risk')}</th>
                    <th className="text-left px-4 py-3 font-medium">{t('approvals.col.status', 'Status')}</th>
                    <th className="text-left px-4 py-3 font-medium">{t('approvals.col.decidedBy', 'Decided by')}</th>
                    <th className="text-left px-4 py-3 font-medium">{t('approvals.col.decidedAt', 'Decided at')}</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((record) => (
                    <tr key={record.id} className={clsx('border-t', theme === 'dark' ? 'border-slate-800 text-slate-300' : 'border-slate-100 text-slate-700')}>
                      <td className="px-4 py-3">
                        <div className="font-medium">{record.action}</div>
                        <div className={clsx('text-xs', theme === 'dark' ? 'text-slate-500' : 'text-slate-400')}>
                          {record.resource_type}/{record.resource_id}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium', RISK_STYLES[record.risk_level] ?? RISK_STYLES.low)}>
                          {record.risk_level}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium', STATUS_STYLES[record.status] ?? STATUS_STYLES.pending)}>
                          {record.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">{record.decided_by ?? record.executed_by ?? '—'}</td>
                      <td className="px-4 py-3">{formatTime(record.decided_at ?? record.executed_at)}</td>
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
    <div className={clsx('rounded-lg border p-5', theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200')}>
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium', RISK_STYLES[record.risk_level] ?? RISK_STYLES.low)}>
              {record.risk_level}
            </span>
            <span className={clsx('text-sm font-semibold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {record.action}
            </span>
          </div>
          <p className={clsx('text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
            {t('approvals.tool', 'Tool')}: {record.resource_id}
            {' · '}
            {t('approvals.requester', 'Requester')}: {record.actor_id}
            {' · '}
            {formatTime(record.created_at)}
          </p>
          {record.reason && (
            <p className={clsx('text-sm mt-1', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
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
