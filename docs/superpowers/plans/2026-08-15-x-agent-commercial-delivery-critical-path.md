# X-Agent 商业交付关键路径实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法跟踪。每个任务先做规格审查，再做代码质量审查；未经发布所有者明确授权，不执行付费供应商请求、推送、外部写入、生产部署、数据库恢复或发布标签。

**目标：** 将当前 `codex/commercial-delivery` 本地修复候选推进为证据可复跑、租户安全、真实 Agent 链路完整、具备产品表面和外部门禁的商业 RC。

**架构：** 以 `run_id/trace_id` 为唯一关联键，把认证用户请求、Agent/LLM 状态、聊天历史、工件、下载归档、用量预占/结算/退款和审计记录连成一条真实链。现代 Console 只消费真实 `workbench` 聚合和带鉴权的消息流，不挂载硬编码 control 路由。发布系统采用 fail-closed 状态模型：本地证据、产品表面、真实供应商、Hosted CI 和 Kubernetes 证据必须绑定同一候选 SHA。

**技术栈：** React 18、TypeScript、Vitest、FastAPI、Pydantic、SQLAlchemy、pytest、SSE、PostgreSQL/SQLite、Helm、GitHub Actions、现有 `scripts/rc_*.py` 门禁。

---

## 当前基线与硬边界

- 实际工作树：`D:\AI编程库\项目库\进行中的项目\X-Agent\.worktrees\commercial-delivery`
- 分支/HEAD：`codex/commercial-delivery@90fe9f2`；基线 `main@4f1f5dc` 保持干净。
- 已从 `333065d` 仅提取 25 个源码/测试/计划白名单路径并提交为 `69ad8ee`；候选历史不含 Playwright 状态、运行数据、截图或临时备份。
- 当前候选已通过 19 个 Chat/stream Vitest、9 个 Python Agent stream 合同、TypeScript、生产构建、npm audit、定向 Ruff/ESLint 0 errors；Python 全量 7198 个测试与旧前端 83 个 Vitest 仍须在本候选 SHA 上重跑后才可复用。
- 当前候选全局 ESLint 仍有 22 个错误/239 个警告，是明确未完成门禁。
- 默认 ChatPage 已在 `90fe9f2` 接入真实 Agent POST-SSE；现代 Console 仍有 6 个虚构 overview 404 和消息流 401。
- `333065d` 历史包含 Playwright、运行数据和临时备份工件；后续不得把该提交整体 cherry-pick 或推送到候选。
- 真实付费模型、外部 GitHub/渠道、Hosted CI、真实集群、生产密钥、部署和恢复均是发布所有者授权门。

## 执行顺序

1. 默认聊天真实 Agent POST-SSE，并补齐可运行的 Vitest 测试入口。
2. 聊天持久化与租户隔离。
3. Run 工件、下载、归档与审计闭环。
4. 幂等计费预占、结算、失败退款和未知提交状态。
5. 现代 Console 真实数据纵切。
6. 全局 lint/Ruff/全量测试与四端门禁。
7. 仅在逐项获得明确授权后执行真实供应商、Hosted CI、渠道与生产门禁。

## 文件职责

- `frontend/src/pages/ChatPage.tsx`：默认聊天只走真实 Agent POST-SSE；删除占位 run 和 demo 成功回退。
- `frontend/src/hooks/useAgentStream.ts`：权威 POST-SSE 客户端，携带 Bearer/API Key，暴露 trace/final/error。
- `frontend/src/services/api.ts`：移除或停用占位 chat workflow 合同；聊天历史和工件 API 使用强类型。
- `backend/app/api/agents.py`：真实流式 Agent 入口，绑定 session、tenant、user、trace、审计和商业运行生命周期。
- `backend/app/core/chat_history_store.py`：租户/用户隔离的持久聊天会话仓储。
- `backend/app/api/chat_history.py`：仅通过持久仓储访问，会话所有权错误统一返回 404。
- `backend/app/core/run_artifacts.py`：run manifest、工件哈希、下载/归档状态和审计关联。
- `backend/app/core/artifacts/storage.py`、`backend/app/api/artifacts.py`：工件必须带 tenant/user/run 归属；读取、渲染、下载全部校验所有权。
- `backend/app/core/billing/reservations.py`：幂等用量预占状态机 `reserved -> confirmed|refunded|submission_unknown`。
- `backend/app/api/workbench.py`：从真实 run、memory、tools、organization、collaboration、skills 数据源构建 Console bootstrap。
- `frontend/src/console/services/consoleApi.ts`：Console 统一鉴权 fetch 和 POST/GET SSE 解析。
- `frontend/src/console/hooks/useConsoleRealtimeSync.ts`、`frontend/src/console/ConsoleShell.tsx`：只请求真实 bootstrap/SSE；未交付能力显示 unavailable。
- `scripts/rc_*.py`、`.github/workflows/commercial-rc.yml`：绑定候选 SHA 的本地与外部门禁，不把 mock 结果升级为真实供应商结果。
- `deployment/**`、`monitoring/**`：部署前备份/迁移阻断、真实 smoke URL、指标认证、回滚与恢复证据。

