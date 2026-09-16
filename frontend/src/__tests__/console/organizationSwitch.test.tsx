/**
 * (c) 组织切换 / 组织部门入口 的前端契约。
 *
 * 这里钉住三件在 (c) 之前**根本不成立**的事：
 *
 * 1. **console 的请求必须带凭证**。console 此前一律裸 fetch ⇒ 实测写请求是
 *    403 `{"detail":"CSRF token required"}`、`/api/v1/organization/*` 读请求是 401。
 *    断言打在「实际传给 fetch 的 header」上，而不是「有没有调 consoleFetch」——
 *    后者是内部实现，换个名字就空转了。
 * 2. **组织结构页不再渲染硬编码 fixture**。它此前显示的是 ConsoleShell 传进来的
 *    `departmentCount={8} memberCount={86} roleCount={24}`，真实数据即使拿到也被
 *    `props.x ?? apiData?.x` 静默丢弃。断言用「KPI 等于传入数据的长度」+
 *    「不出现 8 / 86 / 24」双向钉住。
 * 3. **组织下拉与创建入口真的可用**：切换回调、无组织时禁用新建部门、
 *    失败必须渲染 role="alert"（不静默、不假装成功）。
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

import { consoleAuthHeaders, consoleFetch } from '@/console/consoleFetch'
import { OrganizationSwitcher, type OrganizationSwitcherProps } from '@/console/components/organization/OrganizationSwitcher'
import { OrganizationStructurePage, type OrganizationStructurePageProps } from '@/console/pages/organization/OrganizationStructurePage'
import type { DepartmentRecord, OrganizationRecord } from '@/console/hooks/useOrganizationDirectory'

const DEV_KEY = 'xagent-dev-key-2024'

const organization = (overrides: Partial<OrganizationRecord> = {}): OrganizationRecord => ({
  org_id: 'org-a',
  tenant_id: 'default',
  name: '内容事业部',
  description: '',
  owner_user_id: 'admin',
  status: 'active',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...overrides,
})

const department = (overrides: Partial<DepartmentRecord> = {}): DepartmentRecord => ({
  department_id: 'dept-a',
  org_id: 'org-a',
  name: '前端设计部',
  mission: '负责界面',
  leader_agent_id: null,
  parent_department_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...overrides,
})

const okResponse = (payload: unknown) => ({ ok: true, status: 200, json: async () => payload })

const switcherProps = (
  overrides: Partial<OrganizationSwitcherProps> = {},
): OrganizationSwitcherProps => ({
  organizations: [organization(), organization({ org_id: 'org-b', name: '短剧工作室' })],
  departments: [],
  activeOrgId: 'org-a',
  loading: false,
  error: '',
  onSelectOrg: vi.fn(),
  onCreateOrganization: vi.fn().mockResolvedValue(undefined),
  onCreateDepartment: vi.fn().mockResolvedValue(undefined),
  ...overrides,
})

const structureProps = (
  overrides: Partial<OrganizationStructurePageProps> = {},
): OrganizationStructurePageProps => ({
  organizations: [organization()],
  departments: [
    department(),
    department({ department_id: 'dept-b', name: '投放部', mission: '负责买量' }),
  ],
  activeOrgId: 'org-a',
  loading: false,
  error: '',
  onSelectOrg: vi.fn(),
  agentCount: 5,
  ...overrides,
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  localStorage.clear()
})

describe('consoleFetch 凭证注入', () => {
  it('有 api_key 时带 x-api-key，且不额外带 Bearer', async () => {
    localStorage.setItem('api_key', 'key-from-storage')
    const fetchMock = vi.fn().mockResolvedValue(okResponse({}))
    vi.stubGlobal('fetch', fetchMock)

    await consoleFetch('/api/v1/organization/organizations')

    const init = fetchMock.mock.calls[0][1] as RequestInit
    const headers = init.headers as Record<string, string>
    expect(headers['x-api-key']).toBe('key-from-storage')
    expect(headers.Authorization).toBeUndefined()
  })

  it('完全没有凭证时回落到本地开发 key（否则写请求必 403、读请求必 401）', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse({}))
    vi.stubGlobal('fetch', fetchMock)

    await consoleFetch('/api/v1/organization/organizations')

    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>
    expect(headers['x-api-key']).toBe(DEV_KEY)
  })

  it('只有登录 token 时走 Bearer，不用开发 key 顶替登录身份', async () => {
    localStorage.setItem('auth_token', 'jwt-token')
    const fetchMock = vi.fn().mockResolvedValue(okResponse({}))
    vi.stubGlobal('fetch', fetchMock)

    await consoleFetch('/api/v1/organization/organizations')

    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer jwt-token')
    expect(headers['x-api-key']).toBeUndefined()
  })

  it('两者都有时都带上（后端 x-api-key 优先，两者都豁免 CSRF）', () => {
    localStorage.setItem('api_key', 'k')
    localStorage.setItem('auth_token', 't')
    expect(consoleAuthHeaders()).toEqual({ 'x-api-key': 'k', Authorization: 'Bearer t' })
  })

  it('调用方传入的 header 优先于默认头', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse({}))
    vi.stubGlobal('fetch', fetchMock)

    await consoleFetch('/api/v1/x', { headers: { 'X-Custom': '1' } })

    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>
    expect(headers['X-Custom']).toBe('1')
    expect(headers['Content-Type']).toBe('application/json')
  })
})

describe('OrganizationSwitcher', () => {
  it('下拉列出真实组织，切换时把 org_id 交回调用方', () => {
    const onSelectOrg = vi.fn()
    render(<OrganizationSwitcher {...switcherProps({ onSelectOrg })} />)

    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(Array.from(select.options).map((option) => option.value)).toEqual(['org-a', 'org-b'])

    fireEvent.change(select, { target: { value: 'org-b' } })
    expect(onSelectOrg).toHaveBeenCalledWith('org-b')
  })

  it('没有当前组织时「新建部门」不可点（避免建到别的组织下）', () => {
    render(<OrganizationSwitcher {...switcherProps({ activeOrgId: null })} />)
    expect(screen.getByRole('button', { name: '新建部门' })).toBeDisabled()
  })

  it('创建组织成功后给出可见反馈', async () => {
    const onCreateOrganization = vi.fn().mockResolvedValue(undefined)
    render(<OrganizationSwitcher {...switcherProps({ onCreateOrganization })} />)

    fireEvent.click(screen.getByRole('button', { name: '新建组织' }))
    fireEvent.change(screen.getByPlaceholderText('例如：内容事业部'), {
      target: { value: '新事业部' },
    })
    fireEvent.click(screen.getByRole('button', { name: '创建组织' }))

    await screen.findByRole('status')
    expect(screen.getByRole('status')).toHaveTextContent('组织已创建')
    expect(onCreateOrganization).toHaveBeenCalledWith({ name: '新事业部', description: '' })
  })

  it('创建失败必须显示原因，且不谎报成功', async () => {
    const onCreateOrganization = vi
      .fn()
      .mockRejectedValue(new Error('部门内已存在同名组织「新事业部」'))
    render(<OrganizationSwitcher {...switcherProps({ onCreateOrganization })} />)

    fireEvent.click(screen.getByRole('button', { name: '新建组织' }))
    fireEvent.change(screen.getByPlaceholderText('例如：内容事业部'), {
      target: { value: '新事业部' },
    })
    fireEvent.click(screen.getByRole('button', { name: '创建组织' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('创建组织失败：部门内已存在同名组织「新事业部」')
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('名称为空时本地就拦下，不来回打一次请求', () => {
    const onCreateOrganization = vi.fn()
    render(<OrganizationSwitcher {...switcherProps({ onCreateOrganization })} />)

    fireEvent.click(screen.getByRole('button', { name: '新建组织' }))
    fireEvent.click(screen.getByRole('button', { name: '创建组织' }))

    expect(onCreateOrganization).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent('请先填写组织名称')
  })

  it('加载组织目录失败时把原因显示出来', () => {
    render(<OrganizationSwitcher {...switcherProps({ error: '加载组织目录失败：没有权限执行该操作' })} />)
    expect(screen.getByRole('alert')).toHaveTextContent('加载组织目录失败：没有权限执行该操作')
  })
})

describe('OrganizationStructurePage 接真数据', () => {
  it('KPI 与表格都来自传入数据，不再出现 fixture 的 8 / 86 / 24', () => {
    const { container } = render(<OrganizationStructurePage {...structureProps()} />)

    const kpis = Array.from(container.querySelectorAll('.console-kpi')).map(
      (element) => element.textContent ?? '',
    )
    expect(kpis).toContain('部门数2')
    expect(kpis).toContain('成员数5')
    expect(kpis).toContain('组织数1')

    // 两个真实部门都在表里
    expect(screen.getByText('前端设计部')).toBeInTheDocument()
    expect(screen.getByText('投放部')).toBeInTheDocument()

    // 反向：旧 fixture 的编造数字一个都不能出现
    expect(container.textContent).not.toContain('86')
    expect(container.textContent).not.toContain('24')
    expect(container.textContent).not.toContain('统一控制台')
  })

  it('没有部门时给出可行动的引导，而不是留一张空表', () => {
    render(<OrganizationStructurePage {...structureProps({ departments: [], agentCount: 0 })} />)
    expect(screen.getByText(/还没有部门/)).toBeInTheDocument()
  })

  it('有多个组织时提供切换，单个组织时不显示多余的控件', () => {
    const onSelectOrg = vi.fn()
    const { unmount } = render(
      <OrganizationStructurePage
        {...structureProps({
          organizations: [organization(), organization({ org_id: 'org-b', name: '短剧工作室' })],
          onSelectOrg,
        })}
      />,
    )
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'org-b' } })
    expect(onSelectOrg).toHaveBeenCalledWith('org-b')
    unmount()

    render(<OrganizationStructurePage {...structureProps()} />)
    expect(screen.queryByRole('combobox')).toBeNull()
  })

  it('读组织目录失败时显示错误，而不是把 0 当成真实结果', () => {
    render(<OrganizationStructurePage {...structureProps({ error: '加载组织目录失败：登录状态已失效，请重新登录' })} />)
    expect(screen.getByRole('alert')).toHaveTextContent('加载组织目录失败')
  })
})
