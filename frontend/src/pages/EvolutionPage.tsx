import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { useAppStore } from '@/store/appStore'
import { useI18n } from '@/i18n/context'
import clsx from 'clsx'

interface EvolutionStats {
  total_tasks: number
  patterns_extracted: number
  skills_promoted: number
}

interface PromotedSkill {
  name: string
  description?: string
  status?: string
  usage_count?: number
  quality_score?: number
  created_at?: string
}

const EvolutionPage: React.FC = () => {
  const { theme } = useAppStore()
  const { t } = useI18n()
  const isDark = theme === 'dark'
  const [stats, setStats] = useState<EvolutionStats>({ total_tasks: 0, patterns_extracted: 0, skills_promoted: 0 })
  const [skills, setSkills] = useState<PromotedSkill[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [statsResult, skillsResult] = await Promise.allSettled([
        apiClient.getEvolutionStats(),
        apiClient.getEvolutionSkills(),
      ])
      if (statsResult.status === 'fulfilled') {
        setStats({
          total_tasks: statsResult.value?.total_tasks ?? 0,
          patterns_extracted: statsResult.value?.patterns_extracted ?? 0,
          skills_promoted: statsResult.value?.skills_promoted ?? 0,
        })
      }
      if (skillsResult.status === 'fulfilled') {
        setSkills(skillsResult.value ?? [])
      }
      if (statsResult.status === 'rejected' && skillsResult.status === 'rejected') {
        setError('Failed to load evolution data')
      }
    } catch {
      setError('Failed to load evolution data')
    } finally {
      setLoading(false)
    }
  }

  const statCards = [
    { label: t('evolution.totalTasks', 'Total Tasks'), value: stats.total_tasks, icon: '📋' },
    { label: t('evolution.patternsExtracted', 'Patterns Extracted'), value: stats.patterns_extracted, icon: '🧩' },
    { label: t('evolution.skillsPromoted', 'Skills Promoted'), value: stats.skills_promoted, icon: '⚡' },
  ]

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-2xl font-bold">🧬 {t('evolution.title', 'Self-Evolution Engine')}</h1>
        <button
          onClick={loadData}
          disabled={loading}
          className={clsx(
            'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
            isDark ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
          )}
        >
          {loading ? '⏳' : '🔄'} {t('common.refresh', 'Refresh')}
        </button>
      </div>
      <p className={clsx('text-sm mb-6', isDark ? 'text-slate-400' : 'text-slate-500')}>
        {t('evolution.subtitle', 'GEPA closed-loop: Generate → Evaluate → Promote → Apply')}
      </p>

      {/* Error */}
      {error && (
        <div className={clsx(
          'mb-4 p-3 rounded-lg border text-sm',
          isDark ? 'bg-red-900/20 border-red-800 text-red-400' : 'bg-red-50 border-red-200 text-red-600'
        )}>
          ⚠️ {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
        </div>
      ) : (
        <>
          {/* Stats */}
          <div className="grid grid-cols-3 gap-4 mb-8">
            {statCards.map(stat => (
              <div key={stat.label} className={clsx(
                'p-5 rounded-xl border text-center transition-shadow hover:shadow-md',
                isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
              )}>
                <p className="text-2xl mb-1">{stat.icon}</p>
                <p className="text-2xl font-bold">{stat.value}</p>
                <p className={clsx('text-xs mt-1', isDark ? 'text-slate-400' : 'text-slate-500')}>{stat.label}</p>
              </div>
            ))}
          </div>

          {/* Promoted Skills */}
          <h2 className="text-lg font-semibold mb-3">
            ⚡ {t('evolution.promotedSkills', 'Promoted Skills')} {skills.length > 0 && `(${skills.length})`}
          </h2>
          {skills.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-4xl mb-3">🧬</p>
              <p className={clsx('text-sm', isDark ? 'text-slate-500' : 'text-slate-400')}>
                {t('evolution.noSkills', 'No skills promoted yet. Complete tasks to extract patterns and promote reusable skills.')}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {skills.map((skill, i) => (
                <div key={skill.name || i} className={clsx(
                  'p-4 rounded-xl border flex items-center justify-between transition-shadow hover:shadow-md',
                  isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
                )}>
                  <div>
                    <h3 className="font-medium text-sm">{skill.name}</h3>
                    {skill.description && (
                      <p className={clsx('text-xs mt-0.5', isDark ? 'text-slate-400' : 'text-slate-500')}>{skill.description}</p>
                    )}
                    <div className="flex gap-2 mt-1">
                      {skill.status && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                          {skill.status}
                        </span>
                      )}
                      {skill.usage_count != null && (
                        <span className="text-[10px] text-slate-400">used {skill.usage_count}x</span>
                      )}
                      {skill.quality_score != null && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                          quality {Math.round(skill.quality_score * 100)}%
                        </span>
                      )}
                    </div>
                  </div>
                  {skill.created_at && (
                    <span className={clsx('text-xs', isDark ? 'text-slate-500' : 'text-slate-400')}>
                      {new Date(skill.created_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default EvolutionPage
