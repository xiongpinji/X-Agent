import type { ConsoleState } from "./consoleReducer";

export type ExecutionControlRecommendation = {
  action: string;
  reason: string;
};

export type ExecutionControlOverviewData = {
  /**
   * 总览信封是否真的到达。
   *
   * 没有它，调用方只能看到一排 0，无法区分「确实没有活跃执行」和
   * 「请求失败/还没回来」—— 这正是读路径静默降级的本体。
   */
  loaded: boolean;
  activeRuns: number;
  pendingRuns: number;
  failedRuns: number;
  completedRuns: number;
  interventionCount: number;
  riskLevel: string;
  dispatch: DispatchResult | null;
  executionPlan: Record<string, unknown> | null;
  recommendations: ExecutionControlRecommendation[];
};

/**
 * 运行控制总览。
 *
 * 数据来源只有一处：`/api/v1/execution-control/overview` 的真实信封（ConsoleShell
 * 拉取后存入 `state.executionControlOverview`）。信封未到达时 `loaded: false`，
 * 数值一律 0 且 `riskLevel` 为「未知」—— **不伪造**「风险等级：低」这类判定，
 * 也不编造带置信度的建议。
 *
 * 历史缺陷两处：
 * 1. 丢弃真实信封，改用 `state.dispatch` 现算近似值 —— 而后端 DispatchResult 里
 *    根本没有 `actions` / `pending` / `last_result` 字段，恒为空数组 ⇒ KPI 恒 0，
 *    后端明明回了 `active_runs: 6` 却被忽略。
 * 2. `recommendations` 硬编码两条 `confidence: "92%"` 的建议，让用户以为系统
 *    做过置信度评估。
 */
export function selectExecutionControlOverviewData(state: ConsoleState): ExecutionControlOverviewData {
  const api = state.executionControlOverview;

  if (!api) {
    return {
      loaded: false,
      activeRuns: 0,
      pendingRuns: 0,
      failedRuns: 0,
      completedRuns: 0,
      interventionCount: 0,
      riskLevel: "未知",
      dispatch: null,
      executionPlan: null,
      recommendations: [],
    };
  }

  return {
    loaded: true,
    activeRuns: api.primary.active_runs,
    pendingRuns: api.primary.pending_runs,
    failedRuns: api.primary.failed_runs,
    completedRuns: api.primary.completed_runs,
    interventionCount: api.primary.intervention_count,
    riskLevel: api.primary.risk_level,
    dispatch: api.primary.dispatch ?? null,
    executionPlan: api.primary.execution_plan ?? null,
    // 后端 overview 信封没有建议字段。宁可空着，也不编造带置信度的处置建议。
    recommendations: [],
  };
}

/**
 * 详情 / 恢复 / 调度三页当前要看的 run。
 *
 * 这三个页面**自己**从 `/api/v1/execution-control/{detail,recovery,dispatch}/{run_id}`
 * 拉数据，selector 只负责把「用户选中的 run」交给它们。
 *
 * 历史缺陷（Critical）：这里曾无条件返回硬编码 fixture —— `failure: { status:
 * "可恢复", level: "中" }`、`recommendation: { confidence: "92%" }`、
 * `recommendations: demoRecommendations` —— 经 ConsoleShell 以 props 注入页面。
 * 页面里 `props.x ?? (apiData ? 真值 : null)` 因此**永远命中 props 分支**，
 * 页面 fetch 到的真实数据被静默丢弃，控制台渲染的始终是 demo。
 *
 * 同一处还有第二个 bug：没有选中项时用编造的 `"run-001"` / `"run-003"` 去请求，
 * 后端会为任何 id 返回一份体面的假数据 —— 假 run 上跑假流程，用户看不出破绽。
 * 现在返回 `null`，由页面显示「未选择任务」。
 */
export function selectExecutionControlRunId(state: ConsoleState): string | null {
  return state.selectedWorkflowId ?? state.dispatch.last_result?.task_id ?? null;
}
