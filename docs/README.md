# X-Agent 文档总索引

本目录是 X-Agent 的完整文档中心。全部文档按读者角色收敛为四个分册：

| 分册 | 读者 | 内容 |
|------|------|------|
| [concepts/](./concepts/README.md) | 所有人 | 概念、架构、功能设计、项目规划 |
| [operations/](./operations/README.md) | 运维 / 部署工程师 | 安装、配置、部署、监控、故障排除、发布 |
| [admin/](./admin/README.md) | 管理员 / 安全合规 | 安全、SSO、租户与企业功能、订阅计费、审计 |
| [developer/](./developer/README.md) | 开发者 / 贡献者 | API、SDK、插件开发、教程、贡献指南、历史报告 |

## 快速入口

- **项目概览**: [根目录 README](../README.md) · [项目总览与开发指南](./concepts/项目总览与开发指南.md) · [PROJECT_SUMMARY](./concepts/PROJECT_SUMMARY.md)
- **安装与快速开始**: [INSTALL](./operations/setup/INSTALL.md) · [QUICKSTART](./operations/setup/QUICKSTART.md)
- **部署**: [DEPLOYMENT](./operations/deployment/DEPLOYMENT.md) · [商用部署 Runbook](./operations/deployment/COMMERCIAL_DEPLOYMENT_RUNBOOK.md) · [发布就绪清单](./operations/deployment/RELEASE_READINESS.md)
- **API 参考**: [API 完整参考](./developer/api/API.md) · [错误码](./developer/api/API_ERROR_CODES.md) · [OpenAPI Schema](./developer/api/openapi.json)
- **安全**: [安全指南](./admin/security/SECURITY_GUIDE.md) · [SSO 配置](./admin/sso/SSO_CONFIGURATION.md)
- **贡献**: [CONTRIBUTING](../CONTRIBUTING.md) · [开发者指南](./developer/DEVELOPER_GUIDE.md)
- **示例代码**: [examples/ 目录](../examples/README.md)

## 分册结构

```
docs/
├── README.md                 # 本索引
├── concepts/                 # 概念与架构
│   ├── architecture/         # 系统架构、数据层、并发模型
│   ├── features/             # 记忆/工作流/浏览器/技能/多模态等功能说明
│   ├── planning/             # 项目规划、竞品分析、路线图
│   ├── design/               # 技术设计文档(中文系列)
│   ├── case-studies/         # 案例
│   └── diagrams/             # Mermaid 架构图
├── operations/               # 安装/部署/运维
│   ├── setup/                # 安装、快速开始、配置
│   ├── deployment/           # 部署、发布、升级、回滚、灾备、CI/CD
│   ├── monitoring/           # 监控与性能
│   └── support/              # 故障排除、FAQ、客户支持
├── admin/                    # 安全/租户/审计
│   ├── security/             # 安全指南与决策
│   ├── sso/                  # 单点登录(OIDC/SAML/SCIM)
│   ├── enterprise/           # 企业功能、租户、合作伙伴
│   ├── subscription/         # 订阅与计费
│   └── audit/                # 审计与整改
└── developer/                # API/SDK/贡献
    ├── api/                  # REST API 参考与集成指南
    ├── sdk/                  # SDK、CLI、示例说明
    ├── plugins/              # 插件、MCP、技能市场开发
    ├── tutorials/            # 教程、用户手册、培训材料
    ├── best-practices/       # 最佳实践
    ├── contributing/         # 贡献、测试、文档规范
    ├── reference/            # 速查表
    ├── specs/                # 规格说明
    └── reports/              # 历史开发报告(归档)
```

## 文档迁移说明

2026-07-20 文档收敛(P1-21): 原散落在仓库根目录与 `docs/` 平铺的 320+ 篇文档已按四分册归类移动，受影响的对内链接已批量修复。历史文档索引(INDEX、DOCUMENTATION_INDEX 等)保留在 [developer/reports/](./developer/reports/) 仅供参考，以本索引为准。
