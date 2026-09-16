/**
 * console 读路径的「失败 ≠ 空」契约（B0-b 基建）
 *
 * 钉住三件事：
 * 1. 非 2xx 必须进入**失败态**（而不是静默返回后渲染兜底值）；
 * 2. 失败态与空态在 DOM 上**可判别** —— 失败渲染 role="alert"，且不出现
 *    「暂无数据」这类空态文案；反过来空态也不出现失败文案；
 * 3. 失败态在类型与运行时都**没有 data** —— `state.data ?? 0` 这类兜底写不出来。
 *
 * 断言一律选**可观测的 DOM 行为**，不断言内部 state：后者在变异测试里
 * 很容易被空转放过（本仓已有前车之鉴）。
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { useConsoleResource, readFailure, type ReadState } from '@/console/readResource'
import {
  ConsoleReadEmpty,
  ConsoleReadFailure,
  ConsoleReadLoading,
} from '@/console/components/ReadState'

type Payload = { primary: { total_items: number } }

const okResponse = (payload: unknown) => ({ ok: true, status: 200, json: async () => payload })
const failResponse = (status: number) => ({ ok: false, status, json: async () => ({ detail: 'boom' }) })

/** 消费 hook 并按四态分流 —— 这就是页面要写的形态。 */
function Reader({ url = '/api/v1/x', action = '加载发布历史' }: { url?: string; action?: string }) {
  const state = useConsoleResource<Payload>(url, action)
  if (state.status === 'loading') return <ConsoleReadLoading action={action} />
  if (state.status === 'failed') {
    return <ConsoleReadFailure action={action} message={state.error} onRetry={state.reload} />
  }
  return <div data-testid="ready">总数 {state.data.primary.total_items}</div>
}

/** 对照用：可控状态直接喂给视图层，检验失败态与空态互斥。 */
function View({ state }: { state: ReadState<Payload> }) {
  if (state.status === 'loading') return <ConsoleReadLoading action="加载" />
  if (state.status === 'failed') {
    return <ConsoleReadFailure action="加载" message={state.error} />
  }
  if (state.data.primary.total_items === 0) return <ConsoleReadEmpty description="还没有数据" />
  return <div data-testid="ready">总数 {state.data.primary.total_items}</div>
}

/** url 为 null 时（如「没选中任务」）hook 应停在 idle 且不发请求。 */
function IdleReader() {
  const state = useConsoleResource<Payload>(null, '加载发布历史')
  return <div data-testid="status">{state.status}</div>
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useConsoleResource', () => {
  it('成功时进入 ready 并暴露数据', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okResponse({ primary: { total_items: 7 } })))
    render(<Reader />)
    expect(await screen.findByTestId('ready')).toBeTruthy()
    expect(screen.getByTestId('ready').textContent).toContain('7')
  })

  it('非 2xx 进入失败态：渲染 role="alert"，不渲染任何兜底值', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(failResponse(500)))
    render(<Reader />)

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('加载发布历史失败')
    expect(alert.textContent).toContain('服务暂时不可用')
    // ★ 失败时绝不能再出现「数据」—— 这正是历史缺陷的核心
    expect(screen.queryByTestId('ready')).toBeNull()
    // ★ 失败 ≠ 空：失败态不得渲染空态文案
    expect(screen.queryByText(/暂无数据/)).toBeNull()
  })

  it('网络异常进入失败态，原因来自异常本身', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Failed to fetch')))
    render(<Reader />)
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('Failed to fetch')
    expect(screen.queryByTestId('ready')).toBeNull()
  })

  it('404 用状态码口径的中文原因，不暴露裸状态码', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(failResponse(404)))
    render(<Reader />)
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('目标不存在或已被删除')
    expect(alert.textContent).not.toContain('404')
  })

  it('失败后点重试可恢复到 ready', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(failResponse(503))
      .mockResolvedValueOnce(okResponse({ primary: { total_items: 12 } }))
    vi.stubGlobal('fetch', fetchMock)

    render(<Reader />)
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('服务暂时不可用')

    fireEvent.click(screen.getByRole('button', { name: '重试' }))
    await waitFor(() => expect(screen.getByTestId('ready').textContent).toContain('12'))
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('换 url 后旧数据必须立刻消失（不残留、不混着渲染）', async () => {
    // 第二次请求挂起，用来观察「新数据还没回来」这个中间态。
    // 若不做状态重置，中间态会保留上一次的数据 —— 用户看到的是 A 页的数字
    // 挂在 B 页的路由下，而后端其实还没答。
    let releaseSecond: (v: unknown) => void = () => {}
    const pending = new Promise((resolve) => {
      releaseSecond = resolve
    })
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(okResponse({ primary: { total_items: 3 } }))
      .mockReturnValueOnce(pending)
    vi.stubGlobal('fetch', fetchMock)

    const { rerender } = render(<Reader url="/api/v1/a" />)
    expect((await screen.findByTestId('ready')).textContent).toContain('3')

    rerender(<Reader url="/api/v1/b" />)

    // ★ 中间态必须是「加载中」，而不是继续显示 3
    expect(screen.queryByTestId('ready')).toBeNull()
    expect(screen.getByRole('status').textContent).toContain('加载发布历史中')

    releaseSecond(failResponse(500))
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('服务暂时不可用')
    expect(screen.queryByTestId('ready')).toBeNull()
  })

  it('readFailure 只对 failed 返回原因', () => {
    expect(readFailure({ status: 'loading', data: null, error: null })).toBeNull()
    expect(readFailure({ status: 'ready', data: {}, error: null })).toBeNull()
    expect(readFailure({ status: 'failed', data: null, error: '服务暂时不可用，请稍后再试' })).toBe(
      '服务暂时不可用，请稍后再试',
    )
  })

  it('url 为 null 时停在 idle 且不发请求（不是无限 loading）', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    render(<IdleReader />)

    expect(screen.getByTestId('status').textContent).toBe('idle')
    expect(fetchMock).not.toHaveBeenCalled()
    // idle 与 failed 不同：没有失败原因
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('失败态与空态互斥（「失败 ≠ 空」判别式）', () => {
  it('失败态不出现空态文案；空态不出现失败文案', () => {
    const { unmount } = render(
      <View state={{ status: 'failed', data: null, error: '服务暂时不可用，请稍后再试' }} />,
    )
    expect(screen.getByRole('alert').textContent).toContain('加载失败')
    expect(screen.queryByText(/暂无数据/)).toBeNull()
    unmount()

    render(<View state={{ status: 'ready', data: { primary: { total_items: 0 } }, error: null }} />)
    expect(screen.getByText('暂无数据')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('失败态下 data 恒为 null（类型层就不允许有数据）', () => {
    const failed: ReadState<Payload> = { status: 'failed', data: null, error: 'x' }
    expect(failed.data).toBeNull()
  })
})
