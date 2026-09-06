import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { toErrorMessage } from '@/services/errorMessage'
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

const DIVIDER = 'var(--divider)'

// Stage chips — thin-border status badges, no colored fills.
const STAGE_BADGE: Record<string, string> = {
  execute: 'badge-muted',
  evaluate: 'badge-warning',
  optimize: 'badge-muted',
  learn: 'badge-success',
}

function safeJsonParse(raw: string): Record<string, unknown> | null {
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
  const { t } = useI18n()

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

  // `t` from the i18n context is not referentially stable; keep it in a ref so
  // loadData keeps a stable identity and the initial fetch stays mount-only.
  const tRef = useRef(t)
  tRef.current = t

  const loadData = useCallback(async () => {
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
      setError(tRef.current('evolution.loadFailed', 'Failed to load evolution data'))
    }
    setLoading(false)
  }, [setLoading, setError])

  useEffect(() => {
    loadData()
  }, [loadData])

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
    } catch (e) {
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
    } catch (e) {
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
    } catch (e) {
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
    } catch (e) {
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
    } catch (e) {
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
    } catch (e) {
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

  // ── Shared style helpers — hairline, no cards ──

  const inputCls =
    'w-full px-3 py-1.5 border border-[var(--divider)] bg-transparent text-sm outline-none transition-colors focus:border-[var(--fg)] placeholder:opacity-40'
  const btnCls =
    'px-3 py-1.5 bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50'
  const sectionTitle = 'text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2'

  const renderError = (msg: string | null) => (msg ? (
    <div className="mt-2 p-2 border border-[#dc2626]/30 text-xs text-[#dc2626]">⚠️ {msg}</div>
  ) : null)

  const renderJson = (data: Record<string, unknown>) => (
    <pre className="mt-2 p-2 border border-[var(--divider)] bg-transparent text-[11px] overflow-x-auto max-h-48 overflow-y-auto cell-data opacity-80">
      {JSON.stringify(data, null, 2)}
    </pre>
  )

  // KPI rows — single horizontal text lines, hairline vertical dividers.
  const renderStatRow = (items: Array<{ label: string; value: string | number }>) => (
    <dl className="flex flex-wrap gap-y-5">
      {items.map((item, i) => (
        <div
          key={item.label}
          className={clsx('flex flex-col gap-1.5 pr-6 mr-6', i < items.length - 1 && 'border-r')}
          style={i < items.length - 1 ? { borderColor: DIVIDER } : undefined}
        >
          <dd className="font-data text-[20px] leading-none order-2">{item.value}</dd>
          <dt className="text-[11px] uppercase tracking-[0.06em] opacity-50 order-1">{item.label}</dt>
        </div>
      ))}
    </dl>
  )

  const engineStats = [
    { label: t('evolution.totalExecutions', 'Total Executions'), value: stats.total_executions },
    { label: t('evolution.skillDrafts', 'Skill Drafts'), value: stats.skill_drafts },
    { label: t('evolution.skillsPromoted', 'Skills Promoted'), value: stats.promoted_skills },
  ]
  const summaryStats = [
    { label: t('evolution.reflections', 'Reflections'), value: summary.reflections },
    { label: t('evolution.learnings', 'Learnings'), value: summary.learnings },
    { label: t('evolution.capabilities', 'Capabilities'), value: summary.capabilities },
  ]
  const seStatItems = seStats
    ? [
        { label: t('evolution.totalRecords', 'Evolution Records'), value: seStats.total_records },
        { label: t('evolution.avgScore', 'Avg Score'), value: seStats.average_score },
        { label: t('evolution.optimizationsApplied', 'Optimizations'), value: seStats.optimizations_applied },
        { label: t('evolution.distilledSkills', 'Distilled Skills'), value: seStats.distilled_skills },
      ]
    : []

  const cycleDelta =
    cycleOutcome?.score != null && cyclePrevScore != null
      ? cycleOutcome.score - cyclePrevScore
      : null

  return (
    <div className="min-h-full px-8 py-10">
      <div className="max-w-6xl">
        {/* Header — Dashboard-style */}
        <header className="mb-8">
          <div className="w-12 border-t-2 mb-5" style={{ borderColor: 'var(--fg)' }} aria-hidden="true" />
          <div className="flex items-end justify-between gap-4 flex-wrap">
            <div>
              <h1 className="page-title">{t('evolution.title', 'Self-Evolution Engine')}</h1>
              <p className="page-subtitle">
                {t('evolution.subtitle', 'GEPA closed-loop: Generate → Evaluate → Promote → Apply · Self-evolution: Execute → Evaluate → Optimize → Learn')}
              </p>
            </div>
            <button
              onClick={loadData}
              disabled={loading}
              className="px-3 py-2 border border-[var(--divider)] bg-transparent text-sm font-medium transition-colors hover:bg-[var(--hover)] disabled:opacity-50"
            >
              {loading ? '⏳' : '🔄'} {t('common.refresh', 'Refresh')}
            </button>
          </div>
        </header>

        {error && (
          <div className="mb-6 p-3 border border-[#dc2626]/30 text-sm text-[#dc2626]" role="alert">
            ⚠️ {error}
          </div>
        )}

        {loading && history.length === 0 ? (
          <p className="empty-state">{t('common.loading', 'Loading...')}</p>
        ) : (
          <>
            {/* ── Stats — single-row KPI text, no cards ── */}
            <section className="mb-8" aria-label={t('evolution.title', 'Self-Evolution Engine')}>
              {renderStatRow([...engineStats, ...summaryStats, ...seStatItems])}
            </section>

            <hr className="my-10 border-0 border-t" style={{ borderColor: DIVIDER }} />

            {/* ── Trigger console ── */}
            <section className="mb-10">
              <h2 className={sectionTitle}>{t('evolution.triggerConsole', 'Trigger Console')}</h2>
              <div className="grid lg:grid-cols-2 gap-10">
                {/* GEPA trigger */}
                <div>
                  <h3 className="text-sm font-medium mb-1">{t('evolution.gepaTrigger', 'GEPA Loop Trigger')}</h3>
                  <p className="cell-data text-[11px] opacity-50 mb-3">POST /evolution/trigger</p>
                  <label htmlFor="gepa-trajectory" className="block text-[11px] uppercase tracking-[0.06em] opacity-50 mb-1">trajectory (JSON)</label>
                  <textarea
                    id="gepa-trajectory"
                    value={gepaTrajectory}
                    onChange={e => setGepaTrajectory(e.target.value)}
                    placeholder='{"tool_calls": [...], "status": "completed"}'
                    rows={3}
                    className={clsx(inputCls, 'font-mono text-xs')}
                  />
                  <label htmlFor="gepa-result" className="block text-[11px] uppercase tracking-[0.06em] opacity-50 mt-3 mb-1">result (JSON)</label>
                  <textarea
                    id="gepa-result"
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
                    <div className="mt-3 text-xs space-y-1">
                      <p className="flex items-center gap-2 flex-wrap">
                        <span className={clsx('badge-status', gepaOutcome.status === 'completed' ? 'badge-success' : 'badge-muted')}>
                          {gepaOutcome.status}
                        </span>
                        {gepaOutcome.reason && <span className="opacity-50">{gepaOutcome.reason}</span>}
                      </p>
                      {gepaOutcome.status === 'completed' && (
                        <>
                          <p className="opacity-50">
                            {t('evolution.shouldCreateSkill', 'Should create skill')}: {String(gepaOutcome.should_create_skill)}
                            {gepaOutcome.skill_name && ` · ${gepaOutcome.skill_name}`}
                            {gepaOutcome.confidence != null && ` · ${t('evolution.confidence', 'confidence')} ${Math.round(gepaOutcome.confidence * 100)}%`}
                          </p>
                          {gepaOutcome.key_patterns && gepaOutcome.key_patterns.length > 0 && (
                            <p className="opacity-50">{t('evolution.keyPatterns', 'Key patterns')}: {gepaOutcome.key_patterns.join(', ')}</p>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>

                {/* Full cycle trigger */}
                <div>
                  <h3 className="text-sm font-medium mb-1">{t('evolution.fullCycle', 'Full Evolution Cycle')}</h3>
                  <p className="cell-data text-[11px] opacity-50 mb-3">POST /evolution/self-evolution/cycle · Execute → Evaluate → Optimize → Learn</p>
                  <label htmlFor="cycle-task-id" className="block text-[11px] uppercase tracking-[0.06em] opacity-50 mb-1">task_id</label>
                  <input
                    id="cycle-task-id"
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
                        <div className="p-2 border border-[#dc2626]/30 text-[#dc2626]">⚠️ {cycleOutcome.error}</div>
                      ) : (
                        <>
                          <div className="flex flex-wrap gap-2 items-center">
                            <span className={clsx('badge-status', STAGE_BADGE.evaluate)}>
                              score <span className="font-data">{cycleOutcome.score != null ? cycleOutcome.score.toFixed(3) : '—'}</span>
                            </span>
                            {cycleDelta != null && (
                              <span className={clsx('badge-status', cycleDelta >= 0 ? 'badge-success' : 'badge-danger')}>
                                {cycleDelta >= 0 ? '▲' : '▼'} {Math.abs(cycleDelta).toFixed(3)} {t('evolution.vsPrevCycle', 'vs prev')}
                              </span>
                            )}
                            <span className={clsx('badge-status', STAGE_BADGE.optimize)}>
                              {cycleOutcome.optimization?.optimizations?.length ?? 0} {t('evolution.suggestions', 'suggestions')}
                            </span>
                            <span className={clsx('badge-status', STAGE_BADGE.learn)}>
                              {cycleOutcome.skill_distilled ? t('evolution.skillPromoted', 'skill promoted') : t('evolution.noSkill', 'no skill')}
                            </span>
                          </div>
                          {cycleOutcome.optimization?.suggested_approach && (
                            <p className="opacity-50">
                              {t('evolution.suggestedApproach', 'Suggested approach')}: {cycleOutcome.optimization.suggested_approach}
                              {cycleOutcome.optimization.should_retry && ` · ⚠️ ${t('evolution.shouldRetry', 'retry recommended')}`}
                            </p>
                          )}
                          {cycleOutcome.optimization?.optimizations?.map((o, i) => (
                            <p key={i} className="opacity-50">• [{o.type}] {o.detail}</p>
                          ))}
                          {cycleOutcome.skill && (
                            <p className="opacity-50">{cycleOutcome.skill.name} — {cycleOutcome.skill.description}</p>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </section>

            {/* ── Manual ops panel ── */}
            <section className="mb-10">
              <h2 className={sectionTitle}>{t('evolution.manualOps', 'Manual Stage Operations')}</h2>
              <div className="grid lg:grid-cols-2 gap-10">
                {/* Record */}
                <div>
                  <h3 className="text-sm font-medium mb-1">{t('evolution.opRecord', 'Record Execution')}</h3>
                  <p className="cell-data text-[11px] opacity-50 mb-3">POST /evolution/self-evolution/record</p>
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
                    <p className="mt-2 text-xs opacity-50">
                      ✓ execution_id: <code className="cell-data">{recOutcome.execution_id}</code>
                    </p>
                  )}
                </div>

                {/* Evaluate */}
                <div>
                  <h3 className="text-sm font-medium mb-1">{t('evolution.opEvaluate', 'Evaluate Execution')}</h3>
                  <p className="cell-data text-[11px] opacity-50 mb-3">POST /evolution/self-evolution/evaluate</p>
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
                    <p className="mt-2 text-xs opacity-50">
                      ✓ score: <span className="font-data">{evalOutcome.score.toFixed(3)}</span>
                    </p>
                  )}
                </div>

                {/* Optimize */}
                <div>
                  <h3 className="text-sm font-medium mb-1">{t('evolution.opOptimize', 'Optimize Strategy')}</h3>
                  <p className="cell-data text-[11px] opacity-50 mb-3">POST /evolution/self-evolution/optimize</p>
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
                        <div className="p-2 border border-[#dc2626]/30 text-[#dc2626]">⚠️ {optOutcome.error}</div>
                      ) : (
                        <>
                          <p className="opacity-50">
                            {t('evolution.suggestedApproach', 'Suggested approach')}: {optOutcome.suggested_approach}
                            {optOutcome.should_retry && ` · ⚠️ ${t('evolution.shouldRetry', 'retry recommended')}`}
                          </p>
                          {optOutcome.optimizations.map((o, i) => (
                            <p key={i} className="opacity-50">• [{o.type}] {o.detail}</p>
                          ))}
                          {optOutcome.optimizations.length === 0 && (
                            <p className="opacity-50">{t('evolution.noOptimizations', 'No optimization suggestions.')}</p>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>

                {/* Distill */}
                <div>
                  <h3 className="text-sm font-medium mb-1">{t('evolution.opDistill', 'Distill Skill')}</h3>
                  <p className="cell-data text-[11px] opacity-50 mb-3">POST /evolution/self-evolution/distill</p>
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
                        <div className="p-2 border border-[#dc2626]/30 text-[#dc2626]">⚠️ {distillOutcome.error}</div>
                      ) : distillOutcome.skill ? (
                        <>
                          <p className="opacity-50">
                            {distillOutcome.promoted ? '✅ ' + t('evolution.skillPromoted', 'skill promoted') : '⏸️ ' + t('evolution.belowThreshold', 'below promotion threshold')}
                            {' · '}{t('evolution.successRate', 'success rate')} {Math.round(distillOutcome.skill.success_rate * 100)}%
                          </p>
                          <p className="opacity-50">{distillOutcome.skill.name} — {distillOutcome.skill.description}</p>
                        </>
                      ) : null}
                    </div>
                  )}
                </div>
              </div>
            </section>

            <hr className="my-10 border-0 border-t" style={{ borderColor: DIVIDER }} />

            {/* ── Cycle history / record event stream ── */}
            <section className="mb-10">
              <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                <h2 className={clsx(sectionTitle, 'mb-0')}>
                  {t('evolution.history', 'Cycle History & Record Stream')} {history.length > 0 && `(${filteredHistory.length})`}
                </h2>
                <div className="flex gap-1.5">
                  {(['all', 'execute', 'evaluate', 'optimize', 'learn'] as StageFilter[]).map(f => (
                    <button
                      key={f}
                      onClick={() => setStageFilter(f)}
                      className={clsx(
                        'px-2 py-1 text-xs font-medium transition-opacity',
                        stageFilter === f ? 'opacity-100 text-blue-600 dark:text-blue-400' : 'opacity-50 hover:opacity-100'
                      )}
                    >
                      {f === 'all' ? t('evolution.filterAll', 'All') : f}
                    </button>
                  ))}
                </div>
              </div>
              {filteredHistory.length === 0 ? (
                <p className="empty-state">
                  {t('evolution.noHistory', 'No evolution records yet. Record an execution or run a cycle to start the stream.')}
                </p>
              ) : (
                <div>
                  {filteredHistory.map(rec => {
                    const expanded = expandedIds.has(rec.id)
                    return (
                      <div key={rec.id} className="row-line" style={{ padding: '10px 0' }}>
                        <button onClick={() => toggleExpanded(rec.id)} className="w-full flex items-center gap-3 text-left">
                          <span className={clsx('badge-status shrink-0', STAGE_BADGE[rec.stage] ?? 'badge-muted')}>
                            {rec.stage}
                          </span>
                          <span className="cell-data text-xs truncate">{rec.task_id || '—'}</span>
                          {rec.score != null && (
                            <span className="text-[11px] shrink-0 opacity-50 font-data">score {rec.score.toFixed(3)}</span>
                          )}
                          <span className="ml-auto text-[11px] shrink-0 opacity-50 cell-data">
                            {rec.created_at ? new Date(rec.created_at).toLocaleString() : ''}
                          </span>
                          <span className="text-[11px] shrink-0 opacity-50">{expanded ? '▾' : '▸'}</span>
                        </button>
                        {expanded && (
                          <div className="mt-2">
                            <p className="text-[11px] opacity-50">id: <code className="cell-data">{rec.id}</code></p>
                            {Object.keys(rec.input_data ?? {}).length > 0 && renderJson({ input: rec.input_data })}
                            {Object.keys(rec.output_data ?? {}).length > 0 && renderJson({ output: rec.output_data })}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </section>

            <hr className="my-10 border-0 border-t" style={{ borderColor: DIVIDER }} />

            {/* ── Promoted Skills (GEPA) ── */}
            <section className="mb-10">
              <h2 className={sectionTitle}>
                {t('evolution.promotedSkills', 'Promoted Skills')} {skills.length > 0 && `(${skills.length})`}
              </h2>
              {skills.length === 0 ? (
                <p className="empty-state">
                  {t('evolution.noSkills', 'No skills promoted yet. Complete tasks to extract patterns and promote reusable skills.')}
                </p>
              ) : (
                <div>
                  {skills.map((skill, i) => (
                    <div key={skill.id || skill.name || i} className="row-line flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <h3 className="font-medium text-sm truncate">{skill.name}</h3>
                        {skill.description && (
                          <p className="text-xs mt-0.5 opacity-50 truncate">{skill.description}</p>
                        )}
                      </div>
                      <div className="flex gap-2 items-center shrink-0 flex-wrap justify-end">
                        {skill.trigger_pattern && (
                          <span className="badge-status badge-muted">{skill.trigger_pattern}</span>
                        )}
                        <span className="text-[11px] opacity-50 font-data">used {skill.usage_count}x</span>
                        <span className="badge-status badge-success">
                          success {Math.round((skill.success_rate ?? 0) * 100)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <hr className="my-10 border-0 border-t" style={{ borderColor: DIVIDER }} />

            {/* ── Distilled Skills (self-evolution engine) ── */}
            <section>
              <h2 className={sectionTitle}>
                {t('evolution.distilledSkillsList', 'Distilled Skills')} {distilledSkills.length > 0 && `(${distilledSkills.length})`}
              </h2>
              {distilledSkills.length === 0 ? (
                <p className="empty-state">
                  {t('evolution.noDistilledSkills', 'No distilled skills yet. Run distill on successful executions (success rate ≥ 70%).')}
                </p>
              ) : (
                <div>
                  {distilledSkills.map(skill => (
                    <div key={skill.id} className="row-line">
                      <div className="flex items-center justify-between gap-4">
                        <h3 className="font-medium text-sm truncate">{skill.name}</h3>
                        <div className="flex gap-2 items-center shrink-0">
                          <span className="badge-status badge-success">
                            success {Math.round(skill.success_rate * 100)}%
                          </span>
                          <span className="text-[11px] opacity-50 cell-data">
                            {skill.created_at ? new Date(skill.created_at).toLocaleDateString() : ''}
                          </span>
                        </div>
                      </div>
                      <p className="text-xs mt-0.5 opacity-50">{skill.description}</p>
                      {skill.pattern && <p className="text-[11px] mt-1 opacity-50">{skill.pattern}</p>}
                      {skill.tool_sequence.length > 0 && (
                        <div className="flex gap-2 mt-1.5 flex-wrap items-center">
                          {skill.tool_sequence.map(tool => (
                            <span key={tool} className="badge-status badge-muted cell-data">{tool}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  )
}

export default EvolutionPage