### 任务 1：默认聊天接入真实 Agent POST-SSE

**文件：**
- 修改：`frontend/src/pages/ChatPage.tsx`
- 修改：`frontend/src/hooks/useAgentStream.ts`
- 修改：`frontend/src/components/AgentStreamPanel.tsx`
- 修改：`frontend/src/services/api.ts`
- 修改：`frontend/package.json`
- 修改：`frontend/package-lock.json`
- 修改：`backend/app/api/agents.py`
- 创建：`frontend/src/__tests__/pages/ChatPage.test.tsx`
- 创建：`frontend/src/__tests__/components/AgentStreamPanel.test.tsx`
- 测试：`tests/test_chat_entrypoint_contract.py`
- 创建：`tests/test_agent_stream_api.py`

- [x] **步骤 1：写失败合同，禁止默认聊天调用占位 workflow**

```python
def test_default_chat_uses_real_agent_stream() -> None:
    source = (ROOT / "frontend/src/pages/ChatPage.tsx").read_text(encoding="utf-8")
    assert "/workflows/create/chat" not in source
    assert "startStream(messageText" in source
    assert "Task completed (demo mode)" not in source
```

Vitest 同时断言：发送一次消息只产生 `POST /api/v1/agents/run/stream`；Authorization 或 `X-API-Key` 存在；completion 的 `trace_id/answer/status` 写入助手消息；error completion 显示失败且不生成成功消息。

- [x] **步骤 2：运行红灯测试**

运行：

```powershell
python -m pytest tests/test_chat_entrypoint_contract.py tests/test_agent_stream_api.py -q
npm --prefix frontend run test -- src/__tests__/pages/ChatPage.test.tsx src/__tests__/components/AgentStreamPanel.test.tsx
```

预期：旧 ChatPage 仍调用 `apiClient.sendMessage` 和占位 SSE，测试失败。

- [x] **步骤 3：最小实现真实 POST-SSE**

`ChatPage` 使用 `useAgentStream`：

```ts
const { startStream, stopStream, isStreaming } = useAgentStream({
  onEvent: appendVisibleTraceContent,
  onComplete: persistCompletedAssistantMessage,
  onError: failPendingMessage,
})

await startStream(messageText, {
  agent_id: selectedAgent || undefined,
  session_id: sessionIdRef.current || undefined,
})
```

后端 final frame 必须返回：

```json
{"_final":true,"result":{"trace_id":"...","status":"completed","answer":"..."}}
```

异常返回 `status=failed` 和稳定错误码；不得用 5 秒 timeout 或 demo 文本伪装成功。Ultra Mode 失败同样显示真实失败，不得生成 demo completed。

- [x] **步骤 4：回归验证**

已运行任务 1 的 Python/Vitest、`npm --prefix frontend run type-check`、生产构建、npm audit、定向 ESLint/Ruff 和候选卫生检查；全局 lint 失败保留给任务 6，不作为本任务伪造通过。

- [x] **步骤 5：规格审查、质量审查和精确提交**

任务 1 以 5 个精确修复提交完成，最终 HEAD `90fe9f2`；规格审查与代码质量审查均通过，`git diff --check`、秘密扫描和运行工件 denylist 通过。

```text
fix(chat): connect default chat to real agent stream
```

### 任务 2：聊天历史持久化与租户隔离

**文件：**
- 创建：`backend/app/core/chat_history_store.py`
- 修改：`backend/app/api/chat_history.py`
- 创建：`backend/migrations/010_chat_history_tables.sql`
- 测试：`tests/test_chat_history_persistence.py`
- 测试：`tests/test_chat_history_tenant_isolation.py`

- [x] **步骤 1：写失败测试**

```python
session_id = client_a.post("/api/v1/chat/history", json={"title": "A"}).json()["id"]
assert client_b.get(f"/api/v1/chat/history/{session_id}").status_code == 404
assert client_b.post(f"/api/v1/chat/history/{session_id}/messages", json={"role": "user", "content": "x"}).status_code == 404
```

