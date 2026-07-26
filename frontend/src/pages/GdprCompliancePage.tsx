import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import {
  complianceOps,
  DeletionRecord,
  EraseResult,
  PIIScanResult,
  PIIMaskResult,
  MaskStrategy,
  ResidencyConfig,
  TSCMatrixResponse,
  ChangeRecord,
  IncidentRecord,
} from '@/services/complianceOps'
import { useI18n } from '@/i18n/context'
import {
  ShieldCheck,
  RefreshCw,
  Download,
  Trash2,
  FileJson,
  ScanSearch,
  EyeOff,
  Globe2,
  ClipboardCheck,
  AlertTriangle,
  GitPullRequest,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import clsx from 'clsx'

/**
 * GdprCompliancePage (A24) — GDPR 数据主体权利 + SOC2 合规台。
 * 后端路由已于 2026-07-26 经 TestClient 枚举确认全部挂载:
 *   gdpr.py (7 端点) + compliance.py (13 端点), 四个 tab 全部真实可用。
 */

type TabKey = 'rights' | 'pii' | 'residency' | 'soc2'

const REGIONS = ['global', 'eu', 'cn', 'us', 'apac']
const MASK_STRATEGIES: MaskStrategy[] = ['mask', 'hash', 'remove', 'generalize']
const CHANGE_TYPES = ['code', 'config', 'infrastructure', 'database', 'security', 'dependency']
const RISK_LEVELS = ['low', 'medium', 'high', 'critical']
const INCIDENT_CATEGORIES = [
  'data_breach', 'unauthorized_access', 'malware', 'denial_of_service',
  'insider_threat', 'supply_chain', 'misconfiguration', 'other',
]
const INCIDENT_SEVERITIES = ['critical', 'high', 'medium', 'low']

const RISK_STYLES: Record<string, string> = {
  low: 'bg-green-500/10 text-green-600 dark:text-green-400',
  medium: 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400',
  high: 'bg-orange-500/10 text-orange-600 dark:text-orange-400',
  critical: 'bg-red-500/10 text-red-600 dark:text-red-400',
}

const STATUS_STYLES: Record<string, string> = {
  implemented: 'bg-green-500/10 text-green-600 dark:text-green-400',
  partial: 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400',
  planned: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  approved: 'bg-green-500/10 text-green-600 dark:text-green-400',
  pending: 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400',
  rejected: 'bg-red-500/10 text-red-600 dark:text-red-400',
}

export const GdprCompliancePage: React.FC = () => {
  const { theme, setError } = useAppStore()
  const { t } = useI18n()
  const [activeTab, setActiveTab] = useState<TabKey>('rights')
  const [pageError, setPageError] = useState<string | null>(null)

  const reportError = useCallback(
    (error: unknown, fallback: string) => {
      const message = error instanceof Error ? error.message : fallback
      setPageError(message)
      setError(message)
    },
    [setError],
  )

  const tabs: Array<{ key: TabKey; label: string; icon: React.ReactNode }> = [
    { key: 'rights', label: t('compliance.tab.rights', 'Data Rights'), icon: <ShieldCheck size={16} /> },
    { key: 'pii', label: t('compliance.tab.pii', 'PII Governance'), icon: <ScanSearch size={16} /> },
    { key: 'residency', label: t('compliance.tab.residency', 'Data Residency'), icon: <Globe2 size={16} /> },
    { key: 'soc2', label: t('compliance.tab.soc2', 'SOC2 Compliance'), icon: <ClipboardCheck size={16} /> },
  ]

  return (
    <div className={clsx('p-8 min-h-full', theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50')}>
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className={clsx('text-3xl font-bold mb-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
            {t('compliance.title', 'GDPR & SOC2 Compliance')}
          </h1>
          <p className={clsx('text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
            {t('compliance.subtitle', 'Data subject rights (Art.17/20), PII governance, data residency and SOC2 trust criteria')}
          </p>
        </div>

        {pageError && (
          <div
            role="alert"
            className={clsx(
              'mb-6 rounded-lg border px-4 py-3 text-sm flex items-start justify-between gap-4',
              theme === 'dark' ? 'border-red-900 bg-red-950/40 text-red-300' : 'border-red-200 bg-red-50 text-red-700',
            )}
          >
            <span>{pageError}</span>
            <button onClick={() => setPageError(null)} className="text-xs underline shrink-0" aria-label={t('common.dismiss', 'Dismiss')}>
              {t('common.dismiss', 'Dismiss')}
            </button>
          </div>
        )}

        {/* Tab bar */}
        <div className={clsx('flex gap-1 mb-6 border-b', theme === 'dark' ? 'border-slate-800' : 'border-slate-200')} role="tablist">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              role="tab"
              aria-selected={activeTab === tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={clsx(
                'flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-t-lg border-b-2 -mb-px transition-colors',
                activeTab === tab.key
                  ? theme === 'dark'
                    ? 'border-blue-500 text-blue-400 bg-slate-900'
                    : 'border-blue-600 text-blue-700 bg-white'
                  : theme === 'dark'
                    ? 'border-transparent text-slate-400 hover:text-slate-200'
                    : 'border-transparent text-slate-500 hover:text-slate-800',
              )}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'rights' && <DataRightsTab reportError={reportError} />}
        {activeTab === 'pii' && <PiiTab reportError={reportError} />}
        {activeTab === 'residency' && <ResidencyTab reportError={reportError} />}
        {activeTab === 'soc2' && <Soc2Tab reportError={reportError} />}
      </div>
    </div>
  )
}

type ErrorReporter = (error: unknown, fallback: string) => void

// ─── 共享小组件 ──────────────────────────────────────────────────────────────

const useStyles = () => {
  const { theme } = useAppStore()
  const card = clsx('rounded-lg border p-4', theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200')
  const input = clsx(
    'px-3 py-2 rounded-lg text-sm border outline-none w-full',
    theme === 'dark'
      ? 'bg-slate-950 border-slate-700 text-white placeholder-slate-500'
      : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400',
  )
  const label = clsx('block text-xs mb-1', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')
  const primaryBtn = clsx(
    'flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50',
  )
  const ghostBtn = clsx(
    'flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
    theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100',
  )
  const dangerBtn = clsx(
    'flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors disabled:opacity-50',
  )
  const muted = clsx('text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')
  const heading = clsx('text-base font-semibold mb-3', theme === 'dark' ? 'text-white' : 'text-slate-900')
  return { theme, card, input, label, primaryBtn, ghostBtn, dangerBtn, muted, heading }
}

// ─── Tab 1: 数据权利 ─────────────────────────────────────────────────────────

const DataRightsTab: React.FC<{ reportError: ErrorReporter }> = ({ reportError }) => {
  const s = useStyles()
  const { t } = useI18n()
  const [userId, setUserId] = useState('')
  const [tenantId, setTenantId] = useState('')
  const [confirmText, setConfirmText] = useState('')
  const [eraseBusy, setEraseBusy] = useState(false)
  const [exportBusy, setExportBusy] = useState(false)
  const [eraseResult, setEraseResult] = useState<EraseResult | null>(null)
  const [deletions, setDeletions] = useState<DeletionRecord[]>([])
  const [listLoading, setListLoading] = useState(false)
  const [proof, setProof] = useState<Record<string, unknown> | null>(null)

  const loadDeletions = useCallback(async () => {
    setListLoading(true)
    try {
      setDeletions(await complianceOps.listDeletions())
    } catch (error) {
      reportError(error, 'Failed to load deletion records')
    } finally {
      setListLoading(false)
    }
  }, [reportError])

  useEffect(() => {
    loadDeletions()
  }, [loadDeletions])

  const eraseConfirmed = confirmText.trim() === userId.trim() && userId.trim().length > 0

  const handleErase = async () => {
    if (!eraseConfirmed) return
    setEraseBusy(true)
    setEraseResult(null)
    try {
      const result = await complianceOps.eraseUserData(userId.trim(), tenantId.trim())
      setEraseResult(result)
      setConfirmText('')
      await loadDeletions()
    } catch (error) {
      reportError(error, 'Erase request failed')
    } finally {
      setEraseBusy(false)
    }
  }

  const handleExport = async () => {
    if (!userId.trim()) return
    setExportBusy(true)
    try {
      const result = await complianceOps.exportUserData(userId.trim(), tenantId.trim())
      complianceOps.downloadJson(result, `gdpr-export-${result.user_id}-${result.request_id}.json`)
    } catch (error) {
      reportError(error, 'Export request failed')
    } finally {
      setExportBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* 删除权 / 导出权 */}
      <div className={s.card}>
        <h2 className={s.heading}>
          {t('compliance.rights.title', 'Data Subject Rights')}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
          <div>
            <label className={s.label}>{t('compliance.rights.userId', 'User ID')}</label>
            <input className={s.input} value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="user-123" aria-label={t('compliance.rights.userId', 'User ID')} />
          </div>
          <div>
            <label className={s.label}>{t('compliance.rights.tenantId', 'Tenant ID (optional)')}</label>
            <input className={s.input} value={tenantId} onChange={(e) => setTenantId(e.target.value)} placeholder="tenant-a" aria-label={t('compliance.rights.tenantId', 'Tenant ID')} />
          </div>
        </div>

        {/* Art.17 删除权 — 二次确认 */}
        <div className={clsx('rounded-lg border p-3 mb-4', s.theme === 'dark' ? 'border-red-900/60 bg-red-950/20' : 'border-red-200 bg-red-50/60')}>
          <div className={clsx('text-sm font-medium mb-2 flex items-center gap-1.5', s.theme === 'dark' ? 'text-red-300' : 'text-red-700')}>
            <Trash2 size={14} />
            {t('compliance.rights.erase', 'Right to Erasure (Art. 17)')}
          </div>
          <p className={clsx('text-xs mb-2', s.theme === 'dark' ? 'text-red-300/70' : 'text-red-600/80')}>
            {t('compliance.rights.eraseHint', 'Irreversible. Type the user ID again to confirm deletion of all data.')}
          </p>
          <div className="flex flex-wrap gap-2">
            <input
              className={clsx(s.input, 'flex-1 min-w-[200px]')}
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder={t('compliance.rights.confirmPlaceholder', 'Re-type user ID to confirm')}
              aria-label={t('compliance.rights.confirm', 'Confirm erasure')}
            />
            <button onClick={handleErase} disabled={!eraseConfirmed || eraseBusy} className={s.dangerBtn} aria-label={t('compliance.rights.erase', 'Erase')}>
              <Trash2 size={16} />
              {eraseBusy ? t('common.loading', 'Loading...') : t('compliance.rights.eraseAction', 'Erase all data')}
            </button>
            <button onClick={handleExport} disabled={!userId.trim() || exportBusy} className={s.ghostBtn} aria-label={t('compliance.rights.export', 'Export')}>
              <FileJson size={16} />
              {exportBusy ? t('common.loading', 'Loading...') : t('compliance.rights.exportAction', 'Export JSON (Art. 20)')}
            </button>
          </div>
        </div>

        {/* 删除结果 */}
        {eraseResult && (
          <div
            role="status"
            className={clsx(
              'rounded-lg border px-4 py-3 text-sm',
              eraseResult.success
                ? s.theme === 'dark' ? 'border-green-900 bg-green-950/40 text-green-300' : 'border-green-200 bg-green-50 text-green-700'
                : s.theme === 'dark' ? 'border-orange-900 bg-orange-950/40 text-orange-300' : 'border-orange-200 bg-orange-50 text-orange-700',
            )}
          >
            <div className="font-medium mb-1">
              {eraseResult.success
                ? t('compliance.rights.eraseOk', 'Erasure completed')
                : t('compliance.rights.erasePartial', 'Erasure completed with errors')}
              {' · '}{t('compliance.rights.totalDeleted', 'Total deleted')}: {eraseResult.total_deleted}
            </div>
            <div className="text-xs break-all">request_id: {eraseResult.request_id} · {eraseResult.completed_at}</div>
            {Object.keys(eraseResult.deleted_counts).length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {Object.entries(eraseResult.deleted_counts).map(([store, count]) => (
                  <span key={store} className="px-2 py-0.5 rounded-full text-xs bg-black/10 dark:bg-white/10">
                    {store}: {count}
                  </span>
                ))}
              </div>
            )}
            {eraseResult.errors.length > 0 && (
              <ul className="text-xs mt-2 list-disc list-inside">
                {eraseResult.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* 删除记录列表 */}
      <div className={s.card}>
        <div className="flex items-center justify-between mb-3">
          <h2 className={clsx(s.heading, 'mb-0')}>{t('compliance.rights.deletions', 'Deletion Records')}</h2>
          <button onClick={loadDeletions} disabled={listLoading} className={s.ghostBtn} aria-label={t('common.refresh', 'Refresh')}>
            <RefreshCw size={16} className={listLoading ? 'animate-spin' : ''} />
          </button>
        </div>
        {deletions.length === 0 && !listLoading ? (
          <p className={s.muted}>{t('compliance.rights.noDeletions', 'No deletion requests recorded')}</p>
        ) : (
          <div className="space-y-2">
            {deletions.map((d) => (
              <div key={d.request_id} className={clsx('flex items-center gap-3 rounded-lg border px-3 py-2 text-sm', s.theme === 'dark' ? 'border-slate-800' : 'border-slate-200')}>
                <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium shrink-0', d.success ? STATUS_STYLES.approved : STATUS_STYLES.rejected)}>
                  {d.success ? 'success' : 'failed'}
                </span>
                <span className={clsx('font-medium truncate', s.theme === 'dark' ? 'text-white' : 'text-slate-900')}>{d.user_id}</span>
                <span className={clsx('text-xs flex-1 truncate', s.theme === 'dark' ? 'text-slate-500' : 'text-slate-400')}>
                  {t('compliance.rights.totalDeleted', 'Total deleted')}: {d.total_deleted} · {new Date(d.completed_at).toLocaleString()}
                </span>
                <button
                  className={s.ghostBtn}
                  onClick={async () => {
                    try {
                      setProof(await complianceOps.getDeletionProof(d.request_id))
                    } catch (error) {
                      reportError(error, 'Failed to load deletion proof')
                    }
                  }}
                  aria-label={t('compliance.rights.proof', 'Proof')}
                >
                  {t('compliance.rights.proof', 'Proof')}
                </button>
              </div>
            ))}
          </div>
        )}
        {proof && (
          <pre className={clsx('mt-3 rounded-md p-3 text-xs overflow-auto max-h-64', s.theme === 'dark' ? 'bg-slate-950 text-slate-300 border border-slate-800' : 'bg-slate-50 text-slate-700 border border-slate-200')}>
            {JSON.stringify(proof, null, 2)}
          </pre>
        )}
      </div>
    </div>
  )
}

// ─── Tab 2: PII 治理 ─────────────────────────────────────────────────────────

const PiiTab: React.FC<{ reportError: ErrorReporter }> = ({ reportError }) => {
  const s = useStyles()
  const { t } = useI18n()
  const [text, setText] = useState('')
  const [strategy, setStrategy] = useState<MaskStrategy>('mask')
  const [scanResult, setScanResult] = useState<PIIScanResult | null>(null)
  const [maskResult, setMaskResult] = useState<PIIMaskResult | null>(null)
  const [scanBusy, setScanBusy] = useState(false)
  const [maskBusy, setMaskBusy] = useState(false)

  const handleScan = async () => {
    if (!text.trim()) return
    setScanBusy(true)
    try {
      setScanResult(await complianceOps.scanPii(text))
    } catch (error) {
      reportError(error, 'PII scan failed')
    } finally {
      setScanBusy(false)
    }
  }

  const handleMask = async () => {
    if (!text.trim()) return
    setMaskBusy(true)
    try {
      setMaskResult(await complianceOps.maskPii(text, strategy))
    } catch (error) {
      reportError(error, 'PII mask failed')
    } finally {
      setMaskBusy(false)
    }
  }

  // 命中位置高亮: 按 start/end 切分原文
  const highlighted = useMemo(() => {
    if (!scanResult || scanResult.matches.length === 0) return null
    const sorted = [...scanResult.matches].sort((a, b) => a.start - b.start)
    const parts: Array<{ text: string; hit: boolean; type?: string }> = []
    let cursor = 0
    for (const m of sorted) {
      if (m.start > cursor) parts.push({ text: text.slice(cursor, m.start), hit: false })
      if (m.end > m.start) parts.push({ text: text.slice(m.start, m.end), hit: true, type: m.type })
      cursor = Math.max(cursor, m.end)
    }
    if (cursor < text.length) parts.push({ text: text.slice(cursor), hit: false })
    return parts
  }, [scanResult, text])

  return (
    <div className="space-y-6">
      <div className={s.card}>
        <h2 className={s.heading}>{t('compliance.pii.title', 'PII Scan & Masking')}</h2>
        <label className={s.label}>{t('compliance.pii.input', 'Text to inspect')}</label>
        <textarea
          className={clsx(s.input, 'min-h-[120px] font-mono')}
          value={text}
          onChange={(e) => { setText(e.target.value); setScanResult(null); setMaskResult(null) }}
          placeholder={t('compliance.pii.placeholder', 'Paste text containing emails, phone numbers, ID cards...')}
          aria-label={t('compliance.pii.input', 'Text to inspect')}
        />
        <div className="flex flex-wrap items-end gap-3 mt-3">
          <div>
            <label className={s.label}>{t('compliance.pii.strategy', 'Mask strategy')}</label>
            <select className={s.input} value={strategy} onChange={(e) => setStrategy(e.target.value as MaskStrategy)} aria-label={t('compliance.pii.strategy', 'Mask strategy')}>
              {MASK_STRATEGIES.map((st) => <option key={st} value={st}>{st}</option>)}
            </select>
          </div>
          <button onClick={handleScan} disabled={!text.trim() || scanBusy} className={s.primaryBtn} aria-label={t('compliance.pii.scan', 'Scan')}>
            <ScanSearch size={16} />
            {scanBusy ? t('common.loading', 'Loading...') : t('compliance.pii.scan', 'Scan PII')}
          </button>
          <button onClick={handleMask} disabled={!text.trim() || maskBusy} className={s.ghostBtn} aria-label={t('compliance.pii.mask', 'Mask')}>
            <EyeOff size={16} />
            {maskBusy ? t('common.loading', 'Loading...') : t('compliance.pii.maskPreview', 'Mask preview')}
          </button>
        </div>
      </div>

      {/* 扫描结果 */}
      {scanResult && (
        <div className={s.card}>
          <div className="flex items-center gap-2 mb-3">
            <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium', scanResult.has_pii ? STATUS_STYLES.rejected : STATUS_STYLES.approved)}>
              {scanResult.has_pii ? t('compliance.pii.found', 'PII detected') : t('compliance.pii.clean', 'No PII')}
            </span>
            <span className={s.muted}>{t('compliance.pii.count', 'Matches')}: {scanResult.pii_count}</span>
          </div>
          {highlighted && (
            <div className={clsx('rounded-md p-3 text-sm font-mono whitespace-pre-wrap break-all mb-3', s.theme === 'dark' ? 'bg-slate-950 border border-slate-800 text-slate-300' : 'bg-slate-50 border border-slate-200 text-slate-700')}>
              {highlighted.map((part, i) =>
                part.hit ? (
                  <mark key={i} title={part.type} className="bg-yellow-300/70 dark:bg-yellow-500/40 text-inherit rounded px-0.5">
                    {part.text}
                  </mark>
                ) : (
                  <span key={i}>{part.text}</span>
                ),
              )}
            </div>
          )}
          {scanResult.matches.length > 0 && (
            <div className="space-y-1.5">
              {scanResult.matches.map((m, i) => (
                <div key={i} className={clsx('flex items-center gap-3 text-xs rounded-md border px-3 py-1.5', s.theme === 'dark' ? 'border-slate-800' : 'border-slate-200')}>
                  <span className="px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 font-medium shrink-0">{m.type}</span>
                  <span className={clsx('truncate flex-1 font-mono', s.theme === 'dark' ? 'text-slate-300' : 'text-slate-700')}>{m.value}</span>
                  <span className={clsx('shrink-0', s.theme === 'dark' ? 'text-slate-500' : 'text-slate-400')}>
                    [{m.start}, {m.end}) · {(m.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 脱敏预览 */}
      {maskResult && (
        <div className={s.card}>
          <h3 className={clsx('text-sm font-semibold mb-2', s.theme === 'dark' ? 'text-white' : 'text-slate-900')}>
            {t('compliance.pii.maskResult', 'Masked output')} · {strategy} · {t('compliance.pii.count', 'Matches')}: {maskResult.pii_count} · {t('compliance.pii.origLen', 'Original length')}: {maskResult.original_length}
          </h3>
          <pre className={clsx('rounded-md p-3 text-sm whitespace-pre-wrap break-all', s.theme === 'dark' ? 'bg-slate-950 text-green-300 border border-slate-800' : 'bg-slate-50 text-green-700 border border-slate-200')}>
            {maskResult.masked_text}
          </pre>
        </div>
      )}
    </div>
  )
}

// ─── Tab 3: 数据驻留 ─────────────────────────────────────────────────────────

const ResidencyTab: React.FC<{ reportError: ErrorReporter }> = ({ reportError }) => {
  const s = useStyles()
  const { t } = useI18n()
  const [config, setConfig] = useState<ResidencyConfig | null>(null)
  const [loading, setLoading] = useState(false)
  const [tenantId, setTenantId] = useState('')
  const [region, setRegion] = useState('eu')
  const [allowed, setAllowed] = useState<string[]>([])
  const [blockCrossBorder, setBlockCrossBorder] = useState(true)
  const [saveBusy, setSaveBusy] = useState(false)
  const [savedMsg, setSavedMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setConfig(await complianceOps.getResidency())
    } catch (error) {
      reportError(error, 'Failed to load residency config')
    } finally {
      setLoading(false)
    }
  }, [reportError])

  useEffect(() => {
    load()
  }, [load])

  const handleSave = async () => {
    if (!tenantId.trim()) return
    setSaveBusy(true)
    setSavedMsg(null)
    try {
      const result = await complianceOps.setResidencyRule(tenantId.trim(), {
        region,
        allowed_regions: allowed,
        block_cross_border: blockCrossBorder,
      })
      setSavedMsg(`${result.tenant_id} → ${result.region}`)
      await load()
    } catch (error) {
      reportError(error, 'Failed to save residency rule')
    } finally {
      setSaveBusy(false)
    }
  }

  const toggleAllowed = (r: string) => {
    setAllowed((prev) => (prev.includes(r) ? prev.filter((x) => x !== r) : [...prev, r]))
  }

  const ruleEntries = Object.entries(config?.rules ?? {})

  return (
    <div className="space-y-6">
      <div className={s.card}>
        <div className="flex items-center justify-between mb-3">
          <h2 className={clsx(s.heading, 'mb-0')}>{t('compliance.residency.config', 'Residency Configuration')}</h2>
          <button onClick={load} disabled={loading} className={s.ghostBtn} aria-label={t('common.refresh', 'Refresh')}>
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
        <div className="flex flex-wrap gap-4 text-sm mb-4">
          <span className={s.muted}>
            {t('compliance.residency.enabled', 'Enabled')}:{' '}
            <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium', config?.enabled ? STATUS_STYLES.approved : STATUS_STYLES.pending)}>
              {config ? String(config.enabled) : '—'}
            </span>
          </span>
          <span className={s.muted}>{t('compliance.residency.defaultRegion', 'Default region')}: <strong>{config?.default_region ?? '—'}</strong></span>
        </div>
        {ruleEntries.length === 0 ? (
          <p className={s.muted}>{t('compliance.residency.noRules', 'No tenant-specific rules')}</p>
        ) : (
          <div className="space-y-2">
            {ruleEntries.map(([tid, rule]) => (
              <div key={tid} className={clsx('flex flex-wrap items-center gap-3 rounded-lg border px-3 py-2 text-sm', s.theme === 'dark' ? 'border-slate-800' : 'border-slate-200')}>
                <span className={clsx('font-medium', s.theme === 'dark' ? 'text-white' : 'text-slate-900')}>{tid}</span>
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400">{rule.region}</span>
                <span className={clsx('text-xs', s.theme === 'dark' ? 'text-slate-500' : 'text-slate-400')}>
                  {t('compliance.residency.allowed', 'Allowed')}: {rule.allowed_regions.length > 0 ? rule.allowed_regions.join(', ') : '—'}
                </span>
                {rule.block_cross_border && (
                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-orange-500/10 text-orange-600 dark:text-orange-400">
                    {t('compliance.residency.blockCross', 'Cross-border blocked')}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 设置规则 */}
      <div className={s.card}>
        <h2 className={s.heading}>{t('compliance.residency.setRule', 'Set Tenant Rule')}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
          <div>
            <label className={s.label}>{t('compliance.rights.tenantId', 'Tenant ID')}</label>
            <input className={s.input} value={tenantId} onChange={(e) => setTenantId(e.target.value)} placeholder="tenant-a" aria-label={t('compliance.rights.tenantId', 'Tenant ID')} />
          </div>
          <div>
            <label className={s.label}>{t('compliance.residency.region', 'Region')}</label>
            <select className={s.input} value={region} onChange={(e) => setRegion(e.target.value)} aria-label={t('compliance.residency.region', 'Region')}>
              {REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        </div>
        <div className="mb-3">
          <label className={s.label}>{t('compliance.residency.allowed', 'Allowed regions')}</label>
          <div className="flex flex-wrap gap-2">
            {REGIONS.map((r) => (
              <button
                key={r}
                onClick={() => toggleAllowed(r)}
                aria-pressed={allowed.includes(r)}
                className={clsx(
                  'px-3 py-1 rounded-full text-xs font-medium border transition-colors',
                  allowed.includes(r)
                    ? 'bg-blue-600 text-white border-blue-600'
                    : s.theme === 'dark' ? 'border-slate-700 text-slate-400 hover:border-slate-500' : 'border-slate-300 text-slate-600 hover:border-slate-400',
                )}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
        <label className={clsx('flex items-center gap-2 text-sm mb-4 cursor-pointer', s.theme === 'dark' ? 'text-slate-300' : 'text-slate-700')}>
          <input type="checkbox" checked={blockCrossBorder} onChange={(e) => setBlockCrossBorder(e.target.checked)} className="rounded" />
          {t('compliance.residency.blockCross', 'Block cross-border transfer')}
        </label>
        <div className="flex items-center gap-3">
          <button onClick={handleSave} disabled={!tenantId.trim() || saveBusy} className={s.primaryBtn} aria-label={t('common.save', 'Save')}>
            {saveBusy ? t('common.loading', 'Loading...') : t('common.save', 'Save rule')}
          </button>
          {savedMsg && <span className={clsx('text-xs', s.theme === 'dark' ? 'text-green-400' : 'text-green-600')}>{savedMsg}</span>}
        </div>
      </div>
    </div>
  )
}

// ─── Tab 4: SOC2 合规 ────────────────────────────────────────────────────────

const Soc2Tab: React.FC<{ reportError: ErrorReporter }> = ({ reportError }) => {
  const s = useStyles()
  const { t } = useI18n()
  const [matrix, setMatrix] = useState<TSCMatrixResponse | null>(null)
  const [changes, setChanges] = useState<ChangeRecord[]>([])
  const [incidents, setIncidents] = useState<IncidentRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [changeTitle, setChangeTitle] = useState('')
  const [changeType, setChangeType] = useState('code')
  const [changeRisk, setChangeRisk] = useState('medium')
  const [incidentTitle, setIncidentTitle] = useState('')
  const [incidentCategory, setIncidentCategory] = useState('other')
  const [incidentSeverity, setIncidentSeverity] = useState('medium')
  const [createBusy, setCreateBusy] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [m, c, i] = await Promise.all([
        complianceOps.getTscMatrix(),
        complianceOps.listChanges(),
        complianceOps.listIncidents(),
      ])
      setMatrix(m)
      setChanges(c)
      setIncidents(i)
    } catch (error) {
      reportError(error, 'Failed to load SOC2 data')
    } finally {
      setLoading(false)
    }
  }, [reportError])

  useEffect(() => {
    load()
  }, [load])

  const handleCreateChange = async () => {
    if (!changeTitle.trim()) return
    setCreateBusy(true)
    try {
      await complianceOps.createChange({ title: changeTitle.trim(), change_type: changeType, risk_level: changeRisk })
      setChangeTitle('')
      setChanges(await complianceOps.listChanges())
    } catch (error) {
      reportError(error, 'Failed to create change')
    } finally {
      setCreateBusy(false)
    }
  }

  const handleCreateIncident = async () => {
    if (!incidentTitle.trim()) return
    setCreateBusy(true)
    try {
      await complianceOps.reportIncident({ title: incidentTitle.trim(), category: incidentCategory, severity: incidentSeverity })
      setIncidentTitle('')
      setIncidents(await complianceOps.listIncidents())
    } catch (error) {
      reportError(error, 'Failed to report incident')
    } finally {
      setCreateBusy(false)
    }
  }

  const handleApprove = async (changeId: string) => {
    try {
      await complianceOps.approveChange(changeId)
      setChanges(await complianceOps.listChanges())
    } catch (error) {
      reportError(error, 'Failed to approve change')
    }
  }

  const score = matrix ? Math.round(matrix.compliance_score * (matrix.compliance_score <= 1 ? 100 : 1)) : null

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <button onClick={load} disabled={loading} className={s.ghostBtn} aria-label={t('common.refresh', 'Refresh')}>
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          {t('common.refresh', 'Refresh')}
        </button>
      </div>

      {/* TSC 控制项状态矩阵 */}
      <div className={s.card}>
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <h2 className={clsx(s.heading, 'mb-0')}>{t('compliance.soc2.matrix', 'Trust Services Criteria Matrix')}</h2>
          {score !== null && (
            <span className={clsx('px-3 py-1 rounded-full text-sm font-semibold', score >= 80 ? STATUS_STYLES.approved : STATUS_STYLES.pending)}>
              {t('compliance.soc2.score', 'Compliance score')}: {score}%
            </span>
          )}
        </div>
        {matrix && Object.keys(matrix.summary).length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {Object.entries(matrix.summary).map(([status, count]) => (
              <span key={status} className={clsx('px-2 py-0.5 rounded-full text-xs font-medium', STATUS_STYLES[status] ?? 'bg-slate-500/10 text-slate-600 dark:text-slate-300')}>
                {status}: {count}
              </span>
            ))}
          </div>
        )}
        {!matrix || matrix.matrix.length === 0 ? (
          <p className={s.muted}>{loading ? t('common.loading', 'Loading...') : t('compliance.soc2.empty', 'No criteria mappings')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className={clsx('text-left text-xs', s.theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>
                  <th className="pb-2 pr-3">{t('compliance.soc2.criteria', 'Criteria')}</th>
                  <th className="pb-2 pr-3">{t('compliance.soc2.category', 'Category')}</th>
                  <th className="pb-2 pr-3">{t('compliance.soc2.status', 'Status')}</th>
                  <th className="pb-2">{t('compliance.soc2.implementation', 'Implementation')}</th>
                </tr>
              </thead>
              <tbody>
                {matrix.matrix.map((m) => (
                  <tr key={m.criteria_id} className={clsx('border-t', s.theme === 'dark' ? 'border-slate-800' : 'border-slate-100')}>
                    <td className={clsx('py-2 pr-3 font-medium', s.theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                      {m.criteria_id}
                      <div className={clsx('text-xs font-normal', s.theme === 'dark' ? 'text-slate-500' : 'text-slate-400')}>{m.criteria_name}</div>
                    </td>
                    <td className="py-2 pr-3"><span className="px-2 py-0.5 rounded-full text-xs bg-blue-500/10 text-blue-600 dark:text-blue-400">{m.category}</span></td>
                    <td className="py-2 pr-3"><span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium', STATUS_STYLES[m.status] ?? 'bg-slate-500/10 text-slate-600 dark:text-slate-300')}>{m.status}</span></td>
                    <td className={clsx('py-2 text-xs', s.theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>{m.implementation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 变更管理 */}
      <div className={s.card}>
        <h2 className={clsx(s.heading, 'flex items-center gap-2')}><GitPullRequest size={16} />{t('compliance.soc2.changes', 'Change Management')}</h2>
        <div className="flex flex-wrap gap-2 mb-4">
          <input className={clsx(s.input, 'flex-1 min-w-[200px]')} value={changeTitle} onChange={(e) => setChangeTitle(e.target.value)} placeholder={t('compliance.soc2.changeTitle', 'Change title')} aria-label={t('compliance.soc2.changeTitle', 'Change title')} />
          <select className={clsx(s.input, 'w-auto')} value={changeType} onChange={(e) => setChangeType(e.target.value)} aria-label={t('compliance.soc2.changeType', 'Type')}>
            {CHANGE_TYPES.map((ct) => <option key={ct} value={ct}>{ct}</option>)}
          </select>
          <select className={clsx(s.input, 'w-auto')} value={changeRisk} onChange={(e) => setChangeRisk(e.target.value)} aria-label={t('compliance.soc2.changeRisk', 'Risk')}>
            {RISK_LEVELS.map((rl) => <option key={rl} value={rl}>{rl}</option>)}
          </select>
          <button onClick={handleCreateChange} disabled={!changeTitle.trim() || createBusy} className={s.primaryBtn} aria-label={t('compliance.soc2.createChange', 'Create change')}>
            {t('compliance.soc2.createChange', 'Create')}
          </button>
        </div>
        {changes.length === 0 ? (
          <p className={s.muted}>{t('compliance.soc2.noChanges', 'No change requests')}</p>
        ) : (
          <div className="space-y-2">
            {changes.map((c) => (
              <ChangeRow key={c.change_id} change={c} onApprove={handleApprove} />
            ))}
          </div>
        )}
      </div>

      {/* 事件响应 */}
      <div className={s.card}>
        <h2 className={clsx(s.heading, 'flex items-center gap-2')}><AlertTriangle size={16} />{t('compliance.soc2.incidents', 'Security Incidents')}</h2>
        <div className="flex flex-wrap gap-2 mb-4">
          <input className={clsx(s.input, 'flex-1 min-w-[200px]')} value={incidentTitle} onChange={(e) => setIncidentTitle(e.target.value)} placeholder={t('compliance.soc2.incidentTitle', 'Incident title')} aria-label={t('compliance.soc2.incidentTitle', 'Incident title')} />
          <select className={clsx(s.input, 'w-auto')} value={incidentCategory} onChange={(e) => setIncidentCategory(e.target.value)} aria-label={t('compliance.soc2.incidentCategory', 'Category')}>
            {INCIDENT_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select className={clsx(s.input, 'w-auto')} value={incidentSeverity} onChange={(e) => setIncidentSeverity(e.target.value)} aria-label={t('compliance.soc2.incidentSeverity', 'Severity')}>
            {INCIDENT_SEVERITIES.map((sev) => <option key={sev} value={sev}>{sev}</option>)}
          </select>
          <button onClick={handleCreateIncident} disabled={!incidentTitle.trim() || createBusy} className={s.primaryBtn} aria-label={t('compliance.soc2.reportIncident', 'Report incident')}>
            {t('compliance.soc2.reportIncident', 'Report')}
          </button>
        </div>
        {incidents.length === 0 ? (
          <p className={s.muted}>{t('compliance.soc2.noIncidents', 'No incidents reported')}</p>
        ) : (
          <div className="space-y-2">
            {incidents.map((i) => (
              <div key={i.incident_id} className={clsx('flex items-center gap-3 rounded-lg border px-3 py-2 text-sm', s.theme === 'dark' ? 'border-slate-800' : 'border-slate-200')}>
                <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium shrink-0', RISK_STYLES[i.severity] ?? 'bg-slate-500/10 text-slate-600 dark:text-slate-300')}>
                  {i.severity}
                </span>
                <span className={clsx('font-medium truncate', s.theme === 'dark' ? 'text-white' : 'text-slate-900')}>{i.title}</span>
                <span className={clsx('text-xs flex-1 truncate', s.theme === 'dark' ? 'text-slate-500' : 'text-slate-400')}>
                  {i.category} · {i.phase} · {new Date(i.detected_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

const ChangeRow: React.FC<{ change: ChangeRecord; onApprove: (id: string) => void }> = ({ change, onApprove }) => {
  const s = useStyles()
  const { t } = useI18n()
  const [expanded, setExpanded] = useState(false)
  const approvable = change.status !== 'approved' && change.status !== 'rejected'

  return (
    <div className={clsx('rounded-lg border', s.theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200')}>
      <button onClick={() => setExpanded((v) => !v)} className="w-full flex items-center gap-3 px-3 py-2 text-sm text-left" aria-expanded={expanded}>
        <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium shrink-0', RISK_STYLES[change.risk_level] ?? 'bg-slate-500/10 text-slate-600 dark:text-slate-300')}>
          {change.risk_level}
        </span>
        <span className={clsx('font-medium truncate', s.theme === 'dark' ? 'text-white' : 'text-slate-900')}>{change.title}</span>
        <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium shrink-0', STATUS_STYLES[change.status] ?? 'bg-slate-500/10 text-slate-600 dark:text-slate-300')}>
          {change.status}
        </span>
        <span className={clsx('text-xs flex-1 truncate', s.theme === 'dark' ? 'text-slate-500' : 'text-slate-400')}>
          {change.change_type} · {change.requester} · {new Date(change.created_at).toLocaleString()}
        </span>
        {expanded ? <ChevronUp size={16} className="shrink-0 opacity-60" /> : <ChevronDown size={16} className="shrink-0 opacity-60" />}
      </button>
      {expanded && (
        <div className={clsx('px-3 pb-3 pt-1 border-t text-xs space-y-2', s.theme === 'dark' ? 'border-slate-800 text-slate-400' : 'border-slate-100 text-slate-600')}>
          <div>id: {change.change_id} · {t('compliance.soc2.requiredApprovals', 'Required approvals')}: {change.required_approvals}</div>
          {change.description && <div>{change.description}</div>}
          {change.approvals.length > 0 && (
            <div>
              {change.approvals.map((a, i) => (
                <div key={i}>{a.approver} ({a.role}): {a.decision}{a.comment ? ` — ${a.comment}` : ''}</div>
              ))}
            </div>
          )}
          {approvable && (
            <button onClick={() => onApprove(change.change_id)} className={s.primaryBtn} aria-label={t('compliance.soc2.approve', 'Approve')}>
              {t('compliance.soc2.approve', 'Approve')}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default GdprCompliancePage
