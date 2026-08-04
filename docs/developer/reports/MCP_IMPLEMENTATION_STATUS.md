# MCP 实现现状（Implementation Status）

> **本文档是 MCP 功能"实际可用状态"的单一可信来源（single source of truth）。**
> 创建于 2026-06-01；2026-07-20 随 Phase 2 Wave A（P1-01/P1-10）重写。
>
> ⚠️ 背景：仓库内已有多份 MCP 文档（`MCP_API_REFERENCE.md`、`MCP_INTEGRATION_GUIDE.md`
> 等），但其中部分描述的 HTTP 端点**与当前代码不符**（见下方"文档与现实的差异"）。
> 在架构决策落定前，请以**本文档**为准判断哪些功能真正可用。

---

## TL;DR（一句话现状）

- ✅ **MCP 客户端已是真实 MCP 协议**——基于官方 `mcp` Python SDK（≥1.28.1），
  支持 **stdio** 与 **Streamable HTTP** 两种官方传输，市面标准 MCP server 可直接接入。
- ✅ **发现的工具桥接进运行时 ToolRegistry**——Agent 主循环可真实调用 MCP 工具，
  风险等级/审批策略由运行时策略引擎统一裁决（单轨）。
- ⚠️ **MCP 的 HTTP 端点目前对外不可达**——`api/mcp.py` 的 router 尚未注册到
  `main.py`，属于待决策的独立事项。

---

## P1-01/P1-10 之后的核心事实

### 协议与传输（`backend/app/core/mcp/client.py`）

| 项 | 状态 |
|----|------|
| 协议 | ✅ 官方 MCP（JSON-RPC 2.0，`initialize`/`tools/list`/`tools/call`），`mcp` SDK 实现 |
| stdio 传输 | ✅ 子进程拉起 MCP server（`command`/`args`/`env`/`cwd`） |
| Streamable HTTP 传输 | ✅ `url` 指向 MCP 端点（可配 `headers`） |
| SDK 缺失时 | ✅ 显式抛 `MCPUnavailableError`（可选导入模式，不静默伪造） |
| 旧自造 JSON 协议 | ⚠️ 仅 `protocol.py` 兼容保留（已标注弃用），新代码不得使用 |

### 工具注册（`backend/app/core/mcp/discovery.py`）

发现的每个 MCP 工具**双写**：

1. `ToolCatalog`（`core/tool_registry.py`，schema 目录：版本/状态/生命周期）；
2. 运行时 `ToolRegistry`（`core/tools.py`，Agent 主循环执行表）——以可执行
   handler 桥接，主循环 `execute()` 咽喉点直接可调（含 policy/hooks/审批/审计）。

风险模型统一：目录侧 `ToolRiskLevel` ↔ 运行时 `RiskLevel` 只能经
`catalog_risk_to_runtime` / `runtime_risk_to_catalog` 换算；推断信号
（官方 `ToolAnnotations` + 名称/描述关键词 + 整站 `risk_level` 下限）取保守最高值。
HIGH/CRITICAL 工具在默认策略下被拦截并要求审批（`ApprovalStore` 单轨）。

审计单轨：工具执行审计统一写入运行时 `ToolExecutionStore`；
`ToolCatalog.record_call` 仅供 `core/tool_executor.py` 旧管理面使用。

### 三注册表收敛（P1-10 终态）

| 注册表 | 终态 |
|--------|------|
| 运行时 `ToolRegistry`（`core/tools.py`） | ✅ **唯一执行表**（Agent 主循环 + MCP 桥接） |
| `ToolCatalog`（`core/tool_registry.py`） | ✅ **唯一 schema 目录**；`bind_runtime_registry()` 显式组合；`ToolRegistry = ToolCatalog` 仅为兼容别名保留 |
| `core/tool_system.py` 实验注册表 | ✅ 已归档（`archive/dead_code_2026-07-19/`），活代码零引用 |
| `mcp/adapter.py` 裸 dict | ✅ 已消除：改为显式组合运行时 `ToolRegistry`，执行走统一咽喉点 |

---

## 仓库内并存的两套 MCP 系统

### 系统 A：`backend/app/core/mcp/manager.py`（生产路径）

**角色**：MCP 服务器连接、工具发现、双写注册、生命周期管理。

| 项 | 状态 |
|----|------|
| 核心类 `MCPManager` | ✅ 已实现 |
| 工具自动发现 `discovery.py` | ✅ 已实现（stdio + Streamable HTTP） |
| 接入 `main.py` startup/shutdown | ✅ 已集成（见 `startup_event`/`shutdown_event`） |
| 配置文件 `config/mcp_servers.yaml` | ✅ 支持（示例：`config/mcp_servers.example.yaml`，含 stdio 示例） |
| 测试覆盖 | ✅ `test_mcp_discovery`(45) + `test_mcp_config`(44) + `test_mcp_e2e`(26) + `test_mcp_main_integration`(8) + `test_mcp_stdio_e2e`(5，真实 stdio server 端到端) 全通过 |
| HTTP 端点 | ❌ 无（仅 Python API） |

**入口 API（Python）**：
```python
from backend.app.core.mcp.manager import (
    initialize_mcp_manager,   # 启动时初始化全局 MCPManager
    shutdown_mcp_manager,     # 关闭时清理
    get_mcp_manager,          # 获取全局实例（未初始化返回 None）
)
```

**启动行为（已在 main.py 实现，fail-open）**：
- 找不到 `config/mcp_servers.yaml` → 优雅跳过，`get_mcp_manager()` 返回 `None`，**不阻塞应用启动**。
- 配置存在但无 `mcp_servers` 或全部服务器连接失败 → 同样返回 `None`，不崩溃。
- 配置正确且至少一个服务器连接成功 → 初始化全局 manager，工具双写进
  `ToolCatalog` 与（经集成波接线后）运行时 `ToolRegistry`。