创建 store、写入消息、销毁并重建 store 后，tenant A/user A 必须仍能读取相同消息；tenant B、user B 和匿名 principal 必须不可见。

- [x] **步骤 2：实现权威仓储合同**

```python
class ChatHistoryStore(Protocol):
    async def create_session(self, tenant_id: str, user_id: str, title: str, agent_id: str) -> ChatSession: ...
    async def list_sessions(self, tenant_id: str, user_id: str, limit: int) -> list[ChatSession]: ...
    async def get_session(self, tenant_id: str, user_id: str, session_id: str) -> ChatSession | None: ...
    async def append_message(self, tenant_id: str, user_id: str, session_id: str, message: ChatMessageRecord) -> ChatSession | None: ...
    async def delete_session(self, tenant_id: str, user_id: str, session_id: str) -> bool: ...
    async def clear_sessions(self, tenant_id: str, user_id: str) -> int: ...
```

生产使用配置的 PostgreSQL 且依赖显式 migration，缺表时失败关闭；SQLite 自动建表仅用于开发/测试。所有 API 查询都带 `tenant_id + user_id + session_id`，不存在或不属于当前 principal 时统一 404，禁止自动接管他人的 session ID。删除单会话与清空历史同样只作用于当前 principal。

- [x] **步骤 3：运行持久化、隔离和现有聊天回归**

```powershell
python -m pytest tests/test_chat_history_persistence.py tests/test_chat_history_tenant_isolation.py tests/test_chat_entrypoint_contract.py tests/test_agent_stream_api.py -q
```

- [x] **步骤 4：双阶段审查并提交**

提交信息：`feat(chat): persist tenant-isolated history`。

任务 2 以 `fac2bcd`、`e7b05f8`、`d6c9be2` 三个独立提交完成。红灯实际覆盖重启丢失、跨租户/跨用户越权、未知 session 接管、并发计数丢更新、时间戳倒退和非法请求写入；最终目标测试 26 个通过，叠加任务 1 Agent stream 回归共 35 个通过。规格复审与质量复审均通过，最终为 0 Critical、0 Important；生产 PostgreSQL 仍需在任务 7 的受控环境应用 `010_chat_history_tables.sql` 并验收。

### 任务 3：Run 工件、下载、归档与审计闭环

**文件：**
- 创建：`backend/app/core/run_artifacts.py`
- 修改：`backend/app/core/artifacts/storage.py`
- 修改：`backend/app/api/artifacts.py`
- 修改：`backend/app/api/agents.py`
- 修改：`backend/app/main.py`
- 修改：`tests/test_artifacts.py`
- 修改：`tests/test_agent_stream_api.py`
- 测试：`tests/test_run_artifact_lifecycle.py`
- 测试：`tests/test_artifact_tenant_isolation.py`

- [ ] **步骤 1：写失败的完整生命周期测试**

同一 mock Agent run 必须返回 `run_id/trace_id`；终态创建 manifest：

```json
{
  "run_id":"...","trace_id":"...","tenant_id":"tenant-a","user_id":"user-a",
  "status":"completed","artifacts":[{"artifact_id":"...","sha256":"...","download_url":"..."}],
  "archive":null,"audit_ids":["..."]
}
```

完成终态先返回持久 manifest，不提前伪造 archive。随后调用归档端点得到 `archive_id/archive_sha256/download_url`。验证 `GET artifact`、render、download、manifest、archive download 均可打开；SHA-256 与下载字节一致；tenant B 全部返回 404；失败 run 写入 failed manifest 且不生成虚假 completed artifact。

- [ ] **步骤 2：实现 run manifest 与所有权字段**

`Artifact` 增加 `tenant_id/user_id/run_id/trace_id/content_sha256`；存储路径按安全编码后的 tenant 分区。所有 API 从 principal 收敛 tenant/user，不接受客户端覆盖归属。

- [ ] **步骤 3：增加安全下载和归档端点**

将 `artifacts` router 加入显式 keep-list，确保 OpenAPI 和真实应用均可达。下载使用固定 artifact ID 定位，不接受任意文件路径；归档只包含 manifest 声明的文件，并生成 archive SHA-256。创建、下载、归档和失败都写同一 `run_id/trace_id` 审计记录。旧 `agents.py` 中未挂载的 `_run_artifacts/_archived_runs` 占位不得作为通过证据。

- [ ] **步骤 4：运行生命周期、隔离、秘密扫描和审计链测试**

```powershell
python -m pytest tests/test_artifacts.py tests/test_run_artifact_lifecycle.py tests/test_artifact_tenant_isolation.py tests/test_agent_stream_api.py tests/test_first_release_entrypoints.py tests/test_audit*.py -q
```

