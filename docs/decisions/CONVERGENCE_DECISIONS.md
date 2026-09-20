# T5 收敛决策矩阵（v1/v2 双轨 + 僵尸代码盘点）

> 日期：2026-09-20 ｜ 基线：develop @ ecc9343 ｜ 状态：**W1 已执行（a76398e）；W2/W3 待放行**
> 方法：对每个候选模块统计生产代码引用（backend/cli，排除自身与 tests）与测试引用；
> 对 API 模块额外核对是否被 `main.py` 实际注册（include_router）。
> 所有数字可用 `grep -rlnE 'core\.<module>\b' backend cli tests --include='*.py'` 复现。

---

## 0. 最重要的发现：运行时表面 vs 代码表面

- `main.py` 注册了 **49 个 router**（openapi 实测 286 路径 / 317 操作）
- `backend/app/api/` 有 **125 个模块，其中 75 个从未被注册**，且在整个 backend/cli 中**零引用**
- 也就是说：插件市场、技能市场、enterprise_*、sso、billing、subscriptions、forum、
  vision、media、analytics、artifacts、scheduler、webhooks、i18n 等整片 API + 其专属 core 模块
  是"**僵尸岛**"——代码和测试存在，但运行时永远不可达

因此下面很多"v1 vs v2"的问题，实际答案是"**两边都没在跑**"。

**运行时真正活着的内核**（保留区，勿动）：
`core/agent/`（loop，27 处引用）、`core/memory/` 目录（41 处）、`core/audit.py`（13 处）、
`core/mcp/`（startup 接线）、`core/tools.py`、`core/workflows.py` + workflow_view 助手、
`core/sandbox/`、`core/channels/`、`core/hooks/`、`core/context/`、`core/security.py`、
`dependencies.py`（107 处引用）、`agent_communication_bus`（经已注册的 parallel_agents API）、
`memory_graph`（被 memory/store.py 使用）、`memory_classifier` / `memory_merger`（被已注册的
memory_enhanced API 使用）、`memory_postgres`（被 dependencies.py 使用）。

---

## 1. 八组双轨裁决建议

| # | 组 | 裁决建议 | 证据 |
|---|---|---|---|
| 1 | `core/agent/` vs `core/agent_v2/` | **留 agent，归档 agent_v2** | agent: 27 生产引用（5 api + 4 core）；agent_v2: 0 生产引用，仅 2 个测试文件 |
| 2 | memory 家族（26 文件） | **留 v1 目录 + 4 个活文件；归档 memory_v2_* 与 dedup/fusion 子树** | `core/memory/` 41 引用；memory_v2_system/skill/nudge 各仅 1 测试引用，memory_v2_retriever 全零；dedup/fusion 子树只被"测试引用或死代码"引用（链条：benchmark→dead，service→tests-only） |
| 3 | `plugin_system` vs `plugin_system_v2` | **整个 plugin_* core 家族（16 文件）全部归档** | v1: 仅 1 测试引用；v2: 仅 1 测试引用；optimized/loader/lifecycle/marketplace/manager: 0 生产引用；唯一"活"入口 api/plugins.py 未注册。真正的插件路径是 `core/mcp/`（已接 startup） |
| 4 | `skill_system_v2` + skill/skills 家族（25+ 文件） | **全家族归档（需产品确认）** | skill_system.py 已不存在；skill_system_v2 仅 1 测试引用；skill_market_* 链条全部挂在未注册 API（skill_market/skills/skills_api 等 5 个）上；skills_cli/document/executor/loader 零生产引用或家族内互引 |
| 5 | `audit` 家族（5 文件） | **留 audit.py；归档 audit_enhanced / audit_export / audit_logging / audit_postgres** | audit.py: 13 生产引用；audit_enhanced 仅被未注册 api/audit_enhanced.py 和死代码 audit_postgres 引用；audit_postgres/audit_logging 零生产引用（audit_logging←enterprise_integration←无人引用，死链闭合）。⚠️ audit.py 涉及安全簇（HMAC），只留不改 |
| 6 | `collaboration` 家族 | **留 agent_communication_bus；归档 collaboration_enhanced / agent_collaboration / agent_communication / agent_communication_enhanced；`core/collaboration/` 目录标 experimental（M3 多 Agent 协作是路线图项）** | bus: 2 生产引用（已注册的 parallel_agents API）；collaboration_enhanced 仅被未注册 API 引用；agent_communication_enhanced 全零；core/collaboration/ 目录仅 1 测试引用 |
| 7 | `dependencies.py` vs `dependencies_refactored.py` | **留 dependencies.py，删除 dependencies_refactored.py** | 107 vs 0 引用。refactored 是唯一引用死代码 container_config 的地方 |
| 8 | `middleware.py` vs `middleware/` | **删除 middleware/ 目录（sync_middleware 零引用）；middleware.py 标"待与 main.py 内联实现合并"** | main.py 自带内联 `_RateLimiter` + CSRF + 安全头；middleware.py 的 RateLimit/SecurityHeaders 中间件生产零引用（仅 1 测试）——同一功能存在两份实现，实际生效的是 main.py 内联版 |

