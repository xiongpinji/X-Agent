/**
 * console 写路径的失败可见性
 *
 * 历史缺陷：发消息 / 邀请成员 / 创建智能体这些写路径声明 `Promise<void>`，
 * 失败时要么静默 return、要么把异常抛给没人接的调用方；而调用方一律无条件
 * 清空输入框 —— 用户看到「输入没了，消息没发出去」，且没有任何反馈。
 *
 * 这里钉住新契约（console/sendOutcome.ts）：
 * 1. 只有 ok 才清空输入；
 * 2. 失败必须渲染 role="alert" 的内联提示。
 *
 * 断言刻意选「输入框是否还留着原文」这一可观测行为，而不是内部 state ——
 * 后者在变异测试里很容易被空转放过。
 */

import { describe, it, expect, afterEach, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

import { RealtimeChatPage, type RealtimeChatPageProps } from '@/console/pages/chat/RealtimeChatPage'
import { MeetingRoomsPage, type MeetingRoomsPageProps } from '@/console/pages/meetings/MeetingRoomsPage'
import { CreateAgentPage, type CreateAgentPageProps, type AgentCreateResult } from '@/console/pages/agents/CreateAgentPage'
import { apiFailureMessage, httpErrorMessage, sendFailure } from '@/console/sendOutcome'

/** 成功响应（postCollaborationMessage 会读 json） */
const okResponse = (payload: unknown) => ({ ok: true, status: 200, json: async () => payload })

/** 失败响应（postCollaborationMessage / addCollaborationMember 只看 ok，直接 throw） */
const failResponse = (status = 500) => ({ ok: false, status, json: async () => ({ detail: 'boom' }) })

/** 创建成功且无告警（onCreateAgent 的返回契约） */
const created = (warnings: string[] = []): AgentCreateResult => ({ agentId: 'a-new', warnings })

const message = (overrides: Record<string, unknown> = {}) => ({
  message_id: 'm-new',
  sender_name: '我',
  content: '你好',
  message_type: 'text',
  created_at: '2026-01-01T00:00:00Z',
  ...overrides,
})

const chatProps = (): RealtimeChatPageProps => ({
  conversations: [
    { conversation_id: 'c1', title: '对话一', unread_count: 0, participant_ids: ['u1'], last_message_at: null },
  ],
  activeConversationId: 'c1',
  messages: [],
  avatars: [],
  presence: {},
  currentSenderId: 'u1',
  onSelectConversation: vi.fn(),
})

const roomProps = (): MeetingRoomsPageProps => ({
  rooms: [{ room_id: 'r1', name: '房间一', topic: '议题', member_agent_ids: ['a1'] }],
  activeRoomId: 'r1',
  messages: [],
  avatars: [],
  currentSenderId: 'u1',
  onSelectRoom: vi.fn(),
})

const agentProps = (overrides: Partial<CreateAgentPageProps> = {}): CreateAgentPageProps => ({
  roleCatalog: {
    templates: [
      { role_id: 'rt1', role_name: '导演', title: '内容总监', description: '负责内容', core_skills: [], tools: [] },
    ],
    workflows: [],
    role_groups: {},
  },
  organizationGraph: {
    organization: { org_id: 'o1' },
    departments: [{ department_id: 'd1', name: '内容部' }],
    role_templates: [],
    agent_instances: [],
    meeting_rooms: [],
    nodes: [],
    edges: [],
  },
  avatars: [],
  onCreateAgent: vi.fn().mockResolvedValue(created()),
  ...overrides,
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('RealtimeChatPage 发送', () => {
  it('失败时保留输入原文并显示内联错误', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(failResponse(500)))
    render(<RealtimeChatPage {...chatProps()} />)

    const composer = screen.getByPlaceholderText(/输入消息/)
    fireEvent.change(composer, { target: { value: '你好' } })
    fireEvent.click(screen.getByRole('button', { name: '发送' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('发送消息失败：服务暂时不可用，请稍后再试')
    expect(alert).not.toHaveTextContent('Failed to')
    expect(composer).toHaveValue('你好')
  })

  it('成功时才清空输入', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okResponse(message())))
    render(<RealtimeChatPage {...chatProps()} />)

    const composer = screen.getByPlaceholderText(/输入消息/)
    fireEvent.change(composer, { target: { value: '你好' } })
    fireEvent.click(screen.getByRole('button', { name: '发送' }))

    await screen.findByText('你好', { selector: 'div' })
    expect(composer).toHaveValue('')
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('MeetingRoomsPage 发送', () => {
  it('失败时保留输入原文并显示内联错误', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(failResponse(503)))
    render(<MeetingRoomsPage {...roomProps()} />)

    const composer = screen.getByPlaceholderText(/输入会议消息/)
    fireEvent.change(composer, { target: { value: '开会了' } })
    fireEvent.click(screen.getByRole('button', { name: '发送' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('发送消息失败：服务暂时不可用，请稍后再试')
    expect(alert).not.toHaveTextContent('Failed to')
    expect(composer).toHaveValue('开会了')
  })
})

describe('MeetingRoomsPage 邀请成员', () => {
  it('失败时保留 member_id 并显示内联错误（此前是必然可达的静默失败点）', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(failResponse(403)))
    render(<MeetingRoomsPage {...roomProps()} />)

    const input = screen.getByPlaceholderText('输入 member_id')
    fireEvent.change(input, { target: { value: 'agent-9' } })
    fireEvent.click(screen.getByRole('button', { name: '邀请' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('邀请成员失败：没有权限执行该操作')
    expect(alert).not.toHaveTextContent('Failed to')
    expect(input).toHaveValue('agent-9')
  })

  it('成功时才清空 member_id', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okResponse({ ok: true })))
    render(<MeetingRoomsPage {...roomProps()} />)

    const input = screen.getByPlaceholderText('输入 member_id')
    fireEvent.change(input, { target: { value: 'agent-9' } })
    fireEvent.click(screen.getByRole('button', { name: '邀请' }))

    expect(await screen.findByRole('button', { name: '邀请' })).toBeInTheDocument()
    expect(input).toHaveValue('')
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('CreateAgentPage 提交', () => {
  it('必填缺失时列出缺项，且不调用 onCreateAgent', async () => {
    const onCreateAgent = vi.fn().mockResolvedValue(created())
    render(<CreateAgentPage {...agentProps({ onCreateAgent })} />)

    fireEvent.click(screen.getByRole('button', { name: '创建智能体' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('智能体名称')
    expect(onCreateAgent).not.toHaveBeenCalled()
  })

  it('onCreateAgent 抛错时给出内联失败提示', async () => {
    const onCreateAgent = vi.fn().mockRejectedValue(new Error('后端炸了'))
    render(<CreateAgentPage {...agentProps({ onCreateAgent })} />)

    fireEvent.change(screen.getByPlaceholderText('例如：短剧导演智能体'), { target: { value: '新智能体' } })
    fireEvent.click(screen.getByRole('button', { name: '创建智能体' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('创建智能体失败')
    expect(alert).toHaveTextContent('后端炸了')
  })

  it('提交体只含组织定位字段，不含画像 / 会议室等已删字段', async () => {
    // 契约收窄的核心：旧 payload 里 capabilities/plugins/apps 恒被发成空数组、
    // persona/tone/decision_style 恒被发成模板默认常量、room_id 后端从不读。
    // 这些字段一旦被重新加回来，本断言必须红。
    const onCreateAgent = vi.fn().mockResolvedValue(created())
    render(<CreateAgentPage {...agentProps({ onCreateAgent })} />)

    fireEvent.change(screen.getByPlaceholderText('例如：短剧导演智能体'), { target: { value: '新智能体' } })
    fireEvent.change(screen.getByPlaceholderText('例如：内容总监'), { target: { value: '内容总监' } })
    fireEvent.click(screen.getByRole('button', { name: '创建智能体' }))

    await screen.findByRole('button', { name: '创建智能体' })
    expect(onCreateAgent).toHaveBeenCalledTimes(1)
    expect(onCreateAgent.mock.calls[0][0]).toEqual({
      org_id: 'o1',
      department_id: 'd1',
      name: '新智能体',
      role_template_id: 'rt1',
      title: '内容总监',
      manager_agent_id: null,
    })
  })

  it('成功时无任何错误提示', async () => {
    const onCreateAgent = vi.fn().mockResolvedValue(created())
    render(<CreateAgentPage {...agentProps({ onCreateAgent })} />)

    fireEvent.change(screen.getByPlaceholderText('例如：短剧导演智能体'), { target: { value: '新智能体' } })
    fireEvent.click(screen.getByRole('button', { name: '创建智能体' }))

    expect(await screen.findByRole('button', { name: '创建智能体' })).toBeInTheDocument()
    expect(onCreateAgent).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('部分成功（后端返回 warnings）时必须显式展示原因，且不算错误', async () => {
    const onCreateAgent = vi.fn().mockResolvedValue(
      created(['上级智能体「小组长」已达编制上限 1，未建立汇报关系。']),
    )
    render(<CreateAgentPage {...agentProps({ onCreateAgent })} />)

    fireEvent.change(screen.getByPlaceholderText('例如：短剧导演智能体'), { target: { value: '新智能体' } })
    fireEvent.click(screen.getByRole('button', { name: '创建智能体' }))

    const notice = await screen.findByRole('status')
    expect(notice).toHaveTextContent('智能体已创建')
    expect(notice).toHaveTextContent('编制上限')
    // 是「建成了但有遗留」不是「失败」，不能再报一个 alert
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('成功后再次提交会清掉上一次的告警', async () => {
    const onCreateAgent = vi
      .fn()
      .mockResolvedValueOnce(created(['上级智能体已满编，未建立汇报关系。']))
      .mockResolvedValueOnce(created())
    render(<CreateAgentPage {...agentProps({ onCreateAgent })} />)

    fireEvent.change(screen.getByPlaceholderText('例如：短剧导演智能体'), { target: { value: '新智能体' } })
    fireEvent.click(screen.getByRole('button', { name: '创建智能体' }))
    expect(await screen.findByRole('status')).toHaveTextContent('智能体已创建')

    fireEvent.click(screen.getByRole('button', { name: '创建智能体' }))
    await screen.findByRole('button', { name: '创建智能体' })
    expect(screen.queryByRole('status')).toBeNull()
  })
})

describe('apiFailureMessage 口径', () => {
  const failing = (status: number, body: unknown) => ({
    ok: false,
    status,
    json: async () => body,
  }) as unknown as Response

  it('优先用后端 message（业务冲突是具体且已中文化的）', async () => {
    await expect(
      apiFailureMessage(failing(409, { code: 'resource_conflict', message: '部门内已存在同名智能体「短剧导演」' })),
    ).resolves.toBe('部门内已存在同名智能体「短剧导演」')
  })

  it('message 缺失时退回 detail', async () => {
    await expect(apiFailureMessage(failing(403, { detail: 'CSRF token required' }))).resolves.toBe(
      'CSRF token required',
    )
  })

  it('非 JSON 响应体（网关 HTML / 空体）走状态码兜底', async () => {
    const notJson = {
      ok: false,
      status: 503,
      json: async () => {
        throw new SyntaxError('Unexpected token <')
      },
    } as unknown as Response
    await expect(apiFailureMessage(notJson)).resolves.toBe('服务暂时不可用，请稍后再试')
  })

  it('message 是空串 / 非字符串时也走状态码兜底', async () => {
    await expect(apiFailureMessage(failing(500, { message: '   ' }))).resolves.toBe(
      '服务暂时不可用，请稍后再试',
    )
    await expect(apiFailureMessage(failing(500, { message: 42 }))).resolves.toBe(
      '服务暂时不可用，请稍后再试',
    )
  })
})

describe('httpErrorMessage 口径', () => {
  it('把状态码收敛成中文人话，且不泄漏英文机器串或裸码', () => {
    expect(httpErrorMessage(403)).toBe('没有权限执行该操作')
    expect(httpErrorMessage(500)).toBe('服务暂时不可用，请稍后再试')
    expect(httpErrorMessage(503)).toBe('服务暂时不可用，请稍后再试')
    expect(httpErrorMessage(418)).toBe('请求未能完成，请稍后再试')
    for (const status of [400, 401, 403, 404, 409, 422, 429, 500, 503, 418]) {
      const text = httpErrorMessage(status)
      expect(text).not.toContain('Failed')
      expect(text).not.toContain(String(status))
    }
  })
})

describe('sendFailure 口径', () => {
  it('Error 取 message，非 Error 取字符串化，空值退化为无细节文案', () => {
    expect(sendFailure('发送消息', new Error('boom'))).toEqual({ ok: false, error: '发送消息失败：boom' })
    expect(sendFailure('邀请成员', 'oops')).toEqual({ ok: false, error: '邀请成员失败：oops' })
    expect(sendFailure('创建智能体', undefined)).toEqual({ ok: false, error: '创建智能体失败' })
  })
})
