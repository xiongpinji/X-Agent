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
  AlertTriangle,
  CheckCircle,
  Clock,
  Wifi,
  WifiOff,
  Activity,
  X,
} from 'lucide-react'
import clsx from 'clsx'

const RESOLUTION_STRATEGIES = ['local_wins', 'cloud_wins', 'merge', 'manual']

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

  const healthColor = (status?: string) =>
    status === 'healthy' ? 'text-green-600' :
    status === 'degraded' ? 'text-amber-600' :
    status ? 'text-red-600' : 'text-slate-500'

  const statusBadge = (status: string) =>
    clsx(
      'px-2 py-0.5 rounded-full text-xs font-medium capitalize',
      status === 'completed' || status === 'success' ? 'bg-green-100 text-green-700' :
      status === 'failed' || status === 'error' ? 'bg-red-100 text-red-700' :
      status === 'pending' || status === 'running' ? 'bg-blue-100 text-blue-700' :
      'bg-slate-100 text-slate-600',
    )

  return (
    <div className={clsx('p-8', isDark ? 'bg-slate-950' : 'bg-slate-50')}>
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className={clsx('text-3xl font-bold mb-2', isDark ? 'text-white' : 'text-slate-900')}>
              {t('sync.title', 'Sync Center')}
            </h1>
            <p className={clsx('text-sm', isDark ? 'text-slate-400' : 'text-slate-600')}>
              {t('sync.subtitle', 'Local-cloud synchronization status, queue, conflicts and history')}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setShowEnqueue(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
            >
              <Plus size={18} />
              {t('sync.enqueue', 'Enqueue')}
            </button>
            <button
              onClick={handleTrigger}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors',
                isDark ? 'bg-slate-800 hover:bg-slate-700 text-white' : 'bg-white hover:bg-slate-100 text-slate-900 border border-slate-300',
              )}
            >
              <RefreshCw size={18} />
              {t('sync.trigger', 'Trigger Sync')}
            </button>
            {/* Offline toggle requires sync:admin scope + cloud connection — coming soon */}
            <button
              disabled
              title={t('sync.offlineComingSoon', 'Offline toggle requires cloud connection (coming soon)')}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 rounded-lg font-medium opacity-50 cursor-not-allowed',
                isDark ? 'bg-slate-800 text-slate-400' : 'bg-slate-200 text-slate-500',
              )}
            >
              {offline?.enabled ? <WifiOff size={18} /> : <Wifi size={18} />}
              {t('sync.offlineMode', 'Offline Mode')}
              <span className="text-xs">({t('common.comingSoon', 'coming soon')})</span>
            </button>
          </div>
        </div>

        {loadError && (
          <div className={clsx(
            'mb-6 p-4 rounded-lg text-sm',
            isDark ? 'bg-red-900/30 text-red-300' : 'bg-red-50 text-red-700',
          )}>
            {loadError}
          </div>
        )}

        {/* Status cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          <StatCard dark={isDark} icon={<Activity size={18} />} label={t('sync.health', 'Health')}
            value={health ? `${health.health_score}` : '—'} valueClass={healthColor(health?.status)} />
          <StatCard dark={isDark} icon={<Clock size={18} />} label={t('sync.pending', 'Pending')}
            value={stats ? String(stats.pending_syncs) : '—'} />
          <StatCard dark={isDark} icon={<AlertTriangle size={18} />} label={t('sync.failed', 'Failed')}
            value={stats ? String(stats.failed_syncs) : '—'}
            valueClass={stats && stats.failed_syncs > 0 ? 'text-red-600' : undefined} />
          <StatCard dark={isDark} icon={<AlertTriangle size={18} />} label={t('sync.conflicts', 'Conflicts')}
            value={stats ? String(stats.unresolved_conflicts) : '—'}
            valueClass={stats && stats.unresolved_conflicts > 0 ? 'text-amber-600' : undefined} />
          <StatCard dark={isDark} icon={<WifiOff size={18} />} label={t('sync.offlineOps', 'Offline Ops')}
            value={stats ? String(stats.offline_operations) : '—'} />
          <StatCard dark={isDark} icon={<CheckCircle size={18} />} label={t('sync.dbSize', 'DB Size (MB)')}
            value={stats ? stats.database_size_mb.toFixed(2) : '—'} />
        </div>

        {/* Conflicts */}
        <section className={clsx(
          'rounded-lg mb-8 overflow-hidden',
          isDark ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200',
        )}>
          <header className={clsx(
            'px-6 py-4 border-b flex items-center justify-between',
            isDark ? 'border-slate-700' : 'border-slate-200',
          )}>
            <h2 className={clsx('text-lg font-semibold', isDark ? 'text-white' : 'text-slate-900')}>
              {t('sync.conflictList', 'Unresolved Conflicts')} ({conflicts.length})
            </h2>
          </header>
          {conflicts.length === 0 ? (
            <p className={clsx('p-6 text-sm', isDark ? 'text-slate-400' : 'text-slate-500')}>
              {t('sync.noConflicts', 'No unresolved conflicts')}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className={clsx(isDark ? 'bg-slate-800' : 'bg-slate-50')}>
                  <tr>
                    {[t('sync.entity', 'Entity'), t('sync.conflictType', 'Type'),
                      t('sync.localVersion', 'Local v'), t('sync.cloudVersion', 'Cloud v'),
                      t('common.actions', 'Actions')].map((h, i) => (
                      <th key={i} className={clsx(
                        'px-6 py-3 text-left text-sm font-semibold',
                        isDark ? 'text-slate-300' : 'text-slate-900',
                      )}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {conflicts.map((c) => (
                    <tr key={c.id} className={clsx(
                      'border-b',
                      isDark ? 'border-slate-700 hover:bg-slate-800' : 'border-slate-200 hover:bg-slate-50',
                    )}>
                      <td className={clsx('px-6 py-3 text-sm', isDark ? 'text-white' : 'text-slate-900')}>
                        {c.entity_type} / {c.entity_id}
                      </td>
                      <td className={clsx('px-6 py-3 text-sm', isDark ? 'text-slate-300' : 'text-slate-600')}>
                        {c.conflict_type}
                      </td>
                      <td className={clsx('px-6 py-3 text-sm', isDark ? 'text-slate-300' : 'text-slate-600')}>
                        {c.local_version}
                      </td>
                      <td className={clsx('px-6 py-3 text-sm', isDark ? 'text-slate-300' : 'text-slate-600')}>
                        {c.cloud_version}
                      </td>
                      <td className="px-6 py-3">
                        <button
                          onClick={() => setResolving(c)}
                          className="px-3 py-1 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
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

        {/* History */}
        <section className={clsx(
          'rounded-lg overflow-hidden',
          isDark ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200',
        )}>
          <header className={clsx(
            'px-6 py-4 border-b',
            isDark ? 'border-slate-700' : 'border-slate-200',
          )}>
            <h2 className={clsx('text-lg font-semibold', isDark ? 'text-white' : 'text-slate-900')}>
              {t('sync.history', 'Sync History')} ({history.length})
            </h2>
          </header>
          {history.length === 0 ? (
            <p className={clsx('p-6 text-sm', isDark ? 'text-slate-400' : 'text-slate-500')}>
              {t('sync.noHistory', 'No sync history yet')}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className={clsx(isDark ? 'bg-slate-800' : 'bg-slate-50')}>
                  <tr>
                    {[t('sync.batch', 'Batch'), t('sync.entity', 'Entity'), t('sync.operation', 'Op'),
                      t('sync.direction', 'Direction'), t('tasks.status', 'Status'),
                      t('sync.duration', 'Duration (ms)'), t('tasks.createdAt', 'Created')].map((h, i) => (
                      <th key={i} className={clsx(
                        'px-6 py-3 text-left text-sm font-semibold whitespace-nowrap',
                        isDark ? 'text-slate-300' : 'text-slate-900',
                      )}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {history.map((h) => (
                    <tr key={h.id} className={clsx(
                      'border-b',
                      isDark ? 'border-slate-700 hover:bg-slate-800' : 'border-slate-200 hover:bg-slate-50',
                    )}>
                      <td className={clsx('px-6 py-3 text-xs font-mono', isDark ? 'text-slate-400' : 'text-slate-500')}>
                        {h.sync_batch_id.slice(0, 8)}
                      </td>
                      <td className={clsx('px-6 py-3 text-sm', isDark ? 'text-white' : 'text-slate-900')}>
                        {h.entity_type} / {h.entity_id}
                      </td>
                      <td className={clsx('px-6 py-3 text-sm', isDark ? 'text-slate-300' : 'text-slate-600')}>
                        {h.operation}
                      </td>
                      <td className={clsx('px-6 py-3 text-sm', isDark ? 'text-slate-300' : 'text-slate-600')}>
                        {h.direction}
                      </td>
                      <td className="px-6 py-3"><span className={statusBadge(h.status)}>{h.status}</span></td>
                      <td className={clsx('px-6 py-3 text-sm', isDark ? 'text-slate-300' : 'text-slate-600')}>
                        {h.duration_ms}
                      </td>
                      <td className={clsx('px-6 py-3 text-sm whitespace-nowrap', isDark ? 'text-slate-400' : 'text-slate-600')}>
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

interface StatCardProps {
  dark: boolean
  icon: React.ReactNode
  label: string
  value: string
  valueClass?: string
}

const StatCard: React.FC<StatCardProps> = ({ dark, icon, label, value, valueClass }) => (
  <div className={clsx(
    'rounded-lg p-4',
    dark ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200',
  )}>
    <div className={clsx('flex items-center gap-2 mb-2', dark ? 'text-slate-400' : 'text-slate-500')}>
      {icon}
      <span className="text-xs font-medium">{label}</span>
    </div>
    <p className={clsx('text-xl font-bold', valueClass ?? (dark ? 'text-white' : 'text-slate-900'))}>
      {value}
    </p>
  </div>
)

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

  const inputCls = clsx(
    'w-full px-3 py-2 rounded-lg text-sm',
    dark ? 'bg-slate-800 text-white border border-slate-700' : 'bg-slate-50 text-slate-900 border border-slate-300',
  )
  const labelCls = clsx('block text-sm font-medium mb-1', dark ? 'text-slate-300' : 'text-slate-700')

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" role="dialog" aria-modal="true">
      <div className={clsx('rounded-lg p-6 max-w-md w-full mx-4', dark ? 'bg-slate-900' : 'bg-white')}>
        <div className="flex items-center justify-between mb-4">
          <h2 className={clsx('text-xl font-bold', dark ? 'text-white' : 'text-slate-900')}>
            {t('sync.enqueueTitle', 'Enqueue Sync Operation')}
          </h2>
          <button onClick={onClose} aria-label={t('common.close', 'Close')}
            className={dark ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-900'}>
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
          <button onClick={onClose} className={clsx(
            'flex-1 px-4 py-2 rounded-lg font-medium transition-colors',
            dark ? 'bg-slate-700 hover:bg-slate-600 text-white' : 'bg-slate-200 hover:bg-slate-300 text-slate-900',
          )}>
            {t('common.cancel', 'Cancel')}
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting || !entityType.trim() || !entityId.trim()}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
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
      <div className={clsx('rounded-lg p-6 max-w-lg w-full mx-4', dark ? 'bg-slate-900' : 'bg-white')}>
        <h2 className={clsx('text-xl font-bold mb-4', dark ? 'text-white' : 'text-slate-900')}>
          {t('sync.resolveTitle', 'Resolve Conflict')}
        </h2>
        <p className={clsx('text-sm mb-4', dark ? 'text-slate-400' : 'text-slate-600')}>
          {conflict.entity_type} / {conflict.entity_id} — {conflict.conflict_type}
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <p className={clsx('text-xs font-semibold mb-1', dark ? 'text-slate-400' : 'text-slate-500')}>
              {t('sync.localData', 'Local')} (v{conflict.local_version})
            </p>
            <pre className={clsx(
              'text-xs p-3 rounded-lg overflow-auto max-h-40',
              dark ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-700',
            )}>
              {JSON.stringify(conflict.local_data, null, 2)}
            </pre>
          </div>
          <div>
            <p className={clsx('text-xs font-semibold mb-1', dark ? 'text-slate-400' : 'text-slate-500')}>
              {t('sync.cloudData', 'Cloud')} (v{conflict.cloud_version})
            </p>
            <pre className={clsx(
              'text-xs p-3 rounded-lg overflow-auto max-h-40',
              dark ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-700',
            )}>
              {JSON.stringify(conflict.cloud_data, null, 2)}
            </pre>
          </div>
        </div>
        <div className="mb-6">
          <label htmlFor="sync-strategy" className={clsx(
            'block text-sm font-medium mb-1', dark ? 'text-slate-300' : 'text-slate-700',
          )}>
            {t('sync.strategy', 'Resolution strategy')}
          </label>
          <select
            id="sync-strategy"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            className={clsx(
              'w-full px-3 py-2 rounded-lg text-sm',
              dark ? 'bg-slate-800 text-white border border-slate-700' : 'bg-slate-50 text-slate-900 border border-slate-300',
            )}
          >
            {RESOLUTION_STRATEGIES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div className="flex gap-2">
          <button onClick={onClose} className={clsx(
            'flex-1 px-4 py-2 rounded-lg font-medium transition-colors',
            dark ? 'bg-slate-700 hover:bg-slate-600 text-white' : 'bg-slate-200 hover:bg-slate-300 text-slate-900',
          )}>
            {t('common.cancel', 'Cancel')}
          </button>
          <button
            onClick={handleResolve}
            disabled={submitting}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {submitting ? t('common.loading', 'Loading...') : t('sync.resolve', 'Resolve')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default SyncPage
