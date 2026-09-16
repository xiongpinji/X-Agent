/**
 * execution 域读路径 Critical（B1）的契约。
 *
 * 这批缺陷的共同形态是：**读失败或未读，却渲染一套看起来合理的业务数据**。
 * 其中 selector 层是真正的修复点 —— `executionControlSelectors` 曾经无条件返回
 * 硬编码 fixture（`status: "可恢复"` / `confidence: "92%"` / demo 建议列表），
 * 经 ConsoleShell 以 props 注入页面，使页面里的 `props.x ?? 真值` **永远命中
 * props 分支**，fetch 到的真实数据被静默丢弃。所以这里既钉页面，也钉 selector。
 *
 * 断言一律选**可观测的 DOM 行为 / 纯函数返回值**，并且显式断言那些 demo 文案
 * **不再出现** —— 只断言「失败态可见」是不够的：一个既渲染失败态、又留着 demo
 * 兜底的实现同样会通过。
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

import { ExecutionDetailPage } from '@/console/pages/execution/ExecutionDetailPage'
import { ExecutionDispatchPage } from '@/console/pages/execution/ExecutionDispatchPage'
import { ExecutionRecoveryPage } from '@/console/pages/execution/ExecutionRecoveryPage'
import { ExecutionOverviewPage } from '@/console/pages/execution/ExecutionOverviewPage'
import {
  selectExecutionControlOverviewData,
  selectExecutionControlRunId,
} from '@/console/state/executionControlSelectors'
import { createInitialConsoleState, type ExecutionControlOverview } from '@/console/state/consoleReducer'

const okResponse = (payload: unknown) => ({ ok: true, status: 200, json: async () => payload })
const failResponse = (status: number) => ({ ok: false, status, json: async () => ({ detail: 'boom' }) })

/** 全文检索用。断言「不再出现 demo 文案」比只断言失败态严格得多。 */
const bodyText = () => document.body.textContent ?? ''

/** 曾经被硬编码、且与真实业务语义无法区分的 demo 文案。 */
const DEMO_MARKERS = [
  '工具调用工作流',
  '短剧导演',
  '接收任务',
  '生成计划',
  '外部工具超时',
  '先重试，再确认外部依赖',
  '优先处理失败任务',
  '内容生成任务',
  '审计回放任务',
  '工具执行任务',
  '92%',
  '88%',
]

afterEach(() => {
  vi.unstubAllGlobals()
})

// ---------------------------------------------------------------------------
// 执行详情
// ---------------------------------------------------------------------------

const detailPayload = {
  resource_type: 'execution_control_detail',
  resource_id: 'run-9',
  primary: {
    run_id: 'run-9',
    task_name: '真实任务名',
    status: 'running',
    trigger_source: 'workflow',
    owner: 'agent-7',
    current_step: 'tool.execute',
    current_step_label: '调用工具',
    progress: 33,
    progress_label: '33%',
    result_summary: '等待工具返回',
    risk_level: 'high',
  },
  linked_summaries: {
    messages: { summary: { title: '真实消息摘要' }, data: {} },
    audit: { summary: { title: '真实审计摘要' }, data: {} },
    memory: { summary: { title: '真实记忆摘要' }, data: {} },
  },
}

describe('ExecutionDetailPage', () => {
  it('读失败渲染失败态，且不再出现任何 demo 执行剖面', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(failResponse(500)))
    render(<ExecutionDetailPage runId="run-9" />)

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('加载执行详情失败')
    expect(alert.textContent).toContain('服务暂时不可用')

    // 历史兜底：{ name: "工具调用工作流", status: "运行中" } / demoSteps / ?? "medium" / ?? 72%
    for (const marker of DEMO_MARKERS) {
      expect(bodyText()).not.toContain(marker)
    }
    expect(bodyText()).not.toContain('运行中')
    expect(bodyText()).not.toContain('medium')
    expect(bodyText()).not.toContain('72%')
    expect(screen.queryByText(/暂无执行步骤明细/)).toBeNull()
  })

  it('读成功时展示后端真实字段（而不是 demo）', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okResponse(detailPayload)))
    render(<ExecutionDetailPage runId="run-9" />)

    expect(await screen.findByText('真实任务名')).toBeTruthy()
    expect(screen.getByText('33%')).toBeTruthy()
    expect(screen.getByText('high')).toBeTruthy()
    expect(screen.getByText('真实消息摘要')).toBeTruthy()

    for (const marker of DEMO_MARKERS) {
      expect(bodyText()).not.toContain(marker)
    }
  })

  it('未选中 run 时不发请求、也不渲染编造的任务', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<ExecutionDetailPage runId={null} />)

    expect(await screen.findByText('未选择执行任务')).toBeTruthy()
    expect(fetchMock).not.toHaveBeenCalled()
    // 历史上这里会拿 "run-001" 去请求，后端为任何 id 都回一份体面的假数据
    expect(bodyText()).not.toContain('run-001')
  })
})

