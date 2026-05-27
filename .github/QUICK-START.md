# CI/CD 快速启动指南

## 5分钟快速开始

### 1. 本地开发环境设置

```bash
# 克隆仓库
git clone https://github.com/your-org/xagent.git
cd xagent

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -e ".[dev,test]"

# 启动本地服务
docker-compose up -d

# 运行测试
pytest tests/ --cov=backend
```

### 2. GitHub Secrets配置 (5分钟)

1. 进入仓库 > Settings > Secrets and variables > Actions
2. 添加以下Secrets:

```
AWS_ROLE_TO_ASSUME_STAGING=arn:aws:iam::123456789:role/xagent-staging-deploy
AWS_ROLE_TO_ASSUME_PRODUCTION=arn:aws:iam::123456789:role/xagent-prod-deploy
STAGING_DEPLOY_KEY=<your-ssh-key>
PRODUCTION_DEPLOY_KEY=<your-ssh-key>
```

### 3. 创建第一个PR

```bash
# 创建feature分支
git checkout -b feature/my-feature

# 做出更改
# ...

# 提交并推送
git add .
git commit -m "feat: add new feature"
git push origin feature/my-feature

# 在GitHub上创建PR
# 等待所有检查通过
# 请求代码审查
# 合并到develop
```

### 4. 部署到Staging

```bash
# 合并到develop后自动部署
# 检查GitHub Actions日志
# 访问 https://staging.xagent.example.com
```

### 5. 发布到Production

```bash
# 创建版本标签
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# 等待部署完成
# 审批Production部署
# 验证 https://xagent.example.com
```

## 常见任务

### 运行本地测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_api.py

# 运行带覆盖率
pytest tests/ --cov=backend --cov-report=html

# 运行特定标记
pytest tests/ -m "not e2e"
```

### 代码质量检查

```bash
# Ruff linting
ruff check backend/ tests/

# Ruff格式化
ruff format backend/ tests/

# Mypy类型检查
mypy backend/

# Bandit安全检查
bandit -r backend/
```

### Docker操作

```bash
# 构建镜像
docker build -t xagent:latest .

# 运行容器
docker run -p 8000:8000 xagent:latest

# 使用Docker Compose
docker-compose up -d
docker-compose logs -f api
docker-compose down
```

### Kubernetes操作

```bash
# 查看部署状态
kubectl get deployments -n staging
kubectl get pods -n staging

# 查看日志
kubectl logs -f deployment/xagent-api -n staging

# 查看事件
kubectl describe pod <pod-name> -n staging

# 手动部署
kubectl apply -f k8s/staging/deployment.yaml

# 回滚
kubectl rollout undo deployment/xagent-api -n staging
```

## 故障排查

### 测试失败

**问题**: 本地测试通过，但GitHub Actions失败

**解决方案**:
```bash
# 检查Python版本
python --version

# 检查依赖
pip list | grep -E "pytest|ruff|mypy"

# 清理缓存
rm -rf .pytest_cache __pycache__
pip cache purge

# 重新安装
pip install -e ".[dev,test]" --force-reinstall
```

### Docker构建失败

**问题**: Docker镜像构建失败

**解决方案**:
```bash
# 检查Dockerfile
docker build --no-cache -t xagent:latest .

# 查看详细日志
docker build --progress=plain -t xagent:latest .

# 清理Docker
docker system prune -a
```

### 部署失败

**问题**: Kubernetes部署失败

**解决方案**:
```bash
# 检查Pod状态
kubectl describe pod <pod-name> -n staging

# 查看Pod日志
kubectl logs <pod-name> -n staging

# 检查事件
kubectl get events -n staging --sort-by='.lastTimestamp'

# 检查资源
kubectl top nodes
kubectl top pods -n staging
```

### 权限问题

**问题**: AWS凭证错误或权限不足

**解决方案**:
```bash
# 验证IAM角色
aws sts get-caller-identity

# 检查权限
aws iam get-role-policy --role-name xagent-staging-deploy --policy-name ...

