/**
 * (d) 组织治理读路径的前端契约。
 *
 * 这一批修的是同一类缺陷的三个实例：**页面打着恒 404 的未挂载路由，再把失败
 * 伪装成「没有数据」，最后显示调用方硬编码的假数字**。
 *
 * | 位置 | 旧行为 |
 * |------|--------|
 * | OrganizationCenterOverviewPage | fetch `/api/v1/organization-control/overview`（未挂载），`if (!ok) return` 吞掉 ⇒ 显示 0 |
 * | OrganizationRolesPage | props 硬编码 24/21/3/12 + 同款 fetch + `props.x ?? apiData?.x` ⇒ props 永远命中 |
 * | OrganizationAuditPage | props 硬编码 13/10/3 + 同款 fetch |
 *
 * 本文件按「可观测行为」钉住新契约，每条断言都能被一次真实变异打红：
 *
 * 1. 数据只走 `/api/v1/organization/roles` 与 `/api/v1/organization/audit`，
 *    **任何** `/api/v1/organization-control/` 请求都算失败；
 * 2. 三个页面渲染的是传入数据，且**旧 fixture 的编造数字一个都不能出现**；
 * 3. 「所属组织」在创建表单里可切换时，切过去必须真的去拉那个组织的部门，
 *    并且提交体里的 `org_id` / `department_id` 必须**同属一个组织**（这是
 *    「拿着 A 的 department_id 往 B 提交」这条路径的直接证伪）。
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react'

import {
  useOrganizationGovernance,
  type OrganizationAuditPayload,
  type OrganizationRolesPayload,
} from '@/console/hooks/useOrganizationGovernance'
import { OrganizationRolesPage } from '@/console/pages/organization/OrganizationRolesPage'
import { OrganizationAuditPage } from '@/console/pages/organization/OrganizationAuditPage'
import { OrganizationCenterOverviewPage } from '@/console/pages/organization/OrganizationCenterOverviewPage'
import {
  CreateAgentPage,
  type AgentCreateResult,
  type CreateAgentOrganizationOption,
  type CreateAgentPageProps,
} from '@/console/pages/agents/CreateAgentPage'
import { ConsoleApp } from '@/console/ConsoleApp'

/**
 * 真的把 ConsoleShell 渲染起来的接线测试会碰到实时同步（SSE + 轮询）。这里把那
 * 一个 hook 换成最小替身：**只保留「拉 bootstrap 并 dispatch」这一条**，其余
 * （SSE、轮询、重连）全部省略 —— 被测的是「页面接线」，不是同步机制本身。
 *
 * ★ 刻意不返回一个死句柄：`state.organizationGraph` 正是由 bootstrap 派发填充的，
 * 若不派发，组织图相关的数字会恒为 0，那组断言就变成**永远成立的空转断言**。
 */
vi.mock('@/console/hooks/useConsoleRealtimeSync', async () => {
  const React = await import('react')
  return {
    useConsoleRealtimeSync: (
      _state: unknown,
      dispatch: (action: unknown) => void,
      options: { bootstrapUrl?: string },
    ) => {
      const bootstrapUrl = options?.bootstrapUrl
      React.useEffect(() => {
        if (!bootstrapUrl) return
        let cancelled = false
        void (async () => {
          const response = await fetch(bootstrapUrl)
          if (!response.ok) return
          const data = await response.json()
          if (!cancelled) dispatch({ type: 'bootstrap/success', payload: data })
        })()
        return () => {
          cancelled = true
        }
      }, [bootstrapUrl])

      return {
        syncStatus: 'idle',
        lastSyncedAt: null,
        syncError: null,
        manualRefresh: async () => {},
        refreshMessagesOnly: async () => {},
        reconnect: () => {},
        stopPolling: () => {},
        startPolling: () => {},
      }
    },
  }
})

const okResponse = (payload: unknown) => ({ ok: true, status: 200, json: async () => payload })

