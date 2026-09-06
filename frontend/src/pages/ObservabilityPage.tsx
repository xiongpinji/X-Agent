import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import {
  observabilityOps,
  MetricsSummary,
  OpsSummary,
  TraceSummaryItem,
  TraceDetailResponse,
  TraceReplayResponse,
} from '@/services/observabilityOps'
import { useI18n } from '@/i18n/context'
import {
  ChevronRight,
  Play,
  RefreshCw,
} from 'lucide-react'
import clsx from 'clsx'

const DIVIDER = 'var(--divider)'

const TRACE_STATUS_BADGE: Record<string, string> = {
  completed: 'badge-success',
  success: 'badge-success',
  failed: 'badge-danger',
  error: 'badge-danger',
  running: 'badge-muted',
  in_progress: 'badge-muted',
}

/**
 * ObservabilityPage (A22) — 可观测性总览。
 * 数据来源(全部为真实后端端点, 见 services/observabilityOps.ts 头部注释):
 * - 指标卡片: GET /api/v1/metrics/summary
 * - 运维健康: GET /api/v1/ops/summary
 * - Trace 列表/详情/回放: GET /api/v1/traces*, /{id}, /{id}/replay
 *
 * 注: components/AnalyticsDashboard.tsx 依赖的 /api/v1/analytics/* router
 * 未在 backend/app/main.py 挂载, 该孤儿组件不可用, 本页面不复用它;
 * uptime / latency / error-rate 后端未提供, 显示为 "—"。
 */
