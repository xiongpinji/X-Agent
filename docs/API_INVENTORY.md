# API Inventory & Governance（T9 交付物）

> 生成日期：2026-09-20 ｜ 基线：develop（W3 完成后实测 openapi）
> 实测规模：**323 路径 / 361 操作 / 54 注册 router**
> 数据来源：`app.openapi()` 运行时展开（非静态 grep），可用文末命令复现

## 1. 本轮治理动作（已执行）

| 动作 | 详情 |
|---|---|
| 修复 Duplicate Operation ID | `memory_enhanced.py` 前缀 `/api/v1/memory` → `/api/v1/memory/enhanced`（tags 同步改 `memory-enhanced`）。此前其 `POST /search` 与 `memory.py` 完全冲突（永远被遮蔽），`GET /stats` 被 `memory.py` 的 `GET /{memory_id}` 通配符静默吞掉。改动前核实：无测试、无前端消费这些路径 |
| 挂载 5 个休眠 router（W3） | `/api/v1/mcp`(8)、`/api/v1/search`(6)、`/api/v1/api-keys`(11)、`/api/v1/artifacts`(8)、`/api/sessions`(10) |
| 删除 38 个不可达 API 模块（W3） | 见 commit b12a41e 清单 |
| 健康检查收敛 | 删除 `health_checks.py`（第三套健康检查实现）；现存两套：main.py 内联 `/health`、`/ready` + `api/health.py` `/api/v1/health/{live,ready,detailed}`。建议 M2 收敛为一套 |

## 2. API 面分类

### A. 核心域 API（Agent 框架本体）
workflows(25)、agents(14)、memory(11)、tools(3+batch 4)、browser(12)+browser-advanced(16)、
traces(5)、runs、approvals、audit(5)、dispatch、planning、execution、verification、replay、
sandbox(4)、mcp(8)、search(6)、artifacts(8)、sessions(10)、api-keys(11)、collaboration(10)、
parallel-agents、channels(feishu 4)、sync(12)、tasks(10)、auth(9)、users、tenants、org(16)、
security、metrics(2)、health(3)、streaming、feedback(6)、messages、questions、workspace、
file-preview、overview(2)、workbench(2)、evolution(4)、integrations(4)、migration、ops

### B. UI 控制面（`*-control`，23 路径）——前端 console 直接消费，勿动路径
`execution-control`(4)、`tools-control`(4)、`memory-control`(4)、`organization-control`(4)、
`marketplace-control`(4)、`navigation-control`(3)

治理规则：这些是"页面视图模型"端点（BFF 模式）。短期保留（前端 console 在消费：
`frontend/src/console/*` 调用 `memory-control/overview|history|detail` 等）；
中期（M2+）若做 API v2，应迁出 `/api/v1` 命名空间（如 `/api/console/*`）并与前端同步改。

### C. 已知不一致（记录在案，M2 处理）
1. `frontend/src/services/api.ts` 调用 `GET /memory/search`、`PUT/DELETE /memory/{id}` —— 
   后端实际是 `POST /api/v1/memory/search`，且无 PUT/DELETE。该 client 文件与后端契约脱节
   （console 页面走的是 memory-control，未受影响）。T12 前端验证时修复
2. `api/sessions.py` 前缀是 `/api/sessions`（无 v1），与其他 router 命名不一致
3. 健康检查两套并存（见上）

## 3. 新增 API 的治理规则（防复发）

1. 新 router 必须在 `main.py` 注册——未注册 = 不存在（本轮清理的 38 个模块即由此产生）
2. 禁止两个 router 共享同一前缀（memory 冲突的根因）
3. UI 定制端点一律进 `*-control` / console 命名空间，不混入域 API
4. CI 校验：启动时 `-W error::UserWarning` 导入 app，Duplicate Operation ID 直接失败（T8 落地）

## 4. 复现命令

```bash
XAGENT_QDRANT_URL="" XAGENT_LLM_BACKEND=mock python - <<'EOF'
from backend.app.main import app
spec = app.openapi()
ops = sum(len([m for m in v if m in ('get','post','put','delete','patch')]) for v in spec['paths'].values())
print('paths:', len(spec['paths']), 'ops:', ops)
EOF
```
