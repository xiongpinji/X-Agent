import type { ConsoleState } from "./consoleReducer";

export type ExecutionControlOverviewData = {
  activeRuns: number;
  pendingRuns: number;
  failedRuns: number;
  completedRuns: number;
  interventionCount: number;
  riskLevel: string;
  dispatch: DispatchResult | null;
  executionPlan: Record<string, unknown> | null;
  recommendations: Array<{ action: string; reason: string; confidence: string }>;
};

export function selectExecutionControlOverviewData(state: ConsoleState): ExecutionControlOverviewData {
  const dispatch = state.dispatch;
  const activeRuns = dispatch.pending.length ? dispatch.pending.length : dispatch.actions.length;
  const failedRuns = dispatch.last_result ? 1 : 0;
  const completedRuns = dispatch.actions.filter((action) => action.status === "completed").length;
  const pendingRuns = dispatch.pending.length;

  return {
    activeRuns,
    pendingRuns,
    failedRuns,
    completedRuns,
    interventionCount: failedRuns ? 1 : 0,
    riskLevel: failedRuns ? "中等" : "低",
    dispatch,
    executionPlan: dispatch.last_result ? { task_id: dispatch.last_result.task_id } : null,
    recommendations: failedRuns
      ? [
          { action: "优先重试失败任务", reason: "当前存在失败结果", confidence: "92%" },
          { action: "打开恢复页面", reason: "便于快速处理异常", confidence: "88%" },
        ]
      : [
          { action: "继续监控活跃执行", reason: "当前没有明显失败", confidence: "90%" },
        ],
  };
}

export function selectExecutionControlDetailData(state: ConsoleState) {
  const runId = state.selectedWorkflowId ?? state.dispatch.last_result?.task_id ?? "run-001";
  return {
    runId,
    summary: {
      name: "工具调用工作流",
      status: "运行中",
      triggerSource: "工作流调度",
      owner: state.console.agent_id || state.console.user_id,
    },
    steps: [
      { name: "接收任务", status: "done", duration: "2s", result: "已进入队列" },
      { name: "生成计划", status: "done", duration: "8s", result: "已完成规划" },
      { name: "调用工具", status: "running", duration: "18s", result: "等待工具返回" },
    ],
    toolCalls: [
      { tool: "dispatch", time: "10:12", status: "success", cost: "120ms" },
      { tool: "memory.read", time: "10:13", status: "success", cost: "32ms" },
    ],
    linkedTitles: {
      messages: "关联消息",
      audit: "审计记录",
      memory: "记忆引用",
    },
  };
}

export function selectExecutionControlRecoveryData(state: ConsoleState) {
  const runId = state.selectedAuditMessageId ?? state.dispatch.last_result?.task_id ?? "run-003";
  return {
    runId,
    failure: {
      status: "可恢复",
      level: "中",
      currentStep: "工具执行步骤",
      canRetry: true,
    },
    reasons: [
      { title: "外部工具超时", detail: "工具调用等待超过阈值，当前最适合优先重试。", level: "中" },
      { title: "输入参数缺失", detail: "上游节点未提供完整参数，需要人工确认。", level: "高" },
    ],
    recoverySummary: {
      before: "失败",
      after: "待重试",
      suggestion: "先重试，再确认外部依赖。",
    },
    recommendation: "恢复建议：优先检查外部工具是否恢复。",
  };
}

export function selectExecutionControlDispatchData(state: ConsoleState) {
  const runId = state.selectedWorkflowId ?? state.dispatch.last_result?.task_id ?? "execution-control";
  return {
    runId,
    recommendation: {
      action: "优先重试工具调用",
      confidence: "92%",
      risk: "低",
      requiresConfirmation: false,
    },
    recommendations: [
      { action: "优先重试失败任务", reason: "当前存在失败结果", confidence: "92%", risk: "低" },
      { action: "打开恢复页面", reason: "便于快速处理异常", confidence: "88%", risk: "中" },
    ],
    reasoning: {
      trigger: "工具超时 / 任务卡住",
      relatedModules: "工作流、消息、审计、记忆",
      summary: "当前失败点集中在单一外部依赖。",
    },
    impact: {
      expectedResult: "恢复执行并继续当前任务",
      sideEffect: "重复执行消耗额外资源",
      scope: "当前任务及其相关工作流节点",
    },
  };
}
