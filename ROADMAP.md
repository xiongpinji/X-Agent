# X-Agent Core Roadmap

Strategic roadmap for X-Agent Core development, outlining planned features, improvements, and milestones.

> **版本口径**: 版本号以 `pyproject.toml` 为单一事实源 (当前 `0.4.0-alpha`)。本文件已于 2026-07-19 按 `commercial_audit/00_商用交付差距审计报告.md` 的结论重写时间线; 此前版本中的"生产就绪"状态宣称与 2025 年时间线均为过时叙事, 已更正。

## Vision

Build the most capable, secure, and user-friendly autonomous agent framework for enterprise and open-source communities.

## Current Status

**Version**: 0.4.0-alpha (以 `pyproject.toml` 为单一事实源)
**Status**: 商用修复中 — Phase 1「止血与架构收敛」(2026-07-19 启动)
**Audit Baseline**: 2026-07-19 商用交付差距审计综合评分约 31/100, **暂不具备任何形态的对外商用交付条件** (SaaS / 自托管 / 框架 SDK 均不可); 问题集中在"接线、收敛、验证"而非"从零建设", 修复路径是"收敛"而非"重写"。详见 `commercial_audit/00_商用交付差距审计报告.md`。
**Release**: 尚无对外发布版本; git 仓库于 2026-07-19 fresh init (基线提交 f3aab93)。
**Latest Progress**: 2026-08-04 **18 项 P0 修复清零**（复核 16 项已修 + 本日补 P0-04 监控栈收敛 / P0-06 审批租户收敛 / P0-15 降级路径 fail-closed，见 `commercial_audit/P0_STATUS_2026-08-04.md`）；顺序污染隔离工程收官（全量 7359 passed / 28 failed 全固有）。前序：2026-08-03 商用交付冲刺 G1-G8 全绿。

## Roadmap Timeline

### 已完成的开发积累 (截至 2026-07)

> 以下勾选表示仓内**存在**对应实现代码, 不代表已验证的生产可用性; 各项实现深度经 2026-07-19 审计复核 (普遍存在"宣称-存在-接通"三层脱节), 详见 `commercial_audit/` 各分报告。

#### Core Features
- [x] Multi-LLM Router with intelligent routing (生产路径为顺序 fallback, 智能路由 SmartLLMRouter 已接线、flag-gated XAGENT_LLM_ROUTING_MODE=smart, P1-08)
- [x] Advanced Memory System with vector search (伪嵌入/无去重, P1-13)
- [x] Workflow Orchestration and scheduling (JSON 文件存储, 无 cron, P1-07)
- [x] Browser Automation with Playwright (主 API 恒 fallback, P0-11 修复中)
- [x] Observability and tracing with Langfuse
- [x] Approval Workflows for human oversight (审批人身份可伪造, P0-07 修复中)
- [x] Policy Engine for behavior control
- [x] Multi-tenant support with RBAC (隔离中间件未挂载, P0-06 修复中)

#### Infrastructure
- [x] PostgreSQL persistence layer
- [x] Qdrant vector database integration
- [x] Docker and Docker Compose support (标准部署路径修复前必崩, P0-01/02/03)
- [x] CI/CD pipeline 配置 (2026-07-19 git init 前从未运行, P0-09)
- [x] Comprehensive test suite (覆盖率未验证, 默认路径曾全量跳过, P0-10)

#### Documentation
- [x] Installation guide
- [x] API documentation
- [x] Architecture guide
- [x] Contributing guidelines
- [x] Security policy

### 2026 Q3 (当前) — Phase 1「止血与架构收敛」

> 目标: 消除全部"假成功"与"启动即崩", 让标准部署路径真实可用, 质量证据链可信。约 60 人日 (2 名工程师 × 4-6 周)。验收标准见 commercial_audit/00 第六节。

