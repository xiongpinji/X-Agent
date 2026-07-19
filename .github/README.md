# X-Agent CI/CD 配置文档

欢迎使用X-Agent项目的完整CI/CD流水线配置！本文档帮助你快速了解和使用这个企业级的自动化部署系统。

## 📋 文档导航

### 快速开始
- **[快速启动指南](./QUICK-START.md)** - 5分钟快速开始，包含常见任务和命令

### 详细指南
- **[CI/CD配置指南](./CI-CD-GUIDE.md)** - 完整的流水线架构和各个workflow的详细说明
- **[部署配置指南](./DEPLOYMENT-GUIDE.md)** - 环境变量、Secrets、Kubernetes和Docker配置
- **[GitHub Actions最佳实践](./GITHUB-ACTIONS-BEST-PRACTICES.md)** - 工作流设计、安全性、性能优化

### 可视化资源
- **[CI/CD流程图](./CI-CD-FLOWCHARTS.md)** - 完整的流程图、架构图和时间线
- **[配置总结](./CI-CD-SUMMARY.md)** - 所有创建文件的清单和验证检查

## 🚀 快速开始 (5分钟)

### 1. 本地开发环境

```bash
# 克隆仓库
git clone https://github.com/your-org/xagent.git
cd xagent

# 安装依赖
pip install -e ".[dev,test]"

# 运行测试
pytest tests/ --cov=backend
```

### 2. 配置GitHub Secrets

进入仓库 > Settings > Secrets and variables > Actions，添加以下Secrets:

```
AWS_ROLE_TO_ASSUME_STAGING
AWS_ROLE_TO_ASSUME_PRODUCTION
STAGING_DEPLOY_KEY
PRODUCTION_DEPLOY_KEY
```

