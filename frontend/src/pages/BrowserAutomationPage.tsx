import React, { useCallback, useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { useI18n } from '@/i18n/context'
import {
  automationOps,
  isBrowserUnavailable,
  errorMessage,
  BrowserSession,
  DesktopSession,
} from '@/services/automationOps'
import {
  Globe,
  Play,
  RefreshCw,
  XCircle,
  Camera,
  MousePointer,
  Type,
  FileText,
  Plus,
} from 'lucide-react'
import clsx from 'clsx'

type TabKey = 'sessions' | 'advanced' | 'desktop'

const DIVIDER = 'var(--divider)'

export const BrowserAutomationPage: React.FC = () => {
  const { theme } = useAppStore()
  const { t } = useI18n()
  const [tab, setTab] = useState<TabKey>('sessions')
  // 503 from POST /browser/sessions means the real Playwright backend is
  // unavailable — show a graceful banner instead of crashing.
  const [backendUnavailable, setBackendUnavailable] = useState<string | null>(null)

  const handle503 = useCallback((error: unknown): boolean => {
    if (isBrowserUnavailable(error)) {
      setBackendUnavailable(errorMessage(error, 'Browser automation backend unavailable'))
      return true
    }
    return false
  }, [])

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'sessions', label: t('automation.tabs.sessions', 'Session Control') },
    { key: 'advanced', label: t('automation.tabs.advanced', 'Advanced') },
    { key: 'desktop', label: t('automation.tabs.desktop', 'Desktop Macros') },
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
          <h1 className="page-title">{t('automation.title', 'Browser Automation')}</h1>
          <p className="page-subtitle">
            {t('automation.subtitle', 'Real Playwright browser sessions, advanced monitoring, and desktop automation')}
          </p>
        </header>

        {backendUnavailable && (
          <div
            role="alert"
            className="mb-6 rounded-lg border border-[#d97706]/30 px-4 py-3 text-sm text-[#d97706] flex items-start justify-between gap-4"
          >
            <span>
              <strong>{t('automation.unavailable', 'Browser backend unavailable')}</strong>
              {' — '}
              {t(
                'automation.unavailableHint',
                'The server has no Playwright browser runtime (503). Session operations are disabled until the backend installs a browser.'
              )}
              <span className="block mt-1 cell-data opacity-80">{backendUnavailable}</span>
            </span>
            <button
              onClick={() => setBackendUnavailable(null)}
              aria-label={t('common.dismiss', 'Dismiss')}
              className="opacity-70 hover:opacity-100"
            >
              <XCircle size={16} />
            </button>
          </div>
        )}

        {/* Tabs — underline style */}
        <div className="flex gap-1 mb-8 border-b" style={{ borderColor: DIVIDER }} role="tablist">
          {tabs.map((item) => (
            <button
              key={item.key}
              role="tab"
              aria-selected={tab === item.key}
              onClick={() => setTab(item.key)}
              className={clsx(
                'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
                tab === item.key
                  ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                  : 'border-transparent opacity-50 hover:opacity-100'
              )}
            >
              {item.label}
            </button>
          ))}
        </div>

        {tab === 'sessions' && <SessionsTab on503={handle503} unavailable={!!backendUnavailable} />}
        {tab === 'advanced' && <AdvancedTab on503={handle503} />}
        {tab === 'desktop' && <DesktopTab />}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Shared small components
// ---------------------------------------------------------------------------

const Panel: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <section>
    <h3 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-3">
      {title}
    </h3>
    {children}
  </section>
)

const ActionButton: React.FC<{
  onClick: () => void
  busy?: boolean
  disabled?: boolean
  icon?: React.ReactNode
  children: React.ReactNode
  danger?: boolean
  primary?: boolean
}> = ({ onClick, busy, disabled, icon, children, danger, primary }) => {
  const { theme } = useAppStore()
  const { t } = useI18n()
  return (
    <button
      onClick={onClick}
      disabled={busy || disabled}
      className={clsx(
        'flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
        primary
          ? 'bg-blue-600 hover:bg-blue-700 text-white'
          : danger
            ? 'text-[#dc2626] ' + (theme === 'dark' ? 'bg-slate-800 hover:bg-slate-700' : 'bg-white border border-slate-200 hover:bg-slate-100')
            : theme === 'dark'
              ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100'
      )}
    >
      {icon}
      {busy ? t('common.loading', 'Loading...') : children}
    </button>
  )
}