# 更新Secrets
# Settings > Secrets and variables > Actions > 编辑相关Secret
```

## 监控和调试

### 查看GitHub Actions日志

1. 进入仓库 > Actions
2. 选择工作流运行
3. 点击失败的job
4. 展开失败的步骤查看日志

### 启用调试日志

```bash
# 在仓库Secrets中添加
ACTIONS_STEP_DEBUG=true

# 重新运行工作流
# 日志中会显示更详细的信息
```

### 本地运行工作流

```bash
# 安装act
brew install act  # macOS
# 或从 https://github.com/nektos/act 下载

# 运行工作流
act -j test

# 运行特定工作流
act -W .github/workflows/test.yml
```

## 性能优化

### 加速测试

```bash
# 并行运行测试
pytest tests/ -n auto

# 仅运行失败的测试
pytest tests/ --lf

# 运行最慢的测试
pytest tests/ --durations=10
```

### 加速构建

```bash
# 使用Docker BuildKit
DOCKER_BUILDKIT=1 docker build -t xagent:latest .

# 使用缓存
docker build --cache-from xagent:latest -t xagent:latest .
```

### 加速部署

```bash
# 使用蓝绿部署
kubectl apply -f k8s/staging/deployment-blue.yaml
kubectl apply -f k8s/staging/deployment-green.yaml

# 使用金丝雀部署
kubectl apply -f k8s/staging/deployment-canary.yaml
```

## 最佳实践检查清单

### 提交代码前

- [ ] 本地运行所有测试: `pytest tests/`
- [ ] 运行代码质量检查: `ruff check .`
- [ ] 运行类型检查: `mypy backend/`
- [ ] 运行安全扫描: `bandit -r backend/`
- [ ] 提交信息清晰有意义

### 创建PR前

- [ ] 从最新的develop分支创建feature分支
- [ ] 提供清晰的PR描述
- [ ] 链接相关的Issue
- [ ] 添加测试用例
- [ ] 更新文档

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
- [ ] 验证部署

## 有用的命令

### Git命令

```bash
# 查看分支
git branch -a

# 创建并切换分支
git checkout -b feature/my-feature

# 查看提交历史
git log --oneline -10

# 查看更改
git diff

# 暂存更改
git stash

# 恢复暂存
git stash pop

# 重置更改
git reset --hard HEAD
```

### Docker命令

```bash
# 列出镜像
docker images

# 列出容器
docker ps -a

# 删除镜像
docker rmi image-id

# 删除容器
docker rm container-id

# 查看日志
docker logs -f container-id

# 进入容器
docker exec -it container-id bash
```

### Kubernetes命令

```bash
# 列出资源
kubectl get pods -n staging
kubectl get services -n staging
kubectl get deployments -n staging

# 描述资源
kubectl describe pod pod-name -n staging

# 查看日志
kubectl logs pod-name -n staging
kubectl logs -f deployment/xagent-api -n staging

# 执行命令
kubectl exec -it pod-name -n staging -- bash

# 删除资源
kubectl delete pod pod-name -n staging

# 应用配置
kubectl apply -f deployment.yaml

# 回滚
kubectl rollout undo deployment/xagent-api -n staging
```

## 获取帮助

### 文档

- [CI/CD配置指南](./CI-CD-GUIDE.md)
- [GitHub Actions最佳实践](./GITHUB-ACTIONS-BEST-PRACTICES.md)
- [部署配置指南](./DEPLOYMENT-GUIDE.md)
- [CI/CD流程图](./CI-CD-FLOWCHARTS.md)

### 联系方式

- 问题: 提交GitHub Issue
- 讨论: 使用GitHub Discussions
- 紧急: 联系DevOps团队

### 外部资源

- [GitHub Actions文档](https://docs.github.com/en/actions)
- [Docker文档](https://docs.docker.com/)
- [Kubernetes文档](https://kubernetes.io/docs/)
- [Pytest文档](https://docs.pytest.org/)

## 下一步

1. 完成本地开发环境设置
2. 配置GitHub Secrets
3. 创建第一个feature分支
4. 提交PR并观察CI/CD流程
5. 合并到develop并验证Staging部署
6. 创建版本标签并验证Production部署

祝你使用愉快！
