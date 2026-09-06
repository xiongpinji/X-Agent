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

interface GoalCheckpoint {
  label: string
  done: boolean
}

interface Goal {
  id: string
  objective: string
  status: string
  checkpoints?: GoalCheckpoint[]
}

const GoalModePage: React.FC = () => {
  const { t } = useI18n()
  const { theme } = useAppStore()
  const [goals, setGoals] = useState<Goal[]>([])
  const [newGoal, setNewGoal] = useState('')
  const [loading, setLoading] = useState(false)
  const isDark = theme === 'dark'

  useEffect(() => {
    loadGoals()
  }, [])

  const loadGoals = async () => {
    try {
      const data = (await apiClient.getGoals()) as Goal[]
      setGoals(data)
    } catch { /* start with empty list */ }
  }

  const createGoal = async () => {
    if (!newGoal.trim()) return
    setLoading(true)
    try {
      const goal = (await apiClient.createGoal(newGoal)) as Goal
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
    <div className="min-h-full px-8 py-10">
      <div className={clsx('max-w-4xl', isDark ? 'text-slate-200' : 'text-[#333333]')}>
        {/* Header — Dashboard-style */}
        <header className="mb-8">
          <div
            className={clsx('w-12 border-t-2 mb-5', isDark ? 'border-slate-200' : 'border-[#333333]')}
            aria-hidden="true"
          />
          <h1 className="page-title">Goal Mode</h1>
          <p className="page-subtitle">
            {t('goals.subtitle', 'Set long-term objectives and let agents work autonomously toward them')}
          </p>
        </header>

        {/* Create Goal — single input row, hairline-bordered */}
        <div className="flex gap-2 mb-10 pb-8 border-b" style={{ borderColor: 'var(--divider)' }}>
          <input
            type="text"
            value={newGoal}
            onChange={e => setNewGoal(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && createGoal()}
            placeholder={t('goals.placeholder', 'Describe your goal (e.g. "Refactor auth module to use JWT")')}
            className={clsx(
              'flex-1 px-3 py-2 border text-sm bg-transparent',
              isDark ? 'text-white' : 'text-[#333333]'
            )}
            style={{ borderColor: 'var(--divider)' }}
          />
          <button
            onClick={createGoal}
            disabled={!newGoal.trim() || loading}
            className="px-5 py-2 bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? '...' : t('goals.create', 'Create Goal')}
          </button>
        </div>

        {/* Goals List — hairline rows, no cards */}
        {goals.length === 0 ? (
          <p className="empty-state">
            {t('goals.empty', 'No goals yet. Create one to start autonomous execution.')}
          </p>
        ) : (
          <div>
            {goals.map(goal => (
              <div key={goal.id} className="row-line">
                <div className="flex items-center justify-between gap-4 mb-1.5">
                  <h3 className="font-medium text-sm">{goal.objective}</h3>
                  <span className={clsx(
                    'badge-status whitespace-nowrap',
                    goal.status === 'active' ? 'badge-success' :
                    goal.status === 'completed' ? 'badge-muted' :
                    'badge-muted'
                  )}>
                    {goal.status}
                  </span>
                </div>
                {/* Checkpoints — text checklist */}
                <div className="space-y-1">
                  {(goal.checkpoints || []).map((cp, i: number) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <span className={cp.done ? 'text-[#16a34a]' : 'opacity-40'}>{cp.done ? '✓' : '○'}</span>
                      <span className="opacity-60">{cp.label}</span>
                    </div>
                  ))}
                  {(!goal.checkpoints || goal.checkpoints.length === 0) && (
                    <p className="text-xs opacity-40 italic">
                      Decomposing goal into checkpoints...
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default GoalModePage