详见 [部署配置指南](./DEPLOYMENT-GUIDE.md#github-secrets设置)

### 3. 创建第一个PR

```bash
git checkout -b feature/my-feature
# 做出更改
git push origin feature/my-feature
# 在GitHub上创建PR
```

## 📦 包含的Workflows

### 1. 测试套件 (test.yml)
- 多Python版本测试 (3.11, 3.12)
- 单元测试、集成测试、契约测试
- 代码覆盖率报告
- 性能基准测试

**触发**: Push到main/develop或Pull Request

### 2. 代码质量 (lint.yml)
- Ruff代码风格检查
- Mypy类型检查
- 圈复杂度分析
- 可维护性指数

**触发**: Push到main/develop或Pull Request

### 3. 安全扫描 (security.yml)
- Bandit SAST扫描
- 依赖漏洞检查
- 密钥泄露检测
- Semgrep代码分析

**触发**: Push、Pull Request、每日定时扫描

### 4. 构建和部署 (deploy.yml)
- Docker多平台构建
- 镜像推送到GHCR
- Trivy镜像扫描
- Staging自动部署
- Production审批部署
- 自动回滚

**触发**: Push到main/develop、版本标签、手动触发

### 5. 分支保护 (branch-protection.yml)
- Main分支: 2个审查 + 代码所有者
- Develop分支: 1个审查
- 必需检查强制
- 线性历史要求

**触发**: 手动触发

## 🔐 安全性

### 分支保护规则

| 分支 | 审查数 | 代码所有者 | 线性历史 | 强制推送 |
|------|--------|----------|---------|---------|
| main | 2 | ✓ | ✓ | ✗ |
| develop | 1 | ✗ | ✗ | ✗ |

### 必需的检查

**Main分支**:
- unit-tests (3.11, 3.12)
- integration-tests
- contract-tests
- Lint with Ruff
- Type Check with Mypy
- Bandit Security Scan
- Dependency Vulnerability Scan

**Develop分支**:
- unit-tests (3.11, 3.12)
- integration-tests
- Lint with Ruff
- Type Check with Mypy
- Bandit Security Scan

## 📊 性能指标

### 预期执行时间

| 阶段 | 耗时 |
|------|------|
| 测试套件 | 5-8分钟 |
| 代码质量 | 2-3分钟 |
| 安全扫描 | 3-5分钟 |
| Docker构建 | 3-5分钟 |
| 镜像扫描 | 1-2分钟 |
| 部署 | 2-3分钟 |
| **总计** | **18-29分钟** |

### 资源使用

- GitHub Actions: 30-50分钟/PR
- 存储空间: 100-200MB/月
- Docker镜像: 500-800MB
- 并发工作流: 最多5个

## 🛠️ 常见任务

### 运行本地测试

```bash
# 所有测试
pytest tests/

# 特定测试
pytest tests/test_api.py

# 带覆盖率
pytest tests/ --cov=backend --cov-report=html

# 特定标记
pytest tests/ -m "not e2e"
```

### 代码质量检查

```bash
# Ruff检查
ruff check backend/ tests/

# 类型检查
mypy backend/

# 安全检查
bandit -r backend/
```

### Docker操作

```bash
# 构建镜像
docker build -t xagent:latest .

# 运行容器
docker run -p 8000:8000 xagent:latest

# Docker Compose
docker-compose up -d
```

### Kubernetes操作

```bash
# 查看部署
kubectl get deployments -n staging

# 查看日志
kubectl logs -f deployment/xagent-api -n staging

# 应用配置
kubectl apply -f k8s/staging/deployment.yaml

# 回滚
kubectl rollout undo deployment/xagent-api -n staging
```

详见 [快速启动指南](./QUICK-START.md)

## 🔍 故障排查

### 测试失败

```bash
# 清理缓存
rm -rf .pytest_cache __pycache__
pip cache purge

# 重新安装
pip install -e ".[dev,test]" --force-reinstall

# 运行测试
pytest tests/ -v
```

### Docker构建失败

```bash
# 无缓存构建
docker build --no-cache -t xagent:latest .

# 查看详细日志
docker build --progress=plain -t xagent:latest .
```

### 部署失败

```bash
# 检查Pod状态
kubectl describe pod <pod-name> -n staging

# 查看日志
kubectl logs <pod-name> -n staging

# 检查事件
kubectl get events -n staging --sort-by='.lastTimestamp'
```

详见 [快速启动指南 - 故障排查](./QUICK-START.md#故障排查)

## 📈 监控和调试

### 查看GitHub Actions日志

1. 进入仓库 > Actions
2. 选择工作流运行
3. 点击失败的job
4. 展开失败的步骤

### 启用调试日志

在仓库Secrets中添加:
```
ACTIONS_STEP_DEBUG=true
```

### 本地运行工作流

```bash
# 安装act
brew install act

# 运行工作流
act -j test
```

## 💡 最佳实践

### 提交代码前

- [ ] 本地运行所有测试
- [ ] 运行代码质量检查
- [ ] 运行类型检查
- [ ] 运行安全扫描

### 创建PR前

- [ ] 从最新develop创建分支
- [ ] 提供清晰的PR描述
- [ ] 链接相关Issue
- [ ] 添加测试用例

### 合并PR前

- [ ] 所有检查通过
- [ ] 至少1个代码审查
- [ ] 没有冲突
- [ ] 覆盖率达到目标

### 发布前

- [ ] 更新版本号
- [ ] 更新CHANGELOG
- [ ] 创建Release Notes
- [ ] 标记版本

详见 [GitHub Actions最佳实践](./GITHUB-ACTIONS-BEST-PRACTICES.md)

## 🔧 配置和自定义

### 修改工作流

1. 编辑 `.github/workflows/*.yml` 文件
2. 提交更改到feature分支
3. 创建PR进行审查
4. 合并后自动生效

### 添加新的检查

1. 在相应workflow中添加步骤
2. 更新branch-protection.yml中的必需检查
3. 在本地测试workflow

### 集成第三方服务

- Codecov: 代码覆盖率
- Snyk: 依赖扫描
- SonarQube: 代码质量
- Datadog: 性能监控

详见 [CI/CD配置指南 - 扩展和定制](./CI-CD-GUIDE.md#扩展和定制)

## 📚 完整文档

| 文档 | 用途 |
|------|------|
| [快速启动指南](./QUICK-START.md) | 5分钟快速开始 |
| [CI/CD配置指南](./CI-CD-GUIDE.md) | 完整配置说明 |
| [部署配置指南](./DEPLOYMENT-GUIDE.md) | 环境和部署配置 |
| [GitHub Actions最佳实践](./GITHUB-ACTIONS-BEST-PRACTICES.md) | 工作流最佳实践 |
| [CI/CD流程图](./CI-CD-FLOWCHARTS.md) | 流程图和架构 |
| [配置总结](./CI-CD-SUMMARY.md) | 文件清单和验证 |

## 🎯 下一步

### 立即执行 (第1天)

1. [ ] 配置GitHub Secrets
2. [ ] 运行branch-protection workflow
3. [ ] 验证分支保护规则
4. [ ] 测试第一个PR

### 短期 (第1周)

1. [ ] 配置AWS IAM角色
2. [ ] 设置Kubernetes集群
3. [ ] 配置监控和告警
4. [ ] 进行首次Staging部署

### 中期 (第2-4周)

1. [ ] 优化工作流性能
2. [ ] 配置自托管Runner (可选)
3. [ ] 集成第三方服务
4. [ ] 进行首次Production部署

## 📞 获取帮助

### 文档

- 查看相关的详细指南
- 检查故障排查部分
- 查看常见问题解答

### 日志

- 查看GitHub Actions日志
- 启用调试日志
- 本地运行工作流

### 联系

- 提交GitHub Issue
- 使用GitHub Discussions
- 联系DevOps团队

## 🔗 外部资源

- [GitHub Actions官方文档](https://docs.github.com/en/actions)
- [Docker文档](https://docs.docker.com/)
- [Kubernetes文档](https://kubernetes.io/docs/)
- [Pytest文档](https://docs.pytest.org/)
- [Ruff文档](https://docs.astral.sh/ruff/)

## 📝 版本信息

- **配置版本**: 1.0.0
- **创建日期**: 2026-05-27
- **最后更新**: 2026-05-27
- **Python版本**: 3.11+
- **GitHub Actions**: 最新版本

## 📄 许可证

本CI/CD配置遵循X-Agent项目的许可证。

---

**开始使用**: 查看 [快速启动指南](./QUICK-START.md)

**需要帮助?** 查看 [CI/CD配置指南](./CI-CD-GUIDE.md) 或 [故障排查](./QUICK-START.md#故障排查)