- [x] 18 项 P0 修复清零 (compose init.sql / Celery 启动命令 / 环境变量前缀 / 监控接线 / OIDC 签名校验 / 租户隔离 / 审批可信化 / git 历史决策关闭 / 测试路径修复 / 浏览器与并行 Agent 假成功 / React 接线 / 控制台路由与登录 UI / 沙箱宿主直写 / templates.py / 记忆路由冲突与 Cypher 注入 / AST 黑名单沙箱) — 2026-08-04 复核清零，见 `commercial_audit/P0_STATUS_2026-08-04.md`
- [x] 死代码与重复实现收敛 — **2026-08-04 全部三波收官**：生产树移出 ~21.8k 行；LLM 路由/ToolRegistry/workflow/缓存/协作主目标达成；第三波：cloud_executor/插件市场/技能市场子岛归档，orchestrator+multi_agent 保留不挂载（G3 零余量），agent_communication_bus 实证为活保留（详见 `archive/dead_code_2026-08/README.md`）
- [x] 版本叙事统一 (P1-20 提前: pyproject 单一事实源 0.4.0-alpha; 砍 CHANGELOG_NEW; ROADMAP/前端/SDK 口径对齐)
- [x] git init + 基线提交 (2026-07-19, f3aab93); 唯一 CI 打通进行中 (P0-09)

### 2026 Q4 — Phase 2「商用就绪」(功能本体收敛)

> 目标: 对照 2026 五维 checklist 补齐 P1, 达到"可演示的商用部署"。约 158 人日 (3 名工程师 × 8-10 周)。

#### 协议与路由
- [x] MCP 改用官方 SDK (stdio + Streamable HTTP), 工具桥接进运行时 ToolRegistry (P1-01) — 官方 mcp 1.28.1 客户端 + 真实 e2e 背书；2026-08-04 收尾：runtime_registry 接线闭环、默认配置路径修正、P2-04 白名单接入、.mcp.json 兼容层；系统 B 遗留（api/mcp.py，843 行从未挂载）已归档清除
- [x] LLM 路由收敛为一套 + Anthropic/Ollama 接线 + 租户级成本配额 (P1-08) — build_llm_router 单一构造入口 + anthropic/ollama 已接线 + profiles/定价外置 + TokenQuotaManager 租户/用户双桶；2026-08-04 残留收尾：tenant_id/user_id 穿透主循环（fast-path+规划循环）、断链状态端点修复（get_quota_manager）、QuotaExceededError→429 全局映射（tests/test_llm_quota_wiring.py 6 用例）；三套配额系统（llm/quota・tenant_quota・quota_manager）裁决单独立项
- [x] ToolRegistry 合并为单一运行时注册表 + 单一 ToolCatalog (P1-10) — 运行时表 dependencies 单例（8c600c9）；2026-08-04 目录侧实例级单例化收尾：get_tool_catalog() 唯一实例，main/container/ToolExecutor/ToolManager 旧管理面四处构造点改指（显式 storage_path 仍允许隔离实例），裁决记录见 core/tool_registry.py docstring

#### Multi-Agent Collaboration
- [x] Agent-to-agent communication protocol (协作包收敛, P1-09) — 2026-08-04 批次 C 裁决：agent_communication_bus 为唯一通信面，messages send/broadcast/publish/stats 4 端点挂载（295/300）；deprecated 簇闭环归档：parallel_execution_engine+parallel_execution_benchmark+advanced_features（~1700 行，互引闭环零生产引用）；至此协作/通信收敛为 collaboration 包 + parallel_agent_executor + bus 唯一 live 面
- [x] Task delegation and load balancing — delegation 真实落地（capability_match + RoundRobin + agent_spawner 真实子 AgentLoop，已进主循环工具面与 /delegate 端点）；2026-08-04 批次 D 裁决：负载均衡定为 RoundRobin 单语义——api/agents.py extended_router 的复合打分 routing/dispatch 为第二实现、保持不挂载；跨进程 worker 池/心跳明确不做；org 候选源依赖未挂载的 organization_control（生产通常为空，已文档化）
- [x] Capability matching and discovery — 匹配：capability_match（子集、大小写不敏感）已在 /delegate 生效；发现：2026-08-04 批次 D 真实化并挂载 /collaboration/agents/discover（+1 路由，296/300）——真实枚举 org 花名册/spawner 实例/room 成员/隐式 generalist，capability 过滤与 delegation 同一匹配语义（tests/test_collaboration_discover.py 3 用例）
- [x] PROCESS/CONTAINER 隔离落地或删除参数 (P1-09) — spawner 侧 PROCESS 真子进程已落地、CONTAINER 显式拒绝指向沙箱；2026-08-04 批次 B：parallel_agent_executor 的 IsolationMode 装饰参数收敛——SANDBOXED/PROCESS 显式拒绝（NotImplementedError→API 501，指向 agent_spawner 真实隔离），SHARED/ISOLATED/THREAD 为诚实同进程语义（裁决记录见枚举 docstring）
- 批次 A（2026-08-04）：4 个零生产引用协作幽灵模块（task_dispatcher/agent_coordinator/parallel_executor/agent_recovery，~1700 行）已归档，测试拆分随迁；advanced_features 随批次 C 对 parallel_execution_engine 的裁决一并处理
- 批次 E-lite（2026-08-04）：orchestrator `_delegate_subtask` 假实现（sleep+编造输出）已真实化为 CollaborationDelegator 路径（真实子 AgentLoop，失败经 DelegationError 交 failure_policy 裁决）；api/multi_agent.py 补齐鉴权+租户注入+规则分解诚实标注，达可挂载状态但**不挂载**（+4 路由会顶满 G3 300/300，挂载留待路由预算评审）；tests/test_orchestrator_real_delegation.py 3 用例