const rolesPayload = (): OrganizationRolesPayload => ({
  total_templates: 2,
  in_use_total: 1,
  templates: [
    {
      role_id: 'role-dir',
      role_name: '短剧导演',
      category: '内容',
      level: 'P7',
      title: '内容总监',
      description: '负责短剧内容',
      core_skills: ['选题', '分镜', '审片'],
      in_use: 1,
    },
    {
      role_id: 'role-ops',
      role_name: '投放运营',
      category: '增长',
      level: 'P6',
      title: '投放负责人',
      description: '负责买量',
      core_skills: ['出价'],
      in_use: 0,
    },
  ],
  role_groups: { 内容: ['role-dir'], 增长: ['role-ops'] },
})

const auditPayload = (): OrganizationAuditPayload => ({
  total: 2,
  limit: 50,
  offset: 0,
  truncated: false,
  summary: { success: 2, failure: 0, latest_outcome: 'success' },
  records: [
    {
      id: 'audit-2',
      actor_id: 'bootstrap-admin',
      action: 'organization_agent.create',
      resource_type: 'organization_agent',
      resource_id: 'agent-9',
      outcome: 'success',
      created_at: '2026-09-16T10:00:00Z',
      details: { org_id: 'org-a' },
    },
    {
      id: 'audit-1',
      actor_id: 'bootstrap-admin',
      action: 'organization.create',
      resource_type: 'organization',
      resource_id: 'org-a',
      outcome: 'success',
      created_at: '2026-09-16T09:00:00Z',
      details: { name: '内容事业部' },
    },
  ],
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  localStorage.clear()
})

