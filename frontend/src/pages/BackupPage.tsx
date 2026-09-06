import React, { useCallback, useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { governanceOps, BackupListItem, BackupSchedulerStatus, BackupRunResult } from '@/services/governanceOps'
import { useI18n } from '@/i18n/context'
import { RefreshCw, Play, ShieldCheck, RotateCcw, Trash2 } from 'lucide-react'
import clsx from 'clsx'

const DIVIDER = 'var(--divider)'

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

  const ghostBtnCls = clsx(
    'flex items-center gap-1.5 px-3 py-2 border border-[var(--divider)] bg-transparent text-sm font-medium transition-colors hover:bg-[var(--hover)] disabled:opacity-50'
  )

  const statusItems = [
    { label: t('backup.scheduler', 'Scheduler'), value: status ? (status.enabled ? (status.running ? t('backup.running', 'Running') : t('backup.idle', 'Idle')) : t('backup.disabled', 'Disabled')) : '—' },
    { label: t('backup.cron', 'Schedule'), value: status?.schedule_cron ?? '—' },
    { label: t('backup.lastRun', 'Last run'), value: status?.last_run ? new Date(status.last_run).toLocaleString() : '—' },
    { label: t('backup.lastResult', 'Last result'), value: status?.last_success == null ? '—' : status.last_success ? '✓' : '✗' },
  ]

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
          <div className="flex items-end justify-between gap-4 flex-wrap">
            <div>
              <h1 className="page-title">{t('backup.title', 'Backup & Recovery')}</h1>
              <p className="page-subtitle">
                {t('backup.subtitle', 'Run, verify and restore data backups and Qdrant snapshots')}
              </p>
            </div>
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={handleRun}
                disabled={runBusy || status?.enabled === false}
                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
                aria-label={t('backup.runNow', 'Run backup now')}
                title={status?.enabled === false ? t('backup.disabled', 'Backup is disabled on the server') : undefined}
              >
                <Play size={16} />
                {runBusy ? t('common.loading', 'Loading...') : t('backup.runNow', 'Run backup now')}
              </button>
              <button
                onClick={handleCleanup}
                className={ghostBtnCls}
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
                className={clsx(ghostBtnCls, 'opacity-50 cursor-not-allowed')}
              >
                {t('backup.schedules', 'Schedules')} ({comingSoon})
              </button>
              <button
                onClick={load}
                disabled={isLoading}
                className={ghostBtnCls}
                aria-label={t('common.refresh', 'Refresh')}
              >
                <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
              </button>
            </div>
          </div>
        </header>

        {loadError && (
          <div role="alert" className="mb-6 border border-[#dc2626]/30 px-4 py-3 text-sm text-[#dc2626]">
            {loadError}
          </div>
        )}
        {notice && (
          <div role="status" className="mb-6 border border-[#16a34a]/30 px-4 py-3 text-sm text-[#16a34a]">
            {notice}
          </div>
        )}

        {/* Scheduler status — Dashboard-style status row, no cards */}
        <section aria-label={t('backup.title', 'Backup & Recovery')} className="mb-10">
          <dl className="flex flex-wrap gap-y-6">
            {statusItems.map((item, i) => (
              <div
                key={item.label}
                className={clsx('flex flex-col gap-2 pr-8 mr-8', i < statusItems.length - 1 && 'border-r')}
                style={i < statusItems.length - 1 ? { borderColor: DIVIDER } : undefined}
              >
                <dd className="font-data text-[16px] leading-none order-2">{item.value}</dd>
                <dt className="text-[12px] uppercase tracking-[0.06em] opacity-50 order-1">{item.label}</dt>
              </div>
            ))}
          </dl>
        </section>

        {/* Last manual run result */}
        {runResult && (
          <section className="mb-10">
            <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
              {t('backup.lastRunResult', 'Manual backup result')}
            </h2>
            <div className="row-line" style={{ padding: '14px 0' }}>
              <div className="text-sm font-medium mb-2">
                <span className="cell-data">{runResult.backup_id}</span>
                {' — '}
                <span className={runResult.success ? 'text-[#16a34a]' : 'text-[#dc2626]'}>
                  {runResult.success ? '✓' : '✗'}
                </span>
                {' '}
                <span className="cell-data opacity-60">({fmtSize(runResult.total_size_bytes)})</span>
              </div>
              <div className="space-y-1">
                {runResult.components.map((c) => (
                  <div key={c.component} className="cell-data opacity-70 flex gap-2">
                    <span className={c.success ? 'text-[#16a34a]' : 'text-[#dc2626]'}>{c.success ? '✓' : '✗'}</span>
                    <span className="font-medium">{c.component}</span>
                    <span>{fmtSize(c.size_bytes)} · {c.duration_seconds}s</span>
                    {c.error && <span className="text-[#dc2626]">{c.error}</span>}
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* Backup list — dense table, hairline dividers */}
        <section className="mb-10">
          <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
            {t('backup.list', 'Backups')} ({backups.length})
          </h2>
          {backups.length === 0 && !isLoading ? (
            <p className="empty-state">
              {t('backup.empty', 'No backups yet — run one manually to get started')}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="table-dense">
                <thead>
                  <tr>
                    <th>{t('backup.col.id', 'Backup ID')}</th>
                    <th>{t('backup.col.created', 'Created')}</th>
                    <th>{t('backup.col.size', 'Size')}</th>
                    <th>{t('backup.col.status', 'Status')}</th>
                    <th className="text-right">{t('backup.col.actions', 'Actions')}</th>
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

const BackupRow: React.FC<{
  backup: BackupListItem
  fmtSize: (n: number) => string
  onChanged: () => void
}> = ({ backup, fmtSize, onChanged }) => {
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
    <tr>
      <td>
        <div className="font-medium cell-data">{backup.backup_id}</div>
        {rowNotice && <div className="cell-data opacity-50 mt-1">{rowNotice}</div>}
      </td>
      <td className="cell-data opacity-70">{backup.created_at ? new Date(backup.created_at).toLocaleString() : '—'}</td>
      <td className="cell-data opacity-70">{fmtSize(backup.total_size_bytes)}</td>
      <td>
        <span className={clsx('badge-status', backup.success ? 'badge-success' : 'badge-danger')}>
          {backup.success ? 'success' : 'failed'}
        </span>
      </td>
      <td>
        <div className="flex gap-1 justify-end">
          <button
            onClick={handleVerify}
            disabled={busy}
            className="p-1.5 opacity-50 hover:opacity-100 transition-opacity disabled:opacity-30"
            aria-label={t('backup.verify', 'Verify')}
            title={t('backup.verify', 'Verify')}
          >
            <ShieldCheck size={15} />
          </button>
          <button
            onClick={handleRestore}
            disabled={busy || !backup.success}
            className="p-1.5 opacity-50 hover:opacity-100 transition-opacity disabled:opacity-30"
            aria-label={t('backup.restore', 'Restore')}
            title={t('backup.confirmRestore', 'Restore from this backup? Current data may be overwritten. Continue?')}
          >
            <RotateCcw size={15} />
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
  const [snapshots, setSnapshots] = useState<Array<Record<string, unknown>>>([])
  const [busy, setBusy] = useState(false)

  const inputCls = clsx(
    'px-3 py-2 border border-[var(--divider)] bg-transparent text-sm outline-none transition-colors focus:border-[var(--fg)]',
    theme === 'dark' ? 'placeholder:text-slate-500' : 'placeholder:text-slate-400'
  )
  const ghostBtnCls = clsx(
    'px-4 py-2 border border-[var(--divider)] bg-transparent text-sm font-medium transition-colors hover:bg-[var(--hover)] disabled:opacity-50'
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
      <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
        {t('backup.qdrant.title', 'Qdrant snapshots')}
      </h2>
      <div className="row-line mb-4 flex flex-wrap gap-3 items-end" style={{ padding: '14px 0' }}>
        <div>
          <label className="block text-[11px] uppercase tracking-[0.06em] opacity-50 mb-1">
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
          className="px-4 py-2 text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {t('backup.qdrant.createSnapshot', 'Create snapshot')}
        </button>
        <button
          onClick={handleList}
          disabled={busy || !collection}
          className={ghostBtnCls}
        >
          {t('backup.qdrant.listSnapshots', 'List snapshots')}
        </button>
        <button
          onClick={handleCleanup}
          disabled={busy}
          className={ghostBtnCls}
        >
          {t('backup.qdrant.cleanup', 'Cleanup old')}
        </button>
      </div>

      {snapshots.length > 0 && (
        <div className="overflow-x-auto">
          <table className="table-dense">
            <thead>
              <tr>
                <th>{t('backup.qdrant.col.name', 'Snapshot')}</th>
                <th>{t('backup.qdrant.col.created', 'Created')}</th>
                <th className="text-right">{t('backup.col.actions', 'Actions')}</th>
              </tr>
            </thead>
            <tbody>
              {snapshots.map((snapshot, index) => {
                const name = String(snapshot.name ?? snapshot.snapshot_name ?? `#${index}`)
                const created = snapshot.creation_time ?? snapshot.created_at
                return (
                  <tr key={name}>
                    <td className="font-medium cell-data">{name}</td>
                    <td className="cell-data opacity-70">{created ? new Date(String(created)).toLocaleString() : '—'}</td>
                    <td className="text-right">
                      <button
                        onClick={() => handleRestore(name)}
                        disabled={busy}
                        className="p-1.5 opacity-50 hover:opacity-100 transition-opacity disabled:opacity-30"
                        aria-label={t('backup.restore', 'Restore')}
                        title={t('backup.qdrant.confirmRestore', 'Restore this collection from the snapshot? Current vectors may be overwritten. Continue?')}
                      >
                        <RotateCcw size={15} />
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