- [ ] **步骤 5：双阶段审查并提交**

提交信息：`feat(artifacts): close run download and archive lifecycle`。

### 任务 4：幂等用量预占、结算、失败退款

**文件：**
- 创建：`backend/app/core/billing/__init__.py`
- 创建：`backend/app/core/billing/reservations.py`
- 修改：`backend/app/core/llm/backends.py`
- 修改：`backend/app/api/agents.py`
- 修改：`backend/app/api/tenants.py`
- 测试：`tests/test_usage_reservation_lifecycle.py`
- 测试：`tests/test_usage_reservation_idempotency.py`

- [ ] **步骤 1：写失败的状态机测试**

```python
reservation = await store.reserve(operation_id="op-1", tenant_id="a", estimated_cost=Decimal("0.01"))
assert (await store.confirm("op-1", actual_cost=Decimal("0.008"))).status == "confirmed"
assert (await store.confirm("op-1", actual_cost=Decimal("0.008"))).ledger_entry_count == 1
```

显式供应商失败必须 `refunded`；未知 POST 结果必须 `submission_unknown`，禁止自动重试和自动退款；重复 callback 不得二次扣费/退款；跨租户查询返回 404。

- [ ] **步骤 2：实现持久 reservation/ledger**

权威状态仅为 `reserved/confirmed/refunded/submission_unknown`。唯一键为 `tenant_id + operation_id`；每次转换在事务内写不可变 ledger 和审计记录。

- [ ] **步骤 3：接入真实 Agent/LLM 生命周期**

供应商调用前 reserve；拿到明确成功和 token/cost 后 confirm；明确失败 refund；网络超时且无法确认供应商状态时写 `submission_unknown` 并停止自动重试。

- [ ] **步骤 4：以 mock provider 完成成功/失败/未知/重复回调测试**

```powershell
python -m pytest tests/test_llm_quota_wiring.py tests/test_usage_reservation_lifecycle.py tests/test_usage_reservation_idempotency.py -q
```

- [ ] **步骤 5：双阶段审查并提交**

提交信息：`feat(billing): add idempotent run reservations`。

### 任务 5：现代 Console 真实数据纵切

**文件：**
- 创建：`frontend/src/console/services/consoleApi.ts`
- 修改：`frontend/src/console/hooks/useConsoleRealtimeSync.ts`
- 修改：`frontend/src/console/ConsoleShell.tsx`
- 修改：`frontend/src/console/state/consoleReducer.ts`
- 修改：`backend/app/api/workbench.py`
- 修改：`backend/app/api/messages.py`
- 测试：`tests/test_console_real_bootstrap.py`
- 测试：`tests/test_messages_stream.py`
- 测试：`frontend/src/console/__tests__/consoleApi.test.ts`

- [ ] **步骤 1：写失败合同**

启动 Console 只能调用 `/api/v1/workbench` 和 `/api/v1/messages/stream`；不得调用 `*-control/overview`。两者都携带 Bearer 或 API Key。tenant query 必须被服务端 principal 覆盖，tenant B 不能读取 tenant A 的 bootstrap 或事件。

- [ ] **步骤 2：实现统一鉴权 fetch-stream**

```ts
export function consoleAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('auth_token')
  const apiKey = localStorage.getItem('api_key')
  return token ? { Authorization: `Bearer ${token}` } : apiKey ? { 'X-API-Key': apiKey } : {}
}
```

使用 `fetch` + `ReadableStream` 解析 SSE；禁止把 token 放入查询参数。

- [ ] **步骤 3：真实 workbench 聚合**

从真实 run、memory、tool manifest、organization store、collaboration store 和已缓存 skills 状态读取。不可用能力返回 `availability="unavailable"` 和空集合，不得写固定计数或示例实体。GET bootstrap 不创建计划、任务或其他副作用。

- [ ] **步骤 4：运行后端、前端和浏览器回归**

浏览器要求 `/console` 200、0 个 4xx/5xx、0 个 console error，并验证一条当前 principal 范围内的实时事件。

- [ ] **步骤 5：双阶段审查并提交**

提交信息：`feat(console): project authenticated real runtime state`。

### 任务 6：本地 RC、静态债务与四端产品门禁

**文件：**
- 修改：导致 Ruff 85 条错误和未 await warning 的精确源文件
- 修改：`.github/workflows/commercial-rc.yml`
- 修改：`scripts/rc_*.py`
- 修改：Web/desktop/extension/mobile 对应 gate 测试和报告生成器

- [ ] **步骤 1：让所有改动 Python 文件完整 Ruff 为 0**

