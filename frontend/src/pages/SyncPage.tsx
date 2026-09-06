import React, { useCallback, useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { useI18n } from '@/i18n/context'
import {
  syncOps,
  SyncConflict,
  SyncHistoryEntry,
  SyncStats,
  OfflineModeStatus,
  SyncHealth,
} from '@/services/syncOps'
import {
  RefreshCw,
  Plus,
  Wifi,
  WifiOff,
  X,
} from 'lucide-react'
import clsx from 'clsx'

const RESOLUTION_STRATEGIES = ['local_wins', 'cloud_wins', 'merge', 'manual']

const DIVIDER = 'var(--divider)'

const HISTORY_STATUS_BADGE: Record<string, string> = {
  completed: 'badge-success',
  success: 'badge-success',
  failed: 'badge-danger',
  error: 'badge-danger',
  pending: 'badge-muted',
  running: 'badge-muted',
}

const SyncPage: React.FC = () => {
  const { theme, setLoading, setError } = useAppStore()
  const { t } = useI18n()

  const [stats, setStats] = useState<SyncStats | null>(null)
  const [health, setHealth] = useState<SyncHealth | null>(null)
  const [offline, setOffline] = useState<OfflineModeStatus | null>(null)
  const [conflicts, setConflicts] = useState<SyncConflict[]>([])
  const [history, setHistory] = useState<SyncHistoryEntry[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  const [showEnqueue, setShowEnqueue] = useState(false)
  const [resolving, setResolving] = useState<SyncConflict | null>(null)

  const isDark = theme === 'dark'

  const loadAll = useCallback(async () => {
    try {
      setLoading(true)
      setLoadError(null)
      const [s, h, o, c, hist] = await Promise.all([
        syncOps.getSyncStats(),
        syncOps.getSyncHealth(),
        syncOps.getOfflineStatus(),
        syncOps.listConflicts(),
        syncOps.getSyncHistory(),
      ])
      setStats(s)
      setHealth(h)
      setOffline(o)
      setConflicts(c)
      setHistory(hist)
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to load sync state'
      setLoadError(msg)
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [setLoading, setError])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  const handleTrigger = async () => {
    try {
      await syncOps.triggerSync()
      await loadAll()
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to trigger sync')
    }
  }

  const healthBadge =
    health?.status === 'healthy' ? 'badge-success' :
    health?.status === 'degraded' ? 'badge-warning' :
    health?.status ? 'badge-danger' : 'badge-muted'

  const statItems = [
    { label: t('sync.health', 'Health'), value: health ? `${health.health_score}` : '—', badge: health ? healthBadge : null, badgeText: health?.status },
    { label: t('sync.pending', 'Pending'), value: stats ? String(stats.pending_syncs) : '—' },
    { label: t('sync.failed', 'Failed'), value: stats ? String(stats.failed_syncs) : '—', alert: Boolean(stats && stats.failed_syncs > 0) },
    { label: t('sync.conflicts', 'Conflicts'), value: stats ? String(stats.unresolved_conflicts) : '—', warn: Boolean(stats && stats.unresolved_conflicts > 0) },
    { label: t('sync.offlineOps', 'Offline Ops'), value: stats ? String(stats.offline_operations) : '—' },
    { label: t('sync.dbSize', 'DB Size (MB)'), value: stats ? stats.database_size_mb.toFixed(2) : '—' },
  ]

  return (
    <div className={clsx(
      'min-h-full px-8 py-10',
      isDark ? 'bg-slate-950 text-slate-200' : 'bg-[#fafafa] text-[#333333]'
    )}>
      <div className="max-w-6xl">
        {/* Header — Dashboard-style */}
        <header className="mb-8">
          <div
            className={clsx('w-12 border-t-2 mb-5', isDark ? 'border-slate-200' : 'border-[#333333]')}
            aria-hidden="true"
          />
          <div className="flex items-end justify-between gap-4 flex-wrap">
            <div>
              <h1 className="page-title">{t('sync.title', 'Sync Center')}</h1>
              <p className="page-subtitle">
                {t('sync.subtitle', 'Local-cloud synchronization status, queue, conflicts and history')}
              </p>
            </div>
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => setShowEnqueue(true)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors"
              >
                <Plus size={16} />
                {t('sync.enqueue', 'Enqueue')}
              </button>
              <button
                onClick={handleTrigger}
                className="flex items-center gap-2 px-3 py-2 border border-[var(--divider)] text-sm font-medium transition-colors hover:bg-[var(--hover)]"
              >
                <RefreshCw size={16} />
                {t('sync.trigger', 'Trigger Sync')}
              </button>
              {/* Offline toggle requires sync:admin scope + cloud connection — coming soon */}
              <button
                disabled
                title={t('sync.offlineComingSoon', 'Offline toggle requires cloud connection (coming soon)')}
                className="flex items-center gap-2 px-3 py-2 border border-[var(--divider)] text-sm font-medium opacity-50 cursor-not-allowed"
              >
                {offline?.enabled ? <WifiOff size={16} /> : <Wifi size={16} />}
                {t('sync.offlineMode', 'Offline Mode')}
                <span className="text-xs">({t('common.comingSoon', 'coming soon')})</span>
              </button>
            </div>
          </div>
        </header>

        {loadError && (
          <div role="alert" className="mb-6 border border-[#dc2626]/40 px-4 py-3 text-sm text-[#dc2626]">
            {loadError}
          </div>
        )}

        {/* Status row — no cards, 1px vertical dividers */}
        <section aria-label={t('sync.title', 'Sync Center')} className="mb-10">
          <dl className="flex flex-wrap gap-y-6">
            {statItems.map((item, i) => (
              <div
                key={item.label}
                className={clsx('flex flex-col gap-2 pr-8 mr-8', i < statItems.length - 1 && 'border-r')}
                style={i < statItems.length - 1 ? { borderColor: DIVIDER } : undefined}
              >
                <dd className={clsx(
                  'font-data text-[26px] leading-none order-2',
                  item.alert && 'text-[#dc2626]',
                  item.warn && 'text-[#d97706]'
                )}>
                  {item.badge ? (
                    <span className={clsx('badge-status', item.badge)}>{item.badgeText}</span>
                  ) : (
                    item.value
                  )}
                </dd>
                <dt className="text-[12px] uppercase tracking-[0.06em] opacity-50 order-1">
                  {item.label}
                </dt>
              </div>
            ))}
          </dl>
        </section>

        {/* Conflicts — dense table */}
        <section className="mb-10">
          <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
            {t('sync.conflictList', 'Unresolved Conflicts')} ({conflicts.length})
          </h2>
          {conflicts.length === 0 ? (
            <p className="empty-state">
              {t('sync.noConflicts', 'No unresolved conflicts')}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="table-dense">
                <thead>
                  <tr>
                    <th>{t('sync.entity', 'Entity')}</th>
                    <th>{t('sync.conflictType', 'Type')}</th>
                    <th>{t('sync.localVersion', 'Local v')}</th>
                    <th>{t('sync.cloudVersion', 'Cloud v')}</th>
                    <th>{t('common.actions', 'Actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {conflicts.map((c) => (
                    <tr key={c.id}>
                      <td className="font-medium">
                        {c.entity_type} / <span className="cell-data opacity-70">{c.entity_id}</span>
                      </td>
                      <td className="opacity-70">
                        {c.conflict_type}
                      </td>
                      <td className="cell-data opacity-70">
                        {c.local_version}
                      </td>
                      <td className="cell-data opacity-70">
                        {c.cloud_version}
                      </td>
                      <td>
                        <button
                          onClick={() => setResolving(c)}
                          className="px-3 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors"
                        >
                          {t('sync.resolve', 'Resolve')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* History — dense table */}
        <section>
          <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
            {t('sync.history', 'Sync History')} ({history.length})
          </h2>
          {history.length === 0 ? (
            <p className="empty-state">
              {t('sync.noHistory', 'No sync history yet')}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="table-dense">
                <thead>
                  <tr>
                    <th>{t('sync.batch', 'Batch')}</th>
                    <th>{t('sync.entity', 'Entity')}</th>
                    <th>{t('sync.operation', 'Op')}</th>
                    <th>{t('sync.direction', 'Direction')}</th>
                    <th>{t('tasks.status', 'Status')}</th>
                    <th>{t('sync.duration', 'Duration (ms)')}</th>
                    <th>{t('tasks.createdAt', 'Created')}</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h) => (
                    <tr key={h.id}>
                      <td className="cell-data opacity-50">
                        {h.sync_batch_id.slice(0, 8)}
                      </td>
                      <td className="font-medium">
                        {h.entity_type} / <span className="cell-data opacity-70">{h.entity_id}</span>
                      </td>
                      <td className="opacity-70">
                        {h.operation}
                      </td>
                      <td className="opacity-70">
                        {h.direction}
                      </td>
                      <td>
                        <span className={clsx('badge-status', HISTORY_STATUS_BADGE[h.status] ?? 'badge-muted')}>
                          {h.status}
                        </span>
                      </td>
                      <td className="cell-data opacity-70">
                        {h.duration_ms}
                      </td>
                      <td className="cell-data opacity-70 whitespace-nowrap">
                        {new Date(h.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {showEnqueue && (
        <EnqueueModal
          dark={isDark}
          onClose={() => setShowEnqueue(false)}
          onDone={() => { setShowEnqueue(false); loadAll() }}
        />
      )}
      {resolving && (
        <ResolveModal
          dark={isDark}
          conflict={resolving}
          onClose={() => setResolving(null)}
          onDone={() => { setResolving(null); loadAll() }}
        />
      )}
    </div>
  )
}

interface EnqueueModalProps {
  dark: boolean
  onClose: () => void
  onDone: () => void
}

const EnqueueModal: React.FC<EnqueueModalProps> = ({ dark, onClose, onDone }) => {
  const { t } = useI18n()
  const { setError } = useAppStore()
  const [entityType, setEntityType] = useState('')
  const [entityId, setEntityId] = useState('')
  const [operation, setOperation] = useState('CREATE')
  const [dataJson, setDataJson] = useState('{}')
  const [priority, setPriority] = useState(0)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    let data: Record<string, unknown>
    try {
      data = JSON.parse(dataJson || '{}')
    } catch {
      setError(t('sync.invalidJson', 'Data must be valid JSON'))
      return
    }
    try {
      setSubmitting(true)
      await syncOps.enqueueSync({
        entity_type: entityType,
        entity_id: entityId,
        operation,
        data,
        priority,
      })
      onDone()
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to enqueue sync')
    } finally {
      setSubmitting(false)
    }
  }

  const inputCls = 'w-full px-3 py-2 text-sm bg-transparent border border-[var(--divider)]'
  const labelCls = 'block text-[13px] opacity-60 mb-1'

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" role="dialog" aria-modal="true">
      <div
        className={clsx('p-6 max-w-md w-full mx-4 border', dark ? 'bg-slate-900' : 'bg-white')}
        style={{ borderColor: 'var(--divider)' }}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium">
            {t('sync.enqueueTitle', 'Enqueue Sync Operation')}
          </h2>
          <button onClick={onClose} aria-label={t('common.close', 'Close')}
            className="opacity-50 hover:opacity-100 transition-opacity">
            <X size={20} />
          </button>
        </div>
        <div className="space-y-4 mb-6">
          <div>
            <label htmlFor="sync-entity-type" className={labelCls}>{t('sync.entityType', 'Entity type')}</label>
            <input id="sync-entity-type" className={inputCls} value={entityType}
              onChange={(e) => setEntityType(e.target.value)} placeholder="task" />
          </div>
          <div>
            <label htmlFor="sync-entity-id" className={labelCls}>{t('sync.entityId', 'Entity ID')}</label>
            <input id="sync-entity-id" className={inputCls} value={entityId}
              onChange={(e) => setEntityId(e.target.value)} placeholder="task-123" />
          </div>
          <div>
            <label htmlFor="sync-operation" className={labelCls}>{t('sync.operation', 'Operation')}</label>
            <select id="sync-operation" className={inputCls} value={operation}
              onChange={(e) => setOperation(e.target.value)}>
              <option value="CREATE">CREATE</option>
              <option value="UPDATE">UPDATE</option>
              <option value="DELETE">DELETE</option>
            </select>
          </div>
          <div>
            <label htmlFor="sync-data" className={labelCls}>{t('sync.data', 'Data (JSON)')}</label>
            <textarea id="sync-data" className={inputCls} rows={3} value={dataJson}
              onChange={(e) => setDataJson(e.target.value)} />
          </div>
          <div>
            <label htmlFor="sync-priority" className={labelCls}>{t('sync.priority', 'Priority')}</label>
            <input id="sync-priority" type="number" className={inputCls} value={priority}
              onChange={(e) => setPriority(Number(e.target.value))} />
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={onClose} className="flex-1 px-4 py-2 border border-[var(--divider)] text-sm font-medium transition-colors hover:bg-[var(--hover)]">
            {t('common.cancel', 'Cancel')}
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting || !entityType.trim() || !entityId.trim()}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors disabled:opacity-50"
          >
            {submitting ? t('common.loading', 'Loading...') : t('sync.enqueue', 'Enqueue')}
          </button>
        </div>
      </div>
    </div>
  )
}

interface ResolveModalProps {
  dark: boolean
  conflict: SyncConflict
  onClose: () => void
  onDone: () => void
}

const ResolveModal: React.FC<ResolveModalProps> = ({ dark, conflict, onClose, onDone }) => {
  const { t } = useI18n()
  const { setError } = useAppStore()
  const [strategy, setStrategy] = useState('local_wins')
  const [submitting, setSubmitting] = useState(false)

  const handleResolve = async () => {
    // resolved_data follows the chosen strategy; backend records strategy + data.
    const resolvedData =
      strategy === 'local_wins' ? conflict.local_data :
      strategy === 'cloud_wins' ? conflict.cloud_data :
      { ...conflict.cloud_data, ...conflict.local_data }
    try {
      setSubmitting(true)
      await syncOps.resolveConflict(conflict.id, strategy, resolvedData)
      onDone()
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to resolve conflict')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" role="dialog" aria-modal="true">
      <div
        className={clsx('p-6 max-w-lg w-full mx-4 border', dark ? 'bg-slate-900' : 'bg-white')}
        style={{ borderColor: 'var(--divider)' }}
      >
        <h2 className="text-lg font-medium mb-4">
          {t('sync.resolveTitle', 'Resolve Conflict')}
        </h2>
        <p className="text-sm opacity-60 mb-4">
          {conflict.entity_type} / <span className="cell-data">{conflict.entity_id}</span> — {conflict.conflict_type}
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <p className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-1">
              {t('sync.localData', 'Local')} (v{conflict.local_version})
            </p>
            <pre className="cell-data text-xs p-3 border border-[var(--divider)] overflow-auto max-h-40">
              {JSON.stringify(conflict.local_data, null, 2)}
            </pre>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-1">
              {t('sync.cloudData', 'Cloud')} (v{conflict.cloud_version})
            </p>
            <pre className="cell-data text-xs p-3 border border-[var(--divider)] overflow-auto max-h-40">
              {JSON.stringify(conflict.cloud_data, null, 2)}
            </pre>
          </div>
        </div>
        <div className="mb-6">
          <label htmlFor="sync-strategy" className="block text-[13px] opacity-60 mb-1">
            {t('sync.strategy', 'Resolution strategy')}
          </label>
          <select
            id="sync-strategy"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            className="w-full px-3 py-2 text-sm bg-transparent border border-[var(--divider)]"
          >
            {RESOLUTION_STRATEGIES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div className="flex gap-2">
          <button onClick={onClose} className="flex-1 px-4 py-2 border border-[var(--divider)] text-sm font-medium transition-colors hover:bg-[var(--hover)]">
            {t('common.cancel', 'Cancel')}
          </button>
          <button
            onClick={handleResolve}
            disabled={submitting}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors disabled:opacity-50"
          >
            {submitting ? t('common.loading', 'Loading...') : t('sync.resolve', 'Resolve')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default SyncPage