const TextInput: React.FC<{
  value: string
  onChange: (v: string) => void
  placeholder?: string
  type?: string
}> = ({ value, onChange, placeholder, type }) => {
  const { theme } = useAppStore()
  return (
    <input
      type={type ?? 'text'}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={clsx(
        'w-full px-3 py-2 rounded-lg text-sm border outline-none',
        theme === 'dark'
          ? 'bg-slate-800 border-slate-700 text-slate-100 placeholder-slate-500'
          : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400'
      )}
    />
  )
}

const ResultBox: React.FC<{ result: string | null; error?: boolean }> = ({ result, error }) => {
  if (!result) return null
  return (
    <pre
      role="status"
      className={clsx(
        'mt-3 rounded-lg border px-3 py-2 text-xs whitespace-pre-wrap break-words max-h-64 overflow-auto cell-data',
        error
          ? 'border-[#dc2626]/30 text-[#dc2626]'
          : 'border-[rgba(163,169,177,.25)] opacity-80'
      )}
    >
      {result}
    </pre>
  )
}

const SessionListItem: React.FC<{
  id: string
  sub: string
  selected: boolean
  onSelect: () => void
}> = ({ id, sub, selected, onSelect }) => {
  const { theme } = useAppStore()
  return (
    <button
      onClick={onSelect}
      className={clsx(
        'row-line w-full text-left px-2 -mx-2',
        selected && (theme === 'dark' ? 'bg-slate-800' : 'bg-slate-100')
      )}
    >
      <span className="cell-data block truncate">{id}</span>
      <span className="block truncate text-xs opacity-50">
        {sub}
      </span>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Tab 1: session control
// ---------------------------------------------------------------------------

const SessionsTab: React.FC<{ on503: (e: unknown) => boolean; unavailable: boolean }> = ({ on503, unavailable }) => {
  const { t } = useI18n()
  const [sessions, setSessions] = useState<BrowserSession[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [resultError, setResultError] = useState(false)
  const [screenshotSrc, setScreenshotSrc] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [url, setUrl] = useState('https://example.com')
  const [selector, setSelector] = useState('body')
  const [fillValue, setFillValue] = useState('')
  const [shotPath, setShotPath] = useState('shot.png')

  const refresh = useCallback(async () => {
    try {
      setLoadError(null)
      const list = await automationOps.listBrowserSessions()
      setSessions(list)
      if (selectedId && !list.some((s) => s.session_id === selectedId)) setSelectedId(null)
    } catch (error) {
      setLoadError(errorMessage(error, 'Failed to load sessions'))
    }
  }, [selectedId])

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const run = useCallback(
    async (fn: () => Promise<string>) => {
      setBusy(true)
      setResult(null)
      setResultError(false)
      try {
        setResult(await fn())
      } catch (error) {
        if (!on503(error)) {
          setResult(errorMessage(error))
          setResultError(true)
        }
      } finally {
        setBusy(false)
      }
    },
    [on503]
  )

  const selected = sessions.find((s) => s.session_id === selectedId) ?? null

  const createSession = () =>
    run(async () => {
      const session = await automationOps.createBrowserSession()
      await refresh()
      setSelectedId(session.session_id)
      return `${t('automation.sessionCreated', 'Session created')}: ${session.session_id}`
    })

  const showAction = (a: { action: string; ok: boolean; detail: string; data: Record<string, unknown> }) =>
    `${a.ok ? 'OK' : 'FAIL'} [${a.action}] ${a.detail || ''}\n${JSON.stringify(a.data, null, 2)}`.trim()

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
      {/* Session list */}
      <Panel title={t('automation.sessions', 'Browser Sessions')}>
        <div className="flex gap-2 mb-3">
          <ActionButton primary onClick={createSession} busy={busy} disabled={unavailable} icon={<Plus size={16} />}>
            {t('automation.createSession', 'New session')}
          </ActionButton>
          <ActionButton onClick={refresh} icon={<RefreshCw size={16} />}>
            {t('common.refresh', 'Refresh')}
          </ActionButton>
        </div>
        {loadError && <ResultBox result={loadError} error />}
        <div>
          {sessions.map((s) => (
            <SessionListItem
              key={s.session_id}
              id={s.session_id}
              sub={`${s.current_url || t('automation.noUrl', '(no page)')} · ${s.active ? t('automation.active', 'active') : t('automation.closed', 'closed')}`}
              selected={selectedId === s.session_id}
              onSelect={() => setSelectedId(s.session_id)}
            />
          ))}
          {sessions.length === 0 && (
            <p className="empty-state">
              {t('automation.noSessions', 'No sessions yet')}
            </p>
          )}
        </div>
      </Panel>

      {/* Actions */}
      <div className="lg:col-span-2 space-y-8">
        <Panel title={t('automation.navigate', 'Navigate & Capture')}>
          <div className="space-y-3">
            <div className="flex gap-2">
              <TextInput value={url} onChange={setUrl} placeholder="https://example.com" />
              <ActionButton
                onClick={() =>
                  run(async () => {
                    const a = await automationOps.browserGoto(selectedId!, url)
                    await refresh()
                    return showAction(a)
                  })
                }
                busy={busy}
                disabled={!selected || !selected.active}
                icon={<Globe size={16} />}
              >
                {t('automation.goto', 'Go to URL')}
              </ActionButton>
            </div>
            <div className="flex gap-2">
              <TextInput value={shotPath} onChange={setShotPath} placeholder="shot.png" />
              <ActionButton
                onClick={() =>
                  run(async () => {
                    const a = await automationOps.browserScreenshot(selectedId!, shotPath)
                    // Backend saves the screenshot server-side and returns
                    // data.path. If a future backend returns base64 content,
                    // render it inline.
                    const img = (a.data?.base64 ?? a.data?.image) as string | undefined
                    setScreenshotSrc(img ? `data:image/png;base64,${img}` : null)
                    return showAction(a)
                  })
                }
                busy={busy}
                disabled={!selected || !selected.active}
                icon={<Camera size={16} />}
              >
                {t('automation.screenshot', 'Screenshot')}
              </ActionButton>
            </div>
            {screenshotSrc && (
              <img
                src={screenshotSrc}
                alt={t('automation.screenshot', 'Screenshot')}
                className="rounded-lg border max-w-full"
                style={{ borderColor: DIVIDER }}
              />
            )}
          </div>
        </Panel>

        <Panel title={t('automation.interact', 'Interact & Extract')}>
          <div className="space-y-3">
            <TextInput value={selector} onChange={setSelector} placeholder={t('automation.selectorPh', 'CSS selector, e.g. h1 or #submit')} />
            <TextInput value={fillValue} onChange={setFillValue} placeholder={t('automation.fillValuePh', 'Value for fill')} />
            <div className="flex flex-wrap gap-2">
              <ActionButton
                onClick={() => run(async () => showAction(await automationOps.browserClick(selectedId!, selector)))}
                busy={busy}
                disabled={!selected || !selected.active}
                icon={<MousePointer size={16} />}
              >
                {t('automation.click', 'Click')}
              </ActionButton>
              <ActionButton
                onClick={() => run(async () => showAction(await automationOps.browserFill(selectedId!, selector, fillValue)))}
                busy={busy}
                disabled={!selected || !selected.active}
                icon={<Type size={16} />}
              >
                {t('automation.fill', 'Fill')}
              </ActionButton>
              <ActionButton
                onClick={() => run(async () => showAction(await automationOps.browserExtractText(selectedId!, selector)))}
                busy={busy}
                disabled={!selected || !selected.active}
                icon={<FileText size={16} />}
              >
                {t('automation.extractText', 'Extract text')}
              </ActionButton>
              <ActionButton
                onClick={() => run(async () => showAction(await automationOps.browserWaitFor(selectedId!, selector)))}
                busy={busy}
                disabled={!selected || !selected.active}
                icon={<Play size={16} />}
              >
                {t('automation.waitFor', 'Wait for')}
              </ActionButton>
              <ActionButton
                danger
                onClick={() =>
                  run(async () => {
                    await automationOps.closeBrowserSession(selectedId!)
                    await refresh()
                    return t('automation.sessionClosed', 'Session closed')
                  })
                }
                busy={busy}
                disabled={!selected || !selected.active}
                icon={<XCircle size={16} />}
              >
                {t('automation.closeSession', 'Close session')}
              </ActionButton>
            </div>
          </div>
        </Panel>

        <ResultBox result={result} error={resultError} />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab 2: advanced capabilities (browser_advanced.py — mounted)
// ---------------------------------------------------------------------------

const AdvancedTab: React.FC<{ on503: (e: unknown) => boolean }> = ({ on503 }) => {
  const { t } = useI18n()
  const [sessionId, setSessionId] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [resultError, setResultError] = useState(false)
  const [description, setDescription] = useState('')
  const [ref, setRef] = useState('')
  const [refValue, setRefValue] = useState('')
  const [snapLabel, setSnapLabel] = useState('')
  const [beforeLabel, setBeforeLabel] = useState('')
  const [afterLabel, setAfterLabel] = useState('')

  const run = useCallback(
    async (fn: () => Promise<unknown>) => {
      setBusy(true)
      setResult(null)
      setResultError(false)
      try {
        setResult(JSON.stringify(await fn(), null, 2))
      } catch (error) {
        if (!on503(error)) {
          setResult(errorMessage(error))
          setResultError(true)
        }
      } finally {
        setBusy(false)
      }
    },
    [on503]
  )

  const needSession = !sessionId.trim()

  return (
    <div className="space-y-8">
      <Panel title={t('automation.advancedSession', 'Target Session')}>
        <TextInput
          value={sessionId}
          onChange={setSessionId}
          placeholder={t('automation.sessionIdPh', 'Browser session id (from Session Control tab)')}
        />
      </Panel>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <Panel title={t('automation.network', 'Network Monitoring')}>
          <div className="flex flex-wrap gap-2">
            <ActionButton busy={busy} disabled={needSession} icon={<Play size={16} />} onClick={() => run(() => automationOps.networkRequests(sessionId))}>
              {t('automation.networkRequests', 'Requests')}
            </ActionButton>
            <ActionButton busy={busy} disabled={needSession} icon={<Play size={16} />} onClick={() => run(() => automationOps.networkSummary(sessionId))}>
              {t('automation.networkSummary', 'Summary')}
            </ActionButton>
            <ActionButton busy={busy} disabled={needSession} danger icon={<XCircle size={16} />} onClick={() => run(() => automationOps.clearNetwork(sessionId))}>
              {t('automation.clear', 'Clear')}
            </ActionButton>
          </div>
        </Panel>

        <Panel title={t('automation.console', 'Console Monitoring')}>
          <div className="flex flex-wrap gap-2">
            <ActionButton busy={busy} disabled={needSession} icon={<Play size={16} />} onClick={() => run(() => automationOps.consoleMessages(sessionId))}>
              {t('automation.consoleMessages', 'Messages')}
            </ActionButton>
            <ActionButton busy={busy} disabled={needSession} icon={<Play size={16} />} onClick={() => run(() => automationOps.consoleMessages(sessionId, true))}>
              {t('automation.consoleErrors', 'Errors only')}
            </ActionButton>
            <ActionButton busy={busy} disabled={needSession} icon={<Play size={16} />} onClick={() => run(() => automationOps.consoleSummary(sessionId))}>
              {t('automation.consoleSummary', 'Summary')}
            </ActionButton>
          </div>
        </Panel>

        <Panel title={t('automation.elements', 'Element References')}>
          <div className="space-y-3">
            <div className="flex gap-2">
              <TextInput value={description} onChange={setDescription} placeholder={t('automation.findPh', 'Natural language, e.g. "login button"')} />
              <ActionButton busy={busy} disabled={needSession || !description.trim()} icon={<Play size={16} />} onClick={() => run(() => automationOps.findElements(sessionId, description))}>
                {t('automation.find', 'Find')}
              </ActionButton>
            </div>
            <ActionButton busy={busy} disabled={needSession} icon={<Play size={16} />} onClick={() => run(() => automationOps.elementTree(sessionId))}>
              {t('automation.elementTree', 'Build element tree')}
            </ActionButton>
            <div className="flex gap-2">
              <TextInput value={ref} onChange={setRef} placeholder="ref (e.g. e1)" />
              <TextInput value={refValue} onChange={setRefValue} placeholder={t('automation.fillValuePh', 'Value for fill')} />
            </div>
            <div className="flex gap-2">
              <ActionButton busy={busy} disabled={needSession || !ref.trim()} icon={<MousePointer size={16} />} onClick={() => run(() => automationOps.clickElementByRef(sessionId, ref))}>
                {t('automation.clickRef', 'Click by ref')}
              </ActionButton>
              <ActionButton busy={busy} disabled={needSession || !ref.trim() || !refValue} icon={<Type size={16} />} onClick={() => run(() => automationOps.fillElementByRef(sessionId, ref, refValue))}>
                {t('automation.fillRef', 'Fill by ref')}
              </ActionButton>
            </div>
          </div>
        </Panel>

        <Panel title={t('automation.snapshots', 'Page Snapshots')}>
          <div className="space-y-3">
            <div className="flex gap-2">
              <TextInput value={snapLabel} onChange={setSnapLabel} placeholder={t('automation.labelPh', 'Snapshot label')} />
              <ActionButton busy={busy} disabled={needSession} icon={<Camera size={16} />} onClick={() => run(() => automationOps.captureSnapshot(sessionId, snapLabel))}>
                {t('automation.capture', 'Capture')}
              </ActionButton>
            </div>
            <div className="flex gap-2">
              <TextInput value={beforeLabel} onChange={setBeforeLabel} placeholder={t('automation.beforePh', 'before label')} />
              <TextInput value={afterLabel} onChange={setAfterLabel} placeholder={t('automation.afterPh', 'after label')} />
              <ActionButton busy={busy} disabled={needSession || !beforeLabel.trim() || !afterLabel.trim()} icon={<Play size={16} />} onClick={() => run(() => automationOps.compareSnapshots(sessionId, beforeLabel, afterLabel))}>
                {t('automation.compare', 'Compare')}
              </ActionButton>
            </div>
          </div>
        </Panel>
      </div>

      <ResultBox result={result} error={resultError} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab 3: desktop macros (desktop.py — mounted)
// ---------------------------------------------------------------------------

const DesktopTab: React.FC = () => {
  const { t } = useI18n()
  const [sessions, setSessions] = useState<DesktopSession[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [resultError, setResultError] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [action, setAction] = useState('click')
  const [target, setTarget] = useState('')
  const [value, setValue] = useState('')

  const refresh = useCallback(async () => {
    try {
      setLoadError(null)
      const list = await automationOps.listDesktopSessions()
      setSessions(list)
    } catch (error) {
      setLoadError(errorMessage(error, 'Failed to load desktop sessions'))
    }
  }, [])

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const run = useCallback(async (fn: () => Promise<unknown>) => {
    setBusy(true)
    setResult(null)
    setResultError(false)
    try {
      setResult(JSON.stringify(await fn(), null, 2))
    } catch (error) {
      setResult(errorMessage(error))
      setResultError(true)
    } finally {
      setBusy(false)
    }
  }, [])

  const selected = sessions.find((s) => s.session_id === selectedId) ?? null

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
      <Panel title={t('automation.desktopSessions', 'Desktop Sessions')}>
        <div className="flex gap-2 mb-3">
          <ActionButton
            primary
            busy={busy}
            icon={<Plus size={16} />}
            onClick={() =>
              run(async () => {
                const s = await automationOps.createDesktopSession()
                await refresh()
                setSelectedId(s.session_id)
                return s
              })
            }
          >
            {t('automation.createSession', 'New session')}
          </ActionButton>
          <ActionButton icon={<RefreshCw size={16} />} onClick={refresh}>
            {t('common.refresh', 'Refresh')}
          </ActionButton>
        </div>
        {loadError && <ResultBox result={loadError} error />}
        <div>
          {sessions.map((s) => (
            <SessionListItem
              key={s.session_id}
              id={s.session_id}
              sub={`${s.provider ?? 'ui-tars'} · ${s.active ? t('automation.active', 'active') : t('automation.closed', 'closed')}`}
              selected={selectedId === s.session_id}
              onSelect={() => setSelectedId(s.session_id)}
            />
          ))}
          {sessions.length === 0 && (
            <p className="empty-state">
              {t('automation.noSessions', 'No sessions yet')}
            </p>
          )}
        </div>
      </Panel>

      <div className="lg:col-span-2 space-y-8">
        <Panel title={t('automation.desktopAction', 'Execute Desktop Action')}>
          <div className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <TextInput value={action} onChange={setAction} placeholder={t('automation.actionPh', 'action (click/type/key/scroll...)')} />
              <TextInput value={target} onChange={setTarget} placeholder={t('automation.targetPh', 'target (optional)')} />
              <TextInput value={value} onChange={setValue} placeholder={t('automation.valuePh', 'value (optional)')} />
            </div>
            <div className="flex gap-2">
              <ActionButton
                busy={busy}
                disabled={!selected || !selected.active || !action.trim()}
                icon={<Play size={16} />}
                onClick={() =>
                  run(async () => {
                    const resp = await automationOps.sendDesktopAction(selectedId!, {
                      action,
                      target: target || undefined,
                      value: value || undefined,
                    })
                    await refresh()
                    return resp
                  })
                }
              >
                {t('automation.execute', 'Execute')}
              </ActionButton>
              <ActionButton
                danger
                busy={busy}
                disabled={!selected || !selected.active}
                icon={<XCircle size={16} />}
                onClick={() =>
                  run(async () => {
                    const resp = await automationOps.closeDesktopSession(selectedId!)
                    await refresh()
                    return resp
                  })
                }
              >
                {t('automation.closeSession', 'Close session')}
              </ActionButton>
            </div>
          </div>
        </Panel>
        <ResultBox result={result} error={resultError} />
      </div>
    </div>
  )
}

export default BrowserAutomationPage
