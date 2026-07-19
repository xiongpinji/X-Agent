# X-Agent 容量规划与发布流程

## 容量规划

### 1. 资源使用分析

#### 单实例容量指标

| 指标 | 开发环境 | 生产环境 |
|------|---------|---------|
| CPU | 1核 | 4核 |
| 内存 | 2GB | 8GB |
| 磁盘 | 10GB | 100GB |
| 并发连接 | 50 | 1000 |
| QPS | 10 | 500 |
| 数据库连接 | 5 | 20 |

#### 依赖服务容量

| 服务 | 开发环境 | 生产环境 | 备注 |
|------|---------|---------|------|
| PostgreSQL | 1GB内存 | 16GB内存 | 主从复制 |
| Redis | 512MB | 4GB | 集群模式 |
| Qdrant | 2GB | 20GB | 副本数=3 |
| Elasticsearch | 1GB | 8GB | 分片数=5 |

### 2. 扩展策略

#### 水平扩展

```yaml
# Kubernetes HPA配置
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: xagent-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: xagent-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
```

#### 垂直扩展

```bash
# 更新资源请求和限制
kubectl set resources deployment xagent-api \
  --requests=cpu=2,memory=4Gi \
  --limits=cpu=4,memory=8Gi
```

### 3. 性能基准

#### API性能基准

```
正常负载 (100 QPS):
- P50 延迟: 50ms
- P95 延迟: 200ms
- P99 延迟: 500ms
- 错误率: < 0.1%

峰值负载 (500 QPS):
- P50 延迟: 100ms
- P95 延迟: 500ms
- P99 延迟: 1000ms
- 错误率: < 1%
```

#### 数据库性能基准

```
查询性能:
- 简单查询: < 10ms
- 复杂查询: < 100ms
- 批量操作: < 1s

连接池:
- 活跃连接: < 80%
- 等待连接: < 5%
```

### 4. 成本优化

#### 资源优化建议

1. **CPU优化**
   - 启用CPU限流
   - 使用资源请求和限制
   - 定期分析CPU使用模式

2. **内存优化**
   - 启用内存缓存
   - 定期清理过期数据
   - 监控内存泄漏

3. **存储优化**
   - 启用数据压缩
   - 定期归档旧数据
   - 使用分层存储

#### 成本预估

```
月度成本估算 (AWS):

计算:
- 3个 t3.xlarge 实例: $300/月
- 自动扩展到10个: $1000/月

存储:
- PostgreSQL (100GB): $50/月
- Redis (4GB): $20/月
- Qdrant (20GB): $30/月
- EBS (500GB): $50/月

网络:
- 数据传输: $50/月

监控:
- CloudWatch: $20/月

总计: ~$1500-2000/月
```

---

## 发布流程

### 1. 版本管理

#### 版本号规范

遵循 Semantic Versioning (SemVer):
- MAJOR.MINOR.PATCH (例如: 1.2.3)
- MAJOR: 不兼容的API变更
- MINOR: 向后兼容的功能添加
- PATCH: 向后兼容的bug修复

#### 发布分支

```
main (生产)
  ↑
  ├─ release/v1.2.0 (发布分支)
  │   ↑
  │   └─ hotfix/v1.2.1 (紧急修复)
  │
develop (开发)
  ↑
  ├─ feature/xxx (功能分支)
  ├─ bugfix/xxx (修复分支)
  └─ refactor/xxx (重构分支)
```

### 2. 发布检查清单

#### 代码审查

- [ ] 所有代码已通过代码审查
- [ ] 没有TODO或FIXME注释
- [ ] 所有测试通过
- [ ] 代码覆盖率 >= 80%
- [ ] 没有安全漏洞

#### 文档检查

- [ ] CHANGELOG已更新
- [ ] API文档已更新
- [ ] 部署指南已更新
- [ ] 配置文档已更新
- [ ] 已添加迁移指南（如需要）

#### 性能检查

- [ ] 性能测试通过
- [ ] 没有性能回归
- [ ] 数据库迁移已验证
- [ ] 缓存策略已验证

#### 安全检查

- [ ] 安全审计通过
- [ ] 依赖漏洞扫描通过
- [ ] 敏感信息已移除
- [ ] 访问控制已验证

### 3. 发布流程

#### 阶段1: 准备 (1-2天)

```bash
# 1. 创建发布分支
git checkout -b release/v1.2.0 develop

# 2. 更新版本号
sed -i 's/version = "1.1.0"/version = "1.2.0"/' pyproject.toml

# 3. 更新CHANGELOG
# 编辑 CHANGELOG.md

# 4. 提交更改
git add .
git commit -m "chore: prepare release v1.2.0"

# 5. 创建PR进行审查
git push origin release/v1.2.0
```

#### 阶段2: 测试 (1-2天)

