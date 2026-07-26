// mobile/src/services/mobileRunService.ts
// P2-08: 移动端任务触发 + 进度监控服务
// 对齐后端真实端点 backend/app/api/mobile.py:
//   POST /api/v1/mobile/trigger              触发 Agent 执行
//   GET  /api/v1/mobile/runs/{run_id}/status 查询 run 实时状态
//   POST /api/v1/mobile/runs/{run_id}/cancel 取消执行

import { apiClient } from './apiClient';

export type RunStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type TriggerPriority = 'low' | 'normal' | 'high' | 'urgent';

export interface TriggerRequestBody {
  task: string;
  agent_id?: string;
  priority?: TriggerPriority;
  timeout_seconds?: number;
  notify_on_complete?: boolean;
  metadata?: Record<string, any>;
}

export interface TriggerResponseData {
  run_id: string;
  trace_id: string;
  status: string;
  created_at: string;
  estimated_duration_seconds: number;
  ws_url: string;
}

export interface RunStatusData {
  run_id: string;
  trace_id: string;
  status: RunStatus;
  progress_percent: number;
  current_step: string;
  started_at: string | null;
  completed_at: string | null;
  result_summary: string;
  error: string | null;
  iterations: number;
  tool_calls_count: number;
}

export const TERMINAL_STATUSES: RunStatus[] = [
  'completed',
  'failed',
  'cancelled',
];

export const isTerminalStatus = (status: RunStatus): boolean =>
  TERMINAL_STATUSES.includes(status);

/** 远程触发 Agent 执行任务, 返回 run_id 用于后续状态轮询 */
export async function triggerAgentRun(
  body: TriggerRequestBody
): Promise<TriggerResponseData> {
  return apiClient.post<TriggerResponseData>('/api/v1/mobile/trigger', {
    agent_id: 'default',
    priority: 'normal',
    notify_on_complete: true,
    ...body,
  });
}

/** 查询 run 实时状态 */
export async function getRunStatus(runId: string): Promise<RunStatusData> {
  return apiClient.get<RunStatusData>(`/api/v1/mobile/runs/${runId}/status`);
}

/** 取消正在执行的 run */
export async function cancelRun(
  runId: string
): Promise<{ run_id: string; status: string }> {
  return apiClient.post<{ run_id: string; status: string }>(
    `/api/v1/mobile/runs/${runId}/cancel`
  );
}
