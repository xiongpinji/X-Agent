import React, { useEffect, useState, useCallback } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiClient } from '@/services/api'
import { useI18n } from '@/i18n/context'
import { Play, RefreshCw, Plus, GitBranch, Clock, CheckCircle2, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'

interface Workflow {
  id: string
  name: string
  description?: string
  nodes: any[]
  edges: any[]
  created_at?: string
  updated_at?: string
}

interface WorkflowRun {
  run_id: string
  workflow_id: string
  workflow_name?: string
  status: string
  started_at?: string
  completed_at?: string
  node_results?: Record<string, any>
}

export const WorkflowsPage: React.FC = () => {
  const { theme, setLoading, setError } = useAppStore()
  const { t } = useI18n()
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [runs, setRuns] = useState<WorkflowRun[]>([])
  const [selectedWorkflow, setSelectedWorkflow] = useState<Workflow | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      const [wfList, runList] = await Promise.all([
        apiClient.listWorkflows(),
        apiClient.listWorkflowRuns(),
      ])
      setWorkflows(wfList)
      setRuns(runList)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load workflows')
    } finally {
      setLoading(false)
    }
  }, [setLoading, setError])

  const handleRun = async (workflowId: string) => {
    try {
      await apiClient.runWorkflow(workflowId)
      await loadData()
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to run workflow')
    }
  }

  const statusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle2 size={16} className="text-green-500" />
      case 'running': return <RefreshCw size={16} className="text-blue-500 animate-spin" />
      case 'failed': return <AlertTriangle size={16} className="text-red-500" />
      default: return <Clock size={16} className="text-slate-400" />
    }
  }

  return (
    <div className={clsx('p-8', theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50')}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className={clsx('text-3xl font-bold mb-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('workflows.title', 'Workflows')}
            </h1>
            <p className={clsx('text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
              {t('workflows.subtitle', 'DAG-based workflow orchestration')}
            </p>
          </div>
          <button
            onClick={() => {/* Create workflow modal - coming soon */}}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            <Plus size={18} />
            {t('workflows.create', 'New Workflow')}
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Workflow List */}
          <div className="lg:col-span-2 space-y-4">
            <h2 className={clsx('text-lg font-semibold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('workflows.definitions', 'Definitions')} ({workflows.length})
            </h2>
            {workflows.length === 0 ? (
              <div className={clsx(
                'rounded-lg p-8 text-center',
                theme === 'dark' ? 'bg-slate-900 border border-slate-700 text-slate-400' : 'bg-white border border-slate-200 text-slate-500'
              )}>
                <GitBranch size={40} className="mx-auto mb-3 opacity-50" />
                <p>{t('workflows.empty', 'No workflows defined yet')}</p>
              </div>
            ) : (
              workflows.map((wf) => (
                <div
                  key={wf.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedWorkflow(wf)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setSelectedWorkflow(wf); }}
                  className={clsx(
                    'rounded-lg p-4 cursor-pointer transition-colors border',
                    selectedWorkflow?.id === wf.id
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30'
                      : theme === 'dark'
                        ? 'bg-slate-900 border-slate-700 hover:border-slate-600'
                        : 'bg-white border-slate-200 hover:border-slate-300'
                  )}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className={clsx('font-medium', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                        {wf.name}
                      </h3>
                      <p className={clsx('text-sm mt-1', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
                        {wf.description || `${wf.nodes?.length || 0} nodes · ${wf.edges?.length || 0} edges`}
                      </p>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleRun(wf.id) }}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm bg-green-600 hover:bg-green-700 text-white rounded-md transition-colors"
                    >
                      <Play size={14} />
                      Run
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Recent Runs */}
          <div className="space-y-4">
            <h2 className={clsx('text-lg font-semibold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('workflows.recentRuns', 'Recent Runs')}
            </h2>
            {runs.length === 0 ? (
              <div className={clsx(
                'rounded-lg p-6 text-center text-sm',
                theme === 'dark' ? 'bg-slate-900 border border-slate-700 text-slate-400' : 'bg-white border border-slate-200 text-slate-500'
              )}>
                {t('workflows.noRuns', 'No workflow runs yet')}
              </div>
            ) : (
              <div className="space-y-2">
                {runs.slice(0, 10).map((run) => (
                  <div
                    key={run.run_id}
                    className={clsx(
                      'rounded-lg p-3 border',
                      theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
                    )}
                  >
                    <div className="flex items-center gap-2">
                      {statusIcon(run.status)}
                      <span className={clsx('text-sm font-medium truncate', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                        {run.workflow_name || run.workflow_id}
                      </span>
                    </div>
                    <div className={clsx('text-xs mt-1', theme === 'dark' ? 'text-slate-500' : 'text-slate-400')}>
                      {run.status} · {run.run_id.slice(0, 8)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default WorkflowsPage
