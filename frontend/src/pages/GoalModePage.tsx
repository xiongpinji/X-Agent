import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { useI18n } from '@/i18n/context'
import { useAppStore } from '@/store/appStore'
import clsx from 'clsx'

interface _ParallelTask {
  id: string
  agent_id: string
  task: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress?: number
  result?: string
}

const GoalModePage: React.FC = () => {
  const { t } = useI18n()
  const { theme } = useAppStore()
  const [goals, setGoals] = useState<any[]>([])
  const [newGoal, setNewGoal] = useState('')
  const [loading, setLoading] = useState(false)
  const isDark = theme === 'dark'

  useEffect(() => {
    loadGoals()
  }, [])

  const loadGoals = async () => {
    try {
      const data = await apiClient.getGoals()
      setGoals(data)
    } catch { /* start with empty list */ }
  }

  const createGoal = async () => {
    if (!newGoal.trim()) return
    setLoading(true)
    try {
      const goal = await apiClient.createGoal(newGoal)
      setGoals(prev => [...prev, goal])
      setNewGoal('')
    } catch {
      // Optimistic add on failure
      setGoals(prev => [...prev, { id: `goal-${Date.now()}`, objective: newGoal, status: 'active', checkpoints: [] }])
      setNewGoal('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">🎯 Goal Mode</h1>
      <p className={clsx('text-sm mb-6', isDark ? 'text-slate-400' : 'text-slate-500')}>
        {t('goals.subtitle', 'Set long-term objectives and let agents work autonomously toward them')}
      </p>

      {/* Create Goal */}
      <div className="flex gap-2 mb-6">
        <input
          type="text"
          value={newGoal}
          onChange={e => setNewGoal(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && createGoal()}
          placeholder={t('goals.placeholder', 'Describe your goal (e.g. "Refactor auth module to use JWT")')}
          className={clsx(
            'flex-1 px-4 py-2.5 rounded-lg border text-sm',
            isDark ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-slate-300'
          )}
        />
        <button
          onClick={createGoal}
          disabled={!newGoal.trim() || loading}
          className="px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? '...' : t('goals.create', 'Create Goal')}
        </button>
      </div>

      {/* Goals List */}
      {goals.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-4xl mb-3">🎯</p>
          <p className={clsx('text-sm', isDark ? 'text-slate-500' : 'text-slate-400')}>
            {t('goals.empty', 'No goals yet. Create one to start autonomous execution.')}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {goals.map(goal => (
            <div key={goal.id} className={clsx(
              'p-4 rounded-xl border',
              isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
            )}>
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-medium text-sm">{goal.objective}</h3>
                <span className={clsx(
                  'text-xs px-2 py-0.5 rounded-full',
                  goal.status === 'active' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                  goal.status === 'completed' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                  'bg-slate-100 text-slate-500 dark:bg-slate-800'
                )}>
                  {goal.status}
                </span>
              </div>
              {/* Checkpoints timeline */}
              <div className="ml-2 border-l-2 border-slate-200 dark:border-slate-700 pl-3 space-y-1">
                {(goal.checkpoints || []).map((cp: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className={cp.done ? 'text-green-500' : 'text-slate-400'}>{cp.done ? '✓' : '○'}</span>
                    <span className={isDark ? 'text-slate-400' : 'text-slate-500'}>{cp.label}</span>
                  </div>
                ))}
                {(!goal.checkpoints || goal.checkpoints.length === 0) && (
                  <p className={clsx('text-xs italic', isDark ? 'text-slate-600' : 'text-slate-400')}>
                    Decomposing goal into checkpoints...
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default GoalModePage
