import React, { useCallback, useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { governanceOps, AuditLogRecord, AuditChainVerification, AuditSummary } from '@/services/governanceOps'
import { useI18n } from '@/i18n/context'
import { RefreshCw, Download, ShieldCheck, ChevronDown, ChevronUp } from 'lucide-react'
import clsx from 'clsx'

interface Filters {
  action: string
  resource_type: string
  outcome: string
  startDate: string
  endDate: string
}

const EMPTY_FILTERS: Filters = { action: '', resource_type: '', outcome: '', startDate: '', endDate: '' }

const OUTCOME_BADGE: Record<string, string> = {
  success: 'badge-success',
  failed: 'badge-danger',
  denied: 'badge-warning',
}

export const AuditLogsPage: React.FC = () => {
  const { theme, setError } = useAppStore()
  const { t } = useI18n()
  const [records, setRecords] = useState<AuditLogRecord[]>([])
  const [summary, setSummary] = useState<AuditSummary | null>(null)
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [verification, setVerification] = useState<AuditChainVerification | null>(null)
  const [verifyBusy, setVerifyBusy] = useState(false)
  const [exportBusy, setExportBusy] = useState(false)
  const comingSoon = t('common.comingSoon', 'Coming soon')

  const loadLogs = useCallback(async (active: Filters) => {
    try {
      setIsLoading(true)
      setLoadError(null)
      const [list, summaryData] = await Promise.all([
        governanceOps.listAuditLogs({
          limit: 200,
          ...(active.action ? { action: active.action } : {}),
          ...(active.resource_type ? { resource_type: active.resource_type } : {}),
          ...(active.outcome ? { outcome: active.outcome } : {}),
        }),
        governanceOps.getAuditSummary().catch(() => null),
      ])
      let items = list.data
      // 时间过滤: 列表端点不支持时间参数, 前端按 created_at 过滤
      if (active.startDate) {
        const start = new Date(active.startDate).getTime()
        items = items.filter((r) => new Date(r.created_at).getTime() >= start)
      }
      if (active.endDate) {
        const end = new Date(active.endDate).getTime() + 24 * 60 * 60 * 1000
        items = items.filter((r) => new Date(r.created_at).getTime() < end)
      }
      setRecords(items)
      setSummary(summaryData)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load audit logs'
      setLoadError(message)
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [setError])

  useEffect(() => {
    loadLogs(EMPTY_FILTERS)
  }, [loadLogs])

  const handleVerify = async () => {
    setVerifyBusy(true)
    try {
      setVerification(await governanceOps.verifyAuditChain())
    } catch (error) {
      setVerification(null)
      setLoadError(error instanceof Error ? error.message : 'Verification failed')
    } finally {
      setVerifyBusy(false)
    }
  }

  const handleExport = async (format: 'csv' | 'json') => {
    setExportBusy(true)
    try {
      const active = {
        ...(filters.action ? { action: filters.action } : {}),
        ...(filters.resource_type ? { resource_type: filters.resource_type } : {}),
        ...(filters.outcome ? { outcome: filters.outcome } : {}),
      }
      if (format === 'csv') {
        await governanceOps.exportAuditCsv(active)
      } else {
        await governanceOps.exportAuditJson(active)
      }
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Export failed')
    } finally {
      setExportBusy(false)
    }
  }

  const inputCls = clsx(
    'px-3 py-2 rounded-lg text-sm border outline-none',
    theme === 'dark' ? 'bg-slate-950 border-slate-700 text-white placeholder-slate-500' : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400'
  )

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
          <div className="flex items-end justify-between gap-4 flex-wrap">
            <div>
              <h1 className="page-title">{t('audit.title', 'Audit Logs')}</h1>
              <p className="page-subtitle">{t('audit.subtitle', 'Inspect, verify and export tamper-evident audit logs')}</p>
            </div>
            <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => handleExport('csv')}
              disabled={exportBusy}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
                theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100'
              )}
              aria-label={t('audit.exportCsv', 'Export CSV')}
            >
              <Download size={16} />
              CSV
            </button>
            <button
              onClick={() => handleExport('json')}
              disabled={exportBusy}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
                theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100'
              )}
              aria-label={t('audit.exportJson', 'Export JSON')}
            >
              <Download size={16} />
              JSON
            </button>
            {/* 增强审计 (audit_enhanced.py: 高级搜索/合规报告/XML/PDF) 未挂载 → coming soon */}
            <button
              disabled
              title={`${t('audit.exportPdf', 'Compliance PDF')} (${comingSoon})`}
              aria-label={`${t('audit.exportPdf', 'Compliance PDF')} (${comingSoon})`}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium opacity-50 cursor-not-allowed',
                theme === 'dark' ? 'bg-slate-800 text-slate-500' : 'bg-slate-200 text-slate-500'
              )}
            >
              <Download size={16} />
              PDF ({comingSoon})
            </button>
            <button
              onClick={handleVerify}
              disabled={verifyBusy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
              aria-label={t('audit.verify', 'Verify chain')}
            >
              <ShieldCheck size={16} />
              {verifyBusy ? t('common.loading', 'Loading...') : t('audit.verify', 'Verify chain')}
            </button>
            <button
              onClick={() => loadLogs(filters)}
              disabled={isLoading}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
                theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100'
              )}
              aria-label={t('common.refresh', 'Refresh')}
            >
              <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
            </button>
            </div>
          </div>
        </header>

        {/* Chain verification result */}
        {verification && (
          <div
            role="status"
            className={clsx(
              'mb-6 rounded-lg border px-4 py-3 text-sm',
              verification.valid
                ? theme === 'dark' ? 'border-green-900 bg-green-950/40 text-green-300' : 'border-green-200 bg-green-50 text-green-700'
                : theme === 'dark' ? 'border-red-900 bg-red-950/40 text-red-300' : 'border-red-200 bg-red-50 text-red-700'
            )}
          >
            {verification.valid
              ? t('audit.chainValid', 'Hash chain is intact')
              : t('audit.chainBroken', 'Hash chain verification failed')}
            {' · '}
            {t('audit.checked', 'Checked')}: {verification.checked}
            {' · '}
            {t('audit.signed', 'Signed')}: {verification.signed}
            {verification.broken_at ? ` · broken_at: ${verification.broken_at}` : ''}
            {verification.reason ? ` · ${verification.reason}` : ''}
          </div>
        )}

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

        {/* Summary — Dashboard-style stat row, no cards */}
        <dl className="flex flex-wrap gap-y-6 mb-8">
          <SummaryStat label={t('audit.totalLogs', 'Total logs')} value={summary?.count ?? '—'} />
          <SummaryStat label={t('audit.success', 'Success')} value={summary?.by_outcome?.success ?? '—'} border />
          <SummaryStat label={t('audit.failed', 'Failed')} value={summary?.by_outcome?.failed ?? '—'} border />
          <SummaryStat label={t('audit.topAction', 'Top action')} value={summary ? topKey(summary.by_action) : '—'} border small />
        </dl>

        {/* Filters — flat row, hairline bottom divider */}
        <div className="pb-4 mb-6 flex flex-wrap gap-3 items-end border-b" style={{ borderColor: 'rgba(163,169,177,.15)' }}>
          <div>
            <label className={clsx('block text-xs mb-1', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>{t('audit.filter.action', 'Action')}</label>
            <input className={inputCls} value={filters.action} onChange={(e) => setFilters({ ...filters, action: e.target.value })} placeholder="approval.approve" />
          </div>
          <div>
            <label className={clsx('block text-xs mb-1', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>{t('audit.filter.resourceType', 'Resource type')}</label>
            <input className={inputCls} value={filters.resource_type} onChange={(e) => setFilters({ ...filters, resource_type: e.target.value })} placeholder="approval" />
          </div>
          <div>
            <label className={clsx('block text-xs mb-1', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>{t('audit.filter.outcome', 'Outcome')}</label>
            <select className={inputCls} value={filters.outcome} onChange={(e) => setFilters({ ...filters, outcome: e.target.value })} aria-label={t('audit.filter.outcome', 'Outcome')}>
              <option value="">{t('audit.filter.all', 'All')}</option>
              <option value="success">success</option>
              <option value="failed">failed</option>
              <option value="denied">denied</option>
            </select>
          </div>
          <div>
            <label className={clsx('block text-xs mb-1', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>{t('audit.filter.from', 'From')}</label>
            <input type="date" className={inputCls} value={filters.startDate} onChange={(e) => setFilters({ ...filters, startDate: e.target.value })} />
          </div>
          <div>
            <label className={clsx('block text-xs mb-1', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>{t('audit.filter.to', 'To')}</label>
            <input type="date" className={inputCls} value={filters.endDate} onChange={(e) => setFilters({ ...filters, endDate: e.target.value })} />
          </div>
          <button
            onClick={() => loadLogs(filters)}
            disabled={isLoading}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {t('audit.applyFilters', 'Apply')}
          </button>
          <button
            onClick={() => { setFilters(EMPTY_FILTERS); loadLogs(EMPTY_FILTERS) }}
            disabled={isLoading}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
              theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            )}
          >
            {t('audit.resetFilters', 'Reset')}
          </button>
        </div>

        {/* Log list — hairline divider rows */}
        {records.length === 0 && !isLoading ? (
          <p className="empty-state">
            {t('audit.noLogs', 'No audit logs')} · {t('audit.noLogsHint', 'Logs will appear once actions are recorded')}
          </p>
        ) : (
          <div>
            {records.map((record) => (
              <AuditLogRow key={record.id} record={record} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function topKey(map: Record<string, number>): string {
  const entries = Object.entries(map)
  if (entries.length === 0) return '—'
  return entries.sort((a, b) => b[1] - a[1])[0][0]
}

const SummaryStat: React.FC<{ label: string; value: string | number; border?: boolean; small?: boolean }> = ({ label, value, border, small }) => (
  <div
    className={clsx('flex flex-col gap-2 pr-8 mr-8', border && 'border-r')}
    style={border ? { borderColor: 'rgba(163,169,177,.15)' } : undefined}
  >
    <dd className={clsx('font-data leading-none order-2', small ? 'text-[13px] truncate max-w-[160px]' : 'text-[26px]')}>
      {value}
    </dd>
    <dt className="text-[12px] uppercase tracking-[0.06em] opacity-50 order-1">{label}</dt>
  </div>
)

const AuditLogRow: React.FC<{ record: AuditLogRecord }> = ({ record }) => {
  const { theme } = useAppStore()
  const { t } = useI18n()
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="row-line">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-3 py-1 text-left"
        aria-expanded={expanded}
      >
        <span className={clsx('badge-status shrink-0', OUTCOME_BADGE[record.outcome] ?? 'badge-muted')}>
          {record.outcome}
        </span>
        <span className="font-medium text-[13px] truncate">
          {record.action}
        </span>
        <span className="cell-data truncate flex-1 opacity-50">
          {record.resource_type}{record.resource_id ? `/${record.resource_id}` : ''} · {record.actor_id}
        </span>
        <span className="cell-data shrink-0 opacity-50">
          {new Date(record.created_at).toLocaleString()}
        </span>
        {expanded ? <ChevronUp size={14} className="shrink-0 opacity-50" /> : <ChevronDown size={14} className="shrink-0 opacity-50" />}
      </button>
      {expanded && (
        <div className={clsx('pb-3 pt-2 border-t', theme === 'dark' ? 'border-slate-800' : 'border-slate-100')}>
          <dl className={clsx('grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-xs mb-3', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
            <div><span className="font-medium">id:</span> {record.id}</div>
            <div><span className="font-medium">tenant:</span> {record.tenant_id}</div>
            <div><span className="font-medium">trace_id:</span> {record.trace_id ?? '—'}</div>
            <div><span className="font-medium">run_id:</span> {record.run_id ?? '—'}</div>
            <div className="sm:col-span-2 break-all"><span className="font-medium">hash:</span> {record.hash ?? '—'}</div>
            <div className="sm:col-span-2 break-all"><span className="font-medium">prev_hash:</span> {record.prev_hash ?? '—'}</div>
          </dl>
          {Object.keys(record.details ?? {}).length > 0 && (
            <>
              <div className={clsx('text-xs font-medium mb-1', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>
                {t('audit.details', 'Details')}
              </div>
              <pre className={clsx(
                'rounded-md p-3 text-xs overflow-auto max-h-48',
                theme === 'dark' ? 'bg-slate-950 text-slate-300 border border-slate-800' : 'bg-slate-50 text-slate-700 border border-slate-200'
              )}>
                {JSON.stringify(record.details, null, 2)}
              </pre>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default AuditLogsPage