## 2. 连带死代码（引用链已闭合，随组归档）

`performance_optimization.py`（0 引用，唯一引用 memory_optimizer）、`memory_optimizer.py`、
`memory_enhancement.py`、`enterprise_integration.py`（0 引用）、`container_config.py`（仅被
dependencies_refactored 引用）、`parallel_agents_integration.py`（0 生产引用）、
`plugin_dev_tools`（仅被未注册 api/plugin_dev_api.py 引用）。

## 3. 75 个未注册 API 模块的处置（T9 范畴，此处仅给默认建议）

- **workflow_* 助手（12 个）**：不是 router，是 api/workflows.py 的函数库 → **保留**
- **mcp / search / api_keys / artifacts / sessions / health_checks**：有潜在价值 → **候选挂载**（逐个评估后 include_router 或归档）
- **其余 ~55 个**（plugin/skill 市场、enterprise_*、sso、billing、subscriptions、forum、
  media、vision、analytics、i18n、translation、partners、recommendations 等）：
  → **默认归档**，若某功能是产品优先级再"复活"（挂载 + 补测试）

## 4. 建议执行波次（T5b，每波一个 commit，波间全量验证）

| 波次 | 内容 | 风险 | 验证 |
|---|---|---|---|
| W1 | 删除零引用（含测试）文件：dependencies_refactored、middleware/ 目录、memory_v2_retriever、memory_enhancement、memory_deduplication_benchmark、memory_optimizer、performance_optimization、audit_postgres、agent_communication_enhanced、skills_cli、skills_document、plugin_system_optimized、container_config、parallel_agents_integration、enterprise_integration | 极低 | compileall + RC 子集 + pytest --collect-only 无错 |
| W2 | 归档"仅测试引用"的僵尸（agent_v2、plugin 家族、memory_v2_*/dedup/fusion 子树、audit_enhanced/export/logging、collaboration 冗余、skills 家族）连同其专属测试文件，移入 `backend/app/core/_archived/`（或直接 git rm，历史可找回） | 低-中：测试总数会下降 ~数百，需在 CHANGELOG 说明 | 同上 + 全量测试基线对比（fail 不得增加） |
| W3 | 75 个未注册 API 的挂载/归档逐个执行 | 中：涉及产品取舍 | openapi 路径数对比 + 前端消费清单核对（T12） |

**归档方式建议**：直接 `git rm`（历史可追溯），不建 `_archived/` 目录——避免"归档区"变成
新的垃圾抽屉。若需查阅：`git log --diff-filter=D --name-only`。

## 5. 红线（继承 CLAUDE.md 约束）

1. `core/audit.py`、`core/security.py`、HMAC/加密相关 → 只保留，不改语义（安全簇 21 测试用户亲管）
2. `core/agent/`、`core/memory/`、`dependencies.py` 等保留区 → 本任务不重构，只删外围
3. W2/W3 执行前需用户对本文档逐组签字（可只回复"按建议执行"）

## 6. 待用户决策清单

> **2026-09-20 用户批复**：① 立即执行 W1（已完成，commit a76398e，17 文件删除，
> 全量收集 4096 tests 0 err，RC 子集 120 passed）；② 技能系统全家族 → **归档**方向确认
> （随 W2 执行）；③ W2/W3 整体执行待用户读完本矩阵后放行。

- [x] 组 1-8 裁决方向确认（技能家族=归档，用户 2026-09-20 拍板）
- [x] W1 执行（2026-09-20，commit a76398e）
- [ ] W2 放行（"仅测试引用"僵尸 + 专属测试，git rm 方式）
- [ ] W3 候选挂载名单（mcp/search/api_keys/artifacts/sessions/health_checks）确认
- [ ] `v1.0.0-beta` tag 处置：删除 tag（推荐）还是保留？
