# X-Agent V2 部署指南

## 目录

1. [概述](#概述)
2. [架构设计](#架构设计)
3. [部署前准备](#部署前准备)
4. [灰度发布策略](#灰度发布策略)
5. [监控和告警](#监控和告警)
6. [回滚流程](#回滚流程)
7. [故障排查](#故障排查)
8. [常见问题](#常见问题)

---

## 概述

### 什么是 Agent V2？

Agent V2 是 X-Agent 的新一代架构，具有以下改进：

- **模块化设计**: 将执行流程分解为独立的阶段（初始化、规划、执行、恢复、完成）
- **增强的状态管理**: 更好的状态跟踪和恢复能力
- **改进的错误处理**: 自动恢复机制和更详细的错误信息
- **更好的可观测性**: 增强的日志和指标收集
- **灰度发布支持**: 通过特性开关实现平滑的灰度发布

### 部署策略

采用**灰度发布**策略，逐步增加 Agent V2 的流量比例：

```
初始状态 (0%)
    ↓
10% 灰度 (5 分钟监控)
    ↓
25% 灰度 (5 分钟监控)
    ↓
50% 灰度 (5 分钟监控)
    ↓
75% 灰度 (5 分钟监控)
    ↓
100% 灰度 (完全切换)
```

每个阶段都会监控关键指标，如果错误率超过阈值，系统将自动回滚。

---

## 架构设计

### 特性开关架构

```
┌─────────────────────────────────────────┐
│         API 请求                        │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│    兼容层 (AgentCompatibilityLayer)     │
│  - 检查特性开关                         │
│  - 路由到 V1 或 V2                      │
│  - 收集执行统计                         │
└────────────────┬────────────────────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
   ┌─────────┐       ┌─────────┐
   │Agent V1 │       │Agent V2 │
   │(Legacy) │       │(New)    │
   └─────────┘       └─────────┘
```

### 特性开关配置

特性开关支持以下配置选项：

```python
{
    "enabled": true,              # 全局启用/禁用
    "rollout_percentage": 10,     # 灰度百分比 (0-100)
    "allowed_tenants": [...],     # 允许的租户列表
    "allowed_users": [...]        # 允许的用户列表
}
```

### 一致性哈希

灰度发布使用一致性哈希确保同一用户始终路由到同一版本：

```python
hash_value = MD5(user_id) % 100
if hash_value < rollout_percentage:
    use_agent_v2()
else:
    use_agent_v1()
```

这确保了：
- 同一用户的多个请求路由到同一版本
- 灰度百分比精确控制
- 用户体验一致

---

## 部署前准备

### 1. 环境检查

```bash
# 检查 Python 版本
python --version  # 需要 3.11+

# 检查依赖
pip list | grep -E "fastapi|asyncpg|pydantic"

# 检查数据库连接
psql -h localhost -U xagent -d xagent -c "SELECT 1"

# 检查 Redis 连接
redis-cli ping

# 检查 Qdrant 连接
curl http://localhost:6333/health
```

### 2. 备份数据

```bash
# 完整数据库备份
pg_dump -h localhost -U xagent xagent > backup_$(date +%Y%m%d_%H%M%S).sql

# 验证备份
pg_restore --list backup_*.sql | head -20

# Redis 备份
redis-cli BGSAVE
redis-cli LASTSAVE

# Qdrant 快照
curl -X POST http://localhost:6333/snapshots
```

### 3. 代码准备

```bash
# 拉取最新代码
git pull origin main

# 检查代码状态
git status

# 运行测试
pytest tests/ -v

# 检查代码质量
ruff check backend/

# 运行安全检查
bandit -r backend/
```

### 4. 配置准备

```bash
# 复制环境配置
cp .env.example .env

# 编辑配置文件
vim .env

# 验证配置
python -c "from backend.app.config import settings; print(settings)"
```

---

## 灰度发布策略

### 阶段 1: 初始化 (10% 灰度)

**目标**: 验证 Agent V2 在生产环境中的基本功能

**持续时间**: 5 分钟

**监控指标**:
- 错误率 < 1%
- 响应时间 < 500ms
- 内存使用 < 500MB

**操作**:
```bash
# 启用 10% 灰度
curl -X POST http://localhost:8000/admin/feature-flags/use_agent_v2 \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "rollout_percentage": 10
  }'

# 监控日志
docker-compose logs -f backend | grep "Agent V2"

# 检查指标
curl http://localhost:8000/admin/metrics/execution
```

**回滚条件**:
- 错误率 > 5%
- 响应时间 > 1000ms
- 任何服务崩溃

### 阶段 2: 扩展 (25% 灰度)

**目标**: 验证 Agent V2 在更大流量下的稳定性

**持续时间**: 5 分钟

**监控指标**:
- 错误率 < 2%
- 响应时间 p95 < 600ms
- 数据库连接池使用率 < 70%

**操作**:
```bash
# 增加到 25% 灰度
curl -X POST http://localhost:8000/admin/feature-flags/use_agent_v2 \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "rollout_percentage": 25
  }'

# 检查性能
curl http://localhost:8000/admin/metrics/performance
```

### 阶段 3: 主流量 (50% 灰度)

**目标**: 验证 Agent V2 能够处理主流量

**持续时间**: 5 分钟

**监控指标**:
- 错误率 < 3%
- 响应时间 p99 < 800ms
- Redis 内存使用率 < 70%

**操作**:
```bash
# 增加到 50% 灰度
curl -X POST http://localhost:8000/admin/feature-flags/use_agent_v2 \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "rollout_percentage": 50
  }'

# 运行负载测试
locust -f tests/load_test.py --host=http://localhost:8000
```

### 阶段 4: 大部分流量 (75% 灰度)

**目标**: 验证 Agent V2 的长期稳定性

**持续时间**: 5 分钟

**监控指标**:
- 错误率 < 4%
- 响应时间稳定
- 没有内存泄漏

**操作**:
```bash
# 增加到 75% 灰度
curl -X POST http://localhost:8000/admin/feature-flags/use_agent_v2 \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "rollout_percentage": 75
  }'

# 检查内存使用
docker stats backend
```

### 阶段 5: 完全切换 (100% 灰度)

**目标**: 完全切换到 Agent V2

**持续时间**: 持续监控

**操作**:
```bash
# 完全启用 Agent V2
curl -X POST http://localhost:8000/admin/feature-flags/use_agent_v2 \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "rollout_percentage": 100
  }'

# 验证所有流量都使用 Agent V2
curl http://localhost:8000/admin/metrics/execution | jq '.v2_executions'
```

---

## 监控和告警

### 关键指标

#### 执行指标

```bash
# 获取执行统计
curl http://localhost:8000/admin/metrics/execution

# 响应示例
{
  "v1_executions": 1000,
  "v2_executions": 100,
  "v1_errors": 5,
  "v2_errors": 2,
  "error_rate_v1": 0.5,
  "error_rate_v2": 2.0
}
```

#### 性能指标

```bash
# 获取性能指标
curl http://localhost:8000/admin/metrics/performance

# 响应示例
{
  "execution_time_p50": 150,
  "execution_time_p95": 450,
  "execution_time_p99": 800,
  "memory_usage_mb": 256,
  "cpu_usage_percent": 45
}
```

### 告警规则

#### 错误率告警

```yaml
alert: AgentV2ErrorRateHigh
expr: |
  (rate(agent_v2_errors[5m]) / rate(agent_v2_executions[5m])) > 0.05
for: 5m
annotations:
  summary: "Agent V2 错误率过高"
  description: "错误率: {{ $value | humanizePercentage }}"
```

#### 响应时间告警

```yaml
alert: APIResponseTimeHigh
expr: |
  histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
for: 5m
annotations:
  summary: "API 响应时间过长"
  description: "P95 响应时间: {{ $value }}s"
```

#### 资源告警

```yaml
alert: DatabaseConnectionPoolExhausted
expr: db_connection_pool_usage > 0.9
for: 5m
annotations:
  summary: "数据库连接池即将耗尽"
  description: "使用率: {{ $value | humanizePercentage }}"
```

### 日志查询

```bash
# 查看 Agent V2 日志
docker-compose logs backend | grep "Agent V2"

# 查看错误日志
docker-compose logs backend | grep ERROR

# 查看特定时间范围的日志
docker-compose logs backend --since 10m --until 5m

# 导出日志到文件
docker-compose logs backend > deployment_logs.txt
```

---

## 回滚流程

### 自动回滚

系统在以下情况下自动回滚：

1. **错误率过高**: 错误率 > 5% 持续 5 分钟
2. **性能下降**: 响应时间 p95 > 1000ms 持续 5 分钟
3. **资源耗尽**: 连接池使用率 > 90%
4. **服务崩溃**: 健康检查失败 3 次

### 手动回滚

```bash
# 立即禁用 Agent V2
curl -X POST http://localhost:8000/admin/feature-flags/use_agent_v2 \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": false,
    "rollout_percentage": 0
  }'

# 验证回滚
curl http://localhost:8000/admin/metrics/execution

# 检查所有流量都使用 Agent V1
curl http://localhost:8000/admin/metrics/execution | jq '.v1_executions'
```

### 数据恢复

如果需要恢复数据：

```bash
# 从备份恢复数据库
psql -h localhost -U xagent xagent < backup_YYYYMMDD_HHMMSS.sql

# 清空 Redis 缓存
redis-cli FLUSHALL

# 重启服务
docker-compose restart backend
```

---

## 故障排查

### 常见问题

#### 问题 1: Agent V2 执行失败

**症状**: 错误日志中出现 "Agent V2 execution failed"

**排查步骤**:
```bash
# 1. 检查日志
docker-compose logs backend | grep "Agent V2"

# 2. 检查特性开关状态
curl http://localhost:8000/admin/feature-flags/use_agent_v2

# 3. 检查数据库连接
psql -h localhost -U xagent -d xagent -c "SELECT 1"

# 4. 检查 Redis 连接
redis-cli ping

# 5. 检查 Qdrant 连接
curl http://localhost:6333/health
```

**解决方案**:
- 检查数据库连接字符串
- 检查 Redis 是否运行
- 检查 Qdrant 是否运行
- 查看详细错误日志

#### 问题 2: 性能下降

**症状**: 响应时间增加，错误率上升

**排查步骤**:
```bash
# 1. 检查资源使用
docker stats backend

# 2. 检查数据库连接池
curl http://localhost:8000/admin/metrics/database

# 3. 检查缓存命中率
curl http://localhost:8000/admin/metrics/cache

# 4. 检查慢查询
docker-compose exec postgres psql -U xagent -d xagent -c \
  "SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"
```

**解决方案**:
- 增加数据库连接池大小
- 增加 Redis 内存
- 优化数据库查询
- 增加服务器资源

#### 问题 3: 内存泄漏

**症状**: 内存使用持续增加

**排查步骤**:
```bash
# 1. 监控内存使用
docker stats backend --no-stream

# 2. 检查内存使用趋势
watch -n 5 'docker stats backend --no-stream'

# 3. 生成内存快照
docker-compose exec backend python -m memory_profiler

# 4. 分析内存使用
python -m tracemalloc
```

**解决方案**:
- 检查是否有循环引用
- 检查是否有未关闭的连接
- 检查是否有缓存溢出
- 重启服务

---

## 常见问题

### Q1: 如何验证 Agent V2 是否正确部署？

**A**: 运行以下命令验证：

```bash
# 1. 检查特性开关
curl http://localhost:8000/admin/feature-flags/use_agent_v2

# 2. 检查执行统计
curl http://localhost:8000/admin/metrics/execution

# 3. 运行测试任务
curl -X POST http://localhost:8000/api/agents/run \
  -H "Content-Type: application/json" \
  -d '{"task": "test", "context": {}}'

# 4. 检查日志
docker-compose logs backend | grep "Agent V2"
```

### Q2: 如何快速回滚到 Agent V1？

**A**: 运行以下命令：

```bash
curl -X POST http://localhost:8000/admin/feature-flags/use_agent_v2 \
  -H "Content-Type: application/json" \
  -d '{"enabled": false, "rollout_percentage": 0}'
```

### Q3: 如何监控灰度发布进度？

**A**: 使用以下命令监控：

```bash
# 实时监控
watch -n 5 'curl -s http://localhost:8000/admin/metrics/execution | jq'

# 或使用脚本
while true; do
  curl -s http://localhost:8000/admin/metrics/execution | jq '.'
  sleep 5
done
```

### Q4: 如何处理灰度发布中的错误？

**A**: 
1. 立即禁用 Agent V2
2. 检查错误日志
3. 修复问题
4. 重新部署

### Q5: 灰度发布需要多长时间？

**A**: 标准灰度发布流程需要约 25-30 分钟（5 个阶段 × 5 分钟 + 缓冲时间）。

---

**文档版本**: 1.0  
**最后更新**: 2026-05-26  
**维护者**: X-Agent 团队
