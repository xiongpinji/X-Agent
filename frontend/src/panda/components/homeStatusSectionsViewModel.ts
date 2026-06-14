import type { PandaWorkbenchDataSource } from '../api/workbenchClient'
import type { PandaWorkbenchHome, PandaWorkbenchMetrics } from '../types'

export type PlatformSnapshotMetricRow = readonly [label: string, value: number | string, unit: string]

export type PlatformSnapshotViewModel = {
  readonly loadingTitle: string
  readonly loadingDescription: string
  readonly errorDescription: string | null
  readonly metricRows: readonly PlatformSnapshotMetricRow[]
  readonly controlRows: readonly PlatformSnapshotMetricRow[]
  readonly runtimeRows: readonly PlatformSnapshotMetricRow[]
  readonly coreLabel: string
  readonly summary: string
  readonly controlBoundary: string
  readonly runtimeBoundary: string
}

export function buildPlatformSnapshotMetricRows(
  metrics: PandaWorkbenchMetrics | undefined,
): readonly PlatformSnapshotMetricRow[] {
  return [
    ['活跃智能体', metrics?.activeAgents ?? 8, '个'],
    ['运行工作流', metrics?.runningWorkflows ?? 5, '条'],
    ['待审批', metrics?.pendingApprovals ?? 3, '项'],
    ['API 调用', metrics?.apiCalls ?? 12428, '次'],
    ['存储使用', metrics?.storageUsed ?? '45.2 GB / 1 TB', ''],
  ] as const
}

export function buildPlatformSnapshotViewModel({
  home,
  source,
  isLoading,
  error,
}: {
  readonly home: PandaWorkbenchHome | null
  readonly source: PandaWorkbenchDataSource
  readonly isLoading: boolean
  readonly error: string | null
}): PlatformSnapshotViewModel {
  const errorDescription =
    !isLoading && source === 'mock' && error
      ? `${error}。当前展示本地演示数据，等待后端主线收尾后切换真实资源。`
      : null

  return {
    loadingTitle: '正在同步工作台',
    loadingDescription: '正在读取首页聚合数据和执行态势。',
    errorDescription,
    metricRows: buildPlatformSnapshotMetricRows(home?.metrics),
    controlRows: [
      ['Plan 草稿', home?.controlSummary.planCount ?? 0, '项'],
      ['Goal 目标', home?.controlSummary.goalCount ?? 0, '项'],
      ['执行入口', home?.controlSummary.executeEnabled ? '已暴露' : '未暴露', ''],
    ],
    runtimeRows: [
      ['主线能力', home?.runtimeCapabilitySummary.mainlineWiredCount ?? 0, '项'],
      ['API/CLI 证据', home?.runtimeCapabilitySummary.apiCliEvidenceCount ?? 0, '项'],
      ['候选未接入', home?.runtimeCapabilitySummary.detachedCandidateCount ?? 0, '项'],
      ['过期证据', home?.runtimeCapabilitySummary.staleEvidenceCount ?? 0, '项'],
    ],
    coreLabel: 'Powered by X-Agent Autonomous Framework',
    summary: home?.summary ?? '企业级自主智能体框架，覆盖编排、记忆、工具、审计和多渠道运行。',
    controlBoundary:
      home?.controlSummary.boundary ??
      'Control plan/goal state is unavailable in this view; no execution controls are exposed.',
    runtimeBoundary:
      home?.runtimeCapabilitySummary.boundary ??
      'Runtime capability status is unavailable; detached candidates are not delivered mainline capability.',
  }
}