#### Memory & Reasoning
- [x] 真实嵌入服务替换哈希伪嵌入; 去重接通主存储 (P1-13) — OpenAI/sentence-transformers 真实嵌入 + 显式降级；去重已接主存储（写路径 WritePathDeduper）；2026-08-04 残留收尾：UnifiedMemorySystem 结束零消费——主循环运行结束镜像存储 + 相关记忆检索合并（失败不阻断，tests/test_unified_memory_wiring.py 3 用例）；三套记忆模型统一（MemorySystem/Unified/Hybrid）与默认部署哈希 fallback 文档兜底单独立项
- [x] 上下文管理接入 Agent 主循环 (token 级压缩 + 会话恢复, P1-14) — tiktoken 真实 token 压缩 + Bridge/ACM 双轨会话恢复已在主循环；2026-08-04 残留收尾：sessions REST 路由注册（+10 路由，291/300）+ startup 注入 dependencies 共享 ContextManager（与 AgentLoop 桥接同 data/sessions 存储），全生命周期冒烟通过；ACM/Bridge 双轨合并为技术债
- [x] 技能系统接线或删除; 插件系统接线或归档 (P1-11/12) — 技能：主循环接线（skill__ 工具进统一 ToolRegistry）+ 管理平面裁决挂载 skills_api（P1-11 修复版、测试齐全）、重复实现 api/skills.py 已归档；插件：plugin_runtime_router 挂载 + startup 加载冒烟通过（5 插件发现、legacy 格式诚实标注）；skill_sediment 路由保持不挂载（Phase 3 技能自沉淀闭环 surface）
- [ ] Chain-of-thought reasoning / Multi-step planning (延后至 Phase 3 评估)

#### Workflow & Developer Experience
- [x] Workflow 存储迁移 Postgres + cron 调度 + 并行分支 (P1-07) — 核验已在产：workflow_store.py SQL 实现（Postgres/SQLite 双后端 auto/db/file 显式选择，db 模式失败显式报错）、5 字段 cron（croniter + 内置降级）、层级并行分支执行（max_parallel/parallel_mode）、崩溃恢复（worker lease + 快照版本 + 中间进度持久化）、独立 worker console script；103 个 workflow 测试全绿（2026-08-05 核验）
- [x] CLI 循环导入修复; SDK 补打包元数据 (P1-22) — 核验已在产：CLI 23 个模块全量导入零失败、console script xagent 可用；SDK pyproject 元数据齐备（构建后端/依赖/分类器，动态版本）；2026-08-05 修 SDK __version__ 0.3.0-alpha→0.4.0-alpha 与仓根单一事实源对齐（dist/ 旧 0.2.0 轮子为过时构建产物，重新发布时需重建）
- [x] 文档收敛为概念/操作/管理员/安全四分册 (P1-21) — 核验已在产（2026-07-20 迁移）：docs/ 四分册索引（concepts/operations/admin/developer，安全子卷在 admin/security，与审计四分册口径的偏差已文档化）；失效示例已清除（虚构的 01_basic_agent 等 8 个已删），examples/ 现存 4 个真实示例 2026-08-05 复验（py_compile 全过 + llm_provider_example 无 key 显式跳过可运行）；README 无仓库地址占位符（Quick Start 已重写不含 clone 占位）
- [ ] Visual workflow builder (延后评估)

### 2027 Q1 — Phase 2「商用就绪」(安全合规与部署运维)

