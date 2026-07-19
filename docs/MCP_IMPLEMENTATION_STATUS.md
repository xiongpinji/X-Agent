# MCP 实现现状（Implementation Status）

> **本文档是 MCP 功能"实际可用状态"的单一可信来源（single source of truth）。**
> 创建于 2026-06-01，对应 Phase 1（MCP 协议增强）收尾。
>
> ⚠️ 背景：仓库内已有多份 MCP 文档（`MCP_API_REFERENCE.md`、`MCP_INTEGRATION_GUIDE.md`
> 等），但其中部分描述的 HTTP 端点**与当前代码不符**（见下方"文档与现实的差异"）。
> 在架构决策落定前，请以**本文档**为准判断哪些功能真正可用。

---

## TL;DR（一句话现状）

- ✅ **系统 A（MCPManager）已完成并接入应用启动流程**——通过 Python API 可用，有完整测试覆盖。
- ⚠️ **MCP 的 HTTP 端点目前对外不可达**——`api/mcp.py` 的 router 尚未注册到 `main.py`，属于待决策的独立事项。

---

## 仓库内并存的两套 MCP 系统

X-Agent 当前同时存在两套 MCP 相关实现，**职责不同、初始化不同、全局状态不同**：

### 系统 A：`backend/app/core/mcp/manager.py`（Phase 1 核心交付）

**角色**：MCP 工具的发现、注册、生命周期管理。

| 项 | 状态 |
|----|------|
| 核心类 `MCPManager` | ✅ 已实现 |
| 工具自动发现 `discovery.py` | ✅ 已实现 |
| 接入 `main.py` startup/shutdown | ✅ 已集成（见 `startup_event`/`shutdown_event`） |
| 配置文件 `config/mcp_servers.yaml` | ✅ 支持（示例：`config/mcp_servers.example.yaml`） |
| 测试覆盖 | ✅ `test_mcp_discovery`(45) + `test_mcp_config`(44) + `test_mcp_e2e`(26) + `test_mcp_main_integration`(8) 全通过 |
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
- 配置正确且至少一个服务器连接成功 → 初始化全局 manager，注册工具到 `ToolRegistry`。

### 系统 B：`backend/app/api/mcp.py`（历史遗留，未启用）

**角色**：一套面向 file/search/browser 工具的 MCP HTTP API。

| 项 | 状态 |
|----|------|
| HTTP 端点定义 | ✅ 代码中存在 |
| 初始化函数 `initialize_mcp_system()` | ✅ 存在，但**未在 startup 调用** |
| router 注册到 `main.py` | ❌ **未注册**（`app.include_router` 列表中无 mcp_router） |
| 因此端点实际可达性 | ❌ **不可达** |

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

## 待决策的独立事项（不属于 Phase 1）

以下是已识别但**有意推迟**的架构决策，需单独立项：

1. **系统 B 端点是否启用**：注册 `api/mcp.py` 的 router 到 `main.py` 并在 startup 调 `initialize_mcp_system()`。
   - 风险：两套 MCP 并存、职责重叠（都管"工具"），需先想清分工。

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
# 验证系统 B 未注册：搜 main.py 无 mcp router
grep -c "include_router.*mcp" backend/app/main.py   # → 0
```

---

## 相关文档

- `config/mcp_servers.example.yaml` — 系统 A 的配置示例
- `docs/MCP_CONFIGURATION_GUIDE.md` — 系统 A 配置详解（与现实一致）
- `docs/MCP_API_REFERENCE.md` — ⚠️ HTTP 端点章节与现实脱节，待收敛
- `MCP_ENHANCEMENT_REPORT.md` — Phase 1 进度报告

---

**最后更新**：2026-06-01
**对应阶段**：Phase 1（MCP 协议增强）收尾
**结论**：系统 A 已完成并验证；系统 B 端点接入及文档收敛为独立待决策事项。
