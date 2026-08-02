# Changelog

All notable changes to X-Agent are documented in this file.

> **版本单一事实源**: 全仓版本号以 `pyproject.toml` 的 `project.version` 为准, 当前为 **0.4.0-alpha** (Codex 能力对齐 + 前端完善)。
> 本文件历史中出现过的一切高于 0.2.0-alpha 的版本标签 (含 1.x 系列与 0.7.x-0.9.x 标记) 均为 2026-07-19 商用审计 (`commercial_audit/00_商用交付差距审计报告.md`) 之前遗留的过程性标记, 从未对应任何实际对外发布的版本; 仓库 git 历史于 2026-07-19 fresh init, 不存在已发布 tag。

## [0.4.0-alpha] - 2026-07-30

### Added
- 前端 POST-based SSE 流式消费 (fetch + ReadableStream 实时展示 Agent 步骤)
- Docker 沙箱隔离执行 (run_command 支持 docker/local 双模式, --network none --memory 512m)
- 代码搜索工具 grep_code (正则匹配 + 文件类型过滤 + 上下文行)
- 多语言测试命令识别 detect_test_command (Python/JS/TS/Rust/Go/Java/Ruby/PHP)
- Git 状态 REST API (GET /agents/git/status) + 前端 GitStatusPanel
- 运行历史面板 RunHistoryPanel (自动刷新 + 展开详情)
- 任务模板快捷按钮 (修 Bug / 写测试 / 重构 / 新功能)
- API Key 快捷登录 (开发模式)
- 工具输出截断 _trim_observation (4000 字符 head+tail 保留)

### Fixed
- FastAPI 路由顺序冲突 (/{agent_id} 拦截 /runs, /git/status 等固定路径)
- git status --porcelain 路径解析首字符丢失
- 前端登录状态刷新后丢失 (isAuthenticated 未持久化)
- tools.py _os 未定义引用 + 未使用变量

### Changed
- 多文件任务匹配改为 basename 精确匹配 (消除子串误判)
- plan 阶段强制多文件检测 + reflect 注入
- AgentWorkspace 三栏布局 (左:目录 / 中:流式面板 / 右:Git+历史)

## [0.3.0-alpha] - 2026-07-21

### Added
- MCP 官方 SDK 集成 (stdio + Streamable HTTP)
- WebAuthn FIDO2 签名验证 (EC P-256 + RSA)
- 审计日志轮转 (50MB/30天) + Webhook/Syslog 外送
- Agent 上下文管理 (sliding_window/summarize/hybrid)
- 插件系统工具注册 (plugin__<name>__<tool>)
- Goals CRUD API
- 支付 Provider 模式 (Mock/Stripe/Alipay)
- 通知 Provider 模式 (Console/SMTP/Webhook/Noop)
- 租户配额管理 (6项资源限制 + 429执行)
- Qdrant 快照/恢复 API
- Alembic 版本化数据库迁移
- Grafana 预置仪表盘 (6个)
- 多区域灾备配置 + 自动故障转移
- Locust 负载测试 (4 profile)
- Demo 种子数据脚本
- 发布自动化 (scripts/release.py)
- 自动备份调度 (PG/文件/Qdrant/审计)
- 优雅停机 (7步反依赖关闭)
- SOC2 合规自动验证 (18控制点, 93.3%)

### Changed
- 启动时间 9.2s → 1.4s (延迟路由注册)
- Docker 镜像改为 3 阶段构建 + 非 root
- admin_store 默认 file 持久化
- 前端 i18n 对齐 (EN/ZH 各 390 键)
- CI 全 blocking 门禁 (6 jobs)
- pytest 默认并行 (-n auto)

### Fixed
- 测试隔离 (CSRF session 唯一化 + conftest 单例重置)
- docker-compose neo4j profiles 冲突
- requirements-lock.txt 移除 pywin32 (Linux 不兼容)
- collaboration.py SyntaxError
- ESLint .eslintrc.cjs 语法错误

### Security
- 生产守卫 12 项验证 (CORS/HSTS/CSRF/CSP/限流)
- 滑动窗口限流中间件
- 租户隔离中间件
- Bandit 安全扫描 0 告警

<details>
<summary>商用交付升级详情 (38/100 → 75+/100)</summary>

