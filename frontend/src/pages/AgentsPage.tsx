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
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{t('agents.title', 'Agents')}</h1>
          <p className={clsx('text-sm mt-1', isDark ? 'text-slate-400' : 'text-slate-500')}>
            {t('agents.subtitle', 'Manage your AI agents and their capabilities')}
          </p>
        </div>
        <button
          onClick={() => { resetForm(); setShowCreateModal(true) }}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          aria-label={t('agents.create', 'Create Agent')}
        >
          + {t('agents.create', 'Create Agent')}
        </button>
      </div>

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
        <div className="text-center py-20">
          <p className="text-4xl mb-4">🤖</p>
          <p className={clsx('text-lg', isDark ? 'text-slate-400' : 'text-slate-500')}>
            {t('agents.empty', 'No agents yet. Create your first agent to get started.')}
          </p>
        </div>
      ) : (
        /* Agent Grid */
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {agents.map(agent => (
            <div
              key={agent.id}
              className={clsx(
                'p-5 rounded-xl border transition-shadow hover:shadow-md',
                isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
              )}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-lg">
                    🤖
                  </div>
                  <div>
                    <h3 className="font-semibold">{agent.name}</h3>
                    <span className={clsx(
                      'inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full',
                      agent.status === 'active'
                        ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                        : 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400'
                    )}>
                      <span className={clsx('w-1.5 h-1.5 rounded-full', agent.status === 'active' ? 'bg-green-500' : 'bg-slate-400')} />
                      {agent.status === 'active' ? t('agents.active', 'Active') : t('agents.inactive', 'Inactive')}
                    </span>
                  </div>
                </div>
              </div>

              {/* Capabilities */}
              <div className="mb-4">
                <p className={clsx('text-xs font-medium mb-1', isDark ? 'text-slate-500' : 'text-slate-400')}>
                  {t('agents.capabilities', 'Capabilities')}
                </p>
                <div className="flex flex-wrap gap-1">
                  {agent.capabilities.length > 0 ? (
                    agent.capabilities.map(cap => (
                      <span key={cap} className={clsx(
                        'text-xs px-2 py-0.5 rounded',
                        isDark ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'
                      )}>
                        {cap}
                      </span>
                    ))
                  ) : (
                    <span className={clsx('text-xs italic', isDark ? 'text-slate-600' : 'text-slate-400')}>
                      {t('agents.noCapabilities', 'No capabilities defined')}
                    </span>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 pt-3 border-t border-slate-100 dark:border-slate-800">
                <button
                  onClick={() => handleToggleStatus(agent)}
                  className={clsx(
                    'px-3 py-1.5 text-xs rounded-lg font-medium transition-colors',
                    agent.status === 'active'
                      ? 'bg-amber-100 text-amber-700 hover:bg-amber-200 dark:bg-amber-900/30 dark:text-amber-400'
                      : 'bg-green-100 text-green-700 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-400'
                  )}
                >
                  {agent.status === 'active' ? t('agents.deactivate', 'Deactivate') : t('agents.activate', 'Activate')}
                </button>
                <button
                  onClick={() => openEdit(agent)}
                  className={clsx(
                    'px-3 py-1.5 text-xs rounded-lg font-medium transition-colors',
                    isDark ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  )}
                >
                  {t('common.edit', 'Edit')}
                </button>
                <button
                  onClick={() => handleDelete(agent.id)}
                  className="px-3 py-1.5 text-xs rounded-lg font-medium bg-red-50 text-red-600 hover:bg-red-100 dark:bg-red-900/20 dark:text-red-400 transition-colors"
                >
                  {t('common.delete', 'Delete')}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

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
