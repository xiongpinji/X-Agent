import React, { useCallback, useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { useI18n } from '@/i18n/context'
import { syncOps, WorkSession } from '@/services/syncOps'
import {
  Plus,
  Play,
  Pause,
  StepForward,
  Eye,
  RefreshCw,
  ArchiveRestore,
  X,
} from 'lucide-react'
import clsx from 'clsx'

const DIVIDER = 'var(--divider)'

const SESSION_BADGE: Record<string, string> = {
  active: 'badge-success',
  paused: 'badge-warning',
  completed: 'badge-muted',
  failed: 'badge-danger',
  timeout: 'badge-danger',
}

const MILESTONE_BADGE: Record<string, string> = {
  completed: 'badge-success',
  running: 'badge-muted',
  failed: 'badge-danger',
}

const WorkSessionsPage: React.FC = () => {
  const { theme, setLoading, setError } = useAppStore()
  const { t } = useI18n()
  const isDark = theme === 'dark'

  const [sessions, setSessions] = useState<WorkSession[]>([])
  const [selected, setSelected] = useState<WorkSession | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const loadSessions = useCallback(async () => {
    try {
      setLoading(true)
      setLoadError(null)
      const list = await syncOps.listWorkSessions()
      setSessions(list)
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to load work sessions'
      setLoadError(msg)
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [setLoading, setError])

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  const runAction = async (
    sessionId: string,
    action: (id: string) => Promise<WorkSession>,
  ) => {
    try {
      setBusyId(sessionId)
      const updated = await action(sessionId)
      setSessions((prev) => prev.map((s) => (s.session_id === sessionId ? updated : s)))
      if (selected?.session_id === sessionId) setSelected(updated)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Session action failed')
    } finally {
      setBusyId(null)
    }
  }

  const openDetail = async (sessionId: string) => {
    try {
      const detail = await syncOps.getWorkSession(sessionId)
      setSelected(detail)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load session detail')
    }
  }

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
          <div className="flex items-end justify-between gap-4">
            <div>
              <h1 className="page-title">{t('workSessions.title', 'Work Sessions')}</h1>
              <p className="page-subtitle">
                {t('workSessions.subtitle', 'Long-running cross-app work sessions with milestones')}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={loadSessions}
                className={clsx(
                  'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  isDark ? 'bg-slate-800 hover:bg-slate-700 text-slate-300' : 'bg-white hover:bg-slate-100 text-slate-700 border border-slate-200',
                )}
                aria-label={t('common.refresh', 'Refresh')}
              >
                <RefreshCw size={16} />
                {t('common.refresh', 'Refresh')}
              </button>
              <button
                onClick={() => setShowCreate(true)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <Plus size={16} />
                {t('workSessions.newSession', 'New Session')}
              </button>
            </div>
          </div>
        </header>

        {loadError && (
          <div role="alert" className="mb-6 rounded-lg border border-[#dc2626]/30 px-4 py-3 text-sm text-[#dc2626]">
            {loadError}
          </div>
        )}

        {/* Sessions table — dense, hairline dividers */}
        <section className="mb-10">
          {sessions.length === 0 ? (
            <p className="empty-state">
              {t('workSessions.none', 'No work sessions yet')} · {t('workSessions.createHint', 'Create a session to start a long-running goal')}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="table-dense">
                <thead>
                  <tr>
                    <th>{t('workSessions.goal', 'Goal')}</th>
                    <th>{t('tasks.status', 'Status')}</th>
                    <th>{t('workSessions.milestones', 'Milestones')}</th>
                    <th>{t('workSessions.tokens', 'Tokens')}</th>
                    <th>{t('workSessions.started', 'Started')}</th>
                    <th>{t('common.actions', 'Actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr key={s.session_id}>
                      <td className="font-medium max-w-xs truncate" title={s.goal}>
                        {s.goal}
                      </td>
                      <td>
                        <span className={clsx('badge-status', SESSION_BADGE[s.status] ?? 'badge-muted')}>
                          {s.status}
                        </span>
                      </td>
                      <td className="cell-data opacity-70">
                        {s.current_milestone_index}/{s.milestones.length}
                      </td>
                      <td className="cell-data opacity-70">
                        {s.total_tokens_used}
                      </td>
                      <td className="cell-data opacity-70 whitespace-nowrap">
                        {new Date(s.started_at).toLocaleString()}
                      </td>
                      <td>
                        <div className="flex items-center gap-1">
                          <IconBtn title={t('workSessions.view', 'View details')}
                            onClick={() => openDetail(s.session_id)}>
                            <Eye size={15} />
                          </IconBtn>
                          {(s.status === 'active') && (
                            <>
                              <IconBtn title={t('workSessions.pause', 'Pause')}
                                disabled={busyId === s.session_id}
                                onClick={() => runAction(s.session_id, syncOps.pauseWorkSession.bind(syncOps))}>
                                <Pause size={15} />
                              </IconBtn>
                              <IconBtn title={t('workSessions.tick', 'Tick (advance milestone)')}
                                disabled={busyId === s.session_id}
                                onClick={() => runAction(s.session_id, syncOps.tickWorkSession.bind(syncOps))}>
                                <StepForward size={15} />
                              </IconBtn>
                            </>
                          )}
                          {(s.status === 'paused' || s.status === 'timeout') && (
                            <IconBtn title={t('workSessions.resume', 'Resume')}
                              disabled={busyId === s.session_id}
                              onClick={() => runAction(s.session_id, syncOps.resumeWorkSession.bind(syncOps))}>
                              <Play size={15} />
                            </IconBtn>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Context-session storage restore entry — /api/sessions mounted but the
            backend never injects ContextManager (set_context_manager uncalled),
            so it returns 500 at runtime. Render as coming soon, no fake calls. */}
        <section className="row-line" style={{ padding: '16px 0' }}>
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-1">
                {t('workSessions.storageRestore', 'Session Storage Restore')}
              </h2>
              <p className="text-[13px] opacity-60">
                {t('workSessions.storageRestoreHint',
                  'Restore saved context sessions from storage (/api/sessions). Backend context manager injection pending.')}
              </p>
            </div>
            <button
              disabled
              title={t('common.comingSoon', 'coming soon')}
              className={clsx(
                'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium opacity-50 cursor-not-allowed',
                isDark ? 'bg-slate-800 text-slate-400' : 'bg-white border border-slate-200 text-slate-500',
              )}
            >
              <ArchiveRestore size={16} />
              {t('workSessions.restore', 'Restore Session')}
              <span className="text-xs">({t('common.comingSoon', 'coming soon')})</span>
            </button>
          </div>
        </section>
      </div>

      {showCreate && (
        <CreateSessionModal
          dark={isDark}
          onClose={() => setShowCreate(false)}
          onCreated={(s) => {
            setShowCreate(false)
            setSessions((prev) => [s, ...prev])
          }}
        />
      )}
      {selected && (
        <SessionDetailModal dark={isDark} session={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}

interface IconBtnProps {
  title: string
  disabled?: boolean
  onClick: () => void
  children: React.ReactNode
}

const IconBtn: React.FC<IconBtnProps> = ({ title, disabled, onClick, children }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    title={title}
    aria-label={title}
    className="p-1.5 opacity-50 hover:opacity-100 transition-opacity disabled:opacity-30"
  >
    {children}
  </button>
)

interface CreateSessionModalProps {
  dark: boolean
  onClose: () => void
  onCreated: (s: WorkSession) => void
}

const CreateSessionModal: React.FC<CreateSessionModalProps> = ({ dark, onClose, onCreated }) => {
  const { t } = useI18n()
  const { setError } = useAppStore()
  const [goal, setGoal] = useState('')
  const [maxHours, setMaxHours] = useState(8)
  const [maxMilestones, setMaxMilestones] = useState(6)
  const [submitting, setSubmitting] = useState(false)

  const handleCreate = async () => {
    try {
      setSubmitting(true)
      const session = await syncOps.startWorkSession({
        goal,
        max_hours: maxHours,
        max_milestones: maxMilestones,
      })
      onCreated(session)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to create session')
    } finally {
      setSubmitting(false)
    }
  }

  const inputCls = clsx(
    'w-full px-3 py-2 rounded-lg text-sm',
    dark ? 'bg-slate-800 text-white border border-slate-700' : 'bg-slate-50 text-slate-900 border border-slate-300',
  )
  const labelCls = 'block text-[13px] opacity-60 mb-1'

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" role="dialog" aria-modal="true">
      <div className={clsx('rounded-lg p-6 max-w-md w-full mx-4 border', dark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200')}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium">
            {t('workSessions.newSession', 'New Work Session')}
          </h2>
          <button onClick={onClose} aria-label={t('common.close', 'Close')}
            className="opacity-50 hover:opacity-100 transition-opacity">
            <X size={20} />
          </button>
        </div>
        <div className="space-y-4 mb-6">
          <div>
            <label htmlFor="ws-goal" className={labelCls}>{t('workSessions.goal', 'Goal')}</label>
            <textarea id="ws-goal" className={inputCls} rows={3} value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder={t('workSessions.goalPlaceholder', 'Describe the long-running goal...')} />
          </div>
          <div>
            <label htmlFor="ws-hours" className={labelCls}>{t('workSessions.maxHours', 'Max hours (0.5–72)')}</label>
            <input id="ws-hours" type="number" min={0.5} max={72} step={0.5} className={inputCls}
              value={maxHours} onChange={(e) => setMaxHours(Number(e.target.value))} />
          </div>
          <div>
            <label htmlFor="ws-milestones" className={labelCls}>{t('workSessions.maxMilestones', 'Max milestones (1–20)')}</label>
            <input id="ws-milestones" type="number" min={1} max={20} className={inputCls}
              value={maxMilestones} onChange={(e) => setMaxMilestones(Number(e.target.value))} />
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={onClose} className={clsx(
            'flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
            dark ? 'bg-slate-700 hover:bg-slate-600 text-white' : 'bg-slate-200 hover:bg-slate-300 text-slate-900',
          )}>
            {t('common.cancel', 'Cancel')}
          </button>
          <button
            onClick={handleCreate}
            disabled={submitting || !goal.trim()}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            {submitting ? t('common.loading', 'Loading...') : t('common.create', 'Create')}
          </button>
        </div>
      </div>
    </div>
  )
}

interface SessionDetailModalProps {
  dark: boolean
  session: WorkSession
  onClose: () => void
}

const SessionDetailModal: React.FC<SessionDetailModalProps> = ({ dark, session, onClose }) => {
  const { t } = useI18n()

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" role="dialog" aria-modal="true">
      <div className={clsx(
        'rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[85vh] overflow-y-auto border',
        dark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200',
      )}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium">
            {t('workSessions.detail', 'Session Detail')}
          </h2>
          <button onClick={onClose} aria-label={t('common.close', 'Close')}
            className="opacity-50 hover:opacity-100 transition-opacity">
            <X size={20} />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <p className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-1">
              {t('workSessions.goal', 'Goal')}
            </p>
            <p className="text-sm">{session.goal}</p>
          </div>

          <div className="font-data text-[13px]">
            <div className="flex items-baseline justify-between gap-4 py-2 border-b" style={{ borderColor: DIVIDER }}>
              <span className="opacity-50">{t('tasks.status', 'Status')}</span>
              <span className={clsx('badge-status', SESSION_BADGE[session.status] ?? 'badge-muted')}>{session.status}</span>
            </div>
            <div className="flex items-baseline justify-between gap-4 py-2 border-b" style={{ borderColor: DIVIDER }}>
              <span className="opacity-50">{t('workSessions.tokens', 'Tokens')}</span>
              <span className="tabular-nums">{session.total_tokens_used}</span>
            </div>
            <div className="flex items-baseline justify-between gap-4 py-2 border-b" style={{ borderColor: DIVIDER }}>
              <span className="opacity-50">{t('workSessions.maxHours', 'Max hours')}</span>
              <span className="tabular-nums">{session.max_duration_hours}</span>
            </div>
            <div className="flex items-baseline justify-between gap-4 py-2 border-b" style={{ borderColor: DIVIDER }}>
              <span className="opacity-50">{t('workSessions.started', 'Started')}</span>
              <span className="tabular-nums">{new Date(session.started_at).toLocaleString()}</span>
            </div>
          </div>

          <div>
            <p className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2">
              {t('workSessions.milestones', 'Milestones')} ({session.milestones.length})
            </p>
            <div>
              {session.milestones.map((m) => (
                <div key={m.index} className="row-line">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="font-medium text-sm">
                      {m.index + 1}. {m.title}
                    </span>
                    <span className={clsx('badge-status', MILESTONE_BADGE[m.status] ?? 'badge-muted')}>{m.status}</span>
                  </div>
                  {m.output && (
                    <p className="text-xs opacity-60 line-clamp-2">
                      {m.output}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {session.artifacts.length > 0 && (
            <div>
              <p className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2">
                {t('workSessions.artifacts', 'Artifacts')} ({session.artifacts.length})
              </p>
              <div>
                {session.artifacts.map((a) => (
                  <div key={a.artifact_id} className="row-line text-sm">
                    {a.name} <span className="cell-data opacity-50">({a.type})</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <p className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-1">
              {t('workSessions.contextSnapshot', 'Context Snapshot')}
            </p>
            <pre className={clsx(
              'cell-data text-xs p-3 rounded-lg overflow-auto max-h-48',
              dark ? 'bg-slate-800' : 'bg-slate-50',
            )}>
              {JSON.stringify(session, null, 2)}
            </pre>
          </div>
        </div>

        <button
          onClick={onClose}
          className="mt-6 w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
        >
          {t('common.close', 'Close')}
        </button>
      </div>
    </div>
  )
}

export default WorkSessionsPage