#### Phase 1: P0 止血
- 修复 20 个 F821 运行时必崩错误 (ruff check 全通过)
- LLM 默认后端改为 `auto` (有 Key 用真实后端，无 Key 明确报错)
- 记忆系统默认切换 PostgreSQL
- 嵌入模型默认改为 sentence-transformers 真实语义
- RBAC 持久化到 PostgreSQL (PostgresRBACRepository)
- 租户隔离改为服务端 JWT 验证
- 修复中文路径问题 (sitecustomize.py)

#### Phase 2: 商用就绪
- 代码质量大扫除: ruff 错误从 9436 降至 <800
- Workflow PostgreSQL 存储 (ACID 保证)
- Workflow 并行分支执行 (DAG 拓扑排序 + asyncio.gather)
- Qdrant 真实向量检索接入
- Prometheus 监控指标真实埋点
- SSO 完善: LDAP 认证提供者 + SAML Beta

#### Phase 3: 竞品对齐
- 自进化闭环引擎 (GEPA: Execute→Reflect→Extract→Curate→Promote→Reuse)
- Codex 风格代码审查 (多维度并行审查)
- 并行 Agent 执行 (Semaphore 限流 + asyncio.gather)
- Goal Mode 长任务 (自动分解 + checkpoint/resume)
- 三层记忆系统 (Tier1:内存/Redis + Tier2:PostgreSQL + Tier3:Qdrant)
- 渠道网关 (Telegram/飞书/Webhook 适配器)

#### Phase 4: 发布打磨
- 部署一键化 (docker-compose production profile + init_secrets.sh)
- CLI 新增: chat, review, memory, skill 命令
- 核心模块导入验证全通过

</details>

## [Unreleased] — 0.2.0-alpha 开发线

### 商用修复 Phase 1「止血与架构收敛」(2026-07-19 起)

- 依据 `commercial_audit/00_商用交付差距审计报告.md` (综合商用就绪度约 31/100, 不可商用交付) 执行 18 项 P0 修复, 详见该报告第五节。
- **版本叙事统一 (P1-20 提前至 Phase 1)**: 版本号以 `pyproject.toml` 为单一事实源, 定为 `0.2.0-alpha`; `frontend/package.json` 与 `sdks/` (Python / TypeScript / Go / Java) 版本号同步对齐; ROADMAP.md 时间线锚定 2026。
- **双 CHANGELOG 收敛**: 旧中文变更日志 `CHANGELOG_NEW.md` 的主体内容并入本节后, 该文件已删除。其宣称的 1.x 版本 (标记日期 2026-05-27) 从未实际发布, 功能清单作为存档并入下文。

### 旧中文变更日志并入存档 (原 CHANGELOG_NEW.md)

> 以下为原 `CHANGELOG_NEW.md` 的主体功能清单 (原标记日期 2026-05-27)。原文件中"破坏性变更""升级指南""版本发布计划 (1.1.0/1.2.0/2.0.0)""贡献者名单"等小节指向从未存在的发布物或不可核验信息, 收敛时予以省略; 其 0.9.0/0.8.0 条目与本文件下方既有条目日期互相矛盾, 以本文件既有条目为准。清单内容为原文件宣称口径, 各项实现深度以 `commercial_audit/` 各分报告的"宣称-存在-接通"复核为准。

#### 功能清单 (新增)

- **Agent 引擎**: 完整的 Agent 生命周期管理; 多 LLM 路由和智能选择; 思考-行动-观察循环; 执行追踪和审计日志; 支持自定义 Agent 类型
- **Workflow 编排**: 工作流定义和验证; 节点执行和状态管理; 条件分支和并行执行; 错误处理和补偿机制; 工作流回放和调试
- **记忆系统**: 双层记忆架构 (结构化 + 向量); PostgreSQL 结构化存储; Qdrant 向量搜索; 语义相似度检索; 自动记忆清理
- **工具系统**: 浏览器自动化 (Playwright); 文件操作工具; API 调用工具; 代码执行工具; 搜索工具; 自定义工具开发框架
- **审批系统**: 人工审批工作流; 多级审批支持; 审批策略配置; 审批历史追踪
- **审计系统**: 完整的操作审计日志; 资源变更追踪; 用户行为分析; 合规性报告
- **API 接口**: 66 个 REST API 端点; WebSocket 实时推送; SSE 流式响应; 完整的 OpenAPI 文档; 速率限制和配额管理
- **安全功能**: JWT 认证; OAuth 2.0 支持; 基于角色的访问控制 (RBAC); API 密钥管理; 敏感数据加密
- **监控和可观测性**: Prometheus 指标导出; Langfuse 请求追踪; 结构化日志记录; 性能监控; 错误追踪

