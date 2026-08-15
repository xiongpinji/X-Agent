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
  Plus,
  Trash2,
  RefreshCw,
  PlugZap,
} from 'lucide-react'
import clsx from 'clsx'

type TabKey = 'servers' | 'tools' | 'health'

const DIVIDER = 'var(--divider)'

export const McpManagementPage: React.FC = () => {
  const { theme, setError } = useAppStore()
  const { t } = useI18n()
  const [tab, setTab] = useState<TabKey>('servers')

  const input = clsx(
    'w-full px-3 py-2 rounded-lg border text-sm outline-none transition-colors',
    theme === 'dark'
      ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-blue-500'
      : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-blue-500'
  )
  const errBox = clsx(
    'mb-6 rounded-lg border px-4 py-3 text-sm',
    'border-[#dc2626]/30 text-[#dc2626]'
  )

  const tabs: Array<{ key: TabKey; label: string }> = [
    { key: 'servers', label: t('mcp.servers', 'Servers') },
    { key: 'tools', label: t('mcp.tools', 'Tools') },
    { key: 'health', label: t('mcp.healthAudit', 'Health & Audit') },
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
          <h1 className="page-title">{t('mcp.title', 'MCP Management')}</h1>
          <p className="page-subtitle">
            {t('mcp.subtitle', 'Manage MCP servers, discovered tools, health and audit logs')}
          </p>
        </header>

        {/* Tabs — underline style */}
        <div className="flex gap-1 mb-8 border-b" style={{ borderColor: DIVIDER }} role="tablist">
          {tabs.map((tb) => (
            <button
              key={tb.key}
              role="tab"
              aria-selected={tab === tb.key}
              onClick={() => setTab(tb.key)}
              className={clsx(
                'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
                tab === tb.key
                  ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                  : 'border-transparent opacity-50 hover:opacity-100'
              )}
            >
              {tb.label}
            </button>
          ))}
        </div>

        {tab === 'servers' && (
          <ServersTab theme={theme} input={input} errBox={errBox} setError={setError} />
        )}
        {tab === 'tools' && (
          <ToolsTab theme={theme} errBox={errBox} setError={setError} />
        )}
        {tab === 'health' && (
          <HealthTab theme={theme} input={input} errBox={errBox} setError={setError} />
        )}
      </div>
    </div>
  )
}

// ─── Shared tab props ────────────────────────────────────────────────────────

interface TabProps {
  theme: 'light' | 'dark'
  input?: string
  errBox: string
  setError: (e: string | null) => void
}

const ghostBtn = (theme: 'light' | 'dark') => clsx(
  'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
  theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
)

// ─── Servers tab ─────────────────────────────────────────────────────────────