```bash
# 1. 运行完整测试套件
pytest tests/ -v --cov=backend

# 2. 运行集成测试
pytest tests/integration/ -v

# 3. 运行性能测试
locust -f tests/performance/locustfile.py --headless -u 100 -r 10 -t 5m

# 4. 运行安全扫描
bandit -r backend
pip audit

# 5. 构建Docker镜像
docker build -t xagent:v1.2.0 .

# 6. 在staging环境测试
kubectl set image deployment/xagent-api-staging xagent=xagent:v1.2.0
```

#### 阶段3: 发布 (1天)

```bash
# 1. 合并到main分支
git checkout main
git pull origin main
git merge --no-ff release/v1.2.0

# 2. 创建标签
git tag -a v1.2.0 -m "Release version 1.2.0"
git push origin main
git push origin v1.2.0

# 3. 推送Docker镜像
docker tag xagent:v1.2.0 ghcr.io/your-org/xagent:v1.2.0
docker tag xagent:v1.2.0 ghcr.io/your-org/xagent:latest
docker push ghcr.io/your-org/xagent:v1.2.0
docker push ghcr.io/your-org/xagent:latest

# 4. 创建GitHub Release
gh release create v1.2.0 --title "Release v1.2.0" --notes-file CHANGELOG.md

# 5. 部署到生产环境
kubectl set image deployment/xagent-api xagent=ghcr.io/your-org/xagent:v1.2.0
kubectl rollout status deployment/xagent-api
```

#### 阶段4: 验证 (1天)

```bash
# 1. 验证部署
curl https://api.xagent.example.com/health

# 2. 运行烟雾测试
pytest tests/smoke/ -v

# 3. 监控错误率
curl http://prometheus:9090/api/v1/query?query=rate(xagent_errors_total[5m])

# 4. 检查性能指标
curl http://prometheus:9090/api/v1/query?query=xagent_http_request_duration_seconds

# 5. 验证日志
kubectl logs -n xagent -l app=xagent-api --tail=100
```

### 4. 灰度发布

#### 金丝雀发布

```yaml
# Istio VirtualService配置
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: xagent-api
spec:
  hosts:
  - xagent-api
  http:
  - match:
    - uri:
        prefix: /
    route:
    - destination:
        host: xagent-api
        subset: v1
      weight: 90
    - destination:
        host: xagent-api
        subset: v2
      weight: 10
```

#### 蓝绿部署

```bash
# 1. 部署新版本到绿色环境
kubectl apply -f k8s/deployment-green.yml

# 2. 运行测试
pytest tests/smoke/ -v --target=green

# 3. 切换流量
kubectl patch service xagent-api -p '{"spec":{"selector":{"version":"green"}}}'

# 4. 监控
kubectl logs -n xagent -l app=xagent-api,version=green

# 5. 回滚（如需要）
kubectl patch service xagent-api -p '{"spec":{"selector":{"version":"blue"}}}'
```

### 5. 回滚流程

#### 自动回滚

```bash
# 监控错误率，如果超过阈值则自动回滚
kubectl rollout undo deployment/xagent-api
```

#### 手动回滚

```bash
# 1. 查看部署历史
kubectl rollout history deployment/xagent-api

# 2. 回滚到上一个版本
kubectl rollout undo deployment/xagent-api

# 3. 回滚到特定版本
kubectl rollout undo deployment/xagent-api --to-revision=2

# 4. 验证回滚
kubectl rollout status deployment/xagent-api
```

### 6. 发布后检查

#### 监控指标

```
关键指标:
- 错误率: < 0.1%
- P95延迟: < 500ms
- 可用性: > 99.9%
- 数据库连接: < 80%
- 内存使用: < 80%
```

#### 用户反馈

- 收集用户反馈
- 监控支持工单
- 分析使用模式
- 识别问题

#### 文档更新

- 更新用户文档
- 发布发行说明
- 更新API文档
- 发送通知邮件

---

## 应急发布

### 紧急修复流程

```bash
# 1. 从main创建hotfix分支
git checkout -b hotfix/v1.2.1 main

# 2. 修复问题
# 编辑文件...

# 3. 更新版本号
sed -i 's/version = "1.2.0"/version = "1.2.1"/' pyproject.toml

# 4. 提交更改
git add .
git commit -m "fix: critical bug in agent execution"

# 5. 合并到main和develop
git checkout main
git merge --no-ff hotfix/v1.2.1
git checkout develop
git merge --no-ff hotfix/v1.2.1

# 6. 创建标签和发布
git tag -a v1.2.1 -m "Hotfix v1.2.1"
git push origin main develop v1.2.1

# 7. 部署
docker build -t xagent:v1.2.1 .
docker push ghcr.io/your-org/xagent:v1.2.1
kubectl set image deployment/xagent-api xagent=ghcr.io/your-org/xagent:v1.2.1
```

---

**最后更新**: 2026-05-27  
**版本**: 1.0.0
