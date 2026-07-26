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

  const statusBadge = (status: string) =>
    clsx(
      'px-2 py-0.5 rounded-full text-xs font-medium capitalize',
      status === 'active' ? 'bg-green-100 text-green-700' :
      status === 'paused' ? 'bg-amber-100 text-amber-700' :
      status === 'completed' ? 'bg-blue-100 text-blue-700' :
      status === 'failed' || status === 'timeout' ? 'bg-red-100 text-red-700' :
      'bg-slate-100 text-slate-600',
    )

  return (
    <div className={clsx('p-8', isDark ? 'bg-slate-950' : 'bg-slate-50')}>
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className={clsx('text-3xl font-bold mb-2', isDark ? 'text-white' : 'text-slate-900')}>
              {t('workSessions.title', 'Work Sessions')}
            </h1>
            <p className={clsx('text-sm', isDark ? 'text-slate-400' : 'text-slate-600')}>
              {t('workSessions.subtitle', 'Long-running cross-app work sessions with milestones')}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={loadSessions}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors',
                isDark ? 'bg-slate-800 hover:bg-slate-700 text-white' : 'bg-white hover:bg-slate-100 text-slate-900 border border-slate-300',
              )}
            >
              <RefreshCw size={18} />
              {t('common.refresh', 'Refresh')}
            </button>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
            >
              <Plus size={18} />
              {t('workSessions.newSession', 'New Session')}
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

        {/* Sessions table */}
        <div className={clsx(
          'rounded-lg overflow-hidden mb-8',
          isDark ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200',
        )}>
          {sessions.length === 0 ? (
            <div className={clsx('p-8 text-center', isDark ? 'text-slate-400' : 'text-slate-500')}>
              <p className="text-lg font-medium mb-2">{t('workSessions.none', 'No work sessions yet')}</p>
              <p className="text-sm">{t('workSessions.createHint', 'Create a session to start a long-running goal')}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className={clsx(
                  'border-b',
                  isDark ? 'border-slate-700 bg-slate-800' : 'border-slate-200 bg-slate-50',
                )}>
                  <tr>
                    {[t('workSessions.goal', 'Goal'), t('tasks.status', 'Status'),
                      t('workSessions.milestones', 'Milestones'), t('workSessions.tokens', 'Tokens'),
                      t('workSessions.started', 'Started'), t('common.actions', 'Actions')].map((h, i) => (
                      <th key={i} className={clsx(
                        'px-6 py-3 text-left text-sm font-semibold',
                        isDark ? 'text-slate-300' : 'text-slate-900',
                      )}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr key={s.session_id} className={clsx(
                      'border-b transition-colors',
                      isDark ? 'border-slate-700 hover:bg-slate-800' : 'border-slate-200 hover:bg-slate-50',
                    )}>
                      <td className={clsx(
                        'px-6 py-4 text-sm font-medium max-w-xs truncate',
                        isDark ? 'text-white' : 'text-slate-900',
                      )} title={s.goal}>
                        {s.goal}
                      </td>
                      <td className="px-6 py-4"><span className={statusBadge(s.status)}>{s.status}</span></td>
                      <td className={clsx('px-6 py-4 text-sm', isDark ? 'text-slate-300' : 'text-slate-600')}>
                        {s.current_milestone_index}/{s.milestones.length}
                      </td>
                      <td className={clsx('px-6 py-4 text-sm', isDark ? 'text-slate-300' : 'text-slate-600')}>
                        {s.total_tokens_used}
                      </td>
                      <td className={clsx('px-6 py-4 text-sm whitespace-nowrap', isDark ? 'text-slate-400' : 'text-slate-600')}>
                        {new Date(s.started_at).toLocaleString()}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-1">
                          <IconBtn dark={isDark} title={t('workSessions.view', 'View details')}
                            onClick={() => openDetail(s.session_id)}>
                            <Eye size={16} />
                          </IconBtn>
                          {(s.status === 'active') && (
                            <>
                              <IconBtn dark={isDark} title={t('workSessions.pause', 'Pause')}
                                disabled={busyId === s.session_id}
                                onClick={() => runAction(s.session_id, syncOps.pauseWorkSession.bind(syncOps))}>
                                <Pause size={16} />
                              </IconBtn>
                              <IconBtn dark={isDark} title={t('workSessions.tick', 'Tick (advance milestone)')}
                                disabled={busyId === s.session_id}
                                onClick={() => runAction(s.session_id, syncOps.tickWorkSession.bind(syncOps))}>
                                <StepForward size={16} />
                              </IconBtn>
                            </>
                          )}
                          {(s.status === 'paused' || s.status === 'timeout') && (
                            <IconBtn dark={isDark} title={t('workSessions.resume', 'Resume')}
                              disabled={busyId === s.session_id}
                              onClick={() => runAction(s.session_id, syncOps.resumeWorkSession.bind(syncOps))}>
                              <Play size={16} />
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
        </div>

        {/* Context-session storage restore entry — /api/sessions mounted but the
            backend never injects ContextManager (set_context_manager uncalled),
            so it returns 500 at runtime. Render as coming soon, no fake calls. */}
        <section className={clsx(
          'rounded-lg p-6',
          isDark ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200',
        )}>
          <div className="flex items-center justify-between">
            <div>
              <h2 className={clsx('text-lg font-semibold mb-1', isDark ? 'text-white' : 'text-slate-900')}>
                {t('workSessions.storageRestore', 'Session Storage Restore')}
              </h2>
              <p className={clsx('text-sm', isDark ? 'text-slate-400' : 'text-slate-600')}>
                {t('workSessions.storageRestoreHint',
                  'Restore saved context sessions from storage (/api/sessions). Backend context manager injection pending.')}
              </p>
            </div>
            <button
              disabled
              title={t('common.comingSoon', 'coming soon')}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 rounded-lg font-medium opacity-50 cursor-not-allowed',
                isDark ? 'bg-slate-800 text-slate-400' : 'bg-slate-200 text-slate-500',
              )}
            >
              <ArchiveRestore size={18} />
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
  dark: boolean
  title: string
  disabled?: boolean
  onClick: () => void
  children: React.ReactNode
}

const IconBtn: React.FC<IconBtnProps> = ({ dark, title, disabled, onClick, children }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    title={title}
    aria-label={title}
    className={clsx(
      'p-2 rounded-lg transition-colors disabled:opacity-50',
      dark ? 'hover:bg-slate-700 text-slate-400' : 'hover:bg-slate-200 text-slate-600',
    )}
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
  const labelCls = clsx('block text-sm font-medium mb-1', dark ? 'text-slate-300' : 'text-slate-700')

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" role="dialog" aria-modal="true">
      <div className={clsx('rounded-lg p-6 max-w-md w-full mx-4', dark ? 'bg-slate-900' : 'bg-white')}>
        <div className="flex items-center justify-between mb-4">
          <h2 className={clsx('text-xl font-bold', dark ? 'text-white' : 'text-slate-900')}>
            {t('workSessions.newSession', 'New Work Session')}
          </h2>
          <button onClick={onClose} aria-label={t('common.close', 'Close')}
            className={dark ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-900'}>
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
            'flex-1 px-4 py-2 rounded-lg font-medium transition-colors',
            dark ? 'bg-slate-700 hover:bg-slate-600 text-white' : 'bg-slate-200 hover:bg-slate-300 text-slate-900',
          )}>
            {t('common.cancel', 'Cancel')}
          </button>
          <button
            onClick={handleCreate}
            disabled={submitting || !goal.trim()}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
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
  const milestoneBadge = (status: string) =>
    clsx(
      'px-2 py-0.5 rounded-full text-xs font-medium',
      status === 'completed' ? 'bg-green-100 text-green-700' :
      status === 'running' ? 'bg-blue-100 text-blue-700' :
      status === 'failed' ? 'bg-red-100 text-red-700' :
      'bg-slate-100 text-slate-600',
    )

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" role="dialog" aria-modal="true">
      <div className={clsx(
        'rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[85vh] overflow-y-auto',
        dark ? 'bg-slate-900' : 'bg-white',
      )}>
        <div className="flex items-center justify-between mb-4">
          <h2 className={clsx('text-xl font-bold', dark ? 'text-white' : 'text-slate-900')}>
            {t('workSessions.detail', 'Session Detail')}
          </h2>
          <button onClick={onClose} aria-label={t('common.close', 'Close')}
            className={dark ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-900'}>
            <X size={20} />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <p className={clsx('text-xs font-semibold mb-1', dark ? 'text-slate-400' : 'text-slate-500')}>
              {t('workSessions.goal', 'Goal')}
            </p>
            <p className={clsx('text-sm', dark ? 'text-white' : 'text-slate-900')}>{session.goal}</p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <DetailField dark={dark} label={t('tasks.status', 'Status')} value={session.status} />
            <DetailField dark={dark} label={t('workSessions.tokens', 'Tokens')} value={String(session.total_tokens_used)} />
            <DetailField dark={dark} label={t('workSessions.maxHours', 'Max hours')} value={String(session.max_duration_hours)} />
            <DetailField dark={dark} label={t('workSessions.started', 'Started')}
              value={new Date(session.started_at).toLocaleString()} />
          </div>

          <div>
            <p className={clsx('text-xs font-semibold mb-2', dark ? 'text-slate-400' : 'text-slate-500')}>
              {t('workSessions.milestones', 'Milestones')} ({session.milestones.length})
            </p>
            <div className="space-y-2">
              {session.milestones.map((m) => (
                <div key={m.index} className={clsx(
                  'p-3 rounded-lg text-sm',
                  dark ? 'bg-slate-800' : 'bg-slate-50',
                )}>
                  <div className="flex items-center justify-between mb-1">
                    <span className={clsx('font-medium', dark ? 'text-white' : 'text-slate-900')}>
                      {m.index + 1}. {m.title}
                    </span>
                    <span className={milestoneBadge(m.status)}>{m.status}</span>
                  </div>
                  {m.output && (
                    <p className={clsx('text-xs line-clamp-2', dark ? 'text-slate-400' : 'text-slate-600')}>
                      {m.output}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {session.artifacts.length > 0 && (
            <div>
              <p className={clsx('text-xs font-semibold mb-2', dark ? 'text-slate-400' : 'text-slate-500')}>
                {t('workSessions.artifacts', 'Artifacts')} ({session.artifacts.length})
              </p>
              <ul className="space-y-1">
                {session.artifacts.map((a) => (
                  <li key={a.artifact_id} className={clsx(
                    'text-sm px-3 py-2 rounded-lg',
                    dark ? 'bg-slate-800 text-slate-300' : 'bg-slate-50 text-slate-700',
                  )}>
                    {a.name} <span className="text-xs opacity-70">({a.type})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <p className={clsx('text-xs font-semibold mb-1', dark ? 'text-slate-400' : 'text-slate-500')}>
              {t('workSessions.contextSnapshot', 'Context Snapshot')}
            </p>
            <pre className={clsx(
              'text-xs p-3 rounded-lg overflow-auto max-h-48',
              dark ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-700',
            )}>
              {JSON.stringify(session, null, 2)}
            </pre>
          </div>
        </div>

        <button
          onClick={onClose}
          className="mt-6 w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
        >
          {t('common.close', 'Close')}
        </button>
      </div>
    </div>
  )
}

const DetailField: React.FC<{ dark: boolean; label: string; value: string }> = ({ dark, label, value }) => (
  <div className={clsx('p-3 rounded-lg', dark ? 'bg-slate-800' : 'bg-slate-50')}>
    <p className={clsx('text-xs mb-0.5', dark ? 'text-slate-400' : 'text-slate-500')}>{label}</p>
    <p className={clsx('font-medium capitalize', dark ? 'text-white' : 'text-slate-900')}>{value}</p>
  </div>
)

export default WorkSessionsPage
