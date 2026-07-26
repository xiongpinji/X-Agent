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
  Monitor,
  Sparkles,
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

  const tabs: { key: TabKey; label: string; icon: React.ReactNode }[] = [
    { key: 'sessions', label: t('automation.tabs.sessions', 'Session Control'), icon: <Globe size={16} /> },
    { key: 'advanced', label: t('automation.tabs.advanced', 'Advanced'), icon: <Sparkles size={16} /> },
    { key: 'desktop', label: t('automation.tabs.desktop', 'Desktop Macros'), icon: <Monitor size={16} /> },
  ]

  return (
    <div className={clsx('p-8', theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50')}>
      <div className="max-w-6xl mx-auto">
        <div className="mb-6">
          <h1 className={clsx('text-3xl font-bold mb-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
            {t('automation.title', 'Browser Automation')}
          </h1>
          <p className={clsx('text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
            {t('automation.subtitle', 'Real Playwright browser sessions, advanced monitoring, and desktop automation')}
          </p>
        </div>

        {backendUnavailable && (
          <div
            role="alert"
            className={clsx(
              'mb-6 rounded-lg border px-4 py-3 text-sm flex items-start justify-between gap-4',
              theme === 'dark'
                ? 'border-amber-900 bg-amber-950/40 text-amber-300'
                : 'border-amber-200 bg-amber-50 text-amber-700'
            )}
          >
            <span>
              <strong>{t('automation.unavailable', 'Browser backend unavailable')}</strong>
              {' — '}
              {t(
                'automation.unavailableHint',
                'The server has no Playwright browser runtime (503). Session operations are disabled until the backend installs a browser.'
              )}
              <span className="block mt-1 text-xs opacity-80">{backendUnavailable}</span>
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

        {/* Tabs */}
        <div className="flex gap-2 mb-6" role="tablist">
          {tabs.map((item) => (
            <button
              key={item.key}
              role="tab"
              aria-selected={tab === item.key}
              onClick={() => setTab(item.key)}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                tab === item.key
                  ? theme === 'dark'
                    ? 'bg-blue-600/20 text-blue-400 border border-blue-800'
                    : 'bg-blue-100 text-blue-700 border border-blue-200'
                  : theme === 'dark'
                    ? 'text-slate-400 hover:text-slate-200 border border-transparent'
                    : 'text-slate-600 hover:text-slate-900 border border-transparent'
              )}
            >
              {item.icon}
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

const Panel: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => {
  const { theme } = useAppStore()
  return (
    <div
      className={clsx(
        'rounded-lg p-5 border',
        theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
      )}
    >
      <h3 className={clsx('text-sm font-semibold mb-3', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
        {title}
      </h3>
      {children}
    </div>
  )
}

const ActionButton: React.FC<{
  onClick: () => void
  busy?: boolean
  disabled?: boolean
  icon?: React.ReactNode
  children: React.ReactNode
  danger?: boolean
}> = ({ onClick, busy, disabled, icon, children, danger }) => {
  const { theme } = useAppStore()
  const { t } = useI18n()
  return (
    <button
      onClick={onClick}
      disabled={busy || disabled}
      className={clsx(
        'flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
        danger
          ? theme === 'dark'
            ? 'bg-red-600/20 text-red-400 hover:bg-red-600/30'
            : 'bg-red-100 text-red-700 hover:bg-red-200'
          : theme === 'dark'
            ? 'bg-blue-600/20 text-blue-400 hover:bg-blue-600/30'
            : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
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
          : 'bg-slate-50 border-slate-300 text-slate-900 placeholder-slate-400'
      )}
    />
  )
}

const ResultBox: React.FC<{ result: string | null; error?: boolean }> = ({ result, error }) => {
  const { theme } = useAppStore()
  if (!result) return null
  return (
    <pre
      role="status"
      className={clsx(
        'mt-3 rounded-md border px-3 py-2 text-xs whitespace-pre-wrap break-words max-h-64 overflow-auto',
        error
          ? theme === 'dark'
            ? 'border-red-900 bg-red-950/40 text-red-300'
            : 'border-red-200 bg-red-50 text-red-700'
          : theme === 'dark'
            ? 'border-slate-700 bg-slate-800 text-slate-300'
            : 'border-slate-200 bg-slate-50 text-slate-700'
      )}
    >
      {result}
    </pre>
  )
}

// ---------------------------------------------------------------------------
// Tab 1: session control
// ---------------------------------------------------------------------------

const SessionsTab: React.FC<{ on503: (e: unknown) => boolean; unavailable: boolean }> = ({ on503, unavailable }) => {
  const { theme } = useAppStore()
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
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Session list */}
      <Panel title={t('automation.sessions', 'Browser Sessions')}>
        <div className="flex gap-2 mb-3">
          <ActionButton onClick={createSession} busy={busy} disabled={unavailable} icon={<Plus size={16} />}>
            {t('automation.createSession', 'New session')}
          </ActionButton>
          <ActionButton onClick={refresh} icon={<RefreshCw size={16} />}>
            {t('common.refresh', 'Refresh')}
          </ActionButton>
        </div>
        {loadError && <ResultBox result={loadError} error />}
        <ul className="space-y-2">
          {sessions.map((s) => (
            <li key={s.session_id}>
              <button
                onClick={() => setSelectedId(s.session_id)}
                className={clsx(
                  'w-full text-left px-3 py-2 rounded-lg text-xs border transition-colors',
                  selectedId === s.session_id
                    ? theme === 'dark'
                      ? 'border-blue-700 bg-blue-600/10 text-blue-300'
                      : 'border-blue-300 bg-blue-50 text-blue-700'
                    : theme === 'dark'
                      ? 'border-slate-700 text-slate-300 hover:border-slate-600'
                      : 'border-slate-200 text-slate-700 hover:border-slate-300'
                )}
              >
                <span className="font-mono block truncate">{s.session_id}</span>
                <span className={clsx('block truncate', theme === 'dark' ? 'text-slate-500' : 'text-slate-500')}>
                  {s.current_url || t('automation.noUrl', '(no page)')} ·{' '}
                  {s.active ? t('automation.active', 'active') : t('automation.closed', 'closed')}
                </span>
              </button>
            </li>
          ))}
          {sessions.length === 0 && (
            <li className={clsx('text-xs py-4 text-center', theme === 'dark' ? 'text-slate-500' : 'text-slate-500')}>
              {t('automation.noSessions', 'No sessions yet')}
            </li>
          )}
        </ul>
      </Panel>

      {/* Actions */}
      <div className="lg:col-span-2 space-y-6">
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
                className="rounded-lg border border-slate-300 max-w-full"
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
    <div className="space-y-6">
      <Panel title={t('automation.advancedSession', 'Target Session')}>
        <TextInput
          value={sessionId}
          onChange={setSessionId}
          placeholder={t('automation.sessionIdPh', 'Browser session id (from Session Control tab)')}
        />
      </Panel>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
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
  const { theme } = useAppStore()
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
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Panel title={t('automation.desktopSessions', 'Desktop Sessions')}>
        <div className="flex gap-2 mb-3">
          <ActionButton
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
        <ul className="space-y-2">
          {sessions.map((s) => (
            <li key={s.session_id}>
              <button
                onClick={() => setSelectedId(s.session_id)}
                className={clsx(
                  'w-full text-left px-3 py-2 rounded-lg text-xs border transition-colors',
                  selectedId === s.session_id
                    ? theme === 'dark'
                      ? 'border-blue-700 bg-blue-600/10 text-blue-300'
                      : 'border-blue-300 bg-blue-50 text-blue-700'
                    : theme === 'dark'
                      ? 'border-slate-700 text-slate-300 hover:border-slate-600'
                      : 'border-slate-200 text-slate-700 hover:border-slate-300'
                )}
              >
                <span className="font-mono block truncate">{s.session_id}</span>
                <span className={clsx('block', theme === 'dark' ? 'text-slate-500' : 'text-slate-500')}>
                  {s.provider ?? 'ui-tars'} · {s.active ? t('automation.active', 'active') : t('automation.closed', 'closed')}
                </span>
              </button>
            </li>
          ))}
          {sessions.length === 0 && (
            <li className={clsx('text-xs py-4 text-center', theme === 'dark' ? 'text-slate-500' : 'text-slate-500')}>
              {t('automation.noSessions', 'No sessions yet')}
            </li>
          )}
        </ul>
      </Panel>

      <div className="lg:col-span-2 space-y-6">
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