#### Enterprise Security
- [x] 真 SSO (python3-saml/authlib) + SCIM 2.0 (P1-02) — 2026-08-05 挂载收官：实现早已齐备（core/sso 包 OIDC/SAML 验签/session/WebAuthn/MFA、api/scim.py RFC 7643/7644 完整 CRUD+软停用+租户绑定令牌），G3 预算 300→330 评审通过后 oidc_router（/api/v1/sso 7 路由）与 SCIM（/scim/v2 11 路由）正式挂载（APIRoute 323≤330）；UserStoreAdapter 补可用性探测（表未建显式降级内存后端，用户库建表属 P1-03）；enterprise 370 用例全绿 + 3 个挂载回归测试；SCIM 无令牌 fail-closed 503 为设计行为
- [x] 用户/租户库迁移 Postgres (P1-03) — 核验已在产：core/admin_store.py SqlUserStore/SqlTenantStore（契约一致 SQL 后端、create_all 幂等、_records 写穿透兼容、生产 sqlite 被 P1-19 fail-fast 拦截），create_user_store 按 admin_store_backend 接线，31 用例背书；2026-08-05 收尾：models/user_store（SCIM/JIT 路径）补 ensure_models_schema 幂等建表（dev sqlite 实测跨进程持久化，不再 503）；**遗留**：users（SCIM/JIT 写）与 admin_users（主认证读写）两表并存待收敛，单独立项
- [x] 审计留存/轮转/外送 SIEM; 合规报告路由挂载 (P1-04) — 核验已在产：audit_rotation（大小+日期轮转、可配留存、哈希链跨段完整）、audit_shipper startup 接线（syslog/webhook 配置驱动、无配置零开销）；2026-08-05 合规报告路由挂载：/reports/compliance 移植进已挂载的 audit.py（audit_enhanced 整挂会与 audit.py 同前缀阴影且超 G3，移植 +1 路由 324≤330），增强审计存储 provider 迁入 dependencies 共享单例；57 用例全绿（轮转/外送/增强 API/挂载回归）
- [x] 依赖治理全量重扫 + SBOM (P1-05); TLS/CSP/docs 收紧 (P1-06) — 2026-08-05 全量重扫：Python 11 漏洞 5 包（freeze 层追加 3 包）全部升级清零（click 8.4.2/cryptography 50.0.0/starlette 1.3.1/aiohttp 3.14.3/pytest 9.0.3 等，pip-audit 终扫 exit 0）；根治 pyproject 陈旧上限（cryptography<49 遗留钉死漏洞版、aiohttp 漏登记）+ lock 重编译 87→113 components + sbom.json 重建（scripts/generate_sbom.py 可复跑）+ CI 每日已在产；npm：extension 清零、frontend/mobile 残留为构建/lint 工具链大版本升级（已立项，见 security_reports/DEPENDENCY_GOVERNANCE_2026-08-05.md）；升级后全量 6998 passed/28 failed（27 固有+1 阈值 flake 单跑通过）零真实回归；TLS：deployment/tls/ 参考配置（nginx+Caddy）新增、CSP 生产收紧与 /docs 生产关闭核验已在产
- [ ] Advanced audit logging / Compliance reporting (SOC 2 差距评估期末启动, P2-01)

