# concepts — 概念与架构

面向所有读者：理解 X-Agent 是什么、如何设计、具备哪些能力。

## 总览

- [项目总览与开发指南](./项目总览与开发指南.md) — 项目整体定位、模块协作与开发方式（中文）
- [PROJECT_SUMMARY](./PROJECT_SUMMARY.md) — 项目摘要（英文）

## architecture/ — 系统架构

- [ARCHITECTURE](./architecture/ARCHITECTURE.md) — 系统架构主文档
- [ARCHITECTURE_DESIGN](./architecture/ARCHITECTURE_DESIGN.md) — 架构设计
- [ECOSYSTEM_ARCHITECTURE](./architecture/ECOSYSTEM_ARCHITECTURE.md) — 生态架构
- [DATABASE](./architecture/DATABASE.md) — 数据层与 PostgreSQL Schema
- [CONCURRENCY_ARCHITECTURE](./architecture/CONCURRENCY_ARCHITECTURE.md) — 并发架构
- [PARALLEL_AGENTS_README](./architecture/PARALLEL_AGENTS_README.md) / [PARALLEL_TOOLS_INTEGRATION](./architecture/PARALLEL_TOOLS_INTEGRATION.md) / [PARALLEL_TOOLS_README](./architecture/PARALLEL_TOOLS_README.md) — 并行执行
- [GATEWAY_MODE](./architecture/GATEWAY_MODE.md) — 网关模式
- [CAPABILITY_ROUTER_REFACTORING](./architecture/CAPABILITY_ROUTER_REFACTORING.md) — 能力路由
- [DI_CONTAINER_IMPLEMENTATION_SUMMARY](./architecture/DI_CONTAINER_IMPLEMENTATION_SUMMARY.md) / [DI_CONTAINER_MIGRATION_GUIDE](./architecture/DI_CONTAINER_MIGRATION_GUIDE.md) — 依赖注入容器
- [ARCHITECTURE_OPTIMIZATION](./architecture/ARCHITECTURE_OPTIMIZATION.md) — 架构优化

## features/ — 功能能力

- 记忆系统: [HYBRID_MEMORY_IMPLEMENTATION](./features/HYBRID_MEMORY_IMPLEMENTATION.md) · [MEMORY_DEDUPLICATION_IMPLEMENTATION](./features/MEMORY_DEDUPLICATION_IMPLEMENTATION.md) · [MEMORY_FUSION_README](./features/MEMORY_FUSION_README.md) · [memory_v2_complete_guide](./features/memory_v2_complete_guide.md) · [CONTEXT_MANAGEMENT_FILES](./features/CONTEXT_MANAGEMENT_FILES.md)
- 工作流与审批: [WORKFLOW_IMPLEMENTATION](./features/WORKFLOW_IMPLEMENTATION.md) · [APPROVAL_GUIDE](./features/APPROVAL_GUIDE.md)
- 浏览器/文件系统: [BROWSER_AUTOMATION_README](./features/BROWSER_AUTOMATION_README.md) · [BROWSER_AUTOMATION_GUIDE](./features/BROWSER_AUTOMATION_GUIDE.md) · [FILESYSTEM_README](./features/FILESYSTEM_README.md)
- LLM 与多模态: [LLM_FRAMEWORK](./features/LLM_FRAMEWORK.md) · [MULTIMODAL_CAPABILITIES](./features/MULTIMODAL_CAPABILITIES.md) · [AI_CAPABILITIES](./features/AI_CAPABILITIES.md)
- 技能/配置/缓存: [SKILLS_SYSTEM_README](./features/SKILLS_SYSTEM_README.md) · [CONFIG_SYSTEM_README](./features/CONFIG_SYSTEM_README.md) · [CACHE_IMPLEMENTATION](./features/CACHE_IMPLEMENTATION.md)
- 其他: [ADVANCED_FEATURES](./features/ADVANCED_FEATURES.md) · [advanced-features-guide](./features/advanced-features-guide.md) · [FEATURE_ENHANCEMENTS](./features/FEATURE_ENHANCEMENTS.md) · [SANDBOX_POOLING_INTEGRATION](./features/SANDBOX_POOLING_INTEGRATION.md) · [STREAMING_INTEGRATION_GUIDE](./features/STREAMING_INTEGRATION_GUIDE.md) · [STREAMING_EXAMPLES](./features/STREAMING_EXAMPLES.md) · [FEEDBACK_SYSTEM_README](./features/FEEDBACK_SYSTEM_README.md) · [FEEDBACK_COLLECTION_SYSTEM](./features/FEEDBACK_COLLECTION_SYSTEM.md) · [UX_IMPROVEMENTS_USAGE_GUIDE](./features/UX_IMPROVEMENTS_USAGE_GUIDE.md) · [X_AGENT_STANDARD_UPGRADE](./features/X_AGENT_STANDARD_UPGRADE.md) · [X-Agent标准升级文档](./features/X-Agent标准升级文档.md)

## planning/ — 项目规划

- [01-项目规划/04-系统架构设计](./planning/01-项目规划/04-系统架构设计.md)
- [COMPETITIVE_GAP_ANALYSIS_2026](./planning/COMPETITIVE_GAP_ANALYSIS_2026.md) — 竞品差距分析
- [IDE_EXTENSION_ROADMAP](./planning/IDE_EXTENSION_ROADMAP.md) · [INTEGRATION_PLAN](./planning/INTEGRATION_PLAN.md)
- [superpowers/](./planning/superpowers/plans/) — 专项计划

## design/ — 技术设计（中文系列）

[02-技术设计](./design/02-技术设计/)：API 接口设计、Agent 核心引擎、记忆系统、错误码、多 Agent 协作、工作流编排高级用法、浏览器/桌面自动化技巧等 10 篇。

## case-studies/ · diagrams/

- [case-studies/](./case-studies/README.md) — 案例
- [diagrams/](./diagrams/) — Mermaid 架构图（architecture/ 与 workflows/）