#### 改进清单

- 性能优化: 数据库查询优化; 连接池管理; 缓存策略实现; 异步处理优化; 内存使用优化
- 用户体验: 详细的错误消息; 友好的 API 响应格式; 完整的 API 文档; 丰富的代码示例; 交互式 API 测试工具
- 开发体验: 完整的开发环境配置; Docker Compose 支持; 自动化测试框架; 代码质量检查工具; 调试工具集成

#### 修复清单

- Bug 修复: 内存泄漏问题; 并发访问竞态条件; 数据库连接池溢出; WebSocket 连接断开; 工作流节点超时
- 安全修复: SQL 注入漏洞; XSS 漏洞; CSRF 漏洞; 认证绕过; 权限提升漏洞

#### 原文件自述的已知问题 (保留存档, 待 Phase 1/2 复核)

- 大规模工作流 (>1000 节点) 性能下降
- Qdrant 向量搜索在某些情况下精度不足
- WebSocket 连接在网络不稳定时可能断开
- 某些浏览器自动化操作在特定网站上不稳定

### Phase 5.5 - Cloud Sandbox Engine (2026-06-04)

#### Added
- **Cloud Sandbox Execution Engine**: Docker-based isolated code execution with subprocess fallback
  - `DockerSandbox` class: Container isolation with network/memory/CPU limits, read-only rootfs
  - `SandboxOrchestrator`: Persistent drain loop for task scheduling and worker coordination
  - `SandboxWorker`: Parallel task execution with priority queue management
  - `TaskQueue`: Priority-based task queuing with status tracking

- **Sandbox API Endpoints**:
  - `POST /api/v1/sandbox/tasks`: Fire-and-forget task submission with timeout/image/network config
  - `GET /api/v1/sandbox/tasks`: List all tasks with filtering
  - `GET /api/v1/sandbox/tasks/{task_id}`: Poll task status and results
  - `POST /api/v1/sandbox/webhook/github`: HMAC-signed GitHub issue webhook integration

- **GitHub Automation Pipeline**:
  - `GitOperations`: Clone, commit, push, branch creation with token demasking in logs
  - `GitHubWebhookHandler`: HMAC-SHA256 signature validation, constant-time comparison
  - `IssueToPRPipeline`: Complete Issue→Fix→Test→PR workflow with AgentFixRunner
  - Automatic issue assignment detection and PR creation with comments

- **Infrastructure**:
  - Docker backend detection with auto-fallback to subprocess isolation
  - Docker-out-of-Docker (DooD) support for containerized deployments
  - Dockerfile runtime updates: git installation for IssueToPR pipeline
  - requirements.txt optional docker dependency (docker>=7.0.0)

#### Security
- HMAC-SHA256 webhook verification with secret rotation support
- Sandbox:run scope enforcement for all API endpoints
- Network isolation by default (configurable per-task)
- Token demasking in task logs and audit trails

#### Tests
- 38 integration tests covering:
  - Docker container execution and subprocess fallback
  - Parallel task orchestration and priority scheduling
  - API submission, polling, and webhook verification
  - Full Issue→PR pipeline including git operations

---

## [Phase 1-4 开发里程碑] - 2026-06-01

> 本节原标记为更高版本号, 系审计前遗留的过程性标记, 从未对应实际发布; 现按 pyproject 口径归入 0.2.0-alpha 开发线。

### Phase 1-4 Complete

#### Phase 1 - MCP Protocol Enhancement
- MCP tool discovery engine with auto-registration
- MCP manager integration to FastAPI startup/shutdown lifecycle
- MCP server configuration management (YAML-based)
- Tool adapter for unified MCP client handling

#### Phase 2 - CLI Tools
- Typer-based command-line interface with 6 command modules
- Interactive REPL for agent communication
- Configuration management CLI
- Workflow command suite

#### Phase 3 - Hook System
- Extensible hook executor with fail-open semantics
- Hook configuration from `.xagent/hooks.json`
- Integration to startup lifecycle
- Type-safe hook definitions

#### Phase 4 - Context Management Enhanced
- Session recovery with distributed state management
- Code indexing for context compression
- Semantic retrieval from vector store
- Compression pipeline for token optimization

