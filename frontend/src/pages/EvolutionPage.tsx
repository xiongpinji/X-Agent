import React, { useEffect, useMemo, useState } from 'react'
import { toErrorMessage } from '@/services/errorMessage'
import { useAppStore } from '@/store/appStore'
import { useI18n } from '@/i18n/context'
import {
  evolutionOps,
  CycleResult,
  DistillResult,
  DistilledSkill,
  EvolutionEngineStats,
  EvolutionRecordItem,
  EvolutionSummary,
  EvaluateResult,
  GepaTriggerResult,
  OptimizeResult,
  PromotedSkillRecord,
  RecordExecutionResult,
  SelfEvolutionStats,
} from '@/services/evolutionOps'
import clsx from 'clsx'

type StageFilter = 'all' | 'execute' | 'evaluate' | 'optimize' | 'learn'

const STAGE_META: Record<string, { icon: string; badge: string }> = {
  execute: { icon: '▶️', badge: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  evaluate: { icon: '📊', badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' },
  optimize: { icon: '🛠️', badge: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' },
  learn: { icon: '🧠', badge: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
}

function safeJsonParse(raw: string): Record<string, any> | null {
  const trimmed = raw.trim()
  if (!trimmed) return {}
  try {
    const parsed = JSON.parse(trimmed)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null
  } catch {
    return null
  }
}

const EvolutionPage: React.FC = () => {
  const { theme } = useAppStore()
  const { t } = useI18n()
  const isDark = theme === 'dark'

  // ── Data state ──
  const [summary, setSummary] = useState<EvolutionSummary>({ reflections: 0, learnings: 0, capabilities: 0 })
  const [stats, setStats] = useState<EvolutionEngineStats>({ total_executions: 0, skill_drafts: 0, promoted_skills: 0, skill_names: [] })
  const [seStats, setSeStats] = useState<SelfEvolutionStats | null>(null)
  const [skills, setSkills] = useState<PromotedSkillRecord[]>([])
  const [distilledSkills, setDistilledSkills] = useState<DistilledSkill[]>([])
  const [history, setHistory] = useState<EvolutionRecordItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // ── Trigger panel state ──
  const [gepaTrajectory, setGepaTrajectory] = useState('')
  const [gepaResult, setGepaResult] = useState('')
  const [gepaBusy, setGepaBusy] = useState(false)
  const [gepaOutcome, setGepaOutcome] = useState<GepaTriggerResult | null>(null)
  const [gepaError, setGepaError] = useState<string | null>(null)

  const [cycleTaskId, setCycleTaskId] = useState('')
  const [cycleBusy, setCycleBusy] = useState(false)
  const [cycleOutcome, setCycleOutcome] = useState<CycleResult | null>(null)
  const [cyclePrevScore, setCyclePrevScore] = useState<number | null>(null)
  const [cycleError, setCycleError] = useState<string | null>(null)

  // ── Manual ops state ──
  const [recTaskId, setRecTaskId] = useState('')
  const [recTrace, setRecTrace] = useState('')
  const [recBusy, setRecBusy] = useState(false)
  const [recOutcome, setRecOutcome] = useState<RecordExecutionResult | null>(null)
  const [recError, setRecError] = useState<string | null>(null)

  const [evalExecId, setEvalExecId] = useState('')
  const [evalFeedback, setEvalFeedback] = useState('')
  const [evalBusy, setEvalBusy] = useState(false)
  const [evalOutcome, setEvalOutcome] = useState<EvaluateResult | null>(null)
  const [evalError, setEvalError] = useState<string | null>(null)

  const [optExecId, setOptExecId] = useState('')
  const [optScore, setOptScore] = useState('0.5')
  const [optBusy, setOptBusy] = useState(false)
  const [optOutcome, setOptOutcome] = useState<OptimizeResult | null>(null)
  const [optError, setOptError] = useState<string | null>(null)

  const [distillIds, setDistillIds] = useState('')
  const [distillBusy, setDistillBusy] = useState(false)
  const [distillOutcome, setDistillOutcome] = useState<DistillResult | null>(null)
  const [distillError, setDistillError] = useState<string | null>(null)

  // ── History view state ──
  const [stageFilter, setStageFilter] = useState<StageFilter>('all')
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    setError(null)
    const results = await Promise.allSettled([
      evolutionOps.getSummary(),
      evolutionOps.getStats(),
      evolutionOps.getSelfEvolutionStats(),
      evolutionOps.getPromotedSkills(),
      evolutionOps.getDistilledSkills(),
      evolutionOps.getHistory(50),
    ])
    const [summaryR, statsR, seStatsR, skillsR, distilledR, historyR] = results
    if (summaryR.status === 'fulfilled') setSummary(summaryR.value)
    if (statsR.status === 'fulfilled') setStats(statsR.value)
    if (seStatsR.status === 'fulfilled') setSeStats(seStatsR.value)
    if (skillsR.status === 'fulfilled') setSkills(skillsR.value)
    if (distilledR.status === 'fulfilled') setDistilledSkills(distilledR.value)
    if (historyR.status === 'fulfilled') setHistory(historyR.value)
    if (results.every(r => r.status === 'rejected')) {
      setError(t('evolution.loadFailed', 'Failed to load evolution data'))
    }
    setLoading(false)
  }

  // ── Trigger handlers ──

  const runGepaTrigger = async () => {
    const trajectory = safeJsonParse(gepaTrajectory)
    const result = safeJsonParse(gepaResult)
    if (!trajectory || !result) {
      setGepaError(t('evolution.invalidJson', 'Invalid JSON input'))
      return
    }
    setGepaBusy(true)
    setGepaError(null)
    setGepaOutcome(null)
    try {
      setGepaOutcome(await evolutionOps.triggerGepa(trajectory, result))
      await loadData()
    } catch (e: any) {
      setGepaError(toErrorMessage(e, t('evolution.triggerFailed', 'Trigger failed')))
    } finally {
      setGepaBusy(false)
    }
  }

  const runCycle = async () => {
    if (!cycleTaskId.trim()) return
    setCycleBusy(true)
    setCycleError(null)
    setCycleOutcome(null)
    // Capture the previous evaluate score for this task to show metric change.
    const prev = history.find(r => r.task_id === cycleTaskId.trim() && r.stage === 'evaluate' && r.score != null)
    setCyclePrevScore(prev?.score ?? null)
    try {
      setCycleOutcome(await evolutionOps.triggerCycle(cycleTaskId.trim()))
      await loadData()
    } catch (e: any) {
      setCycleError(toErrorMessage(e, t('evolution.cycleFailed', 'Cycle trigger failed')))
    } finally {
      setCycleBusy(false)
    }
  }

  // ── Manual ops handlers ──

  const runRecord = async () => {
    const trace = safeJsonParse(recTrace)
    if (!recTaskId.trim() || !trace) {
      setRecError(t('evolution.invalidJson', 'Invalid JSON input'))
      return
    }
    setRecBusy(true); setRecError(null); setRecOutcome(null)
    try {
      const out = await evolutionOps.recordExecution(recTaskId.trim(), trace)
      setRecOutcome(out)
      setEvalExecId(out.execution_id)
      setOptExecId(out.execution_id)
      await loadData()
    } catch (e: any) {
      setRecError(toErrorMessage(e, 'record failed'))
    } finally { setRecBusy(false) }
  }

  const runEvaluate = async () => {
    if (!evalExecId.trim()) return
    const feedback = safeJsonParse(evalFeedback)
    if (!feedback) {
      setEvalError(t('evolution.invalidJson', 'Invalid JSON input'))
      return
    }
    setEvalBusy(true); setEvalError(null); setEvalOutcome(null)
    try {
      setEvalOutcome(await evolutionOps.evaluateExecution(evalExecId.trim(), evalFeedback.trim() ? feedback : undefined))
      await loadData()
    } catch (e: any) {
      setEvalError(toErrorMessage(e, 'evaluate failed'))
    } finally { setEvalBusy(false) }
  }

  const runOptimize = async () => {
    const score = Number(optScore)
    if (!optExecId.trim() || !Number.isFinite(score) || score < 0 || score > 1) {
      setOptError(t('evolution.invalidScore', 'Score must be a number between 0 and 1'))
      return
    }
    setOptBusy(true); setOptError(null); setOptOutcome(null)
    try {
      setOptOutcome(await evolutionOps.optimizeStrategy(optExecId.trim(), score))
      await loadData()
    } catch (e: any) {
      setOptError(toErrorMessage(e, 'optimize failed'))
    } finally { setOptBusy(false) }
  }

  const runDistill = async () => {
    const ids = distillIds.split(',').map(s => s.trim()).filter(Boolean)
    if (ids.length === 0) return
    setDistillBusy(true); setDistillError(null); setDistillOutcome(null)
    try {
      setDistillOutcome(await evolutionOps.distillSkill(ids))
      await loadData()
    } catch (e: any) {
      setDistillError(toErrorMessage(e, 'distill failed'))
    } finally { setDistillBusy(false) }
  }

  // ── Derived view data ──

  const filteredHistory = useMemo(
    () => (stageFilter === 'all' ? history : history.filter(r => r.stage === stageFilter)),
    [history, stageFilter]
  )

  const toggleExpanded = (id: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  // ── Shared style helpers ──

  const cardCls = clsx(
    'p-5 rounded-xl border transition-shadow hover:shadow-md',
    isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
  )
  const inputCls = clsx(
    'w-full px-3 py-1.5 rounded-lg border text-sm outline-none focus:ring-2 focus:ring-blue-500/40',
    isDark ? 'bg-slate-800 border-slate-700 text-slate-200 placeholder-slate-500' : 'bg-white border-slate-300 text-slate-700 placeholder-slate-400'
  )
  const btnCls = clsx(
    'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
    isDark ? 'bg-blue-600 text-white hover:bg-blue-500' : 'bg-blue-500 text-white hover:bg-blue-600'
  )
  const mutedCls = clsx(isDark ? 'text-slate-400' : 'text-slate-500')
  const errBoxCls = clsx(
    'mt-2 p-2 rounded-lg border text-xs',
    isDark ? 'bg-red-900/20 border-red-800 text-red-400' : 'bg-red-50 border-red-200 text-red-600'
  )

  const renderError = (msg: string | null) => (msg ? <div className={errBoxCls}>⚠️ {msg}</div> : null)

  const renderJson = (data: Record<string, any>) => (
    <pre className={clsx(
      'mt-2 p-2 rounded-lg text-[11px] overflow-x-auto max-h-48 overflow-y-auto',
      isDark ? 'bg-slate-800 text-slate-300' : 'bg-slate-50 text-slate-600'
    )}>
      {JSON.stringify(data, null, 2)}
    </pre>
  )

  const statCards = [
    { label: t('evolution.totalExecutions', 'Total Executions'), value: stats.total_executions, icon: '📋' },
    { label: t('evolution.skillDrafts', 'Skill Drafts'), value: stats.skill_drafts, icon: '🧩' },
    { label: t('evolution.skillsPromoted', 'Skills Promoted'), value: stats.promoted_skills, icon: '⚡' },
  ]
  const summaryCards = [
    { label: t('evolution.reflections', 'Reflections'), value: summary.reflections, icon: '🪞' },
    { label: t('evolution.learnings', 'Learnings'), value: summary.learnings, icon: '📚' },
    { label: t('evolution.capabilities', 'Capabilities'), value: summary.capabilities, icon: '🧰' },
  ]
  const seCards = seStats
    ? [
        { label: t('evolution.totalRecords', 'Evolution Records'), value: seStats.total_records, icon: '🗂️' },
        { label: t('evolution.avgScore', 'Avg Score'), value: seStats.average_score, icon: '📈' },
        { label: t('evolution.optimizationsApplied', 'Optimizations'), value: seStats.optimizations_applied, icon: '🛠️' },
        { label: t('evolution.distilledSkills', 'Distilled Skills'), value: seStats.distilled_skills, icon: '🧠' },
      ]
    : []

  const cycleDelta =
    cycleOutcome?.score != null && cyclePrevScore != null
      ? cycleOutcome.score - cyclePrevScore
      : null

  return (
    <div className="p-6 max-w-6xl mx-auto">
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
      <p className={clsx('text-sm mb-6', mutedCls)}>
        {t('evolution.subtitle', 'GEPA closed-loop: Generate → Evaluate → Promote → Apply · Self-evolution: Execute → Evaluate → Optimize → Learn')}
      </p>

      {error && (
        <div className={clsx(
          'mb-4 p-3 rounded-lg border text-sm',
          isDark ? 'bg-red-900/20 border-red-800 text-red-400' : 'bg-red-50 border-red-200 text-red-600'
        )}>
          ⚠️ {error}
        </div>
      )}

      {loading && history.length === 0 ? (
        <div className="flex justify-center py-16">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
        </div>
      ) : (
        <>
          {/* ── Stats (GEPA engine) ── */}
          <div className="grid grid-cols-3 gap-4 mb-4">
            {statCards.map(stat => (
              <div key={stat.label} className={clsx(cardCls, 'text-center')}>
                <p className="text-2xl mb-1">{stat.icon}</p>
                <p className="text-2xl font-bold">{stat.value}</p>
                <p className={clsx('text-xs mt-1', mutedCls)}>{stat.label}</p>
              </div>
            ))}
          </div>

          {/* ── Summary (evolution store) ── */}
          <div className="grid grid-cols-3 gap-4 mb-4">
            {summaryCards.map(stat => (
              <div key={stat.label} className={clsx(cardCls, 'text-center')}>
                <p className="text-2xl mb-1">{stat.icon}</p>
                <p className="text-2xl font-bold">{stat.value}</p>
                <p className={clsx('text-xs mt-1', mutedCls)}>{stat.label}</p>
              </div>
            ))}
          </div>

          {/* ── Self-evolution engine stats ── */}
          {seCards.length > 0 && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              {seCards.map(stat => (
                <div key={stat.label} className={clsx(cardCls, 'text-center')}>
                  <p className="text-2xl mb-1">{stat.icon}</p>
                  <p className="text-2xl font-bold">{stat.value}</p>
                  <p className={clsx('text-xs mt-1', mutedCls)}>{stat.label}</p>
                </div>
              ))}
            </div>
          )}

          {/* ── Trigger console ── */}
          <h2 className="text-lg font-semibold mb-3">🚀 {t('evolution.triggerConsole', 'Trigger Console')}</h2>
          <div className="grid lg:grid-cols-2 gap-4 mb-8">
            {/* GEPA trigger */}
            <div className={cardCls}>
              <h3 className="font-medium text-sm mb-1">⚡ {t('evolution.gepaTrigger', 'GEPA Loop Trigger')}</h3>
              <p className={clsx('text-xs mb-3', mutedCls)}>POST /evolution/trigger</p>
              <label className={clsx('block text-xs mb-1', mutedCls)}>trajectory (JSON)</label>
              <textarea
                value={gepaTrajectory}
                onChange={e => setGepaTrajectory(e.target.value)}
                placeholder='{"tool_calls": [...], "status": "completed"}'
                rows={3}
                className={clsx(inputCls, 'font-mono text-xs')}
              />
              <label className={clsx('block text-xs mt-2 mb-1', mutedCls)}>result (JSON)</label>
              <textarea
                value={gepaResult}
                onChange={e => setGepaResult(e.target.value)}
                placeholder='{"success": true}'
                rows={2}
                className={clsx(inputCls, 'font-mono text-xs')}
              />
              <button onClick={runGepaTrigger} disabled={gepaBusy} className={clsx(btnCls, 'mt-3')}>
                {gepaBusy ? '⏳' : '▶️'} {t('evolution.runTrigger', 'Run Trigger')}
              </button>
              {renderError(gepaError)}
              {gepaOutcome && (
                <div className={clsx('mt-3 text-xs space-y-1')}>
                  <p>
                    <span className={clsx(
                      'px-1.5 py-0.5 rounded',
                      gepaOutcome.status === 'completed'
                        ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                        : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                    )}>
                      {gepaOutcome.status}
                    </span>
                    {gepaOutcome.reason && <span className={clsx('ml-2', mutedCls)}>{gepaOutcome.reason}</span>}
                  </p>
                  {gepaOutcome.status === 'completed' && (
                    <>
                      <p className={mutedCls}>
                        {t('evolution.shouldCreateSkill', 'Should create skill')}: {String(gepaOutcome.should_create_skill)}
                        {gepaOutcome.skill_name && ` · ${gepaOutcome.skill_name}`}
                        {gepaOutcome.confidence != null && ` · ${t('evolution.confidence', 'confidence')} ${Math.round(gepaOutcome.confidence * 100)}%`}
                      </p>
                      {gepaOutcome.key_patterns && gepaOutcome.key_patterns.length > 0 && (
                        <p className={mutedCls}>{t('evolution.keyPatterns', 'Key patterns')}: {gepaOutcome.key_patterns.join(', ')}</p>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Full cycle trigger */}
            <div className={cardCls}>
              <h3 className="font-medium text-sm mb-1">🔁 {t('evolution.fullCycle', 'Full Evolution Cycle')}</h3>
              <p className={clsx('text-xs mb-3', mutedCls)}>POST /evolution/self-evolution/cycle · Execute → Evaluate → Optimize → Learn</p>
              <label className={clsx('block text-xs mb-1', mutedCls)}>task_id</label>
              <input
                value={cycleTaskId}
                onChange={e => setCycleTaskId(e.target.value)}
                placeholder={t('evolution.taskIdPlaceholder', 'Task ID with a recorded execution')}
                className={inputCls}
              />
              <button onClick={runCycle} disabled={cycleBusy || !cycleTaskId.trim()} className={clsx(btnCls, 'mt-3')}>
                {cycleBusy ? '⏳' : '🔁'} {t('evolution.runCycle', 'Run Cycle')}
              </button>
              {renderError(cycleError)}
              {cycleOutcome && (
                <div className="mt-3 text-xs space-y-2">
                  {cycleOutcome.error ? (
                    <div className={errBoxCls}>⚠️ {cycleOutcome.error}</div>
                  ) : (
                    <>
                      <div className="flex flex-wrap gap-2 items-center">
                        <span className={clsx('px-1.5 py-0.5 rounded', STAGE_META.evaluate.badge)}>
                          📊 score {cycleOutcome.score != null ? cycleOutcome.score.toFixed(3) : '—'}
                        </span>
                        {cycleDelta != null && (
                          <span className={clsx(
                            'px-1.5 py-0.5 rounded',
                            cycleDelta >= 0
                              ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                              : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                          )}>
                            {cycleDelta >= 0 ? '▲' : '▼'} {Math.abs(cycleDelta).toFixed(3)} {t('evolution.vsPrevCycle', 'vs prev')}
                          </span>
                        )}
                        <span className={clsx('px-1.5 py-0.5 rounded', STAGE_META.optimize.badge)}>
                          🛠️ {cycleOutcome.optimization?.optimizations?.length ?? 0} {t('evolution.suggestions', 'suggestions')}
                        </span>
                        <span className={clsx('px-1.5 py-0.5 rounded', STAGE_META.learn.badge)}>
                          🧠 {cycleOutcome.skill_distilled ? t('evolution.skillPromoted', 'skill promoted') : t('evolution.noSkill', 'no skill')}
                        </span>
                      </div>
                      {cycleOutcome.optimization?.suggested_approach && (
                        <p className={mutedCls}>
                          {t('evolution.suggestedApproach', 'Suggested approach')}: {cycleOutcome.optimization.suggested_approach}
                          {cycleOutcome.optimization.should_retry && ` · ⚠️ ${t('evolution.shouldRetry', 'retry recommended')}`}
                        </p>
                      )}
                      {cycleOutcome.optimization?.optimizations?.map((o, i) => (
                        <p key={i} className={mutedCls}>• [{o.type}] {o.detail}</p>
                      ))}
                      {cycleOutcome.skill && (
                        <p className={mutedCls}>🧠 {cycleOutcome.skill.name} — {cycleOutcome.skill.description}</p>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* ── Manual ops panel ── */}
          <h2 className="text-lg font-semibold mb-3">🎛️ {t('evolution.manualOps', 'Manual Stage Operations')}</h2>
          <div className="grid lg:grid-cols-2 gap-4 mb-8">
            {/* Record */}
            <div className={cardCls}>
              <h3 className="font-medium text-sm mb-1">▶️ {t('evolution.opRecord', 'Record Execution')}</h3>
              <p className={clsx('text-xs mb-3', mutedCls)}>POST /evolution/self-evolution/record</p>
              <input value={recTaskId} onChange={e => setRecTaskId(e.target.value)} placeholder="task_id" className={clsx(inputCls, 'mb-2')} />
              <textarea
                value={recTrace}
                onChange={e => setRecTrace(e.target.value)}
                placeholder='trace (JSON), e.g. {"status": "completed", "tool_calls": []}'
                rows={2}
                className={clsx(inputCls, 'font-mono text-xs')}
              />
              <button onClick={runRecord} disabled={recBusy || !recTaskId.trim()} className={clsx(btnCls, 'mt-3')}>
                {recBusy ? '⏳' : '▶️'} {t('evolution.run', 'Run')}
              </button>
              {renderError(recError)}
              {recOutcome && (
                <p className={clsx('mt-2 text-xs', mutedCls)}>
                  ✅ execution_id: <code className="font-mono">{recOutcome.execution_id}</code>
                </p>
              )}
            </div>

            {/* Evaluate */}
            <div className={cardCls}>
              <h3 className="font-medium text-sm mb-1">📊 {t('evolution.opEvaluate', 'Evaluate Execution')}</h3>
              <p className={clsx('text-xs mb-3', mutedCls)}>POST /evolution/self-evolution/evaluate</p>
              <input value={evalExecId} onChange={e => setEvalExecId(e.target.value)} placeholder="execution_id" className={clsx(inputCls, 'mb-2')} />
              <textarea
                value={evalFeedback}
                onChange={e => setEvalFeedback(e.target.value)}
                placeholder='feedback (JSON, optional), e.g. {"success": true, "rating": 4}'
                rows={2}
                className={clsx(inputCls, 'font-mono text-xs')}
              />
              <button onClick={runEvaluate} disabled={evalBusy || !evalExecId.trim()} className={clsx(btnCls, 'mt-3')}>
                {evalBusy ? '⏳' : '📊'} {t('evolution.run', 'Run')}
              </button>
              {renderError(evalError)}
              {evalOutcome && (
                <p className={clsx('mt-2 text-xs', mutedCls)}>
                  ✅ score: <strong>{evalOutcome.score.toFixed(3)}</strong>
                </p>
              )}
            </div>

            {/* Optimize */}
            <div className={cardCls}>
              <h3 className="font-medium text-sm mb-1">🛠️ {t('evolution.opOptimize', 'Optimize Strategy')}</h3>
              <p className={clsx('text-xs mb-3', mutedCls)}>POST /evolution/self-evolution/optimize</p>
              <div className="flex gap-2 mb-2">
                <input value={optExecId} onChange={e => setOptExecId(e.target.value)} placeholder="execution_id" className={inputCls} />
                <input
                  value={optScore}
                  onChange={e => setOptScore(e.target.value)}
                  placeholder="score 0-1"
                  className={clsx(inputCls, 'w-28 shrink-0')}
                />
              </div>
              <button onClick={runOptimize} disabled={optBusy || !optExecId.trim()} className={btnCls}>
                {optBusy ? '⏳' : '🛠️'} {t('evolution.run', 'Run')}
              </button>
              {renderError(optError)}
              {optOutcome && (
                <div className="mt-2 text-xs space-y-1">
                  {optOutcome.error ? (
                    <div className={errBoxCls}>⚠️ {optOutcome.error}</div>
                  ) : (
                    <>
                      <p className={mutedCls}>
                        {t('evolution.suggestedApproach', 'Suggested approach')}: {optOutcome.suggested_approach}
                        {optOutcome.should_retry && ` · ⚠️ ${t('evolution.shouldRetry', 'retry recommended')}`}
                      </p>
                      {optOutcome.optimizations.map((o, i) => (
                        <p key={i} className={mutedCls}>• [{o.type}] {o.detail}</p>
                      ))}
                      {optOutcome.optimizations.length === 0 && (
                        <p className={mutedCls}>{t('evolution.noOptimizations', 'No optimization suggestions.')}</p>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Distill */}
            <div className={cardCls}>
              <h3 className="font-medium text-sm mb-1">🧠 {t('evolution.opDistill', 'Distill Skill')}</h3>
              <p className={clsx('text-xs mb-3', mutedCls)}>POST /evolution/self-evolution/distill</p>
              <input
                value={distillIds}
                onChange={e => setDistillIds(e.target.value)}
                placeholder={t('evolution.distillPlaceholder', 'execution_ids, comma separated')}
                className={clsx(inputCls, 'mb-2')}
              />
              <button onClick={runDistill} disabled={distillBusy || !distillIds.trim()} className={btnCls}>
                {distillBusy ? '⏳' : '🧠'} {t('evolution.run', 'Run')}
              </button>
              {renderError(distillError)}
              {distillOutcome && (
                <div className="mt-2 text-xs space-y-1">
                  {distillOutcome.error ? (
                    <div className={errBoxCls}>⚠️ {distillOutcome.error}</div>
                  ) : distillOutcome.skill ? (
                    <>
                      <p className={mutedCls}>
                        {distillOutcome.promoted ? '✅ ' + t('evolution.skillPromoted', 'skill promoted') : '⏸️ ' + t('evolution.belowThreshold', 'below promotion threshold')}
                        {' · '}{t('evolution.successRate', 'success rate')} {Math.round(distillOutcome.skill.success_rate * 100)}%
                      </p>
                      <p className={mutedCls}>🧠 {distillOutcome.skill.name} — {distillOutcome.skill.description}</p>
                    </>
                  ) : null}
                </div>
              )}
            </div>
          </div>

          {/* ── Cycle history / record event stream ── */}
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold">
              🗂️ {t('evolution.history', 'Cycle History & Record Stream')} {history.length > 0 && `(${filteredHistory.length})`}
            </h2>
            <div className="flex gap-1.5">
              {(['all', 'execute', 'evaluate', 'optimize', 'learn'] as StageFilter[]).map(f => (
                <button
                  key={f}
                  onClick={() => setStageFilter(f)}
                  className={clsx(
                    'px-2 py-1 rounded-lg text-xs font-medium transition-colors',
                    stageFilter === f
                      ? 'bg-blue-500 text-white'
                      : isDark
                        ? 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                        : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                  )}
                >
                  {f === 'all' ? t('evolution.filterAll', 'All') : `${STAGE_META[f].icon} ${f}`}
                </button>
              ))}
            </div>
          </div>
          {filteredHistory.length === 0 ? (
            <div className="text-center py-10 mb-8">
              <p className="text-4xl mb-3">🗂️</p>
              <p className={clsx('text-sm', mutedCls)}>
                {t('evolution.noHistory', 'No evolution records yet. Record an execution or run a cycle to start the stream.')}
              </p>
            </div>
          ) : (
            <div className="space-y-2 mb-8">
              {filteredHistory.map(rec => {
                const meta = STAGE_META[rec.stage] ?? { icon: '•', badge: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400' }
                const expanded = expandedIds.has(rec.id)
                return (
                  <div key={rec.id} className={clsx(cardCls, 'p-3')}>
                    <button onClick={() => toggleExpanded(rec.id)} className="w-full flex items-center gap-3 text-left">
                      <span className={clsx('px-1.5 py-0.5 rounded text-[11px] shrink-0', meta.badge)}>
                        {meta.icon} {rec.stage}
                      </span>
                      <span className="text-xs font-mono truncate">{rec.task_id || '—'}</span>
                      {rec.score != null && (
                        <span className={clsx('text-[11px] shrink-0', mutedCls)}>score {rec.score.toFixed(3)}</span>
                      )}
                      <span className={clsx('ml-auto text-[11px] shrink-0', mutedCls)}>
                        {rec.created_at ? new Date(rec.created_at).toLocaleString() : ''}
                      </span>
                      <span className={clsx('text-[11px] shrink-0', mutedCls)}>{expanded ? '▾' : '▸'}</span>
                    </button>
                    {expanded && (
                      <div className="mt-2">
                        <p className={clsx('text-[11px]', mutedCls)}>id: <code className="font-mono">{rec.id}</code></p>
                        {Object.keys(rec.input_data ?? {}).length > 0 && renderJson({ input: rec.input_data })}
                        {Object.keys(rec.output_data ?? {}).length > 0 && renderJson({ output: rec.output_data })}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* ── Promoted Skills (GEPA) ── */}
          <h2 className="text-lg font-semibold mb-3">
            ⚡ {t('evolution.promotedSkills', 'Promoted Skills')} {skills.length > 0 && `(${skills.length})`}
          </h2>
          {skills.length === 0 ? (
            <div className="text-center py-8 mb-8">
              <p className="text-4xl mb-3">🧬</p>
              <p className={clsx('text-sm', mutedCls)}>
                {t('evolution.noSkills', 'No skills promoted yet. Complete tasks to extract patterns and promote reusable skills.')}
              </p>
            </div>
          ) : (
            <div className="space-y-3 mb-8">
              {skills.map((skill, i) => (
                <div key={skill.id || skill.name || i} className={clsx(cardCls, 'flex items-center justify-between')}>
                  <div>
                    <h3 className="font-medium text-sm">{skill.name}</h3>
                    {skill.description && (
                      <p className={clsx('text-xs mt-0.5', mutedCls)}>{skill.description}</p>
                    )}
                    <div className="flex gap-2 mt-1 flex-wrap">
                      {skill.trigger_pattern && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                          {skill.trigger_pattern}
                        </span>
                      )}
                      <span className="text-[10px] text-slate-400">used {skill.usage_count}x</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                        success {Math.round((skill.success_rate ?? 0) * 100)}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* ── Distilled Skills (self-evolution engine) ── */}
          <h2 className="text-lg font-semibold mb-3">
            🧠 {t('evolution.distilledSkillsList', 'Distilled Skills')} {distilledSkills.length > 0 && `(${distilledSkills.length})`}
          </h2>
          {distilledSkills.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-4xl mb-3">🧠</p>
              <p className={clsx('text-sm', mutedCls)}>
                {t('evolution.noDistilledSkills', 'No distilled skills yet. Run distill on successful executions (success rate ≥ 70%).')}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {distilledSkills.map(skill => (
                <div key={skill.id} className={cardCls}>
                  <h3 className="font-medium text-sm">{skill.name}</h3>
                  <p className={clsx('text-xs mt-0.5', mutedCls)}>{skill.description}</p>
                  {skill.pattern && <p className={clsx('text-[11px] mt-1', mutedCls)}>{skill.pattern}</p>}
                  <div className="flex gap-2 mt-1 flex-wrap items-center">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                      success {Math.round(skill.success_rate * 100)}%
                    </span>
                    {skill.tool_sequence.map(tool => (
                      <span key={tool} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 font-mono">
                        {tool}
                      </span>
                    ))}
                    <span className={clsx('text-[10px] ml-auto', mutedCls)}>
                      {skill.created_at ? new Date(skill.created_at).toLocaleDateString() : ''}
                    </span>
                  </div>
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
