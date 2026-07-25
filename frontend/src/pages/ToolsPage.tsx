import React, { useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiClient, Tool } from '@/services/api'
import { useI18n } from '@/i18n/context'
import { Settings, Play, ToggleLeft } from 'lucide-react'
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

  // The backend exposes only GET /api/v1/tools (read-only manifest); there is
  // no toggle, test, or configure endpoint, so those actions are disabled and
  // explicitly marked "coming soon".
  const comingSoon = t('common.comingSoon', 'Coming soon')

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
          disabled
          className="p-2 rounded-lg transition-colors opacity-50 cursor-not-allowed bg-slate-500/10 text-slate-600"
          title={`${t('tools.configure', 'Configure')} (${comingSoon})`}
          aria-label={`${t('tools.configure', 'Configure')} (${comingSoon})`}
        >
          <ToggleLeft size={20} />
        </button>
      </div>

      {/* Description */}
      <p className={clsx(
        'text-sm mb-4 line-clamp-2',
        theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
      )}>
        {tool.description}
      </p>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          disabled
          className={clsx(
            'flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors opacity-50 cursor-not-allowed',
            theme === 'dark'
              ? 'bg-blue-600/20 text-blue-400'
              : 'bg-blue-100 text-blue-700'
          )}
          title={`${t('tools.test', 'Test')} (${comingSoon})`}
          aria-label={`${t('tools.test', 'Test')} (${comingSoon})`}
        >
          <Play size={16} />
          {t('tools.test', 'Test')}
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
