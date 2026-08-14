import React, { useEffect, useState, useCallback } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiClient } from '@/services/api'
import { useI18n } from '@/i18n/context'
import { Play, Plus } from 'lucide-react'
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

const RUN_BADGE: Record<string, string> = {
  completed: 'badge-success',
  running: 'badge-warning',
  failed: 'badge-danger',
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

  return (
    <div className={clsx('min-h-full px-8 py-10', theme === 'dark' ? 'bg-slate-950 text-slate-200' : 'bg-[#fafafa] text-[#333333]')}>
      <div className="max-w-7xl">
        {/* Header — Dashboard-style */}
        <header className="mb-8">
          <div
            className={clsx(
              'w-12 border-t-2 mb-5',
              theme === 'dark' ? 'border-slate-200' : 'border-[#333333]'
            )}
            aria-hidden="true"
          />
          <div className="flex items-end justify-between gap-4">
            <div>
              <h1 className="page-title">{t('workflows.title', 'Workflows')}</h1>
              <p className="page-subtitle">{t('workflows.subtitle', 'DAG-based workflow orchestration')}</p>
            </div>
            <button
              onClick={() => {/* Create workflow modal - coming soon */}}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              <Plus size={16} />
              {t('workflows.create', 'New Workflow')}
            </button>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
          {/* Workflow List — hairline divider rows, 2px active indicator */}
          <div className="lg:col-span-2">
            <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
              {t('workflows.definitions', 'Definitions')} ({workflows.length})
            </h2>
            {workflows.length === 0 ? (
              <p className="empty-state">{t('workflows.empty', 'No workflows defined yet')}</p>
            ) : (
              <div>
                {workflows.map((wf) => (
                  <div
                    key={wf.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedWorkflow(wf)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setSelectedWorkflow(wf); }}
                    className="row-line cursor-pointer"
                    style={
                      selectedWorkflow?.id === wf.id
                        ? { boxShadow: theme === 'dark' ? 'inset 2px 0 0 #e2e8f0' : 'inset 2px 0 0 #333333' }
                        : undefined
                    }
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className={clsx('min-w-0', selectedWorkflow?.id === wf.id && 'pl-2')}>
                        <h3 className="text-[13px] font-medium truncate">{wf.name}</h3>
                        <p className="cell-data opacity-50 mt-0.5 truncate">
                          {wf.description || `${wf.nodes?.length || 0} nodes · ${wf.edges?.length || 0} edges`}
                        </p>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleRun(wf.id) }}
                        className="flex items-center gap-1 px-2.5 py-1 text-[12px] shrink-0 text-[#16a34a] border border-current rounded-full hover:opacity-80 transition-opacity"
                      >
                        <Play size={12} />
                        Run
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent Runs — hairline divider rows */}
          <div>
            <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
              {t('workflows.recentRuns', 'Recent Runs')}
            </h2>
            {runs.length === 0 ? (
              <p className="empty-state">{t('workflows.noRuns', 'No workflow runs yet')}</p>
            ) : (
              <div>
                {runs.slice(0, 10).map((run) => (
                  <div key={run.run_id} className="row-line">
                    <div className="flex items-center gap-2">
                      <span className={clsx('badge-status shrink-0', RUN_BADGE[run.status] ?? 'badge-muted')}>
                        {run.status}
                      </span>
                      <span className="text-[13px] font-medium truncate">
                        {run.workflow_name || run.workflow_id}
                      </span>
                    </div>
                    <div className="cell-data opacity-40 mt-1">
                      {run.run_id.slice(0, 8)}
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
