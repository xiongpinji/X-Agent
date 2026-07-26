// mobile/src/store/runStore.ts
// P2-08: 任务触发 run 状态管理 (触发 + 轮询进度)

import { create } from 'zustand';
import {
  triggerAgentRun,
  getRunStatus,
  cancelRun,
  isTerminalStatus,
  TriggerPriority,
  RunStatusData,
} from '../services/mobileRunService';

const POLL_INTERVAL_MS = 3000;

interface RunStore {
  currentRun?: RunStatusData;
  taskText: string;
  submitting: boolean;
  polling: boolean;
  error?: string;

  // Actions
  triggerTask: (task: string, priority?: TriggerPriority) => Promise<boolean>;
  refreshRunStatus: () => Promise<void>;
  startPolling: () => void;
  stopPolling: () => void;
  cancelCurrentRun: () => Promise<void>;
  reset: () => void;
  clearError: () => void;
}

let pollTimer: ReturnType<typeof setInterval> | null = null;

export const useRunStore = create<RunStore>((set, get) => ({
  submitting: false,
  polling: false,
  taskText: '',

  triggerTask: async (task: string, priority: TriggerPriority = 'normal') => {
    if (!task.trim()) {
      set({ error: 'Task description is required' });
      return false;
    }
    set({ submitting: true, error: undefined, currentRun: undefined });
    get().stopPolling();
    try {
      const resp = await triggerAgentRun({
        task: task.trim(),
        priority,
        metadata: { source: 'mobile', device_id: 'expo-app' },
      });
      set({
        taskText: task.trim(),
        currentRun: {
          run_id: resp.run_id,
          trace_id: resp.trace_id,
          status: 'pending',
          progress_percent: 0,
          current_step: '',
          started_at: null,
          completed_at: null,
          result_summary: '',
          error: null,
          iterations: 0,
          tool_calls_count: 0,
        },
        submitting: false,
      });
      get().startPolling();
      return true;
    } catch (error) {
      set({ error: String(error), submitting: false });
      return false;
    }
  },

  refreshRunStatus: async () => {
    const runId = get().currentRun?.run_id;
    if (!runId) return;
    try {
      const status = await getRunStatus(runId);
      set({ currentRun: status });
      if (isTerminalStatus(status.status)) {
        get().stopPolling();
      }
    } catch (error) {
      // 轮询失败不打断流程, 仅记录; 连续失败由用户手动停止
      set({ error: String(error) });
    }
  },

  startPolling: () => {
    get().stopPolling();
    set({ polling: true });
    pollTimer = setInterval(() => {
      get().refreshRunStatus();
    }, POLL_INTERVAL_MS);
  },

  stopPolling: () => {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    set({ polling: false });
  },

  cancelCurrentRun: async () => {
    const runId = get().currentRun?.run_id;
    if (!runId) return;
    try {
      await cancelRun(runId);
      await get().refreshRunStatus();
    } catch (error) {
      set({ error: String(error) });
    } finally {
      get().stopPolling();
    }
  },

  reset: () => {
    get().stopPolling();
    set({ currentRun: undefined, taskText: '', error: undefined });
  },

  clearError: () => set({ error: undefined }),
}));
