import React, { useCallback, useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import {
  mcpOps,
  McpServerInfo,
  McpDiscoveredTool,
  McpLegacyTool,
  McpHealthResponse,
  McpStatusResponse,
  CmServerInfo,
  ConnectServerRequest,
} from '@/services/mcpOps'
import { useI18n } from '@/i18n/context'
import {
  Server,
  Plus,
  Trash2,
  RefreshCw,
  Activity,
  ScrollText,
  Wrench,
  ShieldCheck,
  Plug,
  PlugZap,
} from 'lucide-react'
import clsx from 'clsx'

type TabKey = 'servers' | 'tools' | 'health'

export const McpManagementPage: React.FC = () => {
  const { theme, setError } = useAppStore()
  const { t } = useI18n()
  const [tab, setTab] = useState<TabKey>('servers')

  const card = clsx(
    'rounded-lg p-6',
    theme === 'dark' ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200'
  )
  const muted = clsx('text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')
  const heading = clsx('text-lg font-bold', theme === 'dark' ? 'text-white' : 'text-slate-900')
  const input = clsx(
    'w-full px-3 py-2 rounded-lg border text-sm outline-none transition-colors',
    theme === 'dark'
      ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-blue-500'
      : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-blue-500'
  )
  const errBox = clsx(
    'mb-6 rounded-lg border px-4 py-3 text-sm',
    theme === 'dark'
      ? 'border-red-900 bg-red-950/40 text-red-300'
      : 'border-red-200 bg-red-50 text-red-700'
  )

  const tabs: Array<{ key: TabKey; label: string; icon: React.ReactNode }> = [
    { key: 'servers', label: t('mcp.servers', 'Servers'), icon: <Server size={16} /> },
    { key: 'tools', label: t('mcp.tools', 'Tools'), icon: <Wrench size={16} /> },
    { key: 'health', label: t('mcp.healthAudit', 'Health & Audit'), icon: <Activity size={16} /> },
  ]

  return (
    <div className={clsx('p-8', theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50')}>
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className={clsx('text-3xl font-bold mb-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
            {t('mcp.title', 'MCP Management')}
          </h1>
          <p className={muted}>
            {t('mcp.subtitle', 'Manage MCP servers, discovered tools, health and audit logs')}
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6" role="tablist">
          {tabs.map((tb) => (
            <button
              key={tb.key}
              role="tab"
              aria-selected={tab === tb.key}
              onClick={() => setTab(tb.key)}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                tab === tb.key
                  ? 'bg-blue-600 text-white'
                  : theme === 'dark'
                    ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                    : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
              )}
            >
              {tb.icon}
              {tb.label}
            </button>
          ))}
        </div>

        {tab === 'servers' && (
          <ServersTab theme={theme} card={card} muted={muted} heading={heading} input={input} errBox={errBox} setError={setError} />
        )}
        {tab === 'tools' && (
          <ToolsTab theme={theme} card={card} muted={muted} heading={heading} errBox={errBox} setError={setError} />
        )}
        {tab === 'health' && (
          <HealthTab theme={theme} card={card} muted={muted} heading={heading} input={input} errBox={errBox} setError={setError} />
        )}
      </div>
    </div>
  )
}

// ─── Shared tab props ────────────────────────────────────────────────────────

interface TabProps {
  theme: 'light' | 'dark'
  card: string
  muted: string
  heading: string
  input?: string
  errBox: string
  setError: (e: string | null) => void
}

// ─── Servers tab ─────────────────────────────────────────────────────────────

const ServersTab: React.FC<TabProps> = ({ theme, card, muted, heading, input, errBox, setError }) => {
  const { t } = useI18n()
  const [servers, setServers] = useState<McpServerInfo[]>([])
  const [cmServers, setCmServers] = useState<CmServerInfo[]>([])
  const [mcpEnabled, setMcpEnabled] = useState(true)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [busy, setBusy] = useState(false)
  const comingSoon = t('common.comingSoon', 'Coming soon')

  // Add-server form state (matches ConnectServerRequest in the backend)
  const [form, setForm] = useState({
    name: '',
    transport: 'http',
    url: '',
    command: '',
    args: '',
    headers: '',
    env: '',
    timeout: '30',
  })

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const [mgr, cm] = await Promise.allSettled([mcpOps.listServers(), mcpOps.cmListServers()])
      if (mgr.status === 'fulfilled') {
        setServers(mgr.value.servers ?? [])
        setMcpEnabled(mgr.value.mcp_enabled !== false)
      } else {
        setServers([])
      }
      if (cm.status === 'fulfilled') {
        setCmServers(cm.value.servers ?? [])
      } else {
        setCmServers([])
      }
      if (mgr.status === 'rejected' && cm.status === 'rejected') {
        const msg = mgr.reason instanceof Error ? mgr.reason.message : 'Failed to load servers'
        setLoadError(msg)
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }, [setError])

  useEffect(() => {
    load()
  }, [load])

  const parseJsonObject = (raw: string): Record<string, string> | undefined => {
    const trimmed = raw.trim()
    if (!trimmed) return undefined
    const parsed = JSON.parse(trimmed)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      throw new Error('Expected a JSON object')
    }
    return parsed
  }

  const handleConnect = async () => {
    setBusy(true)
    setLoadError(null)
    try {
      const req: ConnectServerRequest = {
        name: form.name.trim(),
        transport: form.transport,
        timeout: Number(form.timeout) || 30,
      }
      if (form.transport === 'stdio') {
        req.command = form.command.trim()
        req.args = form.args.trim() ? form.args.trim().split(/\s+/) : []
        req.env = parseJsonObject(form.env) ?? null
      } else {
        req.url = form.url.trim()
        req.headers = parseJsonObject(form.headers) ?? null
      }
      await mcpOps.connectServer(req)
      setShowAdd(false)
      setForm({ name: '', transport: 'http', url: '', command: '', args: '', headers: '', env: '', timeout: '30' })
      await load()
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to connect server'
      setLoadError(msg)
      setError(msg)
    } finally {
      setBusy(false)
    }
  }

  const handleDisconnect = async (serverId: string) => {
    if (!confirm(t('mcp.disconnectConfirm', 'Disconnect this server?'))) return
    setBusy(true)
    try {
      await mcpOps.disconnectServer(serverId)
      await load()
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to disconnect server'
      setLoadError(msg)
      setError(msg)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      {loadError && <div role="alert" className={errBox}>{loadError}</div>}

      <div className="flex items-center justify-between mb-4">
        <h2 className={heading}>{t('mcp.serverList', 'MCP Servers')}</h2>
        <div className="flex gap-2">
          <button
            onClick={load}
            disabled={loading}
            className={clsx(
              'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
              theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
            )}
            aria-label={t('common.refresh', 'Refresh')}
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            {t('common.refresh', 'Refresh')}
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            <Plus size={16} />
            {t('mcp.addServer', 'Add Server')}
          </button>
        </div>
      </div>

      {!mcpEnabled && (
        <div className={clsx(
          'mb-4 rounded-lg border px-4 py-3 text-sm',
          theme === 'dark' ? 'border-amber-900 bg-amber-950/40 text-amber-300' : 'border-amber-200 bg-amber-50 text-amber-700'
        )}>
          {t('mcp.disabled', 'MCP manager not initialized (XAGENT_MCP_ENABLED=false or no config)')}
        </div>
      )}

      {/* Discovery-layer servers */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        {servers.map((s) => (
          <div key={s.name} className={card}>
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                {s.connected ? <PlugZap size={18} className="text-green-500" /> : <Plug size={18} className="text-slate-500" />}
                <h3 className={clsx('font-bold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>{s.name}</h3>
              </div>
              <span className={clsx(
                'px-2 py-0.5 rounded-full text-xs font-medium',
                s.connected
                  ? 'bg-green-500/10 text-green-600'
                  : theme === 'dark' ? 'bg-slate-700 text-slate-400' : 'bg-slate-100 text-slate-500'
              )}>
                {s.connected ? t('mcp.connected', 'Connected') : t('mcp.disconnected', 'Disconnected')}
              </span>
            </div>
            <p className={muted}>{t('mcp.transport', 'Transport')}: {s.transport}</p>
            {/* Backend exposes no delete for discovery-layer servers; only
                client-manager connections can be disconnected. */}
            <button
              disabled
              title={`${t('mcp.removeServer', 'Remove')} (${comingSoon})`}
              aria-label={`${t('mcp.removeServer', 'Remove')} (${comingSoon})`}
              className={clsx(
                'mt-4 w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium opacity-50 cursor-not-allowed',
                theme === 'dark' ? 'bg-slate-700 text-slate-300' : 'bg-slate-200 text-slate-700'
              )}
            >
              <Trash2 size={16} />
              {t('mcp.removeServer', 'Remove')} ({comingSoon})
            </button>
          </div>
        ))}
        {servers.length === 0 && cmServers.length === 0 && !loading && (
          <div className={clsx('col-span-full text-center py-8', muted)}>
            {t('mcp.noServers', 'No MCP servers configured')}
          </div>
        )}
      </div>

      {/* Client-manager connections */}
      {cmServers.length > 0 && (
        <>
          <h2 className={clsx(heading, 'mb-4')}>{t('mcp.cmServers', 'Client-Manager Connections')}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
            {cmServers.map((s, i) => {
              const id = String(s.server_id ?? s.name ?? i)
              return (
                <div key={id} className={card}>
                  <div className="flex items-start justify-between mb-3">
                    <h3 className={clsx('font-bold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                      {String(s.name ?? s.server_id ?? id)}
                    </h3>
                    <span className={clsx(
                      'px-2 py-0.5 rounded-full text-xs font-medium',
                      s.connected ? 'bg-green-500/10 text-green-600' : theme === 'dark' ? 'bg-slate-700 text-slate-400' : 'bg-slate-100 text-slate-500'
                    )}>
                      {s.connected ? t('mcp.connected', 'Connected') : t('mcp.disconnected', 'Disconnected')}
                    </span>
                  </div>
                  {s.transport && <p className={muted}>{t('mcp.transport', 'Transport')}: {String(s.transport)}</p>}
                  <button
                    onClick={() => handleDisconnect(id)}
                    disabled={busy}
                    className={clsx(
                      'mt-4 w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
                      theme === 'dark' ? 'bg-red-600/20 text-red-400 hover:bg-red-600/30' : 'bg-red-100 text-red-700 hover:bg-red-200'
                    )}
                  >
                    <Trash2 size={16} />
                    {t('mcp.disconnect', 'Disconnect')}
                  </button>
                </div>
              )
            })}
          </div>
        </>
      )}

      {/* Add server modal */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true">
          <div className={clsx(card, 'w-full max-w-lg max-h-[90vh] overflow-y-auto')}>
            <h3 className={clsx(heading, 'mb-4')}>{t('mcp.addServer', 'Add Server')}</h3>
            <div className="space-y-3">
              <div>
                <label className={clsx(muted, 'block mb-1')}>{t('mcp.serverName', 'Name')}</label>
                <input className={input} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="my-mcp-server" />
              </div>
              <div>
                <label className={clsx(muted, 'block mb-1')}>{t('mcp.transport', 'Transport')}</label>
                <select className={input} value={form.transport} onChange={(e) => setForm({ ...form, transport: e.target.value })}>
                  <option value="http">HTTP</option>
                  <option value="stdio">stdio</option>
                </select>
              </div>
              {form.transport === 'http' ? (
                <>
                  <div>
                    <label className={clsx(muted, 'block mb-1')}>URL</label>
                    <input className={input} value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="http://localhost:8001" />
                  </div>
                  <div>
                    <label className={clsx(muted, 'block mb-1')}>{t('mcp.headers', 'Headers (JSON, optional)')}</label>
                    <input className={input} value={form.headers} onChange={(e) => setForm({ ...form, headers: e.target.value })} placeholder='{"Authorization": "Bearer ..."}' />
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label className={clsx(muted, 'block mb-1')}>{t('mcp.command', 'Command')}</label>
                    <input className={input} value={form.command} onChange={(e) => setForm({ ...form, command: e.target.value })} placeholder="npx" />
                  </div>
                  <div>
                    <label className={clsx(muted, 'block mb-1')}>{t('mcp.args', 'Args (space-separated)')}</label>
                    <input className={input} value={form.args} onChange={(e) => setForm({ ...form, args: e.target.value })} placeholder="-y @modelcontextprotocol/server-everything" />
                  </div>
                  <div>
                    <label className={clsx(muted, 'block mb-1')}>{t('mcp.env', 'Env (JSON, optional)')}</label>
                    <input className={input} value={form.env} onChange={(e) => setForm({ ...form, env: e.target.value })} placeholder='{"KEY": "value"}' />
                  </div>
                </>
              )}
              <div>
                <label className={clsx(muted, 'block mb-1')}>{t('mcp.timeout', 'Timeout (seconds)')}</label>
                <input className={input} type="number" min={1} value={form.timeout} onChange={(e) => setForm({ ...form, timeout: e.target.value })} />
              </div>
            </div>
            <div className="flex gap-2 mt-6">
              <button
                onClick={() => setShowAdd(false)}
                disabled={busy}
                className={clsx(
                  'flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
                  theme === 'dark' ? 'bg-slate-700 text-slate-300 hover:bg-slate-600' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
                )}
              >
                {t('common.cancel', 'Cancel')}
              </button>
              <button
                onClick={handleConnect}
                disabled={busy || !form.name.trim()}
                className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                {busy ? t('common.loading', 'Loading...') : t('mcp.connect', 'Connect')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Tools tab ───────────────────────────────────────────────────────────────

const ToolsTab: React.FC<TabProps> = ({ theme, card, muted, heading, errBox, setError }) => {
  const { t } = useI18n()
  const [legacyTools, setLegacyTools] = useState<McpLegacyTool[]>([])
  const [discovered, setDiscovered] = useState<McpDiscoveredTool[]>([])
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [invokeResult, setInvokeResult] = useState<{ key: string; text: string; ok: boolean } | null>(null)
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const comingSoon = t('common.comingSoon', 'Coming soon')

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const [legacy, disc] = await Promise.allSettled([mcpOps.listTools(), mcpOps.listDiscoveredTools()])
      if (legacy.status === 'fulfilled') setLegacyTools(legacy.value.tools ?? [])
      if (disc.status === 'fulfilled') setDiscovered(disc.value.tools ?? [])
      if (legacy.status === 'rejected' && disc.status === 'rejected') {
        const msg = legacy.reason instanceof Error ? legacy.reason.message : 'Failed to load tools'
        setLoadError(msg)
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }, [setError])

  useEffect(() => {
    load()
  }, [load])

  const handleInvoke = async (tool: McpDiscoveredTool) => {
    const key = `${tool.server}/${tool.name}`
    setBusyKey(key)
    setInvokeResult(null)
    try {
      const resp = await mcpOps.invokeTool(tool.server, tool.name, {})
      setInvokeResult({ key, text: JSON.stringify(resp.result ?? resp, null, 2).slice(0, 500), ok: true })
    } catch (error) {
      setInvokeResult({ key, text: error instanceof Error ? error.message : 'Invoke failed', ok: false })
    } finally {
      setBusyKey(null)
    }
  }

  return (
    <div>
      {loadError && <div role="alert" className={errBox}>{loadError}</div>}

      <div className="flex items-center justify-between mb-4">
        <h2 className={heading}>{t('mcp.toolInventory', 'Tool Inventory')}</h2>
        <button
          onClick={load}
          disabled={loading}
          className={clsx(
            'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
            theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
          )}
          aria-label={t('common.refresh', 'Refresh')}
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          {t('common.refresh', 'Refresh')}
        </button>
      </div>

      {/* Discovered tools (official SDK) */}
      {discovered.length > 0 && (
        <>
          <h3 className={clsx('text-sm font-semibold mb-3', theme === 'dark' ? 'text-slate-300' : 'text-slate-700')}>
            {t('mcp.discoveredTools', 'Discovered (MCP SDK)')}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            {discovered.map((tool) => {
              const key = `${tool.server}/${tool.name}`
              return (
                <div key={key} className={card}>
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h4 className={clsx('font-bold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>{tool.name}</h4>
                      <p className={muted}>{t('mcp.server', 'Server')}: {tool.server}</p>
                    </div>
                    {/* Backend does not expose risk level / approval flags for MCP tools */}
                    <span
                      className={clsx(
                        'px-2 py-0.5 rounded-full text-xs font-medium opacity-60',
                        theme === 'dark' ? 'bg-slate-700 text-slate-400' : 'bg-slate-100 text-slate-500'
                      )}
                      title={`${t('mcp.riskLevel', 'Risk level')} / ${t('mcp.approval', 'Approval')} (${comingSoon})`}
                    >
                      {t('mcp.riskLevel', 'Risk')}: — ({comingSoon})
                    </span>
                  </div>
                  <p className={clsx(muted, 'mb-3 line-clamp-2')}>{tool.description || '—'}</p>
                  <p className={clsx('text-xs mb-3 font-mono', theme === 'dark' ? 'text-slate-500' : 'text-slate-400')}>
                    {tool.registered_name}
                  </p>
                  {invokeResult?.key === key && (
                    <pre className={clsx(
                      'mb-3 rounded-md border px-3 py-2 text-xs overflow-x-auto whitespace-pre-wrap break-all',
                      invokeResult.ok
                        ? theme === 'dark' ? 'border-green-900 bg-green-950/40 text-green-300' : 'border-green-200 bg-green-50 text-green-700'
                        : theme === 'dark' ? 'border-red-900 bg-red-950/40 text-red-300' : 'border-red-200 bg-red-50 text-red-700'
                    )} role="status">
                      {invokeResult.text}
                    </pre>
                  )}
                  <button
                    onClick={() => handleInvoke(tool)}
                    disabled={busyKey === key}
                    className={clsx(
                      'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
                      theme === 'dark' ? 'bg-blue-600/20 text-blue-400 hover:bg-blue-600/30' : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                    )}
                  >
                    <PlugZap size={16} />
                    {busyKey === key ? t('common.loading', 'Loading...') : t('mcp.invoke', 'Invoke (no args)')}
                  </button>
                </div>
              )
            })}
          </div>
        </>
      )}

      {/* Legacy server tools */}
      <h3 className={clsx('text-sm font-semibold mb-3', theme === 'dark' ? 'text-slate-300' : 'text-slate-700')}>
        {t('mcp.legacyTools', 'Registered (Legacy Server)')}
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {legacyTools.map((tool) => (
          <div key={tool.name} className={card}>
            <div className="flex items-start justify-between mb-2">
              <h4 className={clsx('font-bold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>{tool.name}</h4>
              <span
                className={clsx(
                  'px-2 py-0.5 rounded-full text-xs font-medium opacity-60',
                  theme === 'dark' ? 'bg-slate-700 text-slate-400' : 'bg-slate-100 text-slate-500'
                )}
                title={`${t('mcp.approval', 'Approval required')} (${comingSoon})`}
              >
                <ShieldCheck size={12} className="inline mr-1" />
                {comingSoon}
              </span>
            </div>
            <p className={clsx(muted, 'line-clamp-2')}>{tool.description || '—'}</p>
            {tool.input_schema && (
              <pre className={clsx(
                'mt-3 rounded-md px-3 py-2 text-xs overflow-x-auto',
                theme === 'dark' ? 'bg-slate-800 text-slate-400' : 'bg-slate-50 text-slate-600'
              )}>
                {JSON.stringify(tool.input_schema, null, 2)}
              </pre>
            )}
          </div>
        ))}
        {legacyTools.length === 0 && discovered.length === 0 && !loading && (
          <div className={clsx('col-span-full text-center py-8', muted)}>
            {t('mcp.noTools', 'No MCP tools available')}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Health & Audit tab ──────────────────────────────────────────────────────

const HealthTab: React.FC<TabProps> = ({ theme, card, muted, heading, input, errBox, setError }) => {
  const { t } = useI18n()
  const [health, setHealth] = useState<McpHealthResponse | null>(null)
  const [status, setStatus] = useState<McpStatusResponse | null>(null)
  const [cmHealth, setCmHealth] = useState<Record<string, any> | null>(null)
  const [auditEntries, setAuditEntries] = useState<Array<Record<string, any>>>([])
  const [auditCount, setAuditCount] = useState(0)
  const [category, setCategory] = useState('')
  const [permissions, setPermissions] = useState<Record<string, boolean> | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [permBusy, setPermBusy] = useState(false)

  const loadHealth = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const [h, s, cm] = await Promise.allSettled([
        mcpOps.healthCheck(),
        mcpOps.getStatus(),
        mcpOps.cmHealthCheck(),
      ])
      if (h.status === 'fulfilled') setHealth(h.value)
      else setHealth(null)
      if (s.status === 'fulfilled') setStatus(s.value)
      else setStatus(null)
      if (cm.status === 'fulfilled') setCmHealth(cm.value)
      else setCmHealth(null)
      if (h.status === 'rejected' && s.status === 'rejected') {
        const msg = h.reason instanceof Error ? h.reason.message : 'Failed to load health'
        setLoadError(msg)
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }, [setError])

  const loadAudit = useCallback(async (cat: string) => {
    try {
      const resp = await mcpOps.getAuditLogs(cat || undefined)
      setAuditEntries(resp.entries ?? [])
      setAuditCount(resp.count ?? 0)
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to load audit logs'
      setLoadError(msg)
      setError(msg)
    }
  }, [setError])

  const loadPermissions = useCallback(async (cat: string) => {
    if (!cat) {
      setPermissions(null)
      return
    }
    try {
      const resp = await mcpOps.getPermissions(cat)
      setPermissions(resp)
    } catch {
      setPermissions(null)
    }
  }, [])

  useEffect(() => {
    loadHealth()
    loadAudit('')
  }, [loadHealth, loadAudit])

  useEffect(() => {
    loadAudit(category)
    loadPermissions(category)
  }, [category, loadAudit, loadPermissions])

  const handlePermissionToggle = async (perm: string, value: boolean) => {
    if (!category || !permissions) return
    const next = { ...permissions, [perm]: value }
    setPermBusy(true)
    try {
      await mcpOps.updatePermissions(category, next)
      setPermissions(next)
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to update permissions'
      setLoadError(msg)
      setError(msg)
    } finally {
      setPermBusy(false)
    }
  }

  const statusBadge = (ok: boolean) => clsx(
    'px-2 py-0.5 rounded-full text-xs font-medium',
    ok ? 'bg-green-500/10 text-green-600' : 'bg-red-500/10 text-red-600'
  )

  return (
    <div>
      {loadError && <div role="alert" className={errBox}>{loadError}</div>}

      <div className="flex items-center justify-between mb-4">
        <h2 className={heading}>{t('mcp.healthCheck', 'Health Check')}</h2>
        <button
          onClick={loadHealth}
          disabled={loading}
          className={clsx(
            'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
            theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
          )}
          aria-label={t('common.refresh', 'Refresh')}
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          {t('common.refresh', 'Refresh')}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {/* Adapter health */}
        <div className={card}>
          <div className="flex items-center justify-between mb-3">
            <h3 className={clsx('font-bold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('mcp.adapterHealth', 'Adapter')}
            </h3>
            {health && (
              <span className={statusBadge(health.status === 'healthy')}>
                {health.status}
              </span>
            )}
          </div>
          {health ? (
            <div className="space-y-1">
              {Object.entries(health.components).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className={muted}>{k}</span>
                  <span className={clsx('text-xs font-mono', String(v).includes('error') ? 'text-red-500' : 'text-green-600')}>
                    {String(v).slice(0, 40)}
                  </span>
                </div>
              ))}
              <p className={clsx('text-xs mt-2', muted)}>{health.timestamp}</p>
            </div>
          ) : (
            <p className={muted}>{t('mcp.unavailable', 'Unavailable')}</p>
          )}
        </div>

        {/* Legacy server status */}
        <div className={card}>
          <div className="flex items-center justify-between mb-3">
            <h3 className={clsx('font-bold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('mcp.serverStatus', 'Server')}
            </h3>
            {status && <span className={statusBadge(status.status === 'running')}>{status.status}</span>}
          </div>
          {status ? (
            <div className="space-y-1">
              <p className={muted}>{status.host}:{status.port}</p>
              <p className={muted}>{t('mcp.toolsCount', 'Tools')}: {status.tools_count}</p>
              <p className={clsx('text-xs font-mono break-all', theme === 'dark' ? 'text-slate-500' : 'text-slate-400')}>
                {status.tools.join(', ')}
              </p>
            </div>
          ) : (
            <p className={muted}>{t('mcp.unavailable', 'Unavailable')}</p>
          )}
        </div>

        {/* Client-manager health */}
        <div className={card}>
          <div className="flex items-center justify-between mb-3">
            <h3 className={clsx('font-bold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('mcp.cmHealth', 'Client Manager')}
            </h3>
            {cmHealth && (
              <span className={statusBadge(cmHealth.status === 'healthy' || cmHealth.healthy === true)}>
                {String(cmHealth.status ?? (cmHealth.healthy ? 'healthy' : 'unknown'))}
              </span>
            )}
          </div>
          {cmHealth ? (
            <pre className={clsx(
              'text-xs overflow-x-auto rounded-md px-3 py-2',
              theme === 'dark' ? 'bg-slate-800 text-slate-400' : 'bg-slate-50 text-slate-600'
            )}>
              {JSON.stringify(cmHealth, null, 2).slice(0, 400)}
            </pre>
          ) : (
            <p className={muted}>{t('mcp.unavailable', 'Unavailable')}</p>
          )}
        </div>
      </div>

      {/* Permissions */}
      <div className={clsx(card, 'mb-8')}>
        <div className="flex items-center gap-3 mb-4">
          <ShieldCheck size={18} className="text-blue-500" />
          <h3 className={clsx('font-bold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
            {t('mcp.permissions', 'Tool Permissions')}
          </h3>
          <select
            className={clsx(input, 'w-auto')}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            aria-label={t('mcp.category', 'Tool category')}
          >
            <option value="">{t('mcp.selectCategory', 'Select category...')}</option>
            <option value="file">file</option>
            <option value="search">search</option>
            <option value="browser">browser</option>
          </select>
        </div>
        {permissions ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {Object.entries(permissions).map(([perm, allowed]) => (
              <label
                key={perm}
                className={clsx(
                  'flex items-center justify-between rounded-lg border px-3 py-2 text-sm',
                  theme === 'dark' ? 'border-slate-700' : 'border-slate-200',
                  permBusy && 'opacity-50 pointer-events-none'
                )}
              >
                <span className={theme === 'dark' ? 'text-slate-300' : 'text-slate-700'}>{perm}</span>
                <input
                  type="checkbox"
                  checked={allowed}
                  disabled={permBusy}
                  onChange={(e) => handlePermissionToggle(perm, e.target.checked)}
                  className="w-4 h-4 accent-blue-600"
                  aria-label={perm}
                />
              </label>
            ))}
          </div>
        ) : (
          <p className={muted}>
            {category ? t('mcp.permsUnavailable', 'Permissions unavailable for this category') : t('mcp.permsHint', 'Select a category (file / search / browser) to view and edit permissions')}
          </p>
        )}
      </div>

      {/* Audit logs */}
      <div className={card}>
        <div className="flex items-center gap-3 mb-4">
          <ScrollText size={18} className="text-blue-500" />
          <h3 className={clsx('font-bold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
            {t('mcp.auditLogs', 'Audit Logs')}
          </h3>
          <span className={muted}>({auditCount})</span>
          <button
            onClick={() => loadAudit(category)}
            className={clsx(
              'ml-auto flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors',
              theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            )}
            aria-label={t('common.refresh', 'Refresh')}
          >
            <RefreshCw size={14} />
          </button>
        </div>
        {auditEntries.length === 0 ? (
          <p className={muted}>{t('mcp.noAuditLogs', 'No audit log entries')}</p>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {auditEntries.map((entry, i) => (
              <pre
                key={i}
                className={clsx(
                  'rounded-md px-3 py-2 text-xs overflow-x-auto whitespace-pre-wrap break-all',
                  theme === 'dark' ? 'bg-slate-800 text-slate-400' : 'bg-slate-50 text-slate-600'
                )}
              >
                {JSON.stringify(entry, null, 2)}
              </pre>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default McpManagementPage
