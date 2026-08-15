# Kimi 后续 P0 运行合同修复实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 在当前隔离工作树逐任务实现。步骤使用复选框（`- [ ]`）跟踪；不得推送或部署。

**目标：** 保留 Kimi 的界面整理，同时让 API-Key 登录后的管理页请求真实鉴权、Backup 使用真实可校验工件、Tenants 首屏不再调用未交付接口，并修复移动端首屏侧栏遮挡。

**架构：** 认证头由一个前端纯函数统一注入，消除各服务客户端漂移。Backup 新增独立且带 scope 校验的 `/api/v1/backup/scheduler/*` 路由，复用已经通过单测的 `core.backup_scheduler`，不再把 `backup.py` 的占位数据冒充真实备份。Tenants 仅开放已有真实 store 支持的租户 CRUD；依赖占位计量/计费数据的标签暂时禁用且不发请求。

**技术栈：** React 18、TypeScript、Axios、Zustand、FastAPI、pytest、Playwright CLI。

**明确不在本计划内：** 现代 Console 的 `*-control` API 目前部分返回硬编码展示数据；本计划不重新挂载这些假数据路由。Console 真实数据投影单独设计和验收。

---

## 文件职责

- 创建 `frontend/src/services/authHeaders.ts`：统一从 localStorage 读取 Bearer/API-Key 并写入 Axios 请求。
- 修改 `frontend/src/services/{api,adminOps,automationOps,complianceOps,evolutionOps,feedback,governanceOps,mcpOps,observabilityOps,sandboxOps,securityOps,syncOps,workflowOps}.ts`：所有 HTTP 客户端接入统一鉴权函数。
- 修改 `frontend/src/main.tsx`：健康预取改为真实 `/api/v1/health/live`。
- 创建 `backend/app/api/backup_scheduler_api.py`：受保护的真实文件/PostgreSQL/Qdrant 备份 API。
- 修改 `backend/app/main.py`：挂载 backup scheduler API 和 tenants 的既有扩展 CRUD router。
- 修改 `frontend/src/services/governanceOps.ts`、`frontend/src/pages/BackupPage.tsx`：切换到 scheduler 合同。
- 修改 `frontend/src/pages/TenantsBillingPage.tsx`：只在首屏加载租户；禁用未交付的计量/计费标签；删除租户前二次确认。
- 修改 `frontend/src/store/appStore.ts`：移动端侧栏默认关闭且不持久化瞬时 UI 状态。
- 创建 `tests/test_frontend_p0_runtime_contracts.py`、`tests/test_backup_scheduler_api.py`：跨前后端合同和备份工件回归测试。

### 任务 1：固化失败合同

- [ ] **步骤 1：创建前端源码合同测试**

```python
def test_custom_clients_share_api_key_auth():
    helper = (ROOT / "frontend/src/services/authHeaders.ts")
    assert helper.exists()
    for path in AUTH_CLIENTS:
        assert "applyStoredAuth" in path.read_text(encoding="utf-8")

def test_health_prefetch_uses_live_route():
    source = (ROOT / "frontend/src/main.tsx").read_text(encoding="utf-8")
    assert "link.href = '/api/v1/health/live'" in source

def test_mobile_sidebar_is_not_persisted_open():
    source = (ROOT / "frontend/src/store/appStore.ts").read_text(encoding="utf-8")
    assert "sidebarOpen: false" in source
    assert "sidebarOpen: state.sidebarOpen" not in source
```

- [ ] **步骤 2：创建 Backup API 工件测试**

```python
def test_backup_scheduler_routes_require_auth_and_write_manifest(tmp_path, monkeypatch):
    scheduler = BackupScheduler(BackupConfig(backup_dir=str(tmp_path), pg_enabled=False, qdrant_enabled=False))
    monkeypatch.setattr(api, "_get_scheduler", lambda: scheduler)
    assert anonymous.post("/api/v1/backup/scheduler/run").status_code == 401
    response = admin.post("/api/v1/backup/scheduler/run")
    assert response.status_code == 200
    manifest = tmp_path / response.json()["backup_id"] / "manifest.json"
    assert manifest.is_file()
```

- [ ] **步骤 3：运行红灯测试**

运行：`venv/Scripts/python.exe -m pytest tests/test_frontend_p0_runtime_contracts.py tests/test_backup_scheduler_api.py -q -o addopts= -p no:cov`

