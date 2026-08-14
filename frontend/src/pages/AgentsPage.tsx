import React, { useEffect, useState, useCallback } from 'react'
import { apiClient, Agent } from '@/services/api'
import { useI18n } from '@/i18n/context'
import { useAppStore } from '@/store/appStore'
import clsx from 'clsx'

interface AgentFormData {
  name: string
  capabilities: string[]
  status: 'active' | 'inactive'
}

const AgentsPage: React.FC = () => {
  const { t } = useI18n()
  const { theme } = useAppStore()
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null)
  const [formData, setFormData] = useState<AgentFormData>({ name: '', capabilities: [], status: 'active' })
  const [capabilityInput, setCapabilityInput] = useState('')

  const fetchAgents = useCallback(async () => {
    try {
      setLoading(true)
      const data = await apiClient.listAgents()
      setAgents(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load agents')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAgents()
  }, [fetchAgents])

  const handleCreate = async () => {
    if (!formData.name.trim()) return
    try {
      await apiClient.createAgent(formData)
      setShowCreateModal(false)
      resetForm()
      fetchAgents()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create agent')
    }
  }

  const handleUpdate = async () => {
    if (!editingAgent || !formData.name.trim()) return
    try {
      await apiClient.updateAgent(editingAgent.id, formData)
      setEditingAgent(null)
      resetForm()
      fetchAgents()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update agent')
    }
  }

  const handleDelete = async (id: string) => {
    if (!window.confirm(t('agents.confirmDelete', 'Are you sure you want to delete this agent?'))) return
    try {
      await apiClient.deleteAgent(id)
      fetchAgents()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete agent')
    }
  }

  const handleToggleStatus = async (agent: Agent) => {
    try {
      await apiClient.updateAgent(agent.id, {
        status: agent.status === 'active' ? 'inactive' : 'active',
      })
      fetchAgents()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle agent status')
    }
  }

  const openEdit = (agent: Agent) => {
    setEditingAgent(agent)
    setFormData({
      name: agent.name,
      capabilities: agent.capabilities,
      status: agent.status,
    })
  }

  const resetForm = () => {
    setFormData({ name: '', capabilities: [], status: 'active' })
    setCapabilityInput('')
  }

  const addCapability = () => {
    const cap = capabilityInput.trim()
    if (cap && !formData.capabilities.includes(cap)) {
      setFormData(prev => ({ ...prev, capabilities: [...prev.capabilities, cap] }))
      setCapabilityInput('')
    }
  }

  const removeCapability = (cap: string) => {
    setFormData(prev => ({
      ...prev,
      capabilities: prev.capabilities.filter(c => c !== cap),
    }))
  }

  const isDark = theme === 'dark'

  return (
    <div className={clsx(
      'min-h-full px-8 py-10',
      isDark ? 'bg-slate-950 text-slate-200' : 'bg-[#fafafa] text-[#333333]'
    )}>
      <div className="max-w-6xl">
        {/* Header — Dashboard-style */}
        <header className="mb-8">
          <div
            className={clsx(
              'w-12 border-t-2 mb-5',
              isDark ? 'border-slate-200' : 'border-[#333333]'
            )}
            aria-hidden="true"
          />
          <div className="flex items-end justify-between gap-4">
            <div>
              <h1 className="page-title">{t('agents.title', 'Agents')}</h1>
              <p className="page-subtitle">{t('agents.subtitle', 'Manage your AI agents and their capabilities')}</p>
            </div>
            <button
              onClick={() => { resetForm(); setShowCreateModal(true) }}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
              aria-label={t('agents.create', 'Create Agent')}
            >
              + {t('agents.create', 'Create Agent')}
            </button>
          </div>
        </header>

        {/* Error */}
        {error && (
          <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300 text-sm" role="alert">
            {error}
            <button onClick={() => setError(null)} className="ml-2 underline">{t('common.dismiss', 'Dismiss')}</button>
          </div>
        )}

        {/* Loading */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500" role="status" aria-label="Loading" />
          </div>
        ) : agents.length === 0 ? (
          <p className="empty-state">
            {t('agents.empty', 'No agents yet. Create your first agent to get started.')}
          </p>
        ) : (
          /* Agents Table — dense, hairline dividers */
          <div className="overflow-x-auto">
            <table className="table-dense">
              <thead>
                <tr>
                  <th>{t('agents.name', 'Name')}</th>
                  <th>{t('agents.status', 'Status')}</th>
                  <th>{t('agents.capabilities', 'Capabilities')}</th>
                  <th className="ta-right">{t('common.actions', 'Actions')}</th>
                </tr>
              </thead>
              <tbody>
                {agents.map(agent => (
                  <tr key={agent.id}>
                    <td className="font-medium">{agent.name}</td>
                    <td>
                      <span className={clsx('badge-status', agent.status === 'active' ? 'badge-success' : 'badge-muted')}>
                        {agent.status === 'active' ? t('agents.active', 'Active') : t('agents.inactive', 'Inactive')}
                      </span>
                    </td>
                    <td className="max-w-md">
                      {agent.capabilities.length > 0 ? (
                        <span className="cell-data opacity-70">{agent.capabilities.join(', ')}</span>
                      ) : (
                        <span className="text-[11px] opacity-40 italic">{t('agents.noCapabilities', 'No capabilities defined')}</span>
                      )}
                    </td>
                    <td className="ta-right">
                      <div className="flex items-center justify-end gap-3 text-[12px]">
                        <button
                          onClick={() => handleToggleStatus(agent)}
                          className="opacity-60 hover:opacity-100 transition-opacity"
                        >
                          {agent.status === 'active' ? t('agents.deactivate', 'Deactivate') : t('agents.activate', 'Activate')}
                        </button>
                        <button
                          onClick={() => openEdit(agent)}
                          className="opacity-60 hover:opacity-100 transition-opacity"
                        >
                          {t('common.edit', 'Edit')}
                        </button>
                        <button
                          onClick={() => handleDelete(agent.id)}
                          className="text-[#dc2626] opacity-60 hover:opacity-100 transition-opacity"
                        >
                          {t('common.delete', 'Delete')}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {(showCreateModal || editingAgent) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true">
          <div className={clsx(
            'w-full max-w-md p-6 rounded-xl shadow-xl',
            isDark ? 'bg-slate-900' : 'bg-white'
          )}>
            <h2 className="text-lg font-bold mb-4">
              {editingAgent ? t('agents.editTitle', 'Edit Agent') : t('agents.createTitle', 'Create Agent')}
            </h2>

            {/* Name */}
            <label className="block mb-4">
              <span className="text-sm font-medium">{t('agents.name', 'Name')}</span>
              <input
                type="text"
                value={formData.name}
                onChange={e => setFormData(prev => ({ ...prev, name: e.target.value }))}
                className={clsx(
                  'mt-1 w-full px-3 py-2 rounded-lg border text-sm',
                  isDark ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-slate-300'
                )}
                placeholder={t('agents.namePlaceholder', 'e.g. Research Assistant')}
              />
            </label>

            {/* Capabilities */}
            <label className="block mb-4">
              <span className="text-sm font-medium">{t('agents.capabilities', 'Capabilities')}</span>
              <div className="flex gap-2 mt-1">
                <input
                  type="text"
                  value={capabilityInput}
                  onChange={e => setCapabilityInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCapability() } }}
                  className={clsx(
                    'flex-1 px-3 py-2 rounded-lg border text-sm',
                    isDark ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-slate-300'
                  )}
                  placeholder={t('agents.capabilityPlaceholder', 'e.g. web_search, code_gen')}
                />
                <button
                  onClick={addCapability}
                  className="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
                >
                  +
                </button>
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                {formData.capabilities.map(cap => (
                  <span key={cap} className={clsx(
                    'inline-flex items-center gap-1 text-xs px-2 py-1 rounded',
                    isDark ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'
                  )}>
                    {cap}
                    <button onClick={() => removeCapability(cap)} className="hover:text-red-500" aria-label={`Remove ${cap}`}>×</button>
                  </span>
                ))}
              </div>
            </label>

            {/* Status */}
            <label className="block mb-6">
              <span className="text-sm font-medium">{t('agents.status', 'Status')}</span>
              <select
                value={formData.status}
                onChange={e => setFormData(prev => ({ ...prev, status: e.target.value as 'active' | 'inactive' }))}
                className={clsx(
                  'mt-1 w-full px-3 py-2 rounded-lg border text-sm',
                  isDark ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-slate-300'
                )}
              >
                <option value="active">{t('agents.active', 'Active')}</option>
                <option value="inactive">{t('agents.inactive', 'Inactive')}</option>
              </select>
            </label>

            {/* Actions */}
            <div className="flex justify-end gap-3">
              <button
                onClick={() => { setShowCreateModal(false); setEditingAgent(null); resetForm() }}
                className={clsx(
                  'px-4 py-2 rounded-lg text-sm font-medium',
                  isDark ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                )}
              >
                {t('common.cancel', 'Cancel')}
              </button>
              <button
                onClick={editingAgent ? handleUpdate : handleCreate}
                disabled={!formData.name.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {editingAgent ? t('common.save', 'Save') : t('agents.create', 'Create Agent')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default AgentsPage
