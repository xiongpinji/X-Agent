# X-Agent CI/CD 流水线配置指南

## 概述

本文档描述了X-Agent项目的完整CI/CD流水线配置，包括自动化测试、代码质量检查、安全扫描和部署流程。

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                     GitHub Events                               │
│  (Push, Pull Request, Tags, Schedule, Manual Dispatch)          │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
    ┌────────┐      ┌────────┐      ┌────────┐
    │  Test  │      │  Lint  │      │Security│
    │ Suite  │      │ & QA   │      │ Scan   │
    └────────┘      └────────┘      └────────┘
        │                │                │
        └────────────────┼────────────────┘
                         │
                    ┌────▼────┐
                    │  Build   │
                    │  Docker  │
                    └────┬─────┘
                         │
                    ┌────▼────────┐
                    │ Scan Image  │
                    │ (Trivy)     │
                    └────┬────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
    ┌────────┐      ┌────────┐      ┌────────┐
    │Staging │      │  Prod  │      │Rollback│
    │Deploy  │      │ Deploy │      │(if fail)
    └────────┘      └────────┘      └────────┘
```

## Workflow 详细说明

### 1. Test Suite (test.yml)

**触发条件**: Push到main/develop分支或Pull Request

**包含的测试**:

- **Unit Tests** (Python 3.11, 3.12)
  - 运行pytest单元测试
  - 生成代码覆盖率报告
  - 上传到Codecov
  - 支持多Python版本矩阵测试

- **Integration Tests**
  - 测试组件间的集成
  - 使用真实的PostgreSQL、Redis、Qdrant服务

- **Contract Tests**
  - 验证API契约
  - 确保接口兼容性

- **Performance Tests** (仅在main分支push时运行)
  - 性能基准测试
  - 使用Locust进行负载测试

**依赖服务**:
- PostgreSQL 16
- Redis 7
- Qdrant (向量数据库)

**输出**:
- 代码覆盖率报告 (HTML + XML)
- 测试结果
- 性能基准数据

### 2. Lint & Code Quality (lint.yml)

**触发条件**: Push到main/develop分支或Pull Request

**检查项**:

- **Ruff Linting**
  - 代码风格检查
  - 导入排序
  - 代码格式验证

- **Mypy Type Checking**
  - 静态类型检查
  - 生成JUnit XML报告

- **Complexity Analysis**
  - 圈复杂度检查 (Radon)
  - 可维护性指数计算

**输出**:
- Mypy报告
- 复杂度报告

### 3. Security Scan (security.yml)

**触发条件**: Push、Pull Request、每日定时扫描(UTC 2AM)

**扫描类型**:

- **Bandit**
  - Python代码安全扫描
  - 检测常见安全问题

- **Dependency Vulnerability Scan**
  - pip-audit: 依赖漏洞检查
  - safety: 已知安全问题检查

- **Secret Detection**
  - TruffleHog: 密钥泄露检测
  - 扫描整个代码库

- **SAST (Static Application Security Testing)**
  - Semgrep: 代码模式分析
  - 安全审计规则集

**输出**:
- Bandit报告 (JSON)
- 依赖扫描报告
- Semgrep报告
- 安全总结

### 4. Build & Deploy (deploy.yml)

**触发条件**: 
- Push到main/develop分支
- 创建版本标签 (v*)
- 手动触发 (workflow_dispatch)

**构建阶段**:

1. **Docker Build**
   - 使用Docker Buildx多平台构建
   - 推送到GitHub Container Registry (ghcr.io)
   - 自动标签管理:
     - 分支标签 (main, develop)
     - 语义版本标签 (v1.0.0)
     - SHA标签 (git commit hash)
     - Latest标签 (main分支)

2. **Image Scanning**
   - Trivy漏洞扫描
   - 生成SARIF报告
   - 上传到GitHub Security标签页

**部署阶段**:

- **Staging部署** (develop分支)
  - 自动部署到staging环境
  - 运行烟雾测试
  - 发送部署通知

- **Production部署** (版本标签)
  - 需要环境审批
  - 部署到production环境
  - 运行健康检查
  - 创建GitHub Release
  - 失败时自动回滚

**环境变量**:
```
REGISTRY: ghcr.io
IMAGE_NAME: ${{ github.repository }}
```

**Secrets要求**:
- `AWS_ROLE_TO_ASSUME_STAGING`: AWS IAM角色 (Staging)
- `AWS_ROLE_TO_ASSUME_PRODUCTION`: AWS IAM角色 (Production)
- `STAGING_DEPLOY_KEY`: Staging部署密钥
- `PRODUCTION_DEPLOY_KEY`: Production部署密钥

### 5. Branch Protection (branch-protection.yml)

**配置规则**:

#### Main分支
- 需要通过所有必需检查
- 需要2个代码审查
- 需要代码所有者审查
- 禁止强制推送
- 禁止删除分支
- 需要线性历史
- 需要对话解决

#### Develop分支
- 需要通过必需检查
- 需要1个代码审查
- 禁止强制推送
- 禁止删除分支
- 需要对话解决

## 必需的检查 (Required Status Checks)

### Main分支
```
- unit-tests (3.11)
- unit-tests (3.12)
- integration-tests
- contract-tests
- Lint with Ruff
- Type Check with Mypy
- Bandit Security Scan
- Dependency Vulnerability Scan
```

### Develop分支
```
- unit-tests (3.11)
- unit-tests (3.12)
- integration-tests
- Lint with Ruff
- Type Check with Mypy
- Bandit Security Scan
```

## 环境配置

### 本地开发环境

1. **安装依赖**:
```bash
pip install -e ".[dev,test]"
```

2. **运行测试**:
```bash
pytest tests/ --cov=backend --cov-report=html
```

3. **代码质量检查**:
```bash
ruff check backend/ tests/
ruff format backend/ tests/
mypy backend/
```

4. **安全扫描**:
```bash
bandit -r backend/
pip-audit
```

### GitHub Actions Secrets

需要在GitHub仓库设置中配置以下Secrets:

| Secret名称 | 说明 | 示例 |
|-----------|------|------|
| `AWS_ROLE_TO_ASSUME_STAGING` | Staging环境AWS IAM角色ARN | `arn:aws:iam::123456789:role/staging-deploy` |
| `AWS_ROLE_TO_ASSUME_PRODUCTION` | Production环境AWS IAM角色ARN | `arn:aws:iam::123456789:role/prod-deploy` |
| `STAGING_DEPLOY_KEY` | Staging部署密钥 | (SSH密钥或API令牌) |
| `PRODUCTION_DEPLOY_KEY` | Production部署密钥 | (SSH密钥或API令牌) |
| `CODECOV_TOKEN` | Codecov上传令牌 | (可选，用于私有仓库) |

## 工作流触发规则

| Workflow | 触发条件 | 分支 |
|----------|---------|------|
| test.yml | Push / PR | main, develop |
| lint.yml | Push / PR | main, develop |
| security.yml | Push / PR / 每日2AM | main, develop |
| deploy.yml | Push / 标签 / 手动 | main, develop, v* |
| branch-protection.yml | 手动触发 | - |

## 最佳实践

### 1. 代码提交

- 在本地运行所有检查后再提交
- 使用有意义的提交信息
- 保持提交原子性

### 2. Pull Request

- 提供清晰的PR描述
- 链接相关的Issue
- 等待所有检查通过
- 至少需要1-2个审查

### 3. 版本发布

- 使用语义版本 (v1.0.0)
- 创建Release Notes
- 标签会自动触发Production部署

### 4. 监控和告警

- 定期检查Codecov覆盖率
- 监控安全扫描结果
- 跟踪性能基准变化
- 设置GitHub通知

## 故障排查

### 测试失败

1. 检查本地环境是否一致
2. 查看GitHub Actions日志
3. 验证依赖服务是否正常
4. 检查环境变量配置

### 部署失败

1. 检查Docker镜像构建日志
2. 验证AWS凭证和权限
3. 检查部署脚本
4. 查看回滚日志

### 安全扫描告警

1. 审查扫描报告
2. 评估风险等级
3. 修复或豁免问题
4. 更新依赖版本

## 性能优化

### 缓存策略

- 使用GitHub Actions缓存加速pip安装
- Docker层缓存优化构建速度
- 并发运行独立的workflow

### 并发控制

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

这确保同一分支的旧workflow被新的取消。

## 扩展和定制

### 添加新的检查

1. 在相应的workflow中添加新步骤
2. 更新branch-protection.yml中的必需检查列表
3. 在本地测试workflow

### 集成第三方服务

- Codecov: 代码覆盖率
- Snyk: 依赖扫描
- SonarQube: 代码质量
- Datadog: 性能监控

## 参考资源

- [GitHub Actions文档](https://docs.github.com/en/actions)
- [Ruff文档](https://docs.astral.sh/ruff/)
- [Pytest文档](https://docs.pytest.org/)
- [Docker文档](https://docs.docker.com/)
- [Kubernetes文档](https://kubernetes.io/docs/)

## 联系和支持

如有问题或建议，请提交Issue或联系DevOps团队。