> ✅ **接线已闭环（2026-08-04）**：`main.py` 调用点已传 `runtime_registry=`
> （dependencies 单例，commit 8c600c9）——AgentLoop、技能注册、MCP 桥接共享
> 同一运行时 ToolRegistry，主循环可直接调用 MCP 工具。回归测试：
> `tests/test_runtime_registry_wiring.py`。
>
> 同批收尾：① 默认 `mcp_config_path` 从 example 文件改为 `config/mcp_servers.yaml`
> （不存在即跳过，避免对 5 个假 server 健康检查）；② P2-04 白名单接入 settings
> （`mcp_server_whitelist`）并经 `MCPManager` 透传 discovery；③ 配置兼容层：
> 支持 `.mcp.json`（Claude Code/Codex 格式）+ `${VAR}` 环境变量展开，旧 `sse`
> type 映射 streamable HTTP（tests/test_mcp_config_compat.py）。

### 系统 B：`backend/app/api/mcp.py`（历史遗留，未启用）

**角色**：一套面向 file/search/browser 工具的 MCP HTTP API。

| 项 | 状态 |
|----|------|
| HTTP 端点定义 | ✅ 代码中存在 |
| 初始化函数 `initialize_mcp_system()` | ✅ 存在，但**未在 startup 调用** |
| router 注册到 `main.py` | ❌ **未注册**（`app.include_router` 列表中无 mcp_router） |
| 因此端点实际可达性 | ❌ **不可达** |
| 适配器内部结构 | ✅ P1-10 已收敛：`MCPToolAdapter` 显式组合运行时 `ToolRegistry`，无裸 dict |

**系统 B 代码中定义的端点**（当前均不可达）：
```
POST /api/v1/mcp/request
POST /api/v1/mcp/tools/execute
GET  /api/v1/mcp/tools
GET  /api/v1/mcp/health
GET  /api/v1/mcp/audit-logs
GET  /api/v1/mcp/permissions/{tool_category}
PUT  /api/v1/mcp/permissions/{tool_category}
GET  /api/v1/mcp/status
```
所有端点需要认证（`principal`）+ scope 校验（`mcp:read` / `mcp:execute` / `mcp:admin`）。

---

## 文档与现实的差异（重要）

仓库内 `docs/MCP_API_REFERENCE.md`（1057 行）描述了一批 HTTP 端点，例如：
```
GET  /api/v1/mcp/stats
GET  /api/v1/mcp/servers
GET  /api/v1/mcp/servers/{server_name}
POST /api/v1/mcp/tools/{tool_id}/execute
POST /api/v1/mcp/tools/batch/execute
```

**这些端点既不匹配系统 A（无 HTTP 端点），也不匹配系统 B（端点路径不同）**——它们更像是早期规划但从未落地的设计。

**结论**：在以下架构决策落定前，`MCP_API_REFERENCE.md` 中的 HTTP 端点章节**不应被当作可用 API**。判断真实能力请以本文档为准。

---

## 待决策的独立事项（不属于 Phase 1/Phase 2 Wave A）

以下是已识别但**有意推迟**的架构决策，需单独立项：

1. **系统 B 端点是否启用**：注册 `api/mcp.py` 的 router 到 `main.py` 并在 startup 调 `initialize_mcp_system()`。
   - 风险：两套 MCP 并存、职责重叠（都管"工具"），需先想清分工。
   - 已知问题：该文件 `execute_tool` 端点构造 `ToolCallInput` 时缺必填的
     `tool_id` 字段（pydantic 校验会失败），启用前必须修复。

2. **系统 A 是否暴露 HTTP 端点**：基于 `MCPManager.get_stats()` / `health_check()` 等给系统 A 写一套 router。
   - 更干净，但需决定系统 B 的去留（合并 / 废弃）。

3. **文档收敛**：将脱节的 `MCP_API_REFERENCE.md` 与现实对齐（删除/标注不存在的端点）。

---

## 如何验证当前现状（可复现）

```python
# 验证系统 A：启动生命周期（无配置时优雅跳过）
import os; os.environ.setdefault("XAGENT_QDRANT_URL", "")
from starlette.testclient import TestClient
from backend.app.main import app
from backend.app.core.mcp.manager import get_mcp_manager

with TestClient(app) as client:          # 触发真实 startup/shutdown
    assert client.get("/health").status_code == 200
    # 无 mcp_servers.yaml 时，manager 为 None（fail-open，符合预期）
    print("MCP manager:", get_mcp_manager())  # → None
```

```bash
# 端到端：真实 stdio MCP server → 发现 → 双写注册 → 主循环 execute 调用
./venv/Scripts/python.exe -m pytest tests/test_mcp_stdio_e2e.py -v -o addopts= -p no:cov

# 验证系统 B 未注册：搜 main.py 无 mcp router
grep -c "include_router.*mcp" backend/app/main.py   # → 0
```

---

## 相关文档

- `config/mcp_servers.example.yaml` — 系统 A 的配置示例（含 stdio 传输示例）
- `docs/MCP_CONFIGURATION_GUIDE.md` — 系统 A 配置详解
- `docs/MCP_API_REFERENCE.md` — ⚠️ HTTP 端点章节与现实脱节，待收敛
- `MCP_ENHANCEMENT_REPORT.md` — Phase 1 进度报告

---

**最后更新**：2026-07-20（Phase 2 Wave A：P1-01 真实 MCP 协议 + P1-10 注册表收敛）
**结论**：系统 A 已完成并验证（真实 MCP 协议 + 主循环桥接）；`main.py` 的
`runtime_registry` 接线待集成波；系统 B 端点接入及文档收敛为独立待决策事项。
