import React, { useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiClient, Tool } from '@/services/api'
import { Settings, Play, BarChart3, Toggle2 } from 'lucide-react'
import clsx from 'clsx'

export const ToolsPage: React.FC = () => {
  const { theme, tools, setTools, isLoading, setLoading, setError } = useAppStore()
  const [selectedTool, setSelectedTool] = useState<Tool | null>(null)
  const [showTestModal, setShowTestModal] = useState(false)
  const [testParams, setTestParams] = useState<Record<string, any>>({})

  useEffect(() => {
    loadTools()
  }, [])

  const loadTools = async () => {
    try {
      setLoading(true)
      const data = await apiClient.listTools()
      setTools(data)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load tools')
    } finally {
      setLoading(false)
    }
  }

  const handleToggleTool = async (tool: Tool) => {
    try {
      const updated = await apiClient.updateTool(tool.id, {
        enabled: !tool.enabled,
      })
      setTools(tools.map((t) => (t.id === tool.id ? updated : t)))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to update tool')
    }
  }

  const handleTestTool = async () => {
    if (!selectedTool) return

    try {
      setLoading(true)
      const result = await apiClient.testTool(selectedTool.id, testParams)
      alert(`Test result: ${JSON.stringify(result, null, 2)}`)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to test tool')
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
            Tools
          </h1>
          <p className={clsx(
            'text-sm',
            theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
          )}>
            Manage and configure available tools
          </p>
        </div>

        {/* Tools Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {tools.map((tool) => (
            <ToolCard
              key={tool.id}
              tool={tool}
              onToggle={() => handleToggleTool(tool)}
              onTest={() => {
                setSelectedTool(tool)
                setShowTestModal(true)
              }}
              onConfigure={() => {
                setSelectedTool(tool)
              }}
            />
          ))}
        </div>

        {tools.length === 0 && (
          <div className={clsx(
            'text-center py-12',
            theme === 'dark' ? 'text-slate-400' : 'text-slate-500'
          )}>
            <p className="text-lg font-medium mb-2">No tools available</p>
            <p className="text-sm">Tools will appear here once configured</p>
          </div>
        )}
      </div>

      {/* Test Modal */}
      {showTestModal && selectedTool && (
        <ToolTestModal
          tool={selectedTool}
          params={testParams}
          onParamsChange={setTestParams}
          onTest={handleTestTool}
          onClose={() => {
            setShowTestModal(false)
            setSelectedTool(null)
            setTestParams({})
          }}
          isLoading={isLoading}
        />
      )}
    </div>
  )
}

interface ToolCardProps {
  tool: Tool
  onToggle: () => void
  onTest: () => void
  onConfigure: () => void
}

const ToolCard: React.FC<ToolCardProps> = ({ tool, onToggle, onTest, onConfigure }) => {
  const { theme } = useAppStore()

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
            {tool.category}
          </p>
        </div>
        <button
          onClick={onToggle}
          className={clsx(
            'p-2 rounded-lg transition-colors',
            tool.enabled
              ? 'bg-green-500/10 text-green-600'
              : 'bg-slate-500/10 text-slate-600'
          )}
          title={tool.enabled ? 'Disable' : 'Enable'}
        >
          <Toggle2 size={20} />
        </button>
      </div>

      {/* Description */}
      <p className={clsx(
        'text-sm mb-4 line-clamp-2',
        theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
      )}>
        {tool.description}
      </p>

      {/* Stats */}
      {tool.stats && (
        <div className="grid grid-cols-3 gap-2 mb-4 pb-4 border-b border-slate-700">
          <div>
            <p className={clsx(
              'text-xs font-medium',
              theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
            )}>
              Usage
            </p>
            <p className={clsx(
              'text-lg font-bold',
              theme === 'dark' ? 'text-white' : 'text-slate-900'
            )}>
              {tool.stats.usageCount}
            </p>
          </div>
          <div>
            <p className={clsx(
              'text-xs font-medium',
              theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
            )}>
              Success
            </p>
            <p className={clsx(
              'text-lg font-bold',
              theme === 'dark' ? 'text-white' : 'text-slate-900'
            )}>
              {(tool.stats.successRate * 100).toFixed(0)}%
            </p>
          </div>
          <div>
            <p className={clsx(
              'text-xs font-medium',
              theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
            )}>
              Avg Time
            </p>
            <p className={clsx(
              'text-lg font-bold',
              theme === 'dark' ? 'text-white' : 'text-slate-900'
            )}>
              {tool.stats.avgExecutionTime.toFixed(0)}ms
            </p>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={onTest}
          className={clsx(
            'flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
            theme === 'dark'
              ? 'bg-blue-600/20 text-blue-400 hover:bg-blue-600/30'
              : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
          )}
        >
          <Play size={16} />
          Test
        </button>
        <button
          onClick={onConfigure}
          className={clsx(
            'flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
            theme === 'dark'
              ? 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
          )}
        >
          <Settings size={16} />
          Config
        </button>
      </div>
    </div>
  )
}

interface ToolTestModalProps {
  tool: Tool
  params: Record<string, any>
  onParamsChange: (params: Record<string, any>) => void
  onTest: () => void
  onClose: () => void
  isLoading: boolean
}

const ToolTestModal: React.FC<ToolTestModalProps> = ({
  tool,
  params,
  onParamsChange,
  onTest,
  onClose,
  isLoading,
}) => {
  const { theme } = useAppStore()

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className={clsx(
        'rounded-lg p-6 max-w-md w-full mx-4',
        theme === 'dark' ? 'bg-slate-900' : 'bg-white'
      )}>
        <h2 className={clsx(
          'text-2xl font-bold mb-4',
          theme === 'dark' ? 'text-white' : 'text-slate-900'
        )}>
          Test {tool.name}
        </h2>

        <div className="space-y-4 mb-6">
          <div>
            <label className={clsx(
              'block text-sm font-medium mb-2',
              theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
            )}>
              Test Parameters
            </label>
            <textarea
              value={JSON.stringify(params, null, 2)}
              onChange={(e) => {
                try {
                  onParamsChange(JSON.parse(e.target.value))
                } catch {
                  // Invalid JSON, ignore
                }
              }}
              className={clsx(
                'w-full px-3 py-2 rounded-lg text-sm font-mono',
                theme === 'dark'
                  ? 'bg-slate-800 text-white border border-slate-700'
                  : 'bg-slate-50 text-slate-900 border border-slate-300'
              )}
              rows={6}
            />
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={onClose}
            className={clsx(
              'flex-1 px-4 py-2 rounded-lg font-medium transition-colors',
              theme === 'dark'
                ? 'bg-slate-700 hover:bg-slate-600 text-white'
                : 'bg-slate-200 hover:bg-slate-300 text-slate-900'
            )}
          >
            Cancel
          </button>
          <button
            onClick={onTest}
            disabled={isLoading}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {isLoading ? 'Testing...' : 'Test'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ToolsPage