运行 `ruff check` 全规则；不得只跑致命规则或禁用规则。修复 coroutine 未 await、收集警告和可重复的非确定性测试。

- [ ] **步骤 2：重跑本地全门禁**

包括 7198+ Python 测试、前端 lint/type/Vitest/build/audit、`git diff --check`、RC 聚合测试。mock/local 模式必须在报告中显式标识，不得生成真实供应商 passed。

- [ ] **步骤 3：四端机器可读门禁**

Web、桌面、浏览器扩展和移动端分别构建/安装/启动；任务提交、状态查询、结果查看必须指向同一后端合同。缺失平台证书只能为 `action_required`。

- [ ] **步骤 4：双阶段审查并按子系统提交**

每个产品表面独立提交，禁止把生成报告和源代码混成一个提交。

### 任务 7：真实供应商、Hosted CI、渠道与生产授权门

**文件：**
- 生成但默认不暂存：`.xagent_runtime/reports/*.json`
- 修改：`deployment/scripts/deploy.sh`、`deployment/scripts/rollback.sh`
- 修改：`.github/workflows/deploy-production.yml`
- 修改：`monitoring/prometheus.yml`

- [ ] **步骤 1：完成无外部写入的 dry-run/preflight**

运行 owner gate dry-run、Helm lint/template、部署配置验证、生产 smoke URL 非占位检查、迁移失败 fail-closed 检查、监控鉴权合同测试。

- [ ] **步骤 2：请求一次性真实模型授权**

请求中固定 provider、model、最大 token、预计费用、唯一 `operation_id`、余额/价格证据和“只提交一次”规则。只有明确授权后才执行一次真实调用；未知结果写 `submission_unknown`，不自动重试。

- [ ] **步骤 3：请求外部所有者资源和权限**

需明确提供或批准：Feishu 测试应用、一次性 GitHub issue/repo/token、Hosted GitHub Actions、生产外部 URL、kubeconfig、外部 secret store。任何缺失项保持 `action_required`。

- [ ] **步骤 4：经授权完成同一 SHA 外部链**

验证真实模型响应/工具/失败模式、真实渠道签名回调、GitHub 只读预检和受控 Issue-to-PR、Hosted CI、生产 secrets、Kubernetes 就绪/负载/备份恢复/回滚。恢复脚本会 DROP DATABASE，必须再次获得专门授权。

### 任务 8：干净候选、证据包与发布所有者交付

**文件：**
- 读取：`docs/operations/deployment/RC_STAGING_MANIFEST.md`
- 生成：`.xagent_runtime/reports/*.json`
- 生成：`.xagent_runtime/release/*`

- [ ] **步骤 1：生成不含运行工件的干净候选历史**

候选必须排除 `.playwright-cli/**`、`frontend/.playwright-cli/**`、`output/playwright/**`、`tmp-api-debug-auth/**`、运行态 JSON/GZ/截图和本机密钥。不得直接 cherry-pick `333065d`，不得使用 `git add .`。

- [ ] **步骤 2：绑定同一候选 SHA 重新生成全部证据**

`rc_final_gate.py --require-ready-to-tag` 必须退出 0；任何 external gate 的 skipped/action_required 都阻止 `ready_for_rc_tag`。

- [ ] **步骤 3：精确路径 staging 审查**

运行 `git diff --cached --stat`、`git diff --cached --check`、秘密扫描、artifact SHA-256 和文件数复核； staged path 必须与批准 manifest 完全一致。

- [ ] **步骤 4：发布所有者批准后提交、标签和部署**

批准请求必须包含最终状态、候选 SHA、artifact 路径/SHA-256/文件数、receipt、剩余风险和精确 staging 命令。未获批准不得 commit/tag/push/deploy。

## 完成定义

只有以下全部成立才完成长期目标：

1. 默认 Web 聊天通过真实 Agent/LLM，同一 run 可读取终态、历史、工件、下载、归档、审计和计费状态。
2. 成功、明确失败、未知提交和重复回调的状态/扣费/退款均经同链验证。
3. Console 只显示真实或明确 unavailable 数据，鉴权和租户隔离通过。
4. 四端产品门禁、全量测试、静态检查、供应链和秘密扫描通过。
5. 同一候选 SHA 的真实供应商、真实渠道/GitHub、Hosted CI、生产 secrets 和 Kubernetes 部署/监控/备份恢复/回滚证据通过。
6. `rc_final_gate.py --require-ready-to-tag` 退出 0，`full_parity_claimed=false`。
7. 发布所有者批准精确 staging、提交、标签和部署；历史中不包含验收数据、临时备份或本机密钥。