### Bug Fixes

#### LLM Backend & Tool Execution
- Fixed retry coroutine leakage in `llm_providers.py`
- Fixed schema validation for tool execution arguments
- Fixed tool name normalization across MCP and native registries
- Fixed argument parsing for complex nested tool inputs
- Fixed tool root path resolution for file operations

#### Production Infrastructure
- Fixed Dockerfile git installation (IssueToPR dependency)
- Fixed requirements.txt optional docker package declaration
- Fixed FastAPI route regex deprecation (pattern parameter)

#### Memory & Context
- Fixed memory store/retrieve interface contracts
- Fixed session recovery deadlock in non-reentrant locks
- Fixed compression regex unicode support
- Fixed code index enumeration state management

---

## 早期开发里程碑 (过程性标记, 均未对外发布)

### [0.9.x 标记] - 2026-05-30
- Test suite consolidation (backend/tests → root tests/enterprise)
- Pytest collection error fixes (75 errors resolved)
- QueuePool async engine compatibility fixes
- Prometheus duplicate registry fixes
- Observability contract fixes (error envelope structure)

### [0.8.x 标记] - 2026-05-28
- PBKDF2HMAC security implementation
- AST-based execution sandbox
- Concurrent lock refactoring
- Random salt generation for encryption
- Authentication TTL enforcement

### [0.7.x 标记] - 2026-05-25
- Multi-cluster version drift fixes (57 failures)
- Starlette route API updates
- HTTPx transport parameter alignment
- SQLite executescript for multi-statement support

---

## Development Milestones

- **2026 Q2**: Phase 5.5 Cloud Sandbox 开发完成 (实现深度以审计复核为准)
- **2026 Q3 (当前)**: 商用修复 Phase 1「止血与架构收敛」—— 18 项 P0 清零 + 死代码收敛 + 版本叙事统一 (见 ROADMAP.md 与 commercial_audit/00)
- **2026 Q4 - 2027 Q1**: 商用修复 Phase 2「商用就绪」—— MCP 官方 SDK 返工、真 SSO/SCIM、部署资产收敛等 P1 项
- **2027+**: Phase 3「差异化竞争」—— 完全自托管 / air-gapped、证据驱动完成、移动端触发、商业化管道

---

**Format**: Following [Keep a Changelog](https://keepachangelog.com/) and [Semantic Versioning](https://semver.org/). 版本号以 `pyproject.toml` 为单一事实源。
- Fixed requirements.txt optional docker package declaration
- Fixed FastAPI route regex deprecation (pattern parameter)

#### Memory & Context
- Fixed memory store/retrieve interface contracts
- Fixed session recovery deadlock in non-reentrant locks
- Fixed compression regex unicode support
- Fixed code index enumeration state management

---

## 早期开发里程碑 (过程性标记, 均未对外发布)

### [0.9.x 标记] - 2026-05-30
- Test suite consolidation (backend/tests → root tests/enterprise)
- Pytest collection error fixes (75 errors resolved)
- QueuePool async engine compatibility fixes
- Prometheus duplicate registry fixes
- Observability contract fixes (error envelope structure)

### [0.8.x 标记] - 2026-05-28
- PBKDF2HMAC security implementation
- AST-based execution sandbox
- Concurrent lock refactoring
- Random salt generation for encryption
- Authentication TTL enforcement

### [0.7.x 标记] - 2026-05-25
- Multi-cluster version drift fixes (57 failures)
- Starlette route API updates
- HTTPx transport parameter alignment
- SQLite executescript for multi-statement support

---

## Development Milestones

- **2026 Q2**: Phase 5.5 Cloud Sandbox 开发完成 (实现深度以审计复核为准)
- **2026 Q3 (当前)**: 商用修复 Phase 1「止血与架构收敛」—— 18 项 P0 清零 + 死代码收敛 + 版本叙事统一 (见 ROADMAP.md 与 commercial_audit/00)
- **2026 Q4 - 2027 Q1**: 商用修复 Phase 2「商用就绪」—— MCP 官方 SDK 返工、真 SSO/SCIM、部署资产收敛等 P1 项
- **2027+**: Phase 3「差异化竞争」—— 完全自托管 / air-gapped、证据驱动完成、移动端触发、商业化管道

---

**Format**: Following [Semantic Versioning](https://semver.org/) with Phase numbering for major features. 版本号以 `pyproject.toml` 为单一事实源。