describe('useOrganizationGovernance 只打真实端点', () => {
  it('拉 roles + audit 两个真实端点，并带上凭证', async () => {
    localStorage.setItem('api_key', 'key-from-storage')
    const fetchMock = vi.fn().mockImplementation(async (input: string) => {
      if (String(input).startsWith('/api/v1/organization/roles')) return okResponse(rolesPayload())
      if (String(input).startsWith('/api/v1/organization/audit')) return okResponse(auditPayload())
      throw new Error(`不该打到这个地址：${input}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useOrganizationGovernance('org-a'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    const urls = fetchMock.mock.calls.map((call) => String(call[0]))
    expect(urls.some((url) => url.includes('/api/v1/organization/roles?org_id=org-a'))).toBe(true)
    expect(urls.some((url) => url.includes('/api/v1/organization/audit'))).toBe(true)

    // 反向：那个模块的 4 个 GET 全是硬编码 fixture，且未挂载恒 404 —— 一个都不能打
    expect(urls.filter((url) => url.includes('/api/v1/organization-control/'))).toEqual([])

    // 凭证必须落到实际请求头上（裸 fetch ⇒ 浏览器里 401/403）
    for (const call of fetchMock.mock.calls) {
      const headers = (call[1] as RequestInit).headers as Record<string, string>
      expect(headers['x-api-key']).toBe('key-from-storage')
    }

    expect(result.current.roles?.total_templates).toBe(2)
    expect(result.current.audit?.records[0].resource_id).toBe('agent-9')
    expect(result.current.error).toBe('')
  })

  it('任一端点失败时把原因说出来，而不是留下一片空白', async () => {
    const fetchMock = vi.fn().mockImplementation(async (input: string) => {
      if (String(input).startsWith('/api/v1/organization/roles')) return okResponse(rolesPayload())
      return { ok: false, status: 500, json: async () => ({ detail: 'boom' }) }
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useOrganizationGovernance(null))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toContain('加载组织治理数据失败')

    // 没有组织时不应带 org_id 查询参数
    expect(String(fetchMock.mock.calls[0][0])).toBe('/api/v1/organization/roles')
  })
})

describe('OrganizationRolesPage 接真数据', () => {
  it('KPI 与表格都来自传入数据，旧 fixture 的 24 / 21 / 12 一个都不出现', () => {
    const { container } = render(
      <OrganizationRolesPage
        templates={rolesPayload().templates}
        totalTemplates={2}
        inUseTotal={1}
        roleGroups={rolesPayload().role_groups}
        activeOrgId="org-a"
      />,
    )

    const kpis = Array.from(container.querySelectorAll('.console-kpi')).map(
      (element) => element.textContent ?? '',
    )
    expect(kpis).toContain('模板总数2')
    expect(kpis).toContain('在用智能体1')
    expect(kpis).toContain('有在用的模板1')
    expect(kpis).toContain('角色分组2')

    expect(screen.getByText('短剧导演')).toBeInTheDocument()
    expect(screen.getByText('投放运营')).toBeInTheDocument()

    // 反向：旧 props 的编造数字
    expect(container.textContent).not.toContain('24')
    expect(container.textContent).not.toContain('21')
  })

  it('目录为空时说实话，不拿假数字兜底', () => {
    render(
      <OrganizationRolesPage
        templates={[]}
        totalTemplates={0}
        inUseTotal={0}
        roleGroups={{}}
        activeOrgId={null}
      />,
    )
    expect(screen.getByText(/当前没有可用的岗位模板/)).toBeInTheDocument()
    expect(screen.getByText('未选择')).toBeInTheDocument()
  })
})

describe('OrganizationAuditPage 接真数据', () => {
  it('空租户显示空态，而不是旧 fixture 的 13 条', () => {
    const { container } = render(
      <OrganizationAuditPage
        records={[]}
        total={0}
        summary={{ success: 0, failure: 0, latest_outcome: null }}
      />,
    )
    expect(screen.getByText(/还没有组织域操作记录/)).toBeInTheDocument()

    const kpis = Array.from(container.querySelectorAll('.console-kpi')).map(
      (element) => element.textContent ?? '',
    )
    expect(kpis).toContain('事件总数0')
    expect(kpis).toContain('最近结果-')
    expect(container.textContent).not.toContain('13')
  })

  it('有记录时渲染真实字段，并把截断提示显式暴露', () => {
    const { container } = render(
      <OrganizationAuditPage
        records={auditPayload().records}
        total={2}
        summary={auditPayload().summary}
        truncated
      />,
    )

    expect(screen.getByText('organization_agent.create')).toBeInTheDocument()
    expect(screen.getByText('agent-9')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('后端扫描上界')
    expect(container.textContent).not.toContain('待审')
  })
})

describe('OrganizationCenterOverviewPage 不再打未挂载路由', () => {
  it('整个渲染过程零请求，数字全部来自 props', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const { container } = render(
      <OrganizationCenterOverviewPage
        organizationName="内容事业部"
        totalDepartments={2}
        totalAgents={5}
        totalRoleTemplates={6}
        inUseAgents={3}
        auditTotal={9}
        auditFailure={1}
      />,
    )

    // 旧实现每次打开这一页都打一次 `/api/v1/organization-control/overview`（恒 404）
    expect(fetchMock).not.toHaveBeenCalled()

    const kpis = Array.from(container.querySelectorAll('.console-kpi')).map(
      (element) => element.textContent ?? '',
    )
    expect(kpis).toContain('部门数2')
    expect(kpis).toContain('智能体数5')
    expect(kpis).toContain('岗位模板6')
    expect(kpis).toContain('在用岗位3')
    expect(kpis).toContain('审计事件9')

    expect(container.textContent).not.toContain('86')
    expect(container.textContent).not.toContain('24')
  })

  it('给三个入口回调时三个按钮都渲染且可点', () => {
    const onOpenStructure = vi.fn()
    const onOpenRoles = vi.fn()
    const onOpenAudit = vi.fn()
    render(
      <OrganizationCenterOverviewPage
        organizationName="内容事业部"
        totalDepartments={2}
        totalAgents={5}
        totalRoleTemplates={6}
        inUseAgents={3}
        auditTotal={9}
        auditFailure={1}
        onOpenStructure={onOpenStructure}
        onOpenRoles={onOpenRoles}
        onOpenAudit={onOpenAudit}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '查看组织结构' }))
    fireEvent.click(screen.getByRole('button', { name: '查看角色权限' }))
    fireEvent.click(screen.getByRole('button', { name: '查看审核队列' }))

    expect(onOpenStructure).toHaveBeenCalledTimes(1)
    expect(onOpenRoles).toHaveBeenCalledTimes(1)
    expect(onOpenAudit).toHaveBeenCalledTimes(1)
  })

  it('不传回调时三个入口整体不出现（不给通往空页面的死按钮）', () => {
    render(
      <OrganizationCenterOverviewPage
        organizationName="内容事业部"
        totalDepartments={2}
        totalAgents={5}
        totalRoleTemplates={6}
        inUseAgents={3}
        auditTotal={9}
        auditFailure={1}
      />,
    )
    expect(screen.queryByRole('button', { name: '查看角色权限' })).toBeNull()
    expect(screen.queryByRole('button', { name: '查看审核队列' })).toBeNull()
  })
})

describe('CreateAgentPage 组织可切换', () => {
  const organizations: CreateAgentOrganizationOption[] = [
    { org_id: 'org-a', name: '内容事业部' },
    { org_id: 'org-b', name: '短剧工作室' },
  ]

  const graphA = {
    organization: { org_id: 'org-a', name: '内容事业部' },
    departments: [{ department_id: 'dept-a', name: '内容部' }],
    role_templates: [],
    agent_instances: [{ agent_id: 'agent-a', name: 'A 组组长', title: '组长' }],
    meeting_rooms: [],
    nodes: [],
    edges: [],
  }

  const graphB = {
    organization: { org_id: 'org-b', name: '短剧工作室' },
    departments: [{ department_id: 'dept-b', name: '短剧部' }],
    role_templates: [],
    agent_instances: [{ agent_id: 'agent-b', name: 'B 组组长', title: '组长' }],
    meeting_rooms: [],
    nodes: [],
    edges: [],
  }

  const created = (warnings: string[] = []): AgentCreateResult => ({ agentId: 'a-new', warnings })

  const agentProps = (overrides: Partial<CreateAgentPageProps> = {}): CreateAgentPageProps => ({
    roleCatalog: {
      templates: [
        {
          role_id: 'rt1',
          role_name: '导演',
          title: '内容总监',
          description: '负责内容',
          core_skills: [],
          tools: [],
        },
      ],
      workflows: [],
      role_groups: {},
    },
    organizationGraph: graphA,
    avatars: [],
    organizations,
    onCreateAgent: vi.fn().mockResolvedValue(created()),
    ...overrides,
  })

  /** 表单里的第 1 个下拉就是「所属组织」。 */
  const orgSelect = () => screen.getAllByRole('combobox')[0]
  const departmentSelect = () => screen.getAllByRole('combobox')[1]

  it('切换组织时去拉那个组织的部门，并把「所属部门」换成新组织的', async () => {
    const onLoadOrganizationGraph = vi.fn().mockResolvedValue(graphB)
    render(<CreateAgentPage {...agentProps({ onLoadOrganizationGraph })} />)

    expect(screen.getByRole('option', { name: '内容部' })).toBeInTheDocument()
    expect(departmentSelect()).toHaveValue('dept-a')

    fireEvent.change(orgSelect(), { target: { value: 'org-b' } })

    await waitFor(() => expect(onLoadOrganizationGraph).toHaveBeenCalledWith('org-b'))
    await waitFor(() => expect(screen.getByRole('option', { name: '短剧部' })).toBeInTheDocument())

    // 反向：A 组织的部门/上级不能再出现在 B 组织的选项里
    expect(screen.queryByRole('option', { name: '内容部' })).toBeNull()
    expect(screen.queryByRole('option', { name: 'A 组组长' })).toBeNull()
    // 部门落到新组织的第一个部门
    expect(departmentSelect()).toHaveValue('dept-b')
  })

  it('切换组织后提交的 org_id 与 department_id 必须同属一个组织', async () => {
    const onCreateAgent = vi.fn().mockResolvedValue(created())
    const onLoadOrganizationGraph = vi.fn().mockResolvedValue(graphB)
    render(
      <CreateAgentPage {...agentProps({ onCreateAgent, onLoadOrganizationGraph })} />,
    )

    fireEvent.change(orgSelect(), { target: { value: 'org-b' } })
    await waitFor(() => expect(departmentSelect()).toHaveValue('dept-b'))

    fireEvent.change(screen.getByPlaceholderText('例如：短剧导演智能体'), {
      target: { value: '新智能体' },
    })
    fireEvent.click(screen.getByRole('button', { name: '创建智能体' }))

    await waitFor(() => expect(onCreateAgent).toHaveBeenCalledTimes(1))
    expect(onCreateAgent.mock.calls[0][0]).toMatchObject({
      org_id: 'org-b',
      department_id: 'dept-b',
    })
  })

  it('没有加载通道时显式报错，并把两个组织内下拉禁用（不静默留旧选项）', async () => {
    render(<CreateAgentPage {...agentProps()} />)

    fireEvent.change(orgSelect(), { target: { value: 'org-b' } })

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('当前环境无法加载该组织的部门列表')
    expect(departmentSelect()).toBeDisabled()
    expect(screen.getAllByRole('combobox')[2]).toBeDisabled()
  })

  it('不传 organizations 时退回只读展示，不硬塞一个单选项下拉', () => {
    render(
      <CreateAgentPage
        {...agentProps({ organizations: undefined, organizationName: '内容事业部' })}
      />,
    )
    // 只剩「所属部门」「上级智能体」两个下拉
    expect(screen.getAllByRole('combobox')).toHaveLength(2)
    expect(screen.getByText('内容事业部')).toBeInTheDocument()
  })
})

describe('ConsoleShell 接线（回归防线）', () => {
  /**
   * 这一组是**接线**本身的回归防线。
   *
   * 三个页面被改成「只认真实数据」之后，如果 ConsoleShell 不改传参，或者两个侧边栏
   * 入口没恢复，单测三个页面全绿也说明不了「用户点得到」。这里直接把 ConsoleShell
   * 渲染起来，用真实点击走一遍。
   *
   * 而且它钉住了那个根因：**整个 console 首屏不得再出现任何
   * `/api/v1/organization-control/` 请求**（那个模块 4 个 GET 全是编造字面量且未挂载）。
   */
  const shellGraph = {
    organization: { org_id: 'org-a', name: '内容事业部' },
    departments: [{ department_id: 'dept-a', name: '内容部' }],
    role_templates: [],
    agent_instances: [{ agent_id: 'agent-a', name: '内容组组长', title: '组长' }],
    meeting_rooms: [],
    nodes: [],
    edges: [],
  }

  const notFound = () => ({
    ok: false,
    status: 404,
    json: async () => ({ detail: 'Not Found' }),
  })

  const shellFetch = () =>
    vi.fn().mockImplementation(async (input: string) => {
      const url = String(input)
      if (url.startsWith('/api/v1/workbench')) {
        return okResponse({
          console: {
            mode: 'unified_console',
            tenant_id: 'default',
            org_id: 'org-a',
            agent_id: '',
            session_id: 's-1',
            user_id: 'bootstrap-admin',
            created_at: '2026-09-16T10:00:00Z',
            server_time: '2026-09-16T10:00:00Z',
          },
          organization_graph: shellGraph,
          meeting_rooms: { rooms: [] },
          realtime: { conversations: [], messages: [], presence: {}, unread_count: 0, online_agents: [], typing_agents: [], last_message_at: null },
          avatars: [],
        })
      }
      if (url.startsWith('/api/v1/organization/organizations')) {
        return okResponse([
          { org_id: 'org-a', tenant_id: 'default', name: '内容事业部', description: '', owner_user_id: 'admin', status: 'active', created_at: '', updated_at: '' },
        ])
      }
      if (url.startsWith('/api/v1/organization/departments')) {
        return okResponse([{ department_id: 'dept-a', org_id: 'org-a', name: '内容部', mission: '', leader_agent_id: null, parent_department_id: null, created_at: '', updated_at: '' }])
      }
      if (url.startsWith('/api/v1/organization/roles')) return okResponse(rolesPayload())
      if (url.startsWith('/api/v1/organization/audit')) return okResponse(auditPayload())
      // 其余（execution-control / tools-control / memory-control / marketplace-control /
      // navigation-control 的 overview）在本测试里一律 404 —— 它们的失败本来就被
      // console 静默吞掉，不影响本组断言。
      return notFound()
    })

  it('首屏任何请求里都不出现 organization-control（那个模块是编造数据）', async () => {
    localStorage.setItem('console_active_org_id', 'org-a')
    const fetchMock = shellFetch()
    vi.stubGlobal('fetch', fetchMock)

    render(<ConsoleApp />)

    // 等治理数据也到货，确保请求面已经铺开
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some((call) => String(call[0]).includes('/api/v1/organization/roles')),
      ).toBe(true),
    )

    const urls = fetchMock.mock.calls.map((call) => String(call[0]))
    expect(urls.filter((url) => url.includes('/api/v1/organization-control/'))).toEqual([])
    // 组织切换的记忆值要真的落到请求上
    expect(urls).toContain('/api/v1/workbench?org_id=org-a')
  })

  it('侧边栏的「角色权限」「组织审核」两个入口可达，且点开就是真实数据', async () => {
    localStorage.setItem('console_active_org_id', 'org-a')
    vi.stubGlobal('fetch', shellFetch())

    render(<ConsoleApp />)

    // 入口本身可达（此前这两个按钮被摘除，因为指向的是编造数字）
    fireEvent.click(await screen.findByRole('button', { name: '角色权限' }))
    expect(await screen.findByText('短剧导演')).toBeInTheDocument()
    expect(await screen.findByText('在用智能体')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '组织审核' }))
    expect(await screen.findByText('organization_agent.create')).toBeInTheDocument()
    // 两条记录都出自 bootstrap-admin ⇒ 用 getAllByText 而不是 getByText
    expect(screen.getAllByText('bootstrap-admin')).toHaveLength(2)
    expect(screen.getByText('agent-9')).toBeInTheDocument()
  })

  it('组织权限中心概览显示真实数字（组织名 / 部门 / 智能体 / 模板 / 审计都来自端点）', async () => {
    localStorage.setItem('console_active_org_id', 'org-a')
    vi.stubGlobal('fetch', shellFetch())

    render(<ConsoleApp />)

    fireEvent.click(await screen.findByRole('button', { name: '组织权限中心' }))

    await screen.findByText('组织权限中心', { selector: 'h1' })
    // 这三个数字只能来自 workbench 的组织图 + roles/audit 两个真端点：
    // 旧实现是 `{...organizationCenterData}`，而 organizationCenterData 只由那个
    // 恒 404 的 overview 请求填充 ⇒ 永远是 0。
    await waitFor(() => expect(screen.getByText(/岗位模板 2 个 · 在用 1 个/)).toBeInTheDocument())
    expect(screen.getByText(/组织域审计 2 条 · 失败 0 条/)).toBeInTheDocument()
    // 部门数 / 智能体数来自 workbench 的组织图（经 bootstrap 派发进 state）
    expect(screen.getByText(/部门 1 个 · 智能体 1 个/)).toBeInTheDocument()
    // 组织名来自 workbench 的组织图（顶栏也有同样的文案，所以按页头节点取）
    expect(document.querySelector('.console-resource-id')?.textContent).toContain('内容事业部')
  })
})
