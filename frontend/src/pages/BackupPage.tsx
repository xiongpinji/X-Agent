import React, { useCallback, useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { governanceOps, BackupListItem, BackupSchedulerStatus, BackupRunResult } from '@/services/governanceOps'
import { useI18n } from '@/i18n/context'
import { DatabaseBackup, RefreshCw, Play, ShieldCheck, RotateCcw, Trash2, Layers } from 'lucide-react'
import clsx from 'clsx'

export const BackupPage: React.FC = () => {
  const { theme, setError } = useAppStore()
  const { t } = useI18n()
  const [backups, setBackups] = useState<BackupListItem[]>([])
  const [status, setStatus] = useState<BackupSchedulerStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [runBusy, setRunBusy] = useState(false)
  const [runResult, setRunResult] = useState<BackupRunResult | null>(null)
  const comingSoon = t('common.comingSoon', 'Coming soon')

  const load = useCallback(async () => {
    try {
      setIsLoading(true)
      setLoadError(null)
      const [list, st] = await Promise.all([
        governanceOps.listBackups(),
        governanceOps.getBackupStatus().catch(() => null),
      ])
      setBackups(list.backups)
      setStatus(st)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load backups'
      setLoadError(message)
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [setError])

  useEffect(() => {
    load()
  }, [load])

  const handleRun = async () => {
    setRunBusy(true)
    setRunResult(null)
    setLoadError(null)
    try {
      const result = await governanceOps.runBackup()
      setRunResult(result)
      await load()
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Backup run failed')
    } finally {
      setRunBusy(false)
    }
  }

  const handleCleanup = async () => {
    if (!window.confirm(t('backup.confirmCleanup', 'Delete old backups, keeping the 7 most recent?'))) return
    try {
      const result = await governanceOps.cleanupBackups(7)
      setNotice(result.message)
      await load()
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Cleanup failed')
    }
  }

  const fmtSize = (bytes: number): string => {
    if (!bytes) return '0 B'
    const units = ['B', 'KB', 'MB', 'GB']
    let value = bytes
    let unit = 0
    while (value >= 1024 && unit < units.length - 1) {
      value /= 1024
      unit += 1
    }
    return `${value.toFixed(1)} ${units[unit]}`
  }

  return (
    <div className={clsx('p-8', theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50')}>
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8 flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className={clsx('text-3xl font-bold mb-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('backup.title', 'Backup & Recovery')}
            </h1>
            <p className={clsx('text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
              {t('backup.subtitle', 'Run, verify and restore data backups and Qdrant snapshots')}
            </p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={handleRun}
              disabled={runBusy || status?.enabled === false}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
              aria-label={t('backup.runNow', 'Run backup now')}
              title={status?.enabled === false ? t('backup.disabled', 'Backup is disabled on the server') : undefined}
            >
              <Play size={16} />
              {runBusy ? t('common.loading', 'Loading...') : t('backup.runNow', 'Run backup now')}
            </button>
            <button
              onClick={handleCleanup}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100'
              )}
              aria-label={t('backup.cleanup', 'Cleanup old backups')}
            >
              <Trash2 size={16} />
              {t('backup.cleanup', 'Cleanup')}
            </button>
            {/* 备份计划 CRUD (backup.py /schedule/*) 与监控告警 (backup_monitoring.py) 未挂载 → coming soon */}
            <button
              disabled
              title={`${t('backup.schedules', 'Schedules')} (${comingSoon})`}
              aria-label={`${t('backup.schedules', 'Schedules')} (${comingSoon})`}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium opacity-50 cursor-not-allowed',
                theme === 'dark' ? 'bg-slate-800 text-slate-500' : 'bg-slate-200 text-slate-500'
              )}
            >
              {t('backup.schedules', 'Schedules')} ({comingSoon})
            </button>
            <button
              onClick={load}
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

        {loadError && (
          <div role="alert" className={clsx('mb-6 rounded-lg border px-4 py-3 text-sm', theme === 'dark' ? 'border-red-900 bg-red-950/40 text-red-300' : 'border-red-200 bg-red-50 text-red-700')}>
            {loadError}
          </div>
        )}
        {notice && (
          <div role="status" className={clsx('mb-6 rounded-lg border px-4 py-3 text-sm', theme === 'dark' ? 'border-green-900 bg-green-950/40 text-green-300' : 'border-green-200 bg-green-50 text-green-700')}>
            {notice}
          </div>
        )}

        {/* Scheduler status cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatusCard theme={theme} label={t('backup.scheduler', 'Scheduler')} value={status ? (status.enabled ? (status.running ? t('backup.running', 'Running') : t('backup.idle', 'Idle')) : t('backup.disabled', 'Disabled')) : '—'} />
          <StatusCard theme={theme} label={t('backup.cron', 'Schedule')} value={status?.schedule_cron ?? '—'} small />
          <StatusCard theme={theme} label={t('backup.lastRun', 'Last run')} value={status?.last_run ? new Date(status.last_run).toLocaleString() : '—'} small />
          <StatusCard theme={theme} label={t('backup.lastResult', 'Last result')} value={status?.last_success == null ? '—' : status.last_success ? '✓' : '✗'} />
        </div>

        {/* Last manual run result */}
        {runResult && (
          <div className={clsx('mb-8 rounded-lg border p-4', theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200')}>
            <div className={clsx('text-sm font-semibold mb-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('backup.lastRunResult', 'Manual backup result')}: {runResult.backup_id} — {runResult.success ? '✓' : '✗'} ({fmtSize(runResult.total_size_bytes)})
            </div>
            <div className="space-y-1">
              {runResult.components.map((c) => (
                <div key={c.component} className={clsx('text-xs flex gap-2', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
                  <span className={c.success ? 'text-green-500' : 'text-red-500'}>{c.success ? '✓' : '✗'}</span>
                  <span className="font-medium">{c.component}</span>
                  <span>{fmtSize(c.size_bytes)} · {c.duration_seconds}s</span>
                  {c.error && <span className="text-red-500">{c.error}</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Backup list */}
        <section className="mb-10">
          <h2 className={clsx('text-lg font-semibold mb-4 flex items-center gap-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
            <DatabaseBackup size={18} />
            {t('backup.list', 'Backups')} ({backups.length})
          </h2>
          {backups.length === 0 && !isLoading ? (
            <div className={clsx('text-center py-10 rounded-lg border', theme === 'dark' ? 'border-slate-800 text-slate-400' : 'border-slate-200 text-slate-500 bg-white')}>
              {t('backup.empty', 'No backups yet — run one manually to get started')}
            </div>
          ) : (
            <div className={clsx('rounded-lg border overflow-hidden', theme === 'dark' ? 'border-slate-800' : 'border-slate-200 bg-white')}>
              <table className="w-full text-sm">
                <thead className={theme === 'dark' ? 'bg-slate-900 text-slate-400' : 'bg-slate-50 text-slate-600'}>
                  <tr>
                    <th className="text-left px-4 py-3 font-medium">{t('backup.col.id', 'Backup ID')}</th>
                    <th className="text-left px-4 py-3 font-medium">{t('backup.col.created', 'Created')}</th>
                    <th className="text-left px-4 py-3 font-medium">{t('backup.col.size', 'Size')}</th>
                    <th className="text-left px-4 py-3 font-medium">{t('backup.col.status', 'Status')}</th>
                    <th className="text-right px-4 py-3 font-medium">{t('backup.col.actions', 'Actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {backups.map((backup) => (
                    <BackupRow key={backup.backup_id} backup={backup} fmtSize={fmtSize} onChanged={load} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Qdrant snapshots */}
        <QdrantSection onError={setLoadError} onNotice={setNotice} />
      </div>
    </div>
  )
}

const StatusCard: React.FC<{ theme: string; label: string; value: string; small?: boolean }> = ({ theme, label, value, small }) => (
  <div className={clsx('rounded-lg border p-4', theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200')}>
    <div className={clsx('text-xs mb-1', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>{label}</div>
    <div className={clsx(small ? 'text-sm font-semibold' : 'text-xl font-bold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>{value}</div>
  </div>
)

const BackupRow: React.FC<{
  backup: BackupListItem
  fmtSize: (n: number) => string
  onChanged: () => void
}> = ({ backup, fmtSize, onChanged }) => {
  const { theme } = useAppStore()
  const { t } = useI18n()
  const [busy, setBusy] = useState(false)
  const [rowNotice, setRowNotice] = useState<string | null>(null)

  const handleVerify = async () => {
    setBusy(true)
    setRowNotice(null)
    try {
      const result = await governanceOps.verifyBackup(backup.backup_id)
      setRowNotice(`${result.valid ? '✓' : '✗'} ${result.message}`)
    } catch (error) {
      setRowNotice(error instanceof Error ? error.message : 'Verify failed')
    } finally {
      setBusy(false)
    }
  }

  const handleRestore = async () => {
    // 恢复是不可逆操作, 二次确认
    const confirmed = window.confirm(
      t('backup.confirmRestore', 'Restore from this backup? Current data may be overwritten. Continue?')
    )
    if (!confirmed) return
    setBusy(true)
    setRowNotice(null)
    try {
      const result = await governanceOps.restoreBackup(backup.backup_id)
      setRowNotice(`${result.success ? '✓' : '✗'} ${result.message}`)
      onChanged()
    } catch (error) {
      setRowNotice(error instanceof Error ? error.message : 'Restore failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <tr className={clsx('border-t', theme === 'dark' ? 'border-slate-800 text-slate-300' : 'border-slate-100 text-slate-700')}>
      <td className="px-4 py-3">
        <div className="font-medium">{backup.backup_id}</div>
        {rowNotice && <div className={clsx('text-xs mt-1', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>{rowNotice}</div>}
      </td>
      <td className="px-4 py-3">{backup.created_at ? new Date(backup.created_at).toLocaleString() : '—'}</td>
      <td className="px-4 py-3">{fmtSize(backup.total_size_bytes)}</td>
      <td className="px-4 py-3">
        <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium', backup.success ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-red-500/10 text-red-600 dark:text-red-400')}>
          {backup.success ? 'success' : 'failed'}
        </span>
      </td>
      <td className="px-4 py-3">
        <div className="flex gap-2 justify-end">
          <button
            onClick={handleVerify}
            disabled={busy}
            className={clsx(
              'flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors disabled:opacity-50',
              theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            )}
            aria-label={t('backup.verify', 'Verify')}
          >
            <ShieldCheck size={14} />
            {t('backup.verify', 'Verify')}
          </button>
          <button
            onClick={handleRestore}
            disabled={busy || !backup.success}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium bg-amber-600 text-white hover:bg-amber-700 transition-colors disabled:opacity-50"
            aria-label={t('backup.restore', 'Restore')}
            title={t('backup.confirmRestore', 'Restore from this backup? Current data may be overwritten. Continue?')}
          >
            <RotateCcw size={14} />
            {t('backup.restore', 'Restore')}
          </button>
        </div>
      </td>
    </tr>
  )
}

const QdrantSection: React.FC<{ onError: (msg: string | null) => void; onNotice: (msg: string | null) => void }> = ({ onError, onNotice }) => {
  const { theme } = useAppStore()
  const { t } = useI18n()
  const [collection, setCollection] = useState('')
  const [snapshots, setSnapshots] = useState<Array<Record<string, any>>>([])
  const [busy, setBusy] = useState(false)

  const inputCls = clsx(
    'px-3 py-2 rounded-lg text-sm border outline-none',
    theme === 'dark' ? 'bg-slate-950 border-slate-700 text-white placeholder-slate-500' : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400'
  )

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    onError(null)
    try {
      await fn()
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Qdrant operation failed')
    } finally {
      setBusy(false)
    }
  }

  const handleList = () => run(async () => {
    if (!collection) return
    const result = await governanceOps.listQdrantSnapshots(collection)
    setSnapshots(result.snapshots)
  })

  const handleSnapshot = () => run(async () => {
    const result = await governanceOps.createQdrantSnapshot(collection || undefined)
    onNotice(`${t('backup.qdrant.snapshotCreated', 'Snapshot created')}: ${JSON.stringify(result).slice(0, 200)}`)
    if (collection) await handleList()
  })

  const handleCleanup = () => run(async () => {
    const result = await governanceOps.cleanupQdrantSnapshots()
    onNotice(result.message)
    if (collection) await handleList()
  })

  const handleRestore = (snapshotName: string) => run(async () => {
    // 恢复是不可逆操作, 二次确认
    if (!window.confirm(t('backup.qdrant.confirmRestore', 'Restore this collection from the snapshot? Current vectors may be overwritten. Continue?'))) return
    const result = await governanceOps.restoreQdrantSnapshot(collection, snapshotName)
    onNotice(String(result.message ?? 'Restore requested'))
  })

  return (
    <section>
      <h2 className={clsx('text-lg font-semibold mb-4 flex items-center gap-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
        <Layers size={18} />
        {t('backup.qdrant.title', 'Qdrant snapshots')}
      </h2>
      <div className={clsx('rounded-lg border p-4 mb-4 flex flex-wrap gap-3 items-end', theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200')}>
        <div>
          <label className={clsx('block text-xs mb-1', theme === 'dark' ? 'text-slate-400' : 'text-slate-500')}>
            {t('backup.qdrant.collection', 'Collection name')}
          </label>
          <input
            className={inputCls}
            value={collection}
            onChange={(e) => setCollection(e.target.value)}
            placeholder={t('backup.qdrant.collectionPlaceholder', 'empty = all collections')}
          />
        </div>
        <button
          onClick={handleSnapshot}
          disabled={busy}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {t('backup.qdrant.createSnapshot', 'Create snapshot')}
        </button>
        <button
          onClick={handleList}
          disabled={busy || !collection}
          className={clsx(
            'px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
            theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          )}
        >
          {t('backup.qdrant.listSnapshots', 'List snapshots')}
        </button>
        <button
          onClick={handleCleanup}
          disabled={busy}
          className={clsx(
            'px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
            theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          )}
        >
          {t('backup.qdrant.cleanup', 'Cleanup old')}
        </button>
      </div>

      {snapshots.length > 0 && (
        <div className={clsx('rounded-lg border overflow-hidden', theme === 'dark' ? 'border-slate-800' : 'border-slate-200 bg-white')}>
          <table className="w-full text-sm">
            <thead className={theme === 'dark' ? 'bg-slate-900 text-slate-400' : 'bg-slate-50 text-slate-600'}>
              <tr>
                <th className="text-left px-4 py-3 font-medium">{t('backup.qdrant.col.name', 'Snapshot')}</th>
                <th className="text-left px-4 py-3 font-medium">{t('backup.qdrant.col.created', 'Created')}</th>
                <th className="text-right px-4 py-3 font-medium">{t('backup.col.actions', 'Actions')}</th>
              </tr>
            </thead>
            <tbody>
              {snapshots.map((snapshot, index) => {
                const name = String(snapshot.name ?? snapshot.snapshot_name ?? `#${index}`)
                const created = snapshot.creation_time ?? snapshot.created_at
                return (
                  <tr key={name} className={clsx('border-t', theme === 'dark' ? 'border-slate-800 text-slate-300' : 'border-slate-100 text-slate-700')}>
                    <td className="px-4 py-3 font-medium">{name}</td>
                    <td className="px-4 py-3">{created ? new Date(String(created)).toLocaleString() : '—'}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleRestore(name)}
                        disabled={busy}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium bg-amber-600 text-white hover:bg-amber-700 transition-colors disabled:opacity-50"
                        aria-label={t('backup.restore', 'Restore')}
                      >
                        <RotateCcw size={14} />
                        {t('backup.restore', 'Restore')}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

export default BackupPage
