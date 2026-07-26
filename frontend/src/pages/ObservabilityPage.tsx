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
  Activity,
  AlertTriangle,
  CheckCircle,
  Clock,
  Database,
  GitBranch,
  KeyRound,
  RefreshCw,
  ShieldCheck,
  Workflow,
  XCircle,
  Play,
  ChevronRight,
} from 'lucide-react'
import clsx from 'clsx'

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

  const statusBadge = (status?: string) => {
    const s = status ?? 'unknown'
    if (s === 'completed' || s === 'success') return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
    if (s === 'failed' || s === 'error') return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
    if (s === 'running' || s === 'in_progress') return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
    return 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
  }

  const eventIsFailure = (kind: string) => kind === 'agent.failed' || kind === 'tool.execution.failed'

  const metricCards = useMemo(() => {
    if (!metrics) return []
    return [
      { label: t('obs.runs', 'Runs'), value: metrics.runs, icon: Activity, color: 'text-blue-500' },
      { label: t('obs.traces', 'Traces'), value: metrics.traces, icon: GitBranch, color: 'text-purple-500' },
      { label: t('obs.traceEvents', 'Trace Events'), value: metrics.trace_events, icon: Clock, color: 'text-indigo-500' },
      { label: t('obs.memories', 'Memories'), value: metrics.memories, icon: Database, color: 'text-teal-500' },
      { label: t('obs.workflows', 'Workflows'), value: metrics.workflows, icon: Workflow, color: 'text-amber-500' },
      { label: t('obs.workflowRuns', 'Workflow Runs'), value: metrics.workflow_runs, icon: Play, color: 'text-orange-500' },
      { label: t('obs.auditLogs', 'Audit Logs'), value: metrics.audit_logs, icon: ShieldCheck, color: 'text-slate-500' },
      { label: t('obs.apiKeys', 'API Keys'), value: `${metrics.active_api_keys}/${metrics.api_keys}`, icon: KeyRound, color: 'text-rose-500' },
      { label: t('obs.approvals', 'Approvals'), value: `${metrics.pending_approvals}/${metrics.approvals}`, icon: AlertTriangle, color: 'text-yellow-500' },
    ]
  }, [metrics, t])

  const cardCls = clsx(
    'rounded-lg p-6',
    theme === 'dark' ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200'
  )
  const subTextCls = clsx('text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')

  return (
    <div className={clsx('p-8', theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50')}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className={clsx('text-3xl font-bold mb-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              {t('obs.title', 'Observability')}
            </h1>
            <p className={subTextCls}>
              {t('obs.subtitle', 'Metrics, health status and trace inspection')}
            </p>
          </div>
          <button
            onClick={loadAll}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            {t('common.refresh', 'Refresh')}
          </button>
        </div>

        {/* ── 健康状态 + 指标卡片 ──────────────────────────────── */}
        {ops && (
          <div className={clsx(
            'rounded-lg p-4 mb-6 flex flex-wrap items-center gap-6',
            ops.healthy
              ? 'bg-green-50 border border-green-200 dark:bg-green-900/20 dark:border-green-800'
              : 'bg-red-50 border border-red-200 dark:bg-red-900/20 dark:border-red-800'
          )}>
            <div className="flex items-center gap-2">
              {ops.healthy
                ? <CheckCircle size={20} className="text-green-600" />
                : <XCircle size={20} className="text-red-600" />}
              <span className={clsx('font-semibold', ops.healthy ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400')}>
                {ops.healthy ? t('obs.healthy', 'System Healthy') : t('obs.unhealthy', 'Issues Detected')}
              </span>
            </div>
            <span className={subTextCls}>{t('obs.approvalBacklog', 'Approval backlog')}: <b>{ops.approval_backlog}</b></span>
            <span className={subTextCls}>{t('obs.toolFailures', 'Tool failures')}: <b>{ops.tool_failures}</b></span>
            <span className={subTextCls}>{t('obs.failureTraces', 'Failure traces')}: <b>{ops.failure_traces.length}</b></span>
            <span className={subTextCls}>{t('obs.toolsRegistered', 'Tools registered')}: <b>{ops.overview.tools}</b></span>
          </div>
        )}

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-9 gap-3 mb-8">
          {metricCards.map(({ label, value, icon: Icon, color }) => (
            <div key={label} className={clsx(cardCls, 'p-4')}>
              <div className="flex items-center gap-1.5 mb-1">
                <Icon size={14} className={color} />
                <p className="text-xs text-slate-500 truncate">{label}</p>
              </div>
              <p className={clsx('text-xl font-bold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                {typeof value === 'number' ? value.toLocaleString() : value}
              </p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* ── Trace 列表 ─────────────────────────────────────── */}
          <div className={cardCls}>
            <h2 className={clsx('text-lg font-semibold mb-4 flex items-center gap-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              <GitBranch size={20} className="text-purple-500" />
              {t('obs.tracesTitle', 'Recent Traces')}
            </h2>

            {/* 失败 trace 提示 (来自 /ops/summary) */}
            {ops && ops.failure_traces.length > 0 && (
              <div className={clsx('rounded-lg p-3 mb-4 text-sm', theme === 'dark' ? 'bg-red-900/20 text-red-300' : 'bg-red-50 text-red-700')}>
                <p className="font-medium mb-1 flex items-center gap-1">
                  <AlertTriangle size={14} />
                  {t('obs.recentFailures', 'Recent failures')}
                </p>
                <ul className="space-y-1 text-xs font-mono">
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
              <p className={subTextCls}>{t('obs.noTraces', 'No traces found')}</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className={clsx('border-b', theme === 'dark' ? 'border-slate-700' : 'border-slate-200')}>
                    <tr>
                      {[t('obs.traceId', 'Trace'), t('obs.task', 'Task'), t('obs.status', 'Status'), t('obs.events', 'Events'), t('obs.duration', 'Duration'), ''].map((h, i) => (
                        <th key={i} className={clsx('px-3 py-2 text-left text-sm font-semibold', theme === 'dark' ? 'text-slate-300' : 'text-slate-900')}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {traces.map((tr) => (
                      <tr
                        key={tr.trace_id}
                        className={clsx(
                          'border-b cursor-pointer transition-colors',
                          theme === 'dark' ? 'border-slate-800 hover:bg-slate-800/60' : 'border-slate-100 hover:bg-slate-50',
                          selectedTraceId === tr.trace_id && (theme === 'dark' ? 'bg-slate-800' : 'bg-blue-50')
                        )}
                        onClick={() => handleSelectTrace(tr.trace_id)}
                      >
                        <td className={clsx('px-3 py-2.5 text-sm font-mono', theme === 'dark' ? 'text-slate-300' : 'text-slate-700')}>
                          {tr.trace_id.slice(0, 10)}…
                        </td>
                        <td className={clsx('px-3 py-2.5 text-sm max-w-[180px] truncate', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
                          {tr.task ?? '—'}
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={clsx('text-xs px-2 py-0.5 rounded font-medium', statusBadge(tr.snapshot?.status))}>
                            {tr.snapshot?.status ?? 'unknown'}
                          </span>
                        </td>
                        <td className={clsx('px-3 py-2.5 text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
                          {tr.event_count}
                        </td>
                        <td className={clsx('px-3 py-2.5 text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
                          {durationLabel(tr)}
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <ChevronRight size={14} className="inline text-slate-400" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ── Trace 详情 (事件时间线 + 回放) ─────────────────── */}
          <div className={cardCls}>
            <div className="flex items-center justify-between mb-4">
              <h2 className={clsx('text-lg font-semibold flex items-center gap-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
                <Activity size={20} className="text-blue-500" />
                {t('obs.traceDetail', 'Trace Detail')}
              </h2>
              <button
                onClick={handleReplay}
                disabled={!selectedTraceId || replayLoading}
                className="flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg bg-purple-600 hover:bg-purple-700 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-colors"
              >
                <Play size={14} />
                {replayLoading ? t('common.loading', 'Loading...') : t('obs.replay', 'Replay')}
              </button>
            </div>

            {!selectedTraceId ? (
              <p className={subTextCls}>{t('obs.selectTrace', 'Select a trace from the list to inspect its event timeline')}</p>
            ) : detailLoading ? (
              <p className={subTextCls}>{t('common.loading', 'Loading...')}</p>
            ) : !traceDetail ? (
              <p className={subTextCls}>{t('obs.detailFailed', 'Failed to load trace detail')}</p>
            ) : (
              <>
                {/* 摘要 */}
                <div className={clsx('rounded-lg p-3 mb-4 text-sm grid grid-cols-2 gap-2', theme === 'dark' ? 'bg-slate-800' : 'bg-slate-50')}>
                  <span className={subTextCls}>trace_id</span>
                  <span className={clsx('font-mono text-xs break-all', theme === 'dark' ? 'text-slate-200' : 'text-slate-700')}>
                    {traceDetail.summary.trace_id}
                  </span>
                  <span className={subTextCls}>{t('obs.status', 'Status')}</span>
                  <span className={clsx('text-xs px-2 py-0.5 rounded font-medium w-fit', statusBadge(traceDetail.summary.snapshot?.status))}>
                    {traceDetail.summary.snapshot?.status ?? 'unknown'}
                  </span>
                  <span className={subTextCls}>{t('obs.events', 'Events')}</span>
                  <span className={theme === 'dark' ? 'text-slate-200' : 'text-slate-700'}>{traceDetail.summary.event_count}</span>
                  <span className={subTextCls}>{t('obs.duration', 'Duration')}</span>
                  <span className={theme === 'dark' ? 'text-slate-200' : 'text-slate-700'}>{durationLabel(traceDetail.summary)}</span>
                  {traceDetail.summary.snapshot?.agent_id && (
                    <>
                      <span className={subTextCls}>agent_id</span>
                      <span className={clsx('font-mono text-xs', theme === 'dark' ? 'text-slate-200' : 'text-slate-700')}>
                        {traceDetail.summary.snapshot.agent_id}
                      </span>
                    </>
                  )}
                </div>

                {/* 事件时间线 */}
                <p className={clsx('text-sm font-medium mb-2', theme === 'dark' ? 'text-slate-300' : 'text-slate-700')}>
                  {t('obs.timeline', 'Event Timeline')}
                </p>
                <div className="max-h-80 overflow-y-auto space-y-1 pr-1">
                  {traceDetail.events.length === 0 ? (
                    <p className={subTextCls}>{t('obs.noEvents', 'No events recorded')}</p>
                  ) : (
                    traceDetail.events.map((ev, idx) => (
                      <div
                        key={`${ev.timestamp}-${idx}`}
                        className={clsx(
                          'rounded-lg px-3 py-2 text-sm flex items-start gap-2',
                          eventIsFailure(ev.event)
                            ? (theme === 'dark' ? 'bg-red-900/20' : 'bg-red-50')
                            : (theme === 'dark' ? 'bg-slate-800' : 'bg-slate-50')
                        )}
                      >
                        {eventIsFailure(ev.event)
                          ? <XCircle size={14} className="text-red-500 mt-0.5 shrink-0" />
                          : <CheckCircle size={14} className="text-green-500 mt-0.5 shrink-0" />}
                        <div className="min-w-0">
                          <p className={clsx('font-mono text-xs font-medium', eventIsFailure(ev.event) ? 'text-red-600 dark:text-red-400' : (theme === 'dark' ? 'text-slate-200' : 'text-slate-700'))}>
                            {ev.event}
                          </p>
                          <p className="text-xs text-slate-500">
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
                  <div className="mt-4">
                    <p className={clsx('text-sm font-medium mb-2', theme === 'dark' ? 'text-slate-300' : 'text-slate-700')}>
                      {t('obs.replayResources', 'Replay — Related Resources')}
                    </p>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                      {([
                        ['approvals', traceReplay.snapshot?.related_resources?.approvals?.length ?? 0],
                        ['audit_records', traceReplay.snapshot?.related_resources?.audit_records?.length ?? 0],
                        ['memory_items', traceReplay.snapshot?.related_resources?.memory_items?.length ?? 0],
                        ['tool_executions', traceReplay.snapshot?.related_resources?.tool_executions?.length ?? 0],
                      ] as Array<[string, number]>).map(([name, count]) => (
                        <div key={name} className={clsx('rounded-lg p-2 text-center', theme === 'dark' ? 'bg-slate-800' : 'bg-slate-50')}>
                          <p className={clsx('text-lg font-bold', theme === 'dark' ? 'text-white' : 'text-slate-900')}>{count}</p>
                          <p className="text-xs text-slate-500">{name}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ObservabilityPage
