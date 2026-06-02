# X-Agent 项目说明（Claude Code 专用）

> 本文件由Claude Code自动加载。新会话时Claude会自动读取本文件了解项目背景。

---

## 🎯 项目背景

**X-Agent** 是一个企业级自主智能体框架（Autonomous Agent Framework），定位为AI产品构建者和企业平台的基础设施，而**非**桌面IDE工具或个人开发者助手。

### 与竞品的核心差异
- ❌ 不是 Claude Code、Cursor、Windsurf 这类IDE工具
- ✅ 是 LangChain、AutoGPT 这类Agent框架的企业级版本
- ✅ 目标用户：企业DevOps团队、AI产品公司、平台构建者

### 技术栈
- **后端**：Python 3.11+ / FastAPI / asyncpg
- **数据库**：PostgreSQL 14+ / Qdrant（向量搜索）
- **可观测性**：Langfuse / Prometheus
- **浏览器自动化**：Playwright
- **LLM**：多模型路由（OpenAI、Anthropic等）

---

## 📍 当前进度（2026-06-02 深审校正）

### 升级修复阶段
基于深度竞品分析，正在实施**14周6阶段**的升级计划。

> ⚠️ **2026-06-02 全面深审校正**：原进度表严重滞后于实际代码。经亲读 `backend/app/main.py` 与各模块核实，真实进度如下（不是之前写的"Phase1 80%、其余 0%"）。

| Phase | 任务 | 真实进度 | 核实证据 |
|-------|------|---------|---------|
| Phase 1 | MCP协议增强 | ✅ ~95% | discovery/manager/client/adapter/config/protocol 全真实现；`initialize_mcp_manager`+`shutdown_mcp_manager` **已接入 main.py startup/shutdown 生命周期**；12 个 test_mcp_* 测试存在 |
| Phase 2 | CLI工具开发 | ✅ 完成 | `cli/` 下 Typer 入口+client/config/console/repl+6 命令模块；4 个 test_cli_* |
| Phase 3 | 钩子系统 | ✅ 完成 | `core/hooks/` manager/config/executors/types 全实现；**已接入 main.py startup**（从 `.xagent/hooks.json` 注册，fail-open） |
| Phase 4 | 上下文管理增强 | ✅ 完成 | `core/context/` context_manager/session_recovery/code_index/compression/retrieval 全实现 |
| Phase 5 | 多渠道适配器 | 🔄 ~40% | 仅 Feishu（webhook+事件）完整 + Slack 示例；缺统一渠道框架与其他渠道 |
| Phase 6 | VS Code扩展 | ❌ 0% | 无 VS Code 扩展；但有完整 **Chrome 扩展**（MV3，extension/ 下，含 WebStore 提交指南） |

### Phase 1 已完成（已全部落地）
- ✅ `backend/app/core/mcp/discovery.py` - MCP工具自动发现
- ✅ `backend/app/core/mcp/manager.py` - MCP统一管理器
- ✅ **已集成到 `backend/app/main.py`** startup/shutdown 事件（initialize/shutdown_mcp_manager）
- ✅ 单元测试与集成测试齐备（test_mcp_discovery/config/manager/e2e/main_integration 等）

### 后续真实重点（非 Phase 1）
- 🔄 Phase 5 多渠道：补统一渠道框架 + 更多渠道适配器
- ⏳ 考虑 Phase 6 是否真需要 VS Code 扩展（当前替代品=Chrome 扩展已生产就绪）
- ⏳ 全量测试基线只能在本机跑（沙箱有 44s 命令墙，跑不完 4061 测试）

---

## 🏗️ 项目结构

```
X-Agent/
├── backend/app/
│   ├── main.py                    # FastAPI主入口
│   ├── core/
│   │   ├── mcp/                   # MCP协议模块（重点）
│   │   │   ├── discovery.py      # ✅ 工具发现（新增）
│   │   │   ├── manager.py        # ✅ 管理器（新增）
│   │   │   ├── client.py         # MCP客户端（已有）
│   │   │   ├── adapter.py        # 工具适配器（已有）
│   │   │   ├── config.py         # 配置管理（已有）
│   │   │   └── protocol.py       # 协议定义（已有）
│   │   ├── tool_registry.py      # 工具注册表
│   │   ├── plugin_system.py      # 插件系统
│   │   ├── execution_planner.py  # 工作流引擎
│   │   ├── memory_*.py           # 内存系统
│   │   └── agent_v2/             # Agent v2实现
│   ├── api/                       # REST API
│   ├── services/                  # 服务层（browser/memory/observability）
│   └── tests/                     # 测试目录
├── tests/                         # 根级测试
├── config/                        # 配置文件
├── docs/                          # 文档
└── 升级相关文档（见下方）
```

---

## 📚 关键文档（按重要性排序）

读取以下文档了解完整背景：

1. **`competitive_analysis_report.md`** - 竞品深度分析（8000字）
   - 6个竞品对比（Claude Code、Codex、Cursor、Windsurf等）
   - 6个关键能力差距分析
   - 战略建议

2. **`UPGRADE_PLAN.md`** - 14周升级计划
   - 6个Phase详细任务分解
   - 资源需求和时间线
   - 验收标准

3. **`MCP_ENHANCEMENT_REPORT.md`** - Phase 1 进度报告
   - 已完成的MCP工作
   - 待完成清单
   - 集成示例代码

4. **`UPGRADE_IMPLEMENTATION_REPORT.md`** - 实施报告

5. **`WORK_SUMMARY.md`** - 工作总结

---

## ⚠️ 重要约束（必读）

### 测试套件状态（来自历史会话记忆）
- **当前基线**：3856 passed / 76 fail / 4 err（之前是627 fail，已大幅修复）
- **测试套件统一**：`backend/tests/` 已并入根级 `tests/enterprise/`（2026-05-30）
- **不要动的部分**：
  - 安全簇（HMAC/正则沙箱/固定盐）需要用户定夺，不要自主修改
  - `memory_v2` 模块边界外的代码不要碰
  - HIGH-RISK安全相关改动需要用户审批

### Git策略（关键）
- ❌ **绝对不要 `git add .`** - 大量untracked文件，会污染commit
- ✅ 提交前必须用户确认绿跑
- ✅ 始终用具体路径stage特定文件
- ⚠️ `dr-config.env` 等5个JSON文件含密钥，untrack需用户定夺

### 验证规则（Verify Agent Output）
- 子Agent报告完成后**必须用绝对路径Read核实**
- Agent经常over-report success，不要轻信
- VM bash读CJK大文件会**静默截断**，要用Read工具（Windows视图）核实

### Edit工具陷阱
- Edit/Write经过CJK路径回写会在尾部追加NUL字节，导致 `py_compile` 报错
- Read看不到这些NUL字节，需用 `bash grep` 检测 + `tr` 剥离
- 如果创建文件后py_compile失败，先检查是否有NUL填充

---

## 🎯 X-Agent 核心优势（保持差异化）

这些是竞品**短期内难以复制**的护城河，开发时要保护和强化：

| 能力 | X-Agent | 竞品 |
|------|---------|------|
| 工作流编排 | ⭐⭐⭐⭐⭐ | ⭐ |
| 多智能体协作 | ⭐⭐⭐⭐⭐ | ⭐ |
| 高级内存系统（图+向量） | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 完整可观测性（Langfuse） | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 企业级功能（多租户/审批/审计） | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

---

## 🔴 关键能力差距（待补齐）

### P0 高优先级
1. **MCP协议** - 4个竞品均支持，已成事实标准（🔄进行中）
2. **CLI工具** - 仅API+Web，缺CLI/TUI（⏳下一步）
3. **IDE集成** - 无VS Code扩展（⏳后续）

### P1 中优先级
4. **钩子系统** - 工作流定制不灵活
5. **多渠道接入** - OpenClaw支持22+渠道，X-Agent仅API
6. **上下文管理** - 未充分利用Claude 1M tokens优势

---

## 🚀 推荐的下一步行动

### 选项A: 完成Phase 1（推荐）⭐
**预计时间**: 2-3小时

1. 集成MCP管理器到 `backend/app/main.py` 启动流程
2. 创建MCP相关单元测试
3. 创建端到端集成测试
4. 更新API文档

**起点代码**：
```python
# backend/app/main.py 添加：
from backend.app.core.mcp.manager import (
    initialize_mcp_manager, 
    shutdown_mcp_manager
)
from backend.app.core.tool_registry import ToolRegistry

tool_registry = ToolRegistry()

@app.on_event("startup")
async def startup_event():
    await initialize_mcp_manager(
        tool_registry=tool_registry,
        config_path="config/mcp_servers.yaml"
    )

@app.on_event("shutdown")
async def shutdown_event():
    await shutdown_mcp_manager()
```

### 选项B: 启动Phase 2（CLI工具）
**预计时间**: 1周

技术栈：Click或Typer + Rich + Prompt Toolkit

### 选项C: 设计Phase 3（钩子系统）
**预计时间**: 3-4小时

先做架构设计文档，再开发实现。

---

## 💻 开发环境

### 路径映射
- 项目根目录：`D:\AI编程库\项目库\进行中的项目\X-Agent`
- Hermes-agent venv（如需切换）：`C:\Users\canqu\AppData\Local\hermes\hermes-agent\venv\`

### pip 镜像配置（已完成）
- 配置文件：`C:\Users\canqu\AppData\Roaming\pip\pip.ini`
- 镜像源：`https://pypi.tuna.tsinghua.edu.cn/simple`
- 已清除代理变量

### 推荐做法
```powershell
# 切到项目目录
cd D:\AI编程库\项目库\进行中的项目\X-Agent

# 退出hermes venv（如果在）
deactivate

# 激活X-Agent自己的venv
.\venv\Scripts\Activate.ps1

# 或创建新venv
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

---

## 🔍 代码风格

- 使用 Python 类型注解（必须）
- 完整的 docstring（Google风格）
- 详细的错误处理和日志
- 异步优先（async/await）
- 测试驱动开发（TDD优先）

---

## 📝 提交规范

### Commit message 格式
```
feat: 新功能
fix: bug修复
docs: 文档更新
test: 测试相关
refactor: 重构
chore: 杂项
```

### 示例
```
feat: integrate MCP manager to main.py startup
fix: resolve MCP tool discovery race condition
docs: update MCP integration guide
test: add MCP manager unit tests
```

---

## 🎓 历史会话经验（重要）

### 已踩过的坑
1. **bash读大文件截断** - 用Read工具核实，不用bash compile判断
2. **Edit工具NUL填充** - CJK路径回写时尾部追加NUL，py_compile会炸
3. **Agent过度报告成功** - 必须用绝对路径Read核实
4. **真值默认URL击穿fallback** - 如qdrant_url默认值导致建真client阻塞worker
5. **session_recovery非可重入锁自死锁** - 复合方法去外层锁
6. **LLMManager dedup让primary等自己** - register_or_get_in_flight切primary/follower
7. **同步QueuePool传给async engine** - sqlite用NullPool

### 成熟的工作模式
- 按根因聚类，找代表性失败
- 用baseline.xml做cluster定位
- HIGH-RISK改动留给用户决策
- 修完一层立刻跑确认，避免掀开第二层污染判断

---

## ❓ 新会话开场白（用户使用）

如果用户进入新会话，说"继续X-Agent升级工作"或类似的话，Claude应该：

1. 先读取本文件（CLAUDE.md）了解全貌
2. 读取 `MCP_ENHANCEMENT_REPORT.md` 了解Phase 1详情
3. 读取 `UPGRADE_PLAN.md` 了解后续计划
4. 询问用户选择哪个任务（A/B/C选项）
5. 开始具体工作前，用 codegraph 工具确认现有代码状态

**不要**：
- 重复创建已有的文件
- 跳过测试直接说"完成"
- 假设代码状态，必须实际读取
- 自主决定HIGH-RISK改动

---

**最后更新**: 2026-06-02（深审校正）  
**当前阶段**: Phase 1-4 已完成；Phase 5 多渠道 ~40%；Phase 6 待定  
**下一步**: 补 Phase 5 统一渠道框架，或本机跑全量测试基线确认绿

## 🤝 双模型协作（Kimi Fallback + Review）

本项目配置了 Kimi Code 作为辅助。Claude Code 应当：

### 何时调用 code-reviewer subagent（评审）
- ✅ 改动 backend/app/core/ 下的 .py 文件且 >30 行
- ✅ 安全相关改动（HMAC、SQL、沙箱、认证）
- ✅ 并发相关改动（asyncio、锁、连接池）
- ✅ Phase 任务的关键交付物
- ❌ 单行 typo / 文档改动 / 配置微调

### 何时调用 code-verifier subagent（验证 fallback）
- ✅ pytest 卡死或超时（>60s）
- ✅ py_compile 错误信息看不到上下文
- ✅ ruff/mypy 等工具不可用
- ✅ 同一命令连跑 2 次结果不一致
- ❌ 简单语法检查（py_compile 够用）

### 评审报告处理原则
- VERIFIED 问题: 必须修复或解释为什么不修
- HALLUCINATED 问题: 忽略，但记录在评审历史
- UNVERIFIED 问题: 让用户决定
- 安全簇问题: 升级给用户审批，不自主修

### Token 预算
- 一次完整评审 ~ 15K input + 3K output
- 一次 fallback 验证 ~ 5K input + 1K output
- 不要为小改动调用评审（浪费 token）

---

## 🤖 沙箱全自动测试（Cowork 桌面版专用 - 2026-06-01 打通）

**背景**：Cowork 桌面版运行在隔离 Linux 沙箱（Python 3.10.12），网络封锁（pip 装不了），默认没有项目依赖。这导致"代码验证完全需要用户配合"。本方案已彻底解决——沙箱现在能**全自动跑 pytest**，无需用户中转。

### 已就绪的环境（持久化在沙箱）

1. **离线依赖**：`.wheels/` 目录有 126 个 Linux/py3.10 wheel（27.5MB→已扩充），含 pytest/fastapi/pydantic/asyncpg/openai/anthropic/langfuse/sklearn/scipy/redis 等。已 `pip install --no-index` 装好。
2. **Python 3.10 兼容 shim**：`~/.local/lib/python3.10/site-packages/_xagent_py310_shim.py` + `zzz_xagent_shim.pth`（自动加载）。补丁了项目用的 2 个 3.11+ 特性：
   - `datetime.UTC`（212 文件用）→ `timezone.utc`
   - `enum.StrEnum`（125 文件用）→ 3.10 兼容子类
3. **版本对齐**：fastapi 已升到 0.133.1、pydantic 2.13.4（匹配本机，避开 0.115 的 `-> None` + 204 假错）。

### 跑 pytest 的标准姿势（沙箱内）

```bash
cd /sessions/.../mnt/X-Agent
python3 -m pytest tests/test_XXX.py \
  -o addopts="" \      # 清空 pytest.ini 里写死的 --cov=...（否则报 unrecognized）
  -p no:cov \          # 禁 coverage 插件（挂载层不允许删 .coverage 临时文件）
  -p no:cacheprovider \
  --no-header -q
```

**已验证通过**：test_mcp_discovery(45)、test_mcp_config(44)、test_tools(3) 全 passed。**4053/4056 测试可 collect**，仅 3 个 playwright 测试沙箱跑不了（需浏览器）。

### 关键陷阱（本次踩过）

1. **pytest.ini 的 addopts 写死 `--cov`** → 禁 cov 插件会报 unrecognized → 必须同时 `-o addopts=""`
2. **挂载层不允许 unlink** → pytest-cov 删 .coverage 时 PermissionError → 用 `-p no:cov`
3. **bash 读 CJK 路径文件会截断**（如 manager.py 读成 320 行）→ 用 `stat`/Python UTF-8 直读核实真实大小，py_compile 假错别信，改用本机或 Read 工具
4. **pytest-asyncio 版本**：必须 0.25.0（0.23.0 有 `'Package' object has no attribute 'obj'` collection bug）
5. **langfuse 3.x 依赖 pydantic v1** → 装 langfuse 会把 pydantic 降级到 1.10 → 装完必须 `--force-reinstall --no-deps pydantic==2.13.4` 恢复
6. **跨平台下载 wheel**：本机 PowerShell 用 `pip download --only-binary=:all: --platform manylinux2014_x86_64 --platform manylinux_2_17_x86_64 --python-version 3.10 --abi cp310 --abi none -d .wheels <pkgs>`

### 不能在沙箱跑的（仍需用户本机）

- **playwright 测试**：需下浏览器（几百 MB + 联网），沙箱跑不了
- **torch/paddleocr/opencv/transformers** 相关 ML 测试：GB 级，未装
- **真实 PostgreSQL/Qdrant 集成测试**：服务没起（测试默认用 SQLite/mock，一般不受影响）

### 新会话如何复用

沙箱依赖**不持久**（VM 重置后丢失），但 `.wheels/` 在项目目录（持久）。新会话只需重装：
```bash
cd /sessions/.../mnt/X-Agent
pip install --no-index --find-links .wheels pytest pytest-asyncio==0.25.0 fastapi==0.133.1 \
  pydantic==2.13.4 sqlalchemy aiosqlite asyncpg redis fakeredis scikit-learn scipy networkx \
  httpx starlette typer nest-asyncio orjson openai anthropic langfuse qdrant-client \
  uvicorn celery prometheus-client aiohttp grpcio prompt_toolkit black isort 2>&1 | tail -3
# 装完务必恢复 pydantic（langfuse 会降级它）:
pip install --no-index --find-links .wheels --force-reinstall --no-deps pydantic==2.13.4 pydantic-core==2.46.4
# shim 若丢失则重建（见上方路径）
```

---

## ⏱️ 沙箱测试能力的真实边界（2026-06-01 实测）

**针对性测试可行，全量基线不可行。** 实测数据：

| 测试类型 | 速度 | 沙箱可行性 |
|---------|------|-----------|
| MCP/schema/纯逻辑单元 | ~0.4 秒/个 | ✅ 单文件秒级 |
| agent 类（起 agent 循环/LLM mock） | ~2.7 秒/个 | ⚠️ 单文件可能超 44s |
| 全应用集成（TestClient + agents/run） | ~10 秒/个 | ❌ 几个就超时 |

**根因**：conftest 的 autouse `_init_global_db` fixture 对**每个**测试建临时 SQLite + 全表；agent/集成测试还额外起重型机制。叠加沙箱 **44 秒命令硬墙** + 后台进程会被杀，**完整 4061 测试估计需数小时，沙箱跑不完**。

**实测硬数据**（可信）：
- 可 collect：**4061 测试**，仅 **3 个 collection error**（全 playwright）
- MCP 模块：**123 passed**（discovery 45 + config 44 + e2e 26 + main_integration 8）

**正确用法**：
- ✅ 改了某模块 → 跑该模块的 1~few 个测试文件，秒级~分钟级自验
- ❌ 不要尝试沙箱跑全套件/大批次（撞 44s 墙，浪费时间）
- 全量基线（替换历史 3856/76/4）只能在**用户本机**跑（无 44s 墙、Windows 原生、依赖齐全）

**另一隐患——OS 差异假失败**：沙箱是 Linux，代码里 `os.sep`/路径/平台分支行为不同。例：`test_browser_screenshot_blocks_path_traversal` 在沙箱失败（`C:/Windows/...` 在 Linux 下不含 `..` 故未被 `_sanitize_screenshot_path` 拦截），但本机 Windows 上很可能正常。**涉及 OS/路径的测试，沙箱结果不等于本机，需本机复核。**

---

## 🔬 逐模块验证发现（2026-06-01 进行中）

### ⚠️ 跑测试前必须清代理变量（否则 httpx 假失败）
沙箱有 `ftp_proxy/grpc_proxy=socks5h://localhost:1080`，httpx 不支持 socks5h → 凡用 httpx 的测试假失败（`ValueError: Unknown scheme for proxy URL`）。**标准前缀**：
```bash
unset ALL_PROXY all_proxy HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ftp_proxy grpc_proxy
export XAGENT_QDRANT_URL=""
```
实证：test_mcp_components 带代理 3 failed → 清代理后 19 passed。

### 🔴 真 bug：MCPManager↔MCPToolAdapter 接口不匹配（待修）
`manager.py` 调用了 adapter **不存在的接口**：
- `MCPToolAdapter({})` 传 dict，但 `__init__(mcp_client, file_tool, search_tool, browser_tool)`
- `adapter.add_client(name, client)` → **adapter.py 无此方法** → AttributeError
- `adapter.execute_tool(tool_schema, args)` → 实际签名 `execute_tool(tool_input: ToolCallInput)`

**后果**：`initialize()` 有真实 mcp_servers 配置时必失败（异常被 `on_discovery_error:warn` 吞 → 返回 False）。无配置场景测试通过，掩盖了此 bug。
**证据**：test_mcp_manager.py 的 TestManagerInitialize 3 failed（清代理后仍失败=真bug）。
**修复方案1（推荐，最小改动）**：manager.py 删掉 `adapter.add_client` 调用（client 已存于 discovery.servers），execute_tool 直接走 client。约 5 行。
**待用户决策**：涉及系统A/B架构歧义，未自主修。

### 逐模块验证进度
- ✅ MCP 模块：201 passed / 3 failed（1真bug=上述；其余全绿）
- ✅ 工具/插件模块：78 passed / 1 failed
  - 🔴 真bug #2：`plugin_crawler.py:251` `_is_xagent_plugin` 关键词含 `"plugin"` 过宽，任何带"plugin"的仓库被误判为X-Agent插件。修复=keywords删掉"plugin"，保留["x-agent","xagent"]。证据：test_plugin_market::test_is_xagent_plugin。待用户定。
- ✅ 内存模块：99 passed / 2 failed（retrieval 2p/comprehensive 24p/detail 1p/api 2p/edge 31p/vector 6p/fusion 23p+2f）
  - ⚠️ fusion 失败1 test_adjust_weights：行为歧义非bug——测试要权重精确=0.5又要和=1，矛盾；实现选normalize()→0.4167。需定取舍。
  - ⚠️ fusion 失败2 test_hybrid_retrieve：sklearn维度 X=4 vs Y=128，疑测试mock向量维度不匹配，待查。
