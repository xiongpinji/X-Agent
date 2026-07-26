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
      'p-8',
      theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50'
    )}>
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className={clsx(
            'text-3xl font-bold mb-2',
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          )}>
            {t('tools.title', 'Tools')}
          </h1>
          <p className={clsx(
            'text-sm',
            theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
          )}>
            {t('tools.subtitle', 'Manage and configure available tools')}
          </p>
        </div>

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

        {/* Tools Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {tools.map((tool) => (
            <ToolCard key={tool.id} tool={tool} />
          ))}
        </div>

        {tools.length === 0 && !isLoading && !loadError && (
          <div className={clsx(
            'text-center py-12',
            theme === 'dark' ? 'text-slate-400' : 'text-slate-500'
          )}>
            <p className="text-lg font-medium mb-2">{t('tools.noTools', 'No tools available')}</p>
            <p className="text-sm">{t('tools.toolsAppear', 'Tools will appear here once configured')}</p>
          </div>
        )}
      </div>
    </div>
  )
}

interface ToolCardProps {
  tool: Tool
}

const ToolCard: React.FC<ToolCardProps> = ({ tool }) => {
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
    <div className={clsx(
      'rounded-lg p-6 transition-all',
      theme === 'dark'
        ? 'bg-slate-900 border border-slate-700 hover:border-slate-600'
        : 'bg-white border border-slate-200 hover:border-slate-300'
    )}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className={clsx(
            'text-lg font-bold mb-1',
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          )}>
            {tool.name}
          </h3>
          <p className={clsx(
            'text-sm',
            theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
          )}>
            {t('tools.riskLevel', 'Risk level')}: {tool.riskLevel}
          </p>
        </div>
        <button
          onClick={handleToggle}
          disabled={busy}
          className={clsx(
            'p-2 rounded-lg transition-colors disabled:opacity-50',
            enabled
              ? 'bg-green-500/10 text-green-600 hover:bg-green-500/20'
              : 'bg-slate-500/10 text-slate-600 hover:bg-slate-500/20'
          )}
          title={enabled ? t('tools.disable', 'Disable') : t('tools.enable', 'Enable')}
          aria-label={enabled ? t('tools.disable', 'Disable') : t('tools.enable', 'Enable')}
          aria-pressed={enabled}
        >
          {enabled ? <ToggleRight size={20} /> : <ToggleLeft size={20} />}
        </button>
      </div>

      {/* Description */}
      <p className={clsx(
        'text-sm mb-4 line-clamp-2',
        theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
      )}>
        {tool.description}
      </p>

      {/* Test result */}
      {testResult && (
        <div className={clsx(
          'mb-4 rounded-md border px-3 py-2 text-xs break-words',
          testResult.status === 'success'
            ? theme === 'dark' ? 'border-green-900 bg-green-950/40 text-green-300' : 'border-green-200 bg-green-50 text-green-700'
            : theme === 'dark' ? 'border-red-900 bg-red-950/40 text-red-300' : 'border-red-200 bg-red-50 text-red-700'
        )} role="status">
          {testResult.detail || testResult.status}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={handleTest}
          disabled={busy}
          className={clsx(
            'flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
            theme === 'dark'
              ? 'bg-blue-600/20 text-blue-400 hover:bg-blue-600/30'
              : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
          )}
          title={t('tools.test', 'Test')}
          aria-label={t('tools.test', 'Test')}
        >
          <Play size={16} />
          {busy ? t('common.loading', 'Loading...') : t('tools.test', 'Test')}
        </button>
        <button
          disabled
          className={clsx(
            'flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors opacity-50 cursor-not-allowed',
            theme === 'dark'
              ? 'bg-slate-700 text-slate-300'
              : 'bg-slate-200 text-slate-700'
          )}
          title={`${t('tools.configure', 'Config')} (${comingSoon})`}
          aria-label={`${t('tools.configure', 'Config')} (${comingSoon})`}
        >
          <Settings size={16} />
          {t('tools.configure', 'Config')}
        </button>
      </div>
    </div>
  )
}

export default ToolsPage