预期：FAIL；缺少 `authHeaders.ts`、backup scheduler API，健康路径和 sidebar 持久化断言失败。

### 任务 2：统一 API-Key 请求鉴权和健康路径

- [ ] **步骤 1：实现统一鉴权函数**

```ts
import type { InternalAxiosRequestConfig } from 'axios'

export function applyStoredAuth(config: InternalAxiosRequestConfig): InternalAxiosRequestConfig {
  const token = localStorage.getItem('auth_token')
  const apiKey = localStorage.getItem('api_key')
  if (token) config.headers.Authorization = `Bearer ${token}`
  if (apiKey) config.headers['x-api-key'] = apiKey
  return config
}
```

- [ ] **步骤 2：让所有 Axios 服务客户端调用 `applyStoredAuth`，并修正 health 预取路径**

```ts
this.client.interceptors.request.use(applyStoredAuth)
```

- [ ] **步骤 3：运行合同测试和 TypeScript 检查**

运行：`python -m pytest tests/test_frontend_p0_runtime_contracts.py -q -o addopts= -p no:cov`

运行：`npm run type-check`

预期：鉴权与健康合同通过，TypeScript 0 错误。

### 任务 3：接入真实 Backup Scheduler API

- [ ] **步骤 1：新增带 `backup:read/write` scope 的 scheduler router**

```python
router = APIRouter(prefix="/api/v1/backup/scheduler", tags=["backup-scheduler"])

@router.post("/run", response_model=BackupRunResponse)
async def trigger_backup(principal: PrincipalDependency) -> BackupRunResponse:
    enforce_scope(principal, "backup:write")
    _check_enabled()
    return BackupRunResponse.from_result(await _get_scheduler().run_backup())
```

- [ ] **步骤 2：实现 `/list`、`/status`、`/restore/{id}`、`/verify/{id}`、`/cleanup`，全部调用真实 scheduler 并保留鉴权**

- [ ] **步骤 3：在 `main.py` 挂载 router，前端 governanceOps 切换为 `/backup/scheduler/*`**

- [ ] **步骤 4：运行红绿验证**

运行：`python -m pytest tests/test_backup_scheduler.py tests/test_backup_scheduler_api.py -q -o addopts= -p no:cov`

预期：核心和 API 测试全部通过；测试目录中生成可打开 manifest，并能 verify/list。

### 任务 4：收敛 Tenants 真实能力与移动端状态

- [ ] **步骤 1：挂载 tenants 已有 `extended_router`，恢复真实 store 的 update/delete**

- [ ] **步骤 2：Tenants 首屏只调用 `listTenants`；Detail/Billing/Quota 标签标记 disabled，不调用占位或已归档接口**

```tsx
const tabs = [
  { id: 'tenants', label: 'Tenants', disabled: false },
  { id: 'detail', label: 'Tenant Detail', disabled: true },
  { id: 'billing', label: 'Billing', disabled: true },
  { id: 'quota', label: 'Quota', disabled: true },
]
```

- [ ] **步骤 3：删除租户前增加 `window.confirm`；取消 sidebarOpen 的持久化并将默认值设为 false**

- [ ] **步骤 4：运行合同、类型、构建和相关后端测试**

运行：`python -m pytest tests/test_frontend_p0_runtime_contracts.py tests/test_tenant_quota.py tests/test_api_comprehensive.py -q -o addopts= -p no:cov`

运行：`npm run type-check && npm run build`

预期：测试通过；构建通过；页面首屏不再请求 `/billing/*`、`/tenant/quota`。

### 任务 5：真实浏览器回归和交付审计

- [ ] **步骤 1：启动 mock 后端（Backup 使用临时目录并显式 enabled）和前端**

- [ ] **步骤 2：API-Key 登录后验证 Dashboard、Backup、Tenants 桌面端；确认请求携带 `x-api-key` 且关键请求无 401/404**

- [ ] **步骤 3：390×844 冷启动验证侧栏默认关闭、内容不被遮挡**

- [ ] **步骤 4：运行 lint、diff-check、工作区状态审计；已有无关 lint 失败必须与本次增量分开报告**

- [ ] **步骤 5：本地提交到 `codex/kimi-followup-p0`，不推送、不部署**

```powershell
git add docs/superpowers/plans/2026-08-15-kimi-followup-p0-runtime-contracts.md frontend backend tests
git commit -m "fix(x-agent): repair management runtime contracts"
```
