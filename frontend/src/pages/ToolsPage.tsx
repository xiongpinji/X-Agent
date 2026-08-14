import React, { useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiClient, Tool } from '@/services/api'
import { useI18n } from '@/i18n/context'
import { Settings, Play, ToggleLeft, ToggleRight } from 'lucide-react'
import clsx from 'clsx'

export const ToolsPage: React.FC = () => {
  const { theme, tools, setTools, isLoading, setLoading, setError } = useAppStore()
  const { t } = useI18n()
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    loadTools()
  }, [])

  const loadTools = async () => {
    try {
      setLoading(true)
      setLoadError(null)
      const data = await apiClient.listTools()
      setTools(data)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load tools'
      setLoadError(message)
      setError(message)
    } finally {
      setLoading(false)
    }
  }

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
          <h1 className="page-title">{t('tools.title', 'Tools')}</h1>
          <p className="page-subtitle">{t('tools.subtitle', 'Manage and configure available tools')}</p>
        </header>

        {loadError && (
          <div
            role="alert"
            className={clsx(
              'mb-6 rounded-lg border px-4 py-3 text-sm',
              theme === 'dark'
                ? 'border-red-900 bg-red-950/40 text-red-300'
                : 'border-red-200 bg-red-50 text-red-700'
            )}
          >
            {loadError}
          </div>
        )}

        {/* Tools Table — dense, hairline dividers */}
        {tools.length === 0 && !isLoading && !loadError ? (
          <p className="empty-state">
            {t('tools.noTools', 'No tools available')} · {t('tools.toolsAppear', 'Tools will appear here once configured')}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-dense">
              <thead>
                <tr>
                  <th>{t('tools.col.name', 'Name')}</th>
                  <th>{t('tools.riskLevel', 'Risk level')}</th>
                  <th>{t('tools.col.description', 'Description')}</th>
                  <th>{t('tools.col.status', 'Status')}</th>
                  <th className="ta-right">{t('common.actions', 'Actions')}</th>
                </tr>
              </thead>
              <tbody>
                {tools.map((tool) => (
                  <ToolRow key={tool.id} tool={tool} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

interface ToolRowProps {
  tool: Tool
}

const ToolRow: React.FC<ToolRowProps> = ({ tool }) => {
  const { theme } = useAppStore()
  const { t } = useI18n()

  // PUT /api/v1/tools/{name} and POST /api/v1/tools/{name}/test exist in the
  // backend — toggle and test are wired. Free-form config editing stays
  // disabled because the manifest exposes no config schema.
  const [enabled, setEnabled] = useState(true)
  const [busy, setBusy] = useState(false)
  const [testResult, setTestResult] = useState<{ status: string; detail: string } | null>(null)
  const comingSoon = t('common.comingSoon', 'Coming soon')

  const handleToggle = async () => {
    const next = !enabled
    setBusy(true)
    try {
      const resp = await apiClient.updateTool(tool.name, { enabled: next })
      setEnabled(typeof resp?.enabled === 'boolean' ? resp.enabled : next)
    } catch (error) {
      console.error('Failed to toggle tool:', error)
      setTestResult({ status: 'error', detail: error instanceof Error ? error.message : 'Toggle failed' })
    } finally {
      setBusy(false)
    }
  }

  const handleTest = async () => {
    setBusy(true)
    setTestResult(null)
    try {
      const resp = await apiClient.testTool(tool.name, {})
      if (resp?.status === 'success') {
        setTestResult({ status: 'success', detail: JSON.stringify(resp?.result ?? {}).slice(0, 300) })
      } else {
        setTestResult({ status: 'error', detail: String(resp?.error ?? 'Unknown error') })
      }
    } catch (error) {
      setTestResult({ status: 'error', detail: error instanceof Error ? error.message : 'Test failed' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <tr>
      <td className="cell-data font-medium">{tool.name}</td>
      <td>
        <span className="cell-data opacity-70">{tool.riskLevel}</span>
      </td>
      <td className="max-w-md">
        <span className="truncate-lines-1 opacity-70">{tool.description}</span>
        {testResult && (
          <span
            role="status"
            title={testResult.detail || testResult.status}
            className={clsx(
              'badge-status ml-2',
              testResult.status === 'success' ? 'badge-success' : 'badge-danger'
            )}
          >
            {testResult.status}
          </span>
        )}
      </td>
      <td>
        <button
          onClick={handleToggle}
          disabled={busy}
          className={clsx(
            'inline-flex items-center transition-opacity disabled:opacity-50',
            enabled ? 'text-[#16a34a]' : 'opacity-40'
          )}
          title={enabled ? t('tools.disable', 'Disable') : t('tools.enable', 'Enable')}
          aria-label={enabled ? t('tools.disable', 'Disable') : t('tools.enable', 'Enable')}
          aria-pressed={enabled}
        >
          {enabled ? <ToggleRight size={18} /> : <ToggleLeft size={18} />}
        </button>
      </td>
      <td className="ta-right">
        <div className="flex items-center justify-end gap-1">
          <button
            onClick={handleTest}
            disabled={busy}
            className="p-1.5 opacity-50 hover:opacity-100 transition-opacity disabled:opacity-30"
            title={busy ? t('common.loading', 'Loading...') : t('tools.test', 'Test')}
            aria-label={t('tools.test', 'Test')}
          >
            <Play size={15} />
          </button>
          <button
            disabled
            className="p-1.5 opacity-30 cursor-not-allowed"
            title={`${t('tools.configure', 'Config')} (${comingSoon})`}
            aria-label={`${t('tools.configure', 'Config')} (${comingSoon})`}
          >
            <Settings size={15} />
          </button>
        </div>
      </td>
    </tr>
  )
}

export default ToolsPage
