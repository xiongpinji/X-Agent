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
- [ ] Agent-to-agent communication protocol (协作包收敛, P1-09)
- [ ] Task delegation and load balancing
- [ ] Capability matching and discovery
- [ ] PROCESS/CONTAINER 隔离落地或删除参数 (P1-09)

#### Memory & Reasoning
- [ ] 真实嵌入服务替换哈希伪嵌入; 去重接通主存储 (P1-13)
- [ ] 上下文管理接入 Agent 主循环 (token 级压缩 + 会话恢复, P1-14)
- [ ] 技能系统接线或删除; 插件系统接线或归档 (P1-11/12)
- [ ] Chain-of-thought reasoning / Multi-step planning (延后至 Phase 3 评估)

#### Workflow & Developer Experience
- [ ] Workflow 存储迁移 Postgres + cron 调度 + 并行分支 (P1-07)
- [ ] CLI 循环导入修复; SDK 补打包元数据 (P1-22)
- [ ] 文档收敛为概念/操作/管理员/安全四分册 (P1-21)
- [ ] Visual workflow builder (延后评估)

### 2027 Q1 — Phase 2「商用就绪」(安全合规与部署运维)

#### Enterprise Security
- [ ] 真 SSO (python3-saml/authlib) + SCIM 2.0 (P1-02)
- [ ] 用户/租户库迁移 Postgres (P1-03)
- [ ] 审计留存/轮转/外送 SIEM; 合规报告路由挂载 (P1-04)
- [ ] 依赖治理全量重扫 + SBOM (P1-05); TLS/CSP/docs 收紧 (P1-06)
- [ ] Advanced audit logging / Compliance reporting (SOC 2 差距评估期末启动, P2-01)

#### Deployment & Operations
- [ ] 部署资产收敛为 Helm 单一权威; CD 真实跑通 (P1-15)
- [ ] readinessProbe 切 `/ready` + 优雅停机 (P1-16)
- [ ] Qdrant 快照备份 + 恢复演练 (P1-17)
- [ ] 真实性能基准报告 (替换占位符, P1-18)
- [ ] 生产模式 sqlite/文件存储 fail-fast (P1-19)

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
- API response time: <100ms (p95)
- Memory usage: <500MB baseline
- Throughput: >1000 requests/second
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