// ---------------------------------------------------------------------------
// 调度建议
// ---------------------------------------------------------------------------

const dispatchPayload = {
  resource_type: 'execution_control_dispatch',
  resource_id: 'run-9',
  primary: {
    run_id: 'run-9',
    suggested_action: '排队重试',
    confidence: 0.42,
    risk_level: 'low',
    requires_confirmation: true,
    impact_summary: '影响摘要来自后端',
    recommended_order: ['甲', '乙'],
    decision_reason: '决策理由来自后端',
  },
  linked_summaries: {
    workflow: { summary: { title: '工作流依据' }, data: {} },
  },
}

describe('ExecutionDispatchPage', () => {
  it('读失败渲染失败态，且不再出现 demo 建议与置信度', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(failResponse(503)))
    render(<ExecutionDispatchPage runId="run-9" />)

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('加载调度建议失败')

    expect(bodyText()).not.toContain('优先重试工具调用')
    expect(bodyText()).not.toContain('重试 → 检查依赖 → 恢复执行')
    expect(bodyText()).not.toContain('恢复执行并继续当前任务')
    expect(bodyText()).not.toContain('重复执行消耗额外资源')
    expect(bodyText()).not.toContain('92%')
  })

  it('读成功时置信度与顺序都来自后端真实值', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okResponse(dispatchPayload)))
    render(<ExecutionDispatchPage runId="run-9" />)

    // 「排队重试」同时出现在建议摘要与建议列表
    expect((await screen.findAllByText('排队重试')).length).toBeGreaterThan(0)
    expect(bodyText()).toContain('42%') // 0.42 → 42%，而不是硬编码的 92%
    expect(bodyText()).toContain('甲 → 乙')
    expect(bodyText()).toContain('影响摘要来自后端')
    expect(bodyText()).not.toContain('92%')
  })
})

// ---------------------------------------------------------------------------
// 失败恢复
// ---------------------------------------------------------------------------

const recoveryPayload = {
  resource_type: 'execution_control_recovery',
  resource_id: 'run-9',
  primary: {
    run_id: 'run-9',
    status: 'needs_review',
    failure_level: 'critical',
    failure_reason: '上游凭据已过期',
    current_step: 'auth.refresh',
    can_retry: false,
    can_rollback: true,
    needs_human: true,
    retry_priority: 'low',
    recovery_mode: 'manual-only',
  },
  linked_summaries: {},
}

describe('ExecutionRecoveryPage', () => {
  it('读失败渲染失败态，且不再出现「可恢复 / 优先重试」这类处置指引', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(failResponse(500)))
    render(<ExecutionRecoveryPage runId="run-9" />)

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('加载失败恢复信息失败')

    expect(bodyText()).not.toContain('可恢复')
    expect(bodyText()).not.toContain('工具执行步骤')
    expect(bodyText()).not.toContain('外部工具超时')
    expect(bodyText()).not.toContain('先重试，再确认外部依赖')
    expect(bodyText()).not.toContain('优先检查外部工具是否恢复')
  })

  it('读成功时状态 / 等级 / 失败原因都来自后端', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okResponse(recoveryPayload)))
    render(<ExecutionRecoveryPage runId="run-9" />)

    expect(await screen.findByText('needs_review')).toBeTruthy()
    expect(screen.getByText('critical')).toBeTruthy()
    expect(screen.getByText('上游凭据已过期')).toBeTruthy()
    expect(screen.getByText('manual-only')).toBeTruthy()
    // can_retry=false / needs_human=true —— 与 demo 的「可重试：是」相反，正是要害
    expect(bodyText()).not.toContain('可恢复')
  })
})

// ---------------------------------------------------------------------------
// 运行控制总览（本页不 fetch，缺陷是整页硬编码 demo —— 扫描器扫不到）
// ---------------------------------------------------------------------------

