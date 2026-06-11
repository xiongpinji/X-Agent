import type { ApiWorkbenchActivityItem } from './homeApiContracts'
import { runtimeFixture } from './resourceRuntimeFixtures'

export const workbenchActivityDryRunFixture = {
  id: 'activity-api-1',
  title: 'Activity runtime dry-run',
  subtitle: '右侧态势栏活动运行元数据',
  tone: 'neutral',
  time: '2026-06-10T07:00:00+08:00',
  ...runtimeFixture({ status: 'running', riskLevel: 'warning', progress: 76, ownerAgent: 'Activity Agent', updatedAt: '2026-06-10T07:05:00+08:00', evidenceRef: 'ev-activity-1' }),
} satisfies ApiWorkbenchActivityItem