#### Deployment & Operations
- [x] 部署资产收敛为 Helm 单一权威; CD 真实跑通 (P1-15) — 模板已补全（14 个：api/worker/beat/DB×4/CronJob/Ingress/HPA 等）、values 重复键已修（lint 0 失败）；第二套 deployment/kubernetes/ 2026-07-20 已归档；2026-08-05 收尾：deployment/k8s/ 参考用裸清单归档（全仓无执行路径实证），脚本与文档引用全部指向 Helm；CD 按证据分级——L1（lint×2+template×3 values，各 22 manifest/10 kind）CI 每次必跑且 2026-08-05 复验通过（helm v4.2.1），L2/L3 需真实集群（前置条件清单见 deployment/CD_VERIFICATION.md，诚实标注阻塞）
- [x] readinessProbe 切 `/ready` + 优雅停机 (P1-16) — 核验已在产：根级 /ready 深探针挂载于 main.py（components 本地存储深查 + integrations 只读，停机 503 draining），清单 terminationGracePeriodSeconds 90 + preStop sleep、优雅停机 lifecycle drain 齐备；2026-08-05 补 tests/test_readiness_probe.py 回归锁定（注意：api/health.py extended_router 上有一份未挂载的第二实现，C2 保留不生效）
- [x] Qdrant 快照备份 + 恢复演练 (P1-17) — 核验已在产：backup.sh 走官方快照 API（POST /collections/{name}/snapshots + 下载）；Helm backup-cronjob（每日 02:00、retention 30d、S3 可选）经 `helm template` 渲染验证（24 资源含 CronJob）+ `helm lint` 0 失败；恢复演练 2026-07-26 已执行并归档（disaster-recovery/QDRANT_RESTORE_DRILL.md，mock 环境快照→灾难模拟→upload 恢复→points_count 一致，真实集群演练与 RTO/RPO 实测仍列为待办已诚实标注）
- [x] 真实性能基准报告 (替换占位符, P1-18) — 2026-08-05 Wave A 复测回填根目录 PERFORMANCE_BENCHMARK_REPORT.md（复测环境/复现命令/原始 JSON 齐备）：核心 API p95 40–85ms（login 591ms 为 bcrypt 设计使然）、吞吐 64–113 rps（距 1000 rps 愿景值一个数量级，首个诚实差距数据）、限流显式开启后 100 放行/50 拒绝精确执行（dev 默认关为设计行为）；样例数据报告已带作废声明；内存基线/真实 LLM 延迟/多 worker 形态列入未覆盖清单
- [x] 生产模式 sqlite/文件存储 fail-fast (P1-19) — settings `_production_storage_fail_fast` model validator 已在产：production 下 sqlite database_url / memory・jsonl memory_backend / memory trace_backend / memory・file admin_store_backend 任一命中即拒启动并一次列出全部违规项，tests/test_settings_production_guard_p119.py 11 用例背书

#### Product Surface
- [ ] Web/桌面/扩展/移动端四形态"可安装冒烟" (P1-22)
- [ ] i18n 至少第二语言 + 基础 a11y (P1-23)

### 2027+ — Phase 3「差异化竞争」(持续)

> 定位: 不与 Codex 正面拼云端规模, 围绕"可自证安全的完全自托管 Agent 框架"建立壁垒 (commercial_audit/00 第六节)。

- [ ] 完全自托管叙事做实: 无遥测默认、air-gapped 部署档、客户边界内完整本地审计链
- [ ] 证据驱动完成 (completion contracts): 任务完成附运行证据 (测试/截图/diff)
- [ ] 竞品缝隙: 移动端任务触发/监控 MVP; 断点续跑与部分结果保留
- [ ] 商业化管道: 席位 + 用量双管道、默认预算上限 + 超额 opt-in、社区版→团队版→企业版三档
- [ ] SOC 2 Type I 取得, Type II 观察期启动; 第三方渗透测试
- [ ] Kubernetes 水平扩展 / 多区域部署 (按客户需要)
- [ ] Custom model fine-tuning / 多模态能力 (研究性, 见 Research & Exploration)

## Feature Priorities

### High Priority (Phase 1, 2026 Q3)
1. 18 项 P0 修复 (部署必崩、假成功、安全断链)
2. 死代码与重复实现收敛 (以"删除"为主)
3. git/CI 重建与全量测试真实执行
4. 版本叙事统一 (本次已完成)
5. React 接线或静态控制台降级方案 + 登录 UI

### Medium Priority (Phase 2, 2026 Q4 - 2027 Q1)
1. MCP 官方 SDK 返工与真 SSO + SCIM (关键路径, 最先启动)
2. Workflow/用户库/租户库 Postgres 化 (同一迁移窗口)
3. LLM 路由、协作、工具注册表收敛
4. 部署资产 Helm 单一权威 + 真实性能基准
5. 文档四分册与四形态可安装冒烟

### Low Priority (Phase 3, 2027+)
1. SOC 2 / 渗透测试 (外部主导, Phase 2 期末启动)
2. 移动端 MVP 与断点续跑 (竞品缝隙)
3. 代码评审 agent
4. 技能自沉淀闭环
5. 计费/席位 MVP

## Breaking Changes

### Policy

- **0.4.0-alpha 开发线**: 商用修复期间 API 可能发生不兼容调整, 不做兼容性承诺
- **首个稳定 major 版本 (1.x)**: 发布后 12 个月内无破坏性变更

### Migration Guides

- Detailed migration guides for each major version
- Deprecation warnings in advance
- Extended support period for previous versions

## Deprecation Policy