describe('ExecutionOverviewPage', () => {
  it('信封未到达时显示「尚未加载」，而不是 0 与 demo 任务', () => {
    render(<ExecutionOverviewPage loaded={false} runId={null} />)

    expect(screen.getByText('总览数据尚未加载')).toBeTruthy()

    for (const marker of DEMO_MARKERS) {
      expect(bodyText()).not.toContain(marker)
    }
    expect(bodyText()).not.toContain('72%')
    expect(bodyText()).not.toContain('tool timeout')
    // 未加载时数值位必须是「-」，不能渲染成「0 个失败任务」这种伪结论
    expect(screen.getAllByText('-').length).toBeGreaterThanOrEqual(5)
  })

  it('未显式传 loaded 时按「未加载」处理（fail-closed，不冒充已加载）', () => {
    render(<ExecutionOverviewPage runId={null} />)

    // 默认值必须是 false：漏传参数比「伪造 0」安全得多
    expect(screen.getByText('总览数据尚未加载')).toBeTruthy()
    expect(screen.getAllByText('-').length).toBeGreaterThanOrEqual(5)
    for (const marker of DEMO_MARKERS) {
      expect(bodyText()).not.toContain(marker)
    }
  })

  it('信封到达时 KPI 显示真实数值', () => {
    render(
      <ExecutionOverviewPage
        loaded
        runId="run-9"
        activeRuns={6}
        pendingRuns={4}
        failedRuns={1}
        completedRuns={12}
        interventionCount={1}
        riskLevel="medium"
      />,
    )

    for (const value of ['6', '4', '12', 'medium']) {
      expect(screen.getByText(value)).toBeTruthy()
    }
    expect(screen.queryByText('总览数据尚未加载')).toBeNull()
  })

  it('没有真实选中项时不给「打开详情 / 恢复 / 调度」入口', () => {
    const { unmount } = render(<ExecutionOverviewPage loaded runId={null} />)
    expect(screen.getByText('尚未选中任务')).toBeTruthy()
    expect(screen.queryByText('打开执行详情')).toBeNull()
    unmount()

    const onOpenDetail = vi.fn()
    render(<ExecutionOverviewPage loaded runId="run-9" onOpenDetail={onOpenDetail} />)
    fireEvent.click(screen.getByText('打开执行详情'))
    expect(onOpenDetail).toHaveBeenCalledWith('run-9')
  })
})

// ---------------------------------------------------------------------------
// selector 层 —— 真正的修复点
// ---------------------------------------------------------------------------

describe('executionControlSelectors', () => {
  it('runId 不再兜底成编造的 "run-001"', () => {
    expect(selectExecutionControlRunId(createInitialConsoleState())).toBeNull()
    expect(
      selectExecutionControlRunId({ ...createInitialConsoleState(), selectedWorkflowId: 'wf-1' }),
    ).toBe('wf-1')
  })

  it('总览信封缺失时 loaded=false、数值为 0、风险等级不是「低」', () => {
    const data = selectExecutionControlOverviewData(createInitialConsoleState())

    expect(data.loaded).toBe(false)
    expect(data.activeRuns).toBe(0)
    expect(data.failedRuns).toBe(0)
    expect(data.riskLevel).toBe('未知')
    expect(data.recommendations).toEqual([])
  })

  it('总览信封到达时映射真实值，且建议列表为空（不编造置信度）', () => {
    const envelope: ExecutionControlOverview = {
      resource_type: 'execution_control_overview',
      resource_id: 'sess-1',
      primary: {
        active_runs: 6,
        pending_runs: 4,
        failed_runs: 1,
        completed_runs: 12,
        intervention_count: 1,
        risk_level: 'medium',
        dispatch: createInitialConsoleState().dispatch,
        execution_plan: { task_id: 'run-9' },
      },
      linked_summaries: {
        dispatch: { summary: { title: 'd' }, data: {} },
        execution: { summary: { title: 'e' }, data: {} },
        audit: { summary: { title: 'a' }, data: {} },
        messages: { summary: { title: 'm' }, data: {} },
      },
    }
    const data = selectExecutionControlOverviewData({
      ...createInitialConsoleState(),
      executionControlOverview: envelope,
    })

    expect(data.loaded).toBe(true)
    expect(data.activeRuns).toBe(6)
    expect(data.completedRuns).toBe(12)
    expect(data.riskLevel).toBe('medium')
    // 后端 overview 信封没有建议字段 —— 不编造
    expect(data.recommendations).toEqual([])
    expect(JSON.stringify(data)).not.toContain('92%')
  })
})