const ServersTab: React.FC<TabProps> = ({ theme, input, errBox, setError }) => {
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

  const labelCls = 'block text-[13px] opacity-60 mb-1'

  return (
    <div>
      {loadError && <div role="alert" className={errBox}>{loadError}</div>}

      <div className="flex items-center justify-between mb-2">
        <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50">
          {t('mcp.serverList', 'MCP Servers')}
        </h2>
        <div className="flex gap-2">
          <button
            onClick={load}
            disabled={loading}
            className={ghostBtn(theme)}
            aria-label={t('common.refresh', 'Refresh')}
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            {t('common.refresh', 'Refresh')}
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Plus size={16} />
            {t('mcp.addServer', 'Add Server')}
          </button>
        </div>
      </div>

      {!mcpEnabled && (
        <div className="mb-4 rounded-lg border border-[#d97706]/30 px-4 py-3 text-sm text-[#d97706]">
          {t('mcp.disabled', 'MCP manager not initialized (XAGENT_MCP_ENABLED=false or no config)')}
        </div>
      )}

      {/* Discovery-layer servers — divider rows */}
      <div className="mb-8">
        {servers.map((s) => (
          <div key={s.name} className="row-line flex items-center justify-between gap-4" style={{ padding: '14px 0' }}>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="font-medium text-sm truncate">{s.name}</h3>
                <span className={clsx('badge-status', s.connected ? 'badge-success' : 'badge-muted')}>
                  {s.connected ? t('mcp.connected', 'Connected') : t('mcp.disconnected', 'Disconnected')}
                </span>
              </div>
              <p className="cell-data opacity-50 mt-1">{t('mcp.transport', 'Transport')}: {s.transport}</p>
            </div>
            {/* Backend exposes no delete for discovery-layer servers; only
                client-manager connections can be disconnected. */}
            <button
              disabled
              title={`${t('mcp.removeServer', 'Remove')} (${comingSoon})`}
              aria-label={`${t('mcp.removeServer', 'Remove')} (${comingSoon})`}
              className={clsx(ghostBtn(theme), 'opacity-50 cursor-not-allowed shrink-0')}
            >
              <Trash2 size={16} />
              {t('mcp.removeServer', 'Remove')} ({comingSoon})
            </button>
          </div>
        ))}
        {servers.length === 0 && cmServers.length === 0 && !loading && (
          <p className="empty-state">
            {t('mcp.noServers', 'No MCP servers configured')}
          </p>
        )}
      </div>

      {/* Client-manager connections */}
      {cmServers.length > 0 && (
        <>
          <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
            {t('mcp.cmServers', 'Client-Manager Connections')}
          </h2>
          <div className="mb-8">
            {cmServers.map((s, i) => {
              const id = String(s.server_id ?? s.name ?? i)
              return (
                <div key={id} className="row-line flex items-center justify-between gap-4" style={{ padding: '14px 0' }}>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium text-sm truncate">
                        {String(s.name ?? s.server_id ?? id)}
                      </h3>
                      <span className={clsx('badge-status', s.connected ? 'badge-success' : 'badge-muted')}>
                        {s.connected ? t('mcp.connected', 'Connected') : t('mcp.disconnected', 'Disconnected')}
                      </span>
                    </div>
                    {s.transport && (
                      <p className="cell-data opacity-50 mt-1">{t('mcp.transport', 'Transport')}: {String(s.transport)}</p>
                    )}
                  </div>
                  <button
                    onClick={() => handleDisconnect(id)}
                    disabled={busy}
                    className="p-1.5 text-[#dc2626] opacity-60 hover:opacity-100 transition-opacity disabled:opacity-30 shrink-0"
                    aria-label={t('mcp.disconnect', 'Disconnect')}
                    title={t('mcp.disconnect', 'Disconnect')}
                  >
                    <Trash2 size={16} />
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
          <div className={clsx(
            'rounded-lg p-6 border w-full max-w-lg max-h-[90vh] overflow-y-auto',
            theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
          )}>
            <h3 className="text-lg font-medium mb-4">{t('mcp.addServer', 'Add Server')}</h3>
            <div className="space-y-3">
              <div>
                <label className={labelCls}>{t('mcp.serverName', 'Name')}</label>
                <input className={input} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="my-mcp-server" />
              </div>
              <div>
                <label className={labelCls}>{t('mcp.transport', 'Transport')}</label>
                <select className={input} value={form.transport} onChange={(e) => setForm({ ...form, transport: e.target.value })}>
                  <option value="http">HTTP</option>
                  <option value="stdio">stdio</option>
                </select>
              </div>
              {form.transport === 'http' ? (
                <>
                  <div>
                    <label className={labelCls}>URL</label>
                    <input className={input} value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="http://localhost:8001" />
                  </div>
                  <div>
                    <label className={labelCls}>{t('mcp.headers', 'Headers (JSON, optional)')}</label>
                    <input className={input} value={form.headers} onChange={(e) => setForm({ ...form, headers: e.target.value })} placeholder='{"Authorization": "Bearer ..."}' />
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label className={labelCls}>{t('mcp.command', 'Command')}</label>
                    <input className={input} value={form.command} onChange={(e) => setForm({ ...form, command: e.target.value })} placeholder="npx" />
                  </div>
                  <div>
                    <label className={labelCls}>{t('mcp.args', 'Args (space-separated)')}</label>
                    <input className={input} value={form.args} onChange={(e) => setForm({ ...form, args: e.target.value })} placeholder="-y @modelcontextprotocol/server-everything" />
                  </div>
                  <div>
                    <label className={labelCls}>{t('mcp.env', 'Env (JSON, optional)')}</label>
                    <input className={input} value={form.env} onChange={(e) => setForm({ ...form, env: e.target.value })} placeholder='{"KEY": "value"}' />
                  </div>
                </>
              )}
              <div>
                <label className={labelCls}>{t('mcp.timeout', 'Timeout (seconds)')}</label>
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

const ToolsTab: React.FC<TabProps> = ({ theme, errBox, setError }) => {
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

      <div className="flex items-center justify-between mb-2">
        <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50">
          {t('mcp.toolInventory', 'Tool Inventory')}
        </h2>
        <button
          onClick={load}
          disabled={loading}
          className={ghostBtn(theme)}
          aria-label={t('common.refresh', 'Refresh')}
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          {t('common.refresh', 'Refresh')}
        </button>
      </div>

      {/* Discovered tools (official SDK) */}
      {discovered.length > 0 && (
        <>
          <h3 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2 mt-6">
            {t('mcp.discoveredTools', 'Discovered (MCP SDK)')}
          </h3>
          <div className="mb-8">
            {discovered.map((tool) => {
              const key = `${tool.server}/${tool.name}`
              return (
                <div key={key} className="row-line" style={{ padding: '16px 0' }}>
                  <div className="flex items-start justify-between gap-4 mb-1">
                    <div className="min-w-0">
                      <h4 className="font-medium text-sm">{tool.name}</h4>
                      <p className="cell-data opacity-50">{t('mcp.server', 'Server')}: {tool.server}</p>
                    </div>
                    {/* Backend does not expose risk level / approval flags for MCP tools */}
                    <span
                      className="badge-status badge-muted shrink-0"
                      title={`${t('mcp.riskLevel', 'Risk level')} / ${t('mcp.approval', 'Approval')} (${comingSoon})`}
                    >
                      {t('mcp.riskLevel', 'Risk')}: —
                    </span>
                  </div>
                  <p className="text-[13px] opacity-60 mb-2 line-clamp-2">{tool.description || '—'}</p>
                  <p className="cell-data opacity-50 mb-2">
                    {tool.registered_name}
                  </p>
                  {invokeResult?.key === key && (
                    <pre className={clsx(
                      'mb-3 rounded-lg border px-3 py-2 text-xs overflow-x-auto whitespace-pre-wrap break-all',
                      invokeResult.ok
                        ? 'border-[#16a34a]/30 text-[#16a34a]'
                        : 'border-[#dc2626]/30 text-[#dc2626]'
                    )} role="status">
                      {invokeResult.text}
                    </pre>
                  )}
                  <button
                    onClick={() => handleInvoke(tool)}
                    disabled={busyKey === key}
                    className={ghostBtn(theme)}
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
      <h3 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
        {t('mcp.legacyTools', 'Registered (Legacy Server)')}
      </h3>
      <div>
        {legacyTools.map((tool) => (
          <div key={tool.name} className="row-line" style={{ padding: '16px 0' }}>
            <div className="flex items-start justify-between gap-4 mb-1">
              <h4 className="font-medium text-sm">{tool.name}</h4>
              <span
                className="badge-status badge-muted shrink-0"
                title={`${t('mcp.approval', 'Approval required')} (${comingSoon})`}
              >
                {comingSoon}
              </span>
            </div>
            <p className="text-[13px] opacity-60 line-clamp-2">{tool.description || '—'}</p>
            {tool.input_schema && (
              <pre className="mt-2 cell-data opacity-60 overflow-x-auto whitespace-pre-wrap break-all">
                {JSON.stringify(tool.input_schema, null, 2)}
              </pre>
            )}
          </div>
        ))}
        {legacyTools.length === 0 && discovered.length === 0 && !loading && (
          <p className="empty-state">
            {t('mcp.noTools', 'No MCP tools available')}
          </p>
        )}
      </div>
    </div>
  )
}

// ─── Health & Audit tab ──────────────────────────────────────────────────────

const HealthTab: React.FC<TabProps> = ({ theme, input, errBox, setError }) => {
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

  const statusBadge = (ok: boolean) => clsx('badge-status', ok ? 'badge-success' : 'badge-danger')

  return (
    <div>
      {loadError && <div role="alert" className={errBox}>{loadError}</div>}

      <div className="flex items-center justify-between mb-2">
        <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50">
          {t('mcp.healthCheck', 'Health Check')}
        </h2>
        <button
          onClick={loadHealth}
          disabled={loading}
          className={ghostBtn(theme)}
          aria-label={t('common.refresh', 'Refresh')}
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          {t('common.refresh', 'Refresh')}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-10">
        {/* Adapter health */}
        <section>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-[11px] uppercase tracking-[0.08em] opacity-50">
              {t('mcp.adapterHealth', 'Adapter')}
            </h3>
            {health && (
              <span className={statusBadge(health.status === 'healthy')}>
                {health.status}
              </span>
            )}
          </div>
          {health ? (
            <div className="font-data text-[13px]">
              {Object.entries(health.components).map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3 py-1.5 border-b" style={{ borderColor: DIVIDER }}>
                  <span className="opacity-50">{k}</span>
                  <span className={clsx('text-[12px]', String(v).includes('error') ? 'text-[#dc2626]' : 'text-[#16a34a]')}>
                    {String(v).slice(0, 40)}
                  </span>
                </div>
              ))}
              <p className="cell-data opacity-50 mt-2">{health.timestamp}</p>
            </div>
          ) : (
            <p className="empty-state">{t('mcp.unavailable', 'Unavailable')}</p>
          )}
        </section>

        {/* Legacy server status */}
        <section>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-[11px] uppercase tracking-[0.08em] opacity-50">
              {t('mcp.serverStatus', 'Server')}
            </h3>
            {status && <span className={statusBadge(status.status === 'running')}>{status.status}</span>}
          </div>
          {status ? (
            <div className="font-data text-[13px]">
              <div className="flex justify-between gap-3 py-1.5 border-b" style={{ borderColor: DIVIDER }}>
                <span className="opacity-50">endpoint</span>
                <span className="text-[12px]">{status.host}:{status.port}</span>
              </div>
              <div className="flex justify-between gap-3 py-1.5 border-b" style={{ borderColor: DIVIDER }}>
                <span className="opacity-50">{t('mcp.toolsCount', 'Tools')}</span>
                <span className="text-[12px]">{status.tools_count}</span>
              </div>
              <p className="cell-data opacity-50 break-all mt-2">
                {status.tools.join(', ')}
              </p>
            </div>
          ) : (
            <p className="empty-state">{t('mcp.unavailable', 'Unavailable')}</p>
          )}
        </section>

        {/* Client-manager health */}
        <section>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-[11px] uppercase tracking-[0.08em] opacity-50">
              {t('mcp.cmHealth', 'Client Manager')}
            </h3>
            {cmHealth && (
              <span className={statusBadge(cmHealth.status === 'healthy' || cmHealth.healthy === true)}>
                {String(cmHealth.status ?? (cmHealth.healthy ? 'healthy' : 'unknown'))}
              </span>
            )}
          </div>
          {cmHealth ? (
            <pre className="cell-data opacity-60 overflow-x-auto whitespace-pre-wrap break-all">
              {JSON.stringify(cmHealth, null, 2).slice(0, 400)}
            </pre>
          ) : (
            <p className="empty-state">{t('mcp.unavailable', 'Unavailable')}</p>
          )}
        </section>
      </div>

      {/* Permissions */}
      <section className="mb-10">
        <div className="flex items-center gap-3 mb-2">
          <h3 className="text-[11px] uppercase tracking-[0.08em] opacity-50">
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
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
            {Object.entries(permissions).map(([perm, allowed]) => (
              <label
                key={perm}
                className={clsx(
                  'flex items-center justify-between py-2 border-b text-sm',
                  permBusy && 'opacity-50 pointer-events-none'
                )}
                style={{ borderColor: DIVIDER }}
              >
                <span>{perm}</span>
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
          <p className="empty-state">
            {category ? t('mcp.permsUnavailable', 'Permissions unavailable for this category') : t('mcp.permsHint', 'Select a category (file / search / browser) to view and edit permissions')}
          </p>
        )}
      </section>

      {/* Audit logs */}
      <section>
        <div className="flex items-center gap-3 mb-2">
          <h3 className="text-[11px] uppercase tracking-[0.08em] opacity-50">
            {t('mcp.auditLogs', 'Audit Logs')} ({auditCount})
          </h3>
          <button
            onClick={() => loadAudit(category)}
            className="ml-auto p-1.5 opacity-50 hover:opacity-100 transition-opacity"
            aria-label={t('common.refresh', 'Refresh')}
          >
            <RefreshCw size={14} />
          </button>
        </div>
        {auditEntries.length === 0 ? (
          <p className="empty-state">{t('mcp.noAuditLogs', 'No audit log entries')}</p>
        ) : (
          <div className="max-h-96 overflow-y-auto">
            {auditEntries.map((entry, i) => (
              <pre
                key={i}
                className="row-line cell-data opacity-70 overflow-x-auto whitespace-pre-wrap break-all"
              >
                {JSON.stringify(entry, null, 2)}
              </pre>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

export default McpManagementPage