- **Announcement**: 6 months notice before deprecation
- **Deprecation Period**: 6 months with warnings
- **Removal**: After deprecation period ends
- **Support**: Extended support available for enterprise customers

## Community Contributions

We welcome community contributions! Areas open for contribution:

- [ ] Documentation improvements
- [ ] Bug fixes
- [ ] Performance optimizations
- [ ] New integrations
- [ ] Example applications
- [ ] Language SDKs
- [ ] Plugin development

See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

## Feedback & Suggestions

We value your feedback! Share your ideas:

- **GitHub Issues**: Feature requests and bug reports
- **Discussions**: General discussions and ideas
- **Email**: feedback@x-agent.dev
- **Community Forum**: https://community.x-agent.dev

## Release Schedule

- **Alpha (0.4.0-alpha)**: 2026 Q3 (当前, Phase 1 止血与架构收敛)
- **Beta**: 2026 Q4 (Phase 2 完成, checklist P1 达标率 ≥80%)
- **Release Candidate**: 2027 Q1 (企业演示动线跑通: SSO 登录 → 异步任务 → 沙箱执行 → 审计外送 → Helm 部署)
- **首个稳定 major 版本 (1.x)**: 2027 年内, SOC 2 Type I 取得后评估

## Support Timeline

| Version | Release | Support Until | Status |
|---------|---------|---------------|--------|
| 0.1.x   | 未发布 (仅为 pyproject 历史标记) | — | 已被 0.3.0-alpha 取代 |
| 0.4.0-alpha | 2026-07 (开发线, 未对外发布) | 首个 Beta 发布 | 商用修复中 (当前) |
| 稳定版 1.x | 未发布 | 发布后 12 个月 | 规划中 (2027) |

## Metrics & Goals

> 以下为目标值, 非现状宣称。现状性能数据为零 (基准报告均为占位符, 见审计 13), Phase 2 将发布首个真实基准 (P1-18)。

### Performance Goals
- API response time: <100ms (p95) — 2026-08-05 实测：核心 API 达标（40–85ms），login 591ms（bcrypt 设计）
- Memory usage: <500MB baseline — 未测量（见基准报告 §5）
- Throughput: >1000 requests/second — 2026-08-05 实测 64–113 rps（单 worker mock），差距一个数量级，愿景值未达成
- Availability: 99.9% uptime

### Quality Goals
- Test coverage: >85% (全量真实执行后公布, P0-10)
- Security: Zero critical vulnerabilities (全量依赖重扫后公布, P1-05)
- Documentation: 100% API coverage
- Community: 1000+ GitHub stars by end of 2027

### Adoption Goals
- 100+ production deployments by end of 2027
- 500+ community contributors by end of 2027
- 10,000+ monthly active users by end of 2027

## Technical Debt

### Current Technical Debt (审计确认, 详见 commercial_audit/00 第 4.0 节)
- 同概念多实现并存: LLM 路由 ×5、沙箱 ×6、ToolRegistry ×3+1、协作 ×3、workflow ×2、记忆 ×7+、缓存 ×6、插件 ×6 套
- 大量写完未接线的孤岛代码 (EnhancedLLMRouter ~2,800 行、core/workflow/ 包 4,039 行、记忆融合 ~3,100 行等零生产调用)
- 测试"假绿"修复中 (skip 钩子泄漏, P0-10); 部署资产双轨 (P1-15); 文档泛滥失真 (P1-21)

### Planned Improvements
- Phase 1: 以"删除"为主的架构收敛 (死代码删除量 ≥1 万行, 重复实现收敛到声明的单一实现)
- Phase 2: MCP 官方 SDK 返工、存储层 Postgres 化、部署资产 Helm 单一权威
- Phase 3: 商业化管道与差异化能力建设

## Research & Exploration

### Areas of Interest
- Agentic AI patterns and best practices
- Distributed agent systems
- Federated learning for agents
- Ethical AI and alignment
- Agent safety and control

### Partnerships
- Academic collaborations
- Industry partnerships
- Open-source collaborations
- Research initiatives

## Questions?

For questions about the roadmap:
- **GitHub Discussions**: https://github.com/xiongpinji/X-Agent/discussions
- **Email**: roadmap@x-agent.dev
- **Community Forum**: https://community.x-agent.dev

---

**Last Updated**: 2026-08-04 (顺序污染隔离工程收官，见 DELIVERY_2026-08-02_商用交付验证报告.md §2A)
**Next Review**: 2026-10-19