export const ObservabilityPage: React.FC = () => {
  const { theme, setError } = useAppStore()
  const { t } = useI18n()

  const [metrics, setMetrics] = useState<MetricsSummary | null>(null)
  const [ops, setOps] = useState<OpsSummary | null>(null)
  const [traces, setTraces] = useState<TraceSummaryItem[]>([])
  const [loading, setLoading] = useState(false)

  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null)
  const [traceDetail, setTraceDetail] = useState<TraceDetailResponse | null>(null)
  const [traceReplay, setTraceReplay] = useState<TraceReplayResponse | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [replayLoading, setReplayLoading] = useState(false)

  const loadAll = useCallback(async () => {
    try {
      setLoading(true)
      const [m, o, tr] = await Promise.all([
        observabilityOps.getMetricsSummary(),
        observabilityOps.getOpsSummary(),
        observabilityOps.listTraces(20),
      ])
      setMetrics(m)
      setOps(o)
      setTraces(tr)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load observability data')
    } finally {
      setLoading(false)
    }
  }, [setError])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  const handleSelectTrace = async (traceId: string) => {
    setSelectedTraceId(traceId)
    setTraceReplay(null)
    try {
      setDetailLoading(true)
      setTraceDetail(await observabilityOps.getTrace(traceId))
    } catch (error) {
      setTraceDetail(null)
      setError(error instanceof Error ? error.message : 'Failed to load trace detail')
    } finally {
      setDetailLoading(false)
    }
  }

  const handleReplay = async () => {
    if (!selectedTraceId) return
    try {
      setReplayLoading(true)
      setTraceReplay(await observabilityOps.getTraceReplay(selectedTraceId))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load trace replay')
    } finally {
      setReplayLoading(false)
    }
  }

  const durationLabel = (item: TraceSummaryItem): string => {
    if (!item.started_at || !item.ended_at) return '—'
    const ms = new Date(item.ended_at).getTime() - new Date(item.started_at).getTime()
    if (Number.isNaN(ms) || ms < 0) return '—'
    return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
  }

  const statusBadge = (status?: string) => TRACE_STATUS_BADGE[status ?? 'unknown'] ?? 'badge-muted'

  const eventIsFailure = (kind: string) => kind === 'agent.failed' || kind === 'tool.execution.failed'

  const metricItems = useMemo(() => {
    if (!metrics) return []
    return [
      { label: t('obs.runs', 'Runs'), value: metrics.runs },
      { label: t('obs.traces', 'Traces'), value: metrics.traces },
      { label: t('obs.traceEvents', 'Trace Events'), value: metrics.trace_events },
      { label: t('obs.memories', 'Memories'), value: metrics.memories },
      { label: t('obs.workflows', 'Workflows'), value: metrics.workflows },
      { label: t('obs.workflowRuns', 'Workflow Runs'), value: metrics.workflow_runs },
      { label: t('obs.auditLogs', 'Audit Logs'), value: metrics.audit_logs },
      { label: t('obs.apiKeys', 'API Keys'), value: `${metrics.active_api_keys}/${metrics.api_keys}` },
      { label: t('obs.approvals', 'Approvals'), value: `${metrics.pending_approvals}/${metrics.approvals}` },
    ]
  }, [metrics, t])

  const ghostBtnCls = clsx(
    'flex items-center gap-2 px-3 py-2 border border-[var(--divider)] bg-transparent text-sm font-medium transition-colors hover:bg-[var(--hover)] disabled:opacity-50'
  )

  return (
    <div className={clsx(
      'min-h-full px-8 py-10',
      theme === 'dark' ? 'bg-slate-950 text-slate-200' : 'bg-[#fafafa] text-[#333333]'
    )}>
      <div className="max-w-6xl">
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
              <h1 className="page-title">{t('obs.title', 'Observability')}</h1>
              <p className="page-subtitle">{t('obs.subtitle', 'Metrics, health status and trace inspection')}</p>
            </div>
            <button
              onClick={loadAll}
              disabled={loading}
              className={ghostBtnCls}
              aria-label={t('common.refresh', 'Refresh')}
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
              {t('common.refresh', 'Refresh')}
            </button>
          </div>
        </header>

        {/* ── 健康状态 — inline badge row, no colored panel ─────── */}
        {ops && (
          <section className="mb-8">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
              <span className={clsx('badge-status', ops.healthy ? 'badge-success' : 'badge-danger')}>
                {ops.healthy ? t('obs.healthy', 'System Healthy') : t('obs.unhealthy', 'Issues Detected')}
              </span>
              <span className="text-[13px] opacity-60">
                {t('obs.approvalBacklog', 'Approval backlog')}: <span className="cell-data">{ops.approval_backlog}</span>
              </span>
              <span className="text-[13px] opacity-60">
                {t('obs.toolFailures', 'Tool failures')}: <span className="cell-data">{ops.tool_failures}</span>
              </span>
              <span className="text-[13px] opacity-60">
                {t('obs.failureTraces', 'Failure traces')}: <span className="cell-data">{ops.failure_traces.length}</span>
              </span>
              <span className="text-[13px] opacity-60">
                {t('obs.toolsRegistered', 'Tools registered')}: <span className="cell-data">{ops.overview.tools}</span>
              </span>
            </div>
          </section>
        )}

        {/* ── 指标 — Dashboard-style status row, no cards ──────── */}
        {metricItems.length > 0 && (
          <section aria-label={t('obs.title', 'Observability')} className="mb-10">
            <dl className="flex flex-wrap gap-y-6">
              {metricItems.map((item, i) => (
                <div
                  key={item.label}
                  className={clsx(
                    'flex flex-col gap-2 pr-6 mr-6',
                    i < metricItems.length - 1 && 'border-r'
                  )}
                  style={i < metricItems.length - 1 ? { borderColor: DIVIDER } : undefined}
                >
                  <dd className="font-data text-[22px] leading-none order-2">
                    {typeof item.value === 'number' ? item.value.toLocaleString() : item.value}
                  </dd>
                  <dt className="text-[12px] uppercase tracking-[0.06em] opacity-50 order-1">
                    {item.label}
                  </dt>
                </div>
              ))}
            </dl>
          </section>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
          {/* ── Trace 列表 ─────────────────────────────────────── */}
          <section>
            <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
              {t('obs.tracesTitle', 'Recent Traces')}
            </h2>

            {/* 失败 trace 提示 (来自 /ops/summary) */}
            {ops && ops.failure_traces.length > 0 && (
              <div className="row-line mb-4 text-sm" style={{ padding: '12px 0' }}>
                <p className="font-medium mb-1 text-[#dc2626]">
                  {t('obs.recentFailures', 'Recent failures')}
                </p>
                <ul className="space-y-1 cell-data opacity-70">
                  {ops.failure_traces.slice(0, 5).map((f) => (
                    <li key={f.trace_id}>
                      <button
                        onClick={() => handleSelectTrace(f.trace_id)}
                        className="hover:underline text-left"
                      >
                        {f.trace_id.slice(0, 12)}… · {f.status} · {f.last_event ?? '—'} ({f.event_count} events)
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {traces.length === 0 ? (
              <p className="empty-state">{t('obs.noTraces', 'No traces found')}</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="table-dense">
                  <thead>
                    <tr>
                      <th>{t('obs.traceId', 'Trace')}</th>
                      <th>{t('obs.task', 'Task')}</th>
                      <th>{t('obs.status', 'Status')}</th>
                      <th>{t('obs.events', 'Events')}</th>
                      <th>{t('obs.duration', 'Duration')}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {traces.map((tr) => (
                      <tr
                        key={tr.trace_id}
                        className={clsx(
                          'cursor-pointer',
                          selectedTraceId === tr.trace_id && (theme === 'dark' ? 'bg-slate-800' : 'bg-slate-100')
                        )}
                        onClick={() => handleSelectTrace(tr.trace_id)}
                      >
                        <td className="cell-data opacity-70">
                          {tr.trace_id.slice(0, 10)}…
                        </td>
                        <td className="max-w-[180px] truncate opacity-70">
                          {tr.task ?? '—'}
                        </td>
                        <td>
                          <span className={clsx('badge-status', statusBadge(tr.snapshot?.status))}>
                            {tr.snapshot?.status ?? 'unknown'}
                          </span>
                        </td>
                        <td className="cell-data opacity-70">
                          {tr.event_count}
                        </td>
                        <td className="cell-data opacity-70">
                          {durationLabel(tr)}
                        </td>
                        <td className="text-right">
                          <ChevronRight size={14} className="inline opacity-40" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* ── Trace 详情 (事件时间线 + 回放) ─────────────────── */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50">
                {t('obs.traceDetail', 'Trace Detail')}
              </h2>
              <button
                onClick={handleReplay}
                disabled={!selectedTraceId || replayLoading}
                className={clsx(ghostBtnCls, 'py-1.5')}
              >
                <Play size={14} />
                {replayLoading ? t('common.loading', 'Loading...') : t('obs.replay', 'Replay')}
              </button>
            </div>

            {!selectedTraceId ? (
              <p className="empty-state">{t('obs.selectTrace', 'Select a trace from the list to inspect its event timeline')}</p>
            ) : detailLoading ? (
              <p className="empty-state">{t('common.loading', 'Loading...')}</p>
            ) : !traceDetail ? (
              <p className="empty-state">{t('obs.detailFailed', 'Failed to load trace detail')}</p>
            ) : (
              <>
                {/* 摘要 — mono tabular rows */}
                <div className="font-data text-[13px] mb-6">
                  <div className="flex items-baseline justify-between gap-4 py-2 border-b" style={{ borderColor: DIVIDER }}>
                    <span className="opacity-50">trace_id</span>
                    <span className="text-[12px] break-all text-right">{traceDetail.summary.trace_id}</span>
                  </div>
                  <div className="flex items-baseline justify-between gap-4 py-2 border-b" style={{ borderColor: DIVIDER }}>
                    <span className="opacity-50">{t('obs.status', 'Status')}</span>
                    <span className={clsx('badge-status', statusBadge(traceDetail.summary.snapshot?.status))}>
                      {traceDetail.summary.snapshot?.status ?? 'unknown'}
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between gap-4 py-2 border-b" style={{ borderColor: DIVIDER }}>
                    <span className="opacity-50">{t('obs.events', 'Events')}</span>
                    <span className="tabular-nums">{traceDetail.summary.event_count}</span>
                  </div>
                  <div className="flex items-baseline justify-between gap-4 py-2 border-b" style={{ borderColor: DIVIDER }}>
                    <span className="opacity-50">{t('obs.duration', 'Duration')}</span>
                    <span className="tabular-nums">{durationLabel(traceDetail.summary)}</span>
                  </div>
                  {traceDetail.summary.snapshot?.agent_id && (
                    <div className="flex items-baseline justify-between gap-4 py-2 border-b" style={{ borderColor: DIVIDER }}>
                      <span className="opacity-50">agent_id</span>
                      <span className="text-[12px]">{traceDetail.summary.snapshot.agent_id}</span>
                    </div>
                  )}
                </div>

                {/* 事件时间线 */}
                <h3 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
                  {t('obs.timeline', 'Event Timeline')}
                </h3>
                <div className="max-h-80 overflow-y-auto pr-1">
                  {traceDetail.events.length === 0 ? (
                    <p className="empty-state">{t('obs.noEvents', 'No events recorded')}</p>
                  ) : (
                    traceDetail.events.map((ev, idx) => (
                      <div key={`${ev.timestamp}-${idx}`} className="row-line flex items-start gap-2">
                        <span
                          className={clsx('mt-1.5 h-2 w-2 rounded-full shrink-0', eventIsFailure(ev.event) ? 'bg-[#dc2626]' : 'bg-[#16a34a]')}
                          aria-hidden="true"
                        />
                        <div className="min-w-0">
                          <p className={clsx('font-mono text-xs font-medium', eventIsFailure(ev.event) && 'text-[#dc2626]')}>
                            {ev.event}
                          </p>
                          <p className="cell-data opacity-50">
                            {new Date(ev.timestamp).toLocaleTimeString()}
                            {ev.agent_id ? ` · ${ev.agent_id}` : ''}
                          </p>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {/* 回放: 关联资源计数 */}
                {traceReplay && (
                  <div className="mt-6">
                    <h3 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
                      {t('obs.replayResources', 'Replay — Related Resources')}
                    </h3>
                    <dl className="flex flex-wrap gap-y-4">
                      {([
                        ['approvals', traceReplay.snapshot?.related_resources?.approvals?.length ?? 0],
                        ['audit_records', traceReplay.snapshot?.related_resources?.audit_records?.length ?? 0],
                        ['memory_items', traceReplay.snapshot?.related_resources?.memory_items?.length ?? 0],
                        ['tool_executions', traceReplay.snapshot?.related_resources?.tool_executions?.length ?? 0],
                      ] as Array<[string, number]>).map(([name, count], i) => (
                        <div
                          key={name}
                          className={clsx('flex flex-col gap-1 pr-6 mr-6', i < 3 && 'border-r')}
                          style={i < 3 ? { borderColor: DIVIDER } : undefined}
                        >
                          <dd className="font-data text-[20px] leading-none order-2">{count}</dd>
                          <dt className="text-[12px] uppercase tracking-[0.06em] opacity-50 order-1">{name}</dt>
                        </div>
                      ))}
                    </dl>
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}

export default ObservabilityPage
